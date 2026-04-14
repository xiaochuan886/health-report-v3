# 综合健康检测报告第二阶段渲染 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于第一阶段中间结果生成首版 Markdown 报告，并调用 `md2pdf` 输出第一版 PDF 供评审。

**Architecture:** 在现有数据管道基础上补充一个“渲染输入装配层 + Markdown 生成层 + PDF 导出层”。第一阶段继续负责规则判断；第二阶段只消费结构化结果并输出报告文档。为保证营养说明和医学释义可渲染，第一阶段导出数据允许补充描述字段，但不改变判定规则。

**Tech Stack:** Python 3.11, pandas, json, pytest, local `md2pdf.py` script

---

### Task 1: Enrich Matched Rows With Indicator Descriptions

**Files:**
- Modify: `src/report_pipeline/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add a test that writes a minimal standard workbook containing `指标明细`、`指标对应风险部位`、`指标说明`, runs `run_extract()`, and asserts the output row contains description fields such as `indicator_label`, `indicator_meaning`, and `indicator_application`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_pipeline.py::test_run_extract_includes_indicator_descriptions -v`
Expected: FAIL because description fields are missing.

- [ ] **Step 3: Write minimal implementation**

In `src/report_pipeline/pipeline.py`, read `指标说明` from the standard workbook, join it onto matched rows by `indicator_short_name`, and carry the fields through JSON export.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_pipeline.py::test_run_extract_includes_indicator_descriptions -v`
Expected: PASS.

- [ ] **Step 5: Run regression tests**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_pipeline.py tests/test_sections.py tests/test_reference_parser.py -q`
Expected: PASS.

### Task 2: Build Rendering Input Models

**Files:**
- Create: `src/report_pipeline/render_inputs.py`
- Create: `tests/test_render_inputs.py`

- [ ] **Step 1: Write the failing test**

Write tests for:
- loading the three JSON files from an output directory
- extracting base patient metadata from `matched_indicators.json`
- grouping nutrition explanation rows from matched indicators only
- building a compact context object for Markdown rendering

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_render_inputs.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `src/report_pipeline/render_inputs.py` with helpers to:
- load exported JSON files
- derive cover/basic info fields
- provide summary, cancer, cardio, nutrition, glossary inputs
- normalize missing fields to empty display values

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_render_inputs.py -v`
Expected: PASS.

### Task 3: Add Markdown Style Helpers

**Files:**
- Create: `src/report_pipeline/report_styles.py`
- Create: `tests/test_report_styles.py`

- [ ] **Step 1: Write the failing test**

Add tests for:
- risk status to Chinese label mapping
- simplified risk bar rendering
- markdown-safe placeholder formatting for empty values

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_report_styles.py -v`
Expected: FAIL because file does not exist.

- [ ] **Step 3: Write minimal implementation**

Create helper functions that convert statuses like `above`, `near_upper`, `不足`, `unknown` into display labels and simple text bars usable in Markdown tables.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_report_styles.py -v`
Expected: PASS.

### Task 4: Generate Markdown Report

**Files:**
- Create: `src/report_pipeline/markdown_report.py`
- Create: `tests/test_markdown_report.py`

- [ ] **Step 1: Write the failing test**

Write a test that builds a small render context and asserts the generated markdown contains:
- cover title
- 基础信息 section
- 目录占位 heading structure
- 癌症健康监测小结
- 心脑血管健康监测与指导
- 大营养检测与建议
- 医学名词释义与健康生活指南

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_markdown_report.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create a markdown generator that:
- emits the fixed 8-part structure
- uses tables for summary, cardio, and nutrition result blocks
- emits indicator explanation tables for nutrition
- emits a compact glossary section from matched indicator descriptions
- emits a static short health guide section

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_markdown_report.py -v`
Expected: PASS.

### Task 5: Add PDF Export Wrapper

**Files:**
- Create: `src/report_pipeline/pdf_export.py`
- Create: `tests/test_pdf_export.py`

- [ ] **Step 1: Write the failing test**

Write tests for:
- building the `md2pdf.py` command with expected paths and metadata
- handling a markdown-only fallback if PDF generation fails

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_pdf_export.py -v`
Expected: FAIL because module does not exist.

- [ ] **Step 3: Write minimal implementation**

Create a wrapper that:
- accepts markdown path, pdf path, title, author/header metadata
- invokes `/Users/re.stem/.agents/skills/lovstudio-any2pdf/scripts/md2pdf.py`
- uses a stable default theme for the first version
- raises a clear error if the conversion command fails

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_pdf_export.py -v`
Expected: PASS.

### Task 6: Wire CLI Render Command

**Files:**
- Modify: `src/report_pipeline/cli.py`
- Modify: `tests/test_smoke.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

Extend CLI tests to assert a new `render` subcommand exists with:
- `--input-dir`
- `--markdown-output`
- `--pdf-output`

Also add a behavior test that the command validates required arguments.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_smoke.py tests/test_pipeline.py -q`
Expected: FAIL because `render` command does not exist.

- [ ] **Step 3: Write minimal implementation**

Update `cli.py` so `render`:
- loads render inputs from an output directory
- writes `report.md`
- attempts to write `report.pdf`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest tests/test_smoke.py tests/test_pipeline.py -q`
Expected: PASS.

### Task 7: End-to-End First Version Output

**Files:**
- Modify: `src/report_pipeline/cli.py`
- Output: `output/customer-run/report.md`
- Output: `output/customer-run/report.pdf`

- [ ] **Step 1: Run extract on the real customer data**

Run:
`cd '/Users/re.stem/综合健康检测报告v3.0' && PYTHONPATH=src /opt/anaconda3/bin/python -c "from report_pipeline.pipeline import run_extract; run_extract('/Users/re.stem/Downloads/客户信息文档（上海）/客户基础数据/C-20251224-1406边伟星/检测数据/边伟星-20251224.xls', '/Users/re.stem/Downloads/客户信息文档（上海）/标准文档/客户健康综合检测基础数据V1.6 - 不含白介素.xlsx', 'output/customer-run')"`
Expected: JSON outputs refreshed.

- [ ] **Step 2: Run render on the real customer output**

Run:
`cd '/Users/re.stem/综合健康检测报告v3.0' && PYTHONPATH=src /opt/anaconda3/bin/python -m report_pipeline.cli render --input-dir output/customer-run --markdown-output output/customer-run/report.md --pdf-output output/customer-run/report.pdf`
Expected: `report.md` created and `report.pdf` created if `reportlab` is available.

- [ ] **Step 3: Verify generated files**

Run:
- `ls -lah '/Users/re.stem/综合健康检测报告v3.0/output/customer-run'`
- inspect beginning of markdown
- confirm PDF file exists and is non-empty

- [ ] **Step 4: Run full test suite**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && /opt/anaconda3/bin/python -m pytest -q`
Expected: PASS.

## Self-Review

- Spec coverage: includes markdown assembly, simplified risk display, pdf export, and real-customer output.
- No placeholder steps remain.
- Function/module names are consistent with the rendering spec and existing package naming.

## Execution Note

当前项目目录不是 git 仓库，因此本计划不包含 commit 步骤；代码和产物验证优先。
