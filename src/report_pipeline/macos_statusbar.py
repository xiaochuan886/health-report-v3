from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path

from report_pipeline.web_mvp import ReportJobService, _default_root_dir, _make_handler, _resolve_port


def _looks_like_health_report_process(command: str, executable_name: str) -> bool:
    if "HealthReportWeb.app/Contents/MacOS/HealthReportWeb" in command:
        return True
    if f"/{executable_name} " in command:
        return True
    return command.endswith(f"/{executable_name}")


def _extract_target_pids(ps_output: str, *, executable_name: str, current_pid: int) -> list[int]:
    pids: list[int] = []
    for raw_line in ps_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        pid_text, command = parts
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid == current_pid:
            continue
        if _looks_like_health_report_process(command, executable_name):
            pids.append(pid)
    return pids


def _discover_peer_pids(executable_name: str, current_pid: int) -> list[int]:
    result = subprocess.run(
        ["ps", "-axo", "pid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return _extract_target_pids(result.stdout, executable_name=executable_name, current_pid=current_pid)


def _terminate_pids(pids: list[int], grace_seconds: float = 1.2) -> int:
    unique = sorted(set(pid for pid in pids if pid > 1))
    if not unique:
        return 0

    for pid in unique:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            continue

    deadline = time.time() + grace_seconds
    remaining: set[int] = set(unique)
    while remaining and time.time() < deadline:
        for pid in list(remaining):
            try:
                os.kill(pid, 0)
            except OSError:
                remaining.remove(pid)
        time.sleep(0.05)

    for pid in list(remaining):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    return len(unique)


@dataclass
class _ServerRuntime:
    host: str
    requested_port: int
    root_dir: Path
    _server: ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None
    _actual_port: int | None = None

    def start(self) -> None:
        if self._server is not None:
            return
        service = ReportJobService(root_dir=self.root_dir)
        actual_port = _resolve_port(self.host, self.requested_port)
        server = ThreadingHTTPServer((self.host, actual_port), _make_handler(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._server = server
        self._thread = thread
        self._actual_port = actual_port

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2.0)

    @property
    def url(self) -> str:
        port = self._actual_port if self._actual_port is not None else self.requested_port
        return f"http://{self.host}:{port}"


class _StatusBarController:
    def __init__(self, host: str, port: int, root_dir: Path) -> None:
        self._server_runtime = _ServerRuntime(host=host, requested_port=port, root_dir=root_dir)
        self._executable_name = Path(sys.executable).name
        self._icon = None

    def _open_window(self) -> None:
        webbrowser.open(self._server_runtime.url)

    def _close_all_processes(self) -> int:
        pids = _discover_peer_pids(self._executable_name, os.getpid())
        return _terminate_pids(pids)

    def run(self) -> None:
        import pystray
        from PIL import Image, ImageDraw

        self._server_runtime.start()
        self._open_window()

        image = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((6, 6, 58, 58), fill=(20, 122, 110, 255))
        draw.text((22, 18), "健", fill=(255, 255, 255, 255))

        def on_open(_icon, _item) -> None:
            self._open_window()

        def on_close_all(_icon, _item) -> None:
            def _run() -> None:
                closed = self._close_all_processes()
                print(f"closed peer processes: {closed}")

            threading.Thread(target=_run, daemon=True).start()

        def on_quit(icon, _item) -> None:
            self._server_runtime.stop()
            icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem("打开新窗口", on_open),
            pystray.MenuItem("关闭全部进程", on_close_all),
            pystray.MenuItem("退出", on_quit),
        )
        self._icon = pystray.Icon("HealthReportWeb", image, "综合健康报告", menu)
        self._icon.run()


def run_statusbar_app(argv: list[str] | None = None) -> bool:
    if sys.platform != "darwin":
        return False
    args_in = argv or []
    if "--no-statusbar" in args_in:
        return False
    try:
        __import__("pystray")
    except Exception:
        return False

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root-dir", default=str(_default_root_dir()))
    args, _unknown = parser.parse_known_args(args_in)
    controller = _StatusBarController(args.host, args.port, Path(args.root_dir))
    controller.run()
    return True
