from __future__ import annotations

import argparse
import cgi
import json
import socket
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit

from report_pipeline.pipeline import run_extract
from report_pipeline.markdown_report import generate_markdown_report
from report_pipeline.pdf_export import export_pdf
from report_pipeline.render_inputs import build_render_context, load_render_bundle


StatusFn = Callable[..., Any]


@dataclass
class _JobRecord:
    id: str
    dir: Path
    status: str
    step: str
    created_at: float
    updated_at: float
    error: str = ""
    thread: threading.Thread | None = None


class ReportJobService:
    def __init__(
        self,
        root_dir: str | Path,
        run_extract_fn: StatusFn = run_extract,
        load_render_bundle_fn: StatusFn = load_render_bundle,
        build_render_context_fn: StatusFn = build_render_context,
        generate_markdown_report_fn: StatusFn = generate_markdown_report,
        export_pdf_fn: StatusFn = export_pdf,
        standard_xlsx_path: str | Path | None = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.jobs_dir = self.root_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.standard_xlsx_path = (
            Path(standard_xlsx_path)
            if standard_xlsx_path is not None
            else Path(__file__).parent / "data" / "standard.xlsx"
        )

        self._run_extract = run_extract_fn
        self._load_render_bundle = load_render_bundle_fn
        self._build_render_context = build_render_context_fn
        self._generate_markdown_report = generate_markdown_report_fn
        self._export_pdf = export_pdf_fn

        self._lock = threading.Lock()
        self._jobs: dict[str, _JobRecord] = {}

    def create_job(
        self,
        *,
        lab_filename: str,
        lab_bytes: bytes,
        personal_info_filename: str | None = None,
        personal_info_bytes: bytes | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex
        job_dir = self.jobs_dir / job_id
        inputs_dir = job_dir / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)

        lab_name = Path(lab_filename).name or "lab.xls"
        lab_path = inputs_dir / lab_name
        lab_path.write_bytes(lab_bytes)

        personal_path: Path | None = None
        if personal_info_filename and personal_info_bytes is not None:
            personal_name = Path(personal_info_filename).name or "personal_info.xlsx"
            if personal_name == lab_name:
                ext = Path(personal_name).suffix or ".xlsx"
                stem = Path(personal_name).stem or "personal_info"
                personal_name = f"{stem}__personal{ext}"
            personal_path = inputs_dir / personal_name
            personal_path.write_bytes(personal_info_bytes)

        now = time.time()
        record = _JobRecord(
            id=job_id,
            dir=job_dir,
            status="queued",
            step="queued",
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._jobs[job_id] = record

        t = threading.Thread(
            target=self._run_job,
            args=(job_id, lab_path, personal_path),
            daemon=True,
        )
        record.thread = t
        t.start()
        return job_id

    def _set_status(self, job_id: str, *, status: str, step: str, error: str = "") -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = status
            record.step = step
            record.error = error
            record.updated_at = time.time()

    def _run_job(self, job_id: str, lab_path: Path, personal_path: Path | None) -> None:
        try:
            self._set_status(job_id, status="running", step="extract")
            job_dir = self.jobs_dir / job_id
            if not self.standard_xlsx_path.exists():
                raise FileNotFoundError(f"standard file not found: {self.standard_xlsx_path}")
            self._run_extract(
                str(lab_path),
                str(self.standard_xlsx_path),
                str(job_dir),
                str(personal_path) if personal_path else None,
            )

            self._set_status(job_id, status="running", step="render")
            bundle = self._load_render_bundle(job_dir)
            context = self._build_render_context(bundle)

            md_path = job_dir / "report.md"
            pdf_path = job_dir / "report.pdf"
            md_path.write_text(self._generate_markdown_report(context), encoding="utf-8")

            self._export_pdf(
                str(md_path),
                str(pdf_path),
                context["title"],
                context["hospital_name"],
                patient_name=context.get("patient_name", ""),
                report_date=context.get("report_date", ""),
                institution_name=context.get("institution_name", ""),
                cover_patient=f"{context.get('patient_name', '')}  {context.get('patient_gender', '')}  {context.get('patient_age', '')}岁",
            )
            self._set_status(job_id, status="succeeded", step="done")
        except Exception as exc:  # noqa: BLE001
            self._set_status(job_id, status="failed", step="error", error=str(exc))

    def get_status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(job_id)
            return {
                "job_id": record.id,
                "status": record.status,
                "step": record.step,
                "error": record.error,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }

    def artifact_path(self, job_id: str, artifact_name: str) -> Path:
        if artifact_name not in {"report.pdf", "report.md"}:
            raise ValueError("unsupported artifact")
        p = self.jobs_dir / job_id / artifact_name
        if not p.exists():
            raise FileNotFoundError(str(p))
        return p

    def wait(self, job_id: str, timeout: float | None = None) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(job_id)
            thread = record.thread
        if thread is not None:
            thread.join(timeout=timeout)

    def list_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        with self._lock:
            rows = list(self._jobs.values())
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return [
            {
                "job_id": r.id,
                "status": r.status,
                "step": r.step,
                "error": r.error,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows[:limit]
        ]


_INDEX_HTML = """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <link rel=\"icon\" href=\"data:,\" />
  <title>综合健康报告生成</title>
  <style>
    :root {
      --bg: #f2ede3;
      --card: #fffdf8;
      --card-strong: #fffaf0;
      --accent: #0f766e;
      --accent-2: #0c5c55;
      --text: #1f2937;
      --muted: #6b7280;
      --line: #d8dde3;
      --ok: #166534;
      --err: #9f1239;
      --warn: #9a3412;
      --focus: #0ea5a0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at top right, #dfede4 0%, var(--bg) 42%, #f8f4ec 100%);
      color: var(--text);
      font-family: "Noto Serif SC", "Source Han Serif SC", "PingFang SC", "Microsoft YaHei", serif;
      line-height: 1.5;
    }
    .wrap { max-width: 980px; margin: 24px auto; padding: 0 16px; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
    @media (min-width: 960px) { .grid { grid-template-columns: 1.2fr .8fr; } }
    .card {
      background: linear-gradient(180deg, var(--card) 0%, var(--card-strong) 100%);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 16px 30px rgba(12, 36, 32, .08);
    }
    h1 { margin: 0 0 10px; font-size: 28px; letter-spacing: .5px; }
    h2 { margin: 0 0 8px; font-size: 18px; }
    .hint { color: var(--muted); margin-bottom: 14px; }
    .minor { color: var(--muted); font-size: 14px; }
    .pill {
      display: inline-block;
      border-radius: 999px;
      border: 1px solid #b7d5d1;
      color: var(--accent-2);
      padding: 2px 10px;
      font-size: 12px;
      background: #ebf7f4;
      margin-bottom: 8px;
    }
    .field { margin-bottom: 14px; }
    label { display: block; font-weight: 700; margin-bottom: 6px; }
    .req { color: #b91c1c; }
    input[type=file] {
      width: 100%;
      border: 1px dashed #95a4b8;
      border-radius: 10px;
      padding: 12px;
      background: #f8fafc;
      min-height: 48px;
    }
    input[type=file]:focus-visible, button:focus-visible, a:focus-visible {
      outline: 3px solid var(--focus);
      outline-offset: 2px;
    }
    .file-meta {
      margin-top: 6px;
      font-size: 13px;
      color: #334155;
      min-height: 18px;
    }
    .actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    button {
      margin-top: 8px;
      background: linear-gradient(180deg, var(--accent) 0%, var(--accent-2) 100%);
      color: #fff;
      border: 0;
      border-radius: 10px;
      padding: 12px 18px;
      min-height: 48px;
      cursor: pointer;
      font-weight: 700;
      transition: transform .16s ease-out, opacity .16s ease-out;
    }
    button:hover { transform: translateY(-1px); }
    button:active { transform: translateY(0); }
    button[disabled] { opacity: .55; cursor: not-allowed; transform: none; }
    .status {
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      background: #f8fafc;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
    }
    .progress {
      margin-top: 10px;
      width: 100%;
      height: 10px;
      border-radius: 999px;
      background: #e2e8f0;
      overflow: hidden;
    }
    .progress > span {
      display: block;
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #0f766e, #14b8a6);
      transition: width .28s ease-out;
    }
    .steps {
      margin-top: 8px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 6px;
      font-size: 12px;
    }
    .step {
      border-radius: 999px;
      text-align: center;
      padding: 4px 6px;
      background: #e5e7eb;
      color: #334155;
    }
    .step.active { background: #cdebe6; color: var(--accent-2); font-weight: 700; }
    .step.done { background: #dcfce7; color: var(--ok); font-weight: 700; }
    .step.err { background: #ffe4e6; color: var(--err); font-weight: 700; }
    .downloads { margin-top: 12px; }
    .downloads a {
      display: inline-block;
      margin-right: 8px;
      margin-bottom: 8px;
      border: 1px solid #b7d5d1;
      border-radius: 999px;
      padding: 8px 12px;
      color: var(--accent-2);
      text-decoration: none;
      background: #f0fbf8;
      min-height: 44px;
    }
    .panel-list { padding-left: 18px; margin: 8px 0 0; }
    .panel-list li { margin-bottom: 6px; }
    .system-path {
      margin-top: 10px;
      padding: 8px 10px;
      border-radius: 8px;
      background: #f1f5f9;
      border: 1px solid #dbe6ef;
      font-size: 12px;
      word-break: break-all;
    }
    .error { color: var(--err); font-weight: 700; }
    @media (prefers-reduced-motion: reduce) {
      * { transition: none !important; animation: none !important; }
    }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"grid\">
      <div class=\"card\">
        <span class=\"pill\">MVP / 实用优化版</span>
        <h1>综合健康检测报告生成</h1>
        <div class=\"hint\">只需上传客户检测数据。标准库由系统维护，不需要手动上传。</div>
        <form id=\"job-form\" novalidate>
          <div class=\"field\">
            <label for=\"lab_xls\">lab.xls（检测数据）<span class=\"req\">*</span></label>
            <input id=\"lab_xls\" type=\"file\" name=\"lab_xls\" accept=\".xls,.xlsx\" required aria-describedby=\"lab_meta\" />
            <div id=\"lab_meta\" class=\"file-meta\">未选择文件</div>
          </div>
          <div class=\"field\">
            <label for=\"personal_info_xlsx\">personal_info.xlsx（可选）</label>
            <input id=\"personal_info_xlsx\" type=\"file\" name=\"personal_info_xlsx\" accept=\".xlsx\" aria-describedby=\"personal_meta\" />
            <div id=\"personal_meta\" class=\"file-meta\">未选择文件</div>
          </div>
          <div class=\"actions\">
            <button id=\"submit_btn\" type=\"submit\" disabled>开始生成</button>
            <span class=\"minor\" id=\"form_hint\">请选择必填文件后可提交</span>
          </div>
        </form>

        <div id=\"status\" class=\"status\" aria-live=\"polite\">等待上传...</div>
        <div class=\"progress\" aria-hidden=\"true\"><span id=\"progress_fill\"></span></div>
        <div class=\"steps\" id=\"steps\">
          <div class=\"step\" data-step=\"queued\">排队</div>
          <div class=\"step\" data-step=\"extract\">抽取</div>
          <div class=\"step\" data-step=\"render\">渲染</div>
          <div class=\"step\" data-step=\"done\">完成</div>
        </div>
        <div id=\"downloads\" class=\"downloads\"></div>
      </div>

      <div class=\"card\">
        <h2>使用说明</h2>
        <ul class=\"panel-list\">
          <li>生成流程：上传 -> 后台抽取 -> 组装 Markdown -> 生成 PDF。</li>
          <li>报告完成后可直接下载 PDF，也可查看 Markdown 产物。</li>
          <li>若失败，状态区会显示错误信息，修正文件后可重试。</li>
        </ul>
        <h2 style=\"margin-top:16px;\">最近任务</h2>
        <div id=\"recent_jobs\" class=\"minor\">暂无任务</div>
        <div class=\"system-path\">
          系统标准库路径：<br />
          <strong>/src/report_pipeline/data/standard.xlsx</strong>
        </div>
      </div>
    </div>
  </div>
  <script>
    const form = document.getElementById("job-form");
    const statusEl = document.getElementById("status");
    const downloadsEl = document.getElementById("downloads");
    const submitBtn = document.getElementById("submit_btn");
    const formHint = document.getElementById("form_hint");
    const progressFill = document.getElementById("progress_fill");
    const steps = Array.from(document.querySelectorAll(".step"));
    const labInput = document.getElementById("lab_xls");
    const personalInput = document.getElementById("personal_info_xlsx");
    const labMeta = document.getElementById("lab_meta");
    const personalMeta = document.getElementById("personal_meta");
    const recentJobsEl = document.getElementById("recent_jobs");

    let timer = null;

    function formatFileMeta(file) {
      if (!file) return "未选择文件";
      const kb = Math.max(1, Math.round(file.size / 1024));
      return `${file.name} · ${kb} KB`;
    }

    function updateFormState() {
      const hasLab = labInput.files && labInput.files.length > 0;
      submitBtn.disabled = !hasLab;
      formHint.textContent = hasLab ? "文件已就绪，可开始生成" : "请选择必填文件后可提交";
      labMeta.textContent = formatFileMeta(labInput.files && labInput.files[0]);
      personalMeta.textContent = formatFileMeta(personalInput.files && personalInput.files[0]);
    }

    function showStatus(text, isError = false) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", isError);
    }

    function renderStep(stepName, status) {
      const order = ["queued", "extract", "render", "done"];
      const currentIdx = order.indexOf(stepName);
      const doneIdx = status === "succeeded" ? order.length - 1 : currentIdx;
      const pct = status === "succeeded" ? 100 : status === "failed" ? Math.max(5, (currentIdx + 1) * 25) : Math.max(10, (currentIdx + 1) * 25);
      progressFill.style.width = `${pct}%`;

      steps.forEach((item, idx) => {
        item.classList.remove("active", "done", "err");
        if (status === "failed" && idx === currentIdx) {
          item.classList.add("err");
          return;
        }
        if (idx < doneIdx || (status === "succeeded" && idx === doneIdx)) item.classList.add("done");
        if (status === "running" && idx === currentIdx) item.classList.add("active");
        if (status === "queued" && item.dataset.step === "queued") item.classList.add("active");
      });
    }

    function humanTime(ts) {
      if (!ts) return "--";
      const d = new Date(ts * 1000);
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      const ss = String(d.getSeconds()).padStart(2, "0");
      return `${hh}:${mm}:${ss}`;
    }

    function recentRow(job) {
      const canDownload = job.status === "succeeded";
      const links = canDownload
        ? ` <a href="/api/report-jobs/${job.job_id}/artifacts/report.pdf" target="_blank" rel="noopener noreferrer">PDF</a>`
        : "";
      const err = job.error ? ` · ${job.error}` : "";
      return `<div style="padding:6px 0;border-bottom:1px dashed #d1d5db;">
        <strong>${job.job_id.slice(0, 8)}</strong> · ${job.status}/${job.step} · ${humanTime(job.updated_at)}${links}
        <div class="minor" style="font-size:12px;${job.error ? "color:#9f1239;" : ""}">${err}</div>
      </div>`;
    }

    async function refreshRecentJobs() {
      try {
        const res = await fetch("/api/report-jobs?limit=8");
        if (!res.ok) return;
        const data = await res.json();
        const jobs = data.jobs || [];
        if (!jobs.length) {
          recentJobsEl.textContent = "暂无任务";
          return;
        }
        recentJobsEl.innerHTML = jobs.map(recentRow).join("");
      } catch (_) {
      }
    }

    async function poll(jobId) {
      const res = await fetch(`/api/report-jobs/${jobId}`);
      const data = await res.json();
      renderStep(data.step || "queued", data.status || "queued");
      showStatus(`任务 ${jobId.slice(0, 8)} · 状态=${data.status} · 阶段=${data.step}${data.error ? " · 错误=" + data.error : ""}`, data.status === "failed");

      if (data.status === "succeeded") {
        clearInterval(timer);
        submitBtn.disabled = false;
        downloadsEl.innerHTML = `<a href="/api/report-jobs/${jobId}/artifacts/report.pdf" target="_blank" rel="noopener noreferrer">下载 PDF 报告</a><a href="/api/report-jobs/${jobId}/artifacts/report.md" target="_blank" rel="noopener noreferrer">查看 Markdown</a>`;
        refreshRecentJobs();
      }
      if (data.status === "failed") {
        clearInterval(timer);
        submitBtn.disabled = false;
        downloadsEl.innerHTML = `<span class="error">任务失败，请检查上传文件后重试。</span>`;
        refreshRecentJobs();
      }
    }

    labInput.addEventListener("change", updateFormState);
    personalInput.addEventListener("change", updateFormState);
    updateFormState();
    refreshRecentJobs();

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!(labInput.files && labInput.files.length)) {
        showStatus("请先选择 lab.xls 文件", true);
        return;
      }

      downloadsEl.innerHTML = "";
      submitBtn.disabled = true;
      showStatus("正在创建任务...");
      renderStep("queued", "queued");

      const fd = new FormData(form);
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);
      let created = false;
      try {
        const res = await fetch("/api/report-jobs", {
          method: "POST",
          body: fd,
          signal: controller.signal,
        });
        const data = await res.json();
        if (!res.ok) {
          submitBtn.disabled = false;
          showStatus(`创建失败: ${data.error || "unknown"}`, true);
          return;
        }

        created = true;
        showStatus(`任务已创建：${data.job_id}`);
        timer = setInterval(() => poll(data.job_id), 1000);
        poll(data.job_id);
        refreshRecentJobs();
      } catch (err) {
        const msg = err && err.name === "AbortError" ? "创建超时，请检查服务进程后重试" : `创建失败: ${err?.message || "network error"}`;
        showStatus(msg, true);
      } finally {
        clearTimeout(timeoutId);
        if (!created) {
          submitBtn.disabled = false;
        }
      }
    });
  </script>
</body>
</html>
"""


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _make_handler(service: ReportJobService):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _reply_json(self, code: int, payload: dict[str, Any]) -> None:
            self._reply(code, _json_bytes(payload))

        def do_GET(self) -> None:  # noqa: N802
            split = urlsplit(self.path)
            path = unquote(split.path)
            query = parse_qs(split.query)
            if path == "/":
                body = _INDEX_HTML.encode("utf-8")
                self._reply(HTTPStatus.OK, body, content_type="text/html; charset=utf-8")
                return

            if path == "/api/report-jobs":
                try:
                    limit = int(query.get("limit", ["10"])[0])
                except ValueError:
                    limit = 10
                self._reply_json(HTTPStatus.OK, {"jobs": service.list_jobs(limit=limit)})
                return

            if path.startswith("/api/report-jobs/"):
                parts = path.split("/")
                if len(parts) == 4:
                    job_id = parts[3]
                    try:
                        status = service.get_status(job_id)
                    except KeyError:
                        self._reply_json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
                        return
                    self._reply_json(HTTPStatus.OK, status)
                    return

                if len(parts) == 6 and parts[4] == "artifacts":
                    job_id = parts[3]
                    artifact = parts[5]
                    try:
                        file_path = service.artifact_path(job_id, artifact)
                    except (ValueError, FileNotFoundError):
                        self._reply_json(HTTPStatus.NOT_FOUND, {"error": "artifact not found"})
                        return
                    content_type = "application/pdf" if artifact.endswith(".pdf") else "text/markdown; charset=utf-8"
                    self._reply(HTTPStatus.OK, file_path.read_bytes(), content_type=content_type)
                    return

            self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                if self.path != "/api/report-jobs":
                    self._reply_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return

                ctype = self.headers.get("Content-Type", "")
                if "multipart/form-data" not in ctype:
                    self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "multipart/form-data required"})
                    return

                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        "REQUEST_METHOD": "POST",
                        "CONTENT_TYPE": ctype,
                    },
                )

                try:
                    lab = form["lab_xls"]
                except KeyError:
                    self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "lab_xls is required"})
                    return

                if not getattr(lab, "file", None):
                    self._reply_json(HTTPStatus.BAD_REQUEST, {"error": "invalid upload files"})
                    return

                personal_field = form["personal_info_xlsx"] if "personal_info_xlsx" in form else None
                personal_name = None
                personal_bytes = None
                if personal_field is not None and getattr(personal_field, "file", None):
                    personal_name = personal_field.filename or "personal_info.xlsx"
                    personal_bytes = personal_field.file.read()

                job_id = service.create_job(
                    lab_filename=lab.filename or "lab.xls",
                    lab_bytes=lab.file.read(),
                    personal_info_filename=personal_name,
                    personal_info_bytes=personal_bytes,
                )
                self._reply_json(HTTPStatus.ACCEPTED, {"job_id": job_id})
            except Exception as exc:  # noqa: BLE001
                self._reply_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"create job failed: {exc}"})

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return Handler


def _default_root_dir() -> Path:
    return Path.home() / "HealthReportWebData" / "output" / "web-mvp"


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _resolve_port(host: str, requested_port: int, max_tries: int = 20) -> int:
    for offset in range(max_tries + 1):
        candidate = requested_port + offset
        if _is_port_available(host, candidate):
            return candidate
    raise RuntimeError(f"no available port from {requested_port} to {requested_port + max_tries}")


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    root_dir: str | Path | None = None,
    open_browser: bool = False,
) -> None:
    final_root = Path(root_dir) if root_dir is not None else _default_root_dir()
    service = ReportJobService(root_dir=final_root)
    actual_port = _resolve_port(host, port)
    server = ThreadingHTTPServer((host, actual_port), _make_handler(service))
    url = f"http://{host}:{actual_port}"
    print(f"web mvp server running: {url}")
    print(f"output root: {final_root}")
    if actual_port != port:
        print(f"port {port} is busy, switched to {actual_port}")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="report-web-mvp")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root-dir", default=str(_default_root_dir()))
    parser.add_argument("--open-browser", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args, _unknown = _build_parser().parse_known_args(argv)
    serve(host=args.host, port=args.port, root_dir=args.root_dir, open_browser=args.open_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
