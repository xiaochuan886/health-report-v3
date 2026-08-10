# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

综合健康检测报告生成管线，替代 Power BI 方案。从客户检测 `xls` + 标准规则库 `xlsx` 抽取结构化数据，经匹配/解析/判定后输出中间 JSON，再组装 Markdown 并调用 `md2pdf` 生成 PDF 报告。

## 常用命令

```bash
# 运行全部测试
cd '/Users/re.stem/综合健康检测报告v3.0'
./.venv/bin/python -m pytest -q --ignore=scratch

# 运行单个测试文件
./.venv/bin/python -m pytest -q tests/test_sources.py

# 运行单个测试函数
./.venv/bin/python -m pytest -q tests/test_sources.py::test_function_name

# 生成中间结果 JSON
PYTHONPATH=src ./.venv/bin/python -m report_pipeline.cli extract \
  --lab-xls '/path/to/customer.xls' \
  --standard-xlsx '/path/to/standard.xlsx' \
  --output-dir output/customer-run

# 生成 Markdown 和 PDF
PYTHONPATH=src ./.venv/bin/python -m report_pipeline.cli render \
  --input-dir output/customer-run \
  --markdown-output output/customer-run/report.md \
  --pdf-output output/customer-run/report.pdf
```

Python 解释器使用项目本地虚拟环境 `.venv/bin/python`。`pytest` 配置已在 `pyproject.toml` 中设置 `pythonpath = ["src"]`。`scratch/` 目录下的旧脚本不参与测试。

## 架构

管线分两层，通过 CLI 入口 `src/report_pipeline/cli.py` 调用，支持 `extract`（数据抽取）和 `render`（报告渲染）两个子命令。

### 数据抽取层（extract）

处理流水线：`sources.py` → `whitelist.py` → `reference_parser.py` → `risk.py` → `sections.py` → `pipeline.py`

- **sources.py** — 字段归一化，将新旧版 xls 列名映射为统一内部字段
- **whitelist.py** — 白名单匹配，优先 `指标简称` 匹配，未命中回退 `上海指标码`
- **reference_parser.py** — 解析参考值字段，支持 range / upper_bound / lower_bound / qual_threshold / qual_only / multi_rule / special 七种类型
- **risk.py** — 风险判定，输出 risk_status（above/below/near_upper/near_lower/normal/unknown 等）
- **sections.py** — 按板块（癌筛/心筛/微量元素/维生素）组装结构化数据
- **pipeline.py** — 总控脚本，串联以上模块，导出 `matched_indicators.json`、`summary_sections.json`、`nutrition_sections.json`

### 报告渲染层（render）

- **render_inputs.py** — 读取 JSON，构建模板上下文（含癌种分组、大营养说明、医学释义等）；健康指南始终从 `src/report_pipeline/data/health_guide.md` 读取，不使用 output 目录缓存
- **markdown_report.py** — 将上下文输出为 `report.md`，固定六部分结构（基础信息→第一部分评估小结→第二部分癌筛→第三部分心筛→第四部分大营养→第五部分释义→第六部分健康指南）
- **report_styles.py** — 渲染工具（状态文案映射、风险刻度条、空值显示）
- **pdf_export.py** — 调用本地 `md2pdf` 脚本生成 PDF

### 数据流

```
customer.xls + standard.xlsx
  → extract → matched_indicators.json / summary_sections.json / nutrition_sections.json
  → render → report.md → report.pdf
```

## 关键规则

- 参考值判定唯一来源是 `xls.参考值` 原文，不使用标准库中的"指标及正常区间"
- 指标匹配优先 `指标简称`，回退 `上海指标码`，未命中标记 `unmatched` 不进主报告
- 性别过滤：按 `指标明细.性别` 字段（F/M/F/M）与客户性别比对
- 报告板块由 `风险类别` 决定：癌筛、心筛、微量元素、维生素
- 大营养检测不进入第一部分评估结果小结
- `md2pdf` 仅稳定支持到三级标题，模板避免四级标题

## 依赖

运行时：pandas, openpyxl, pypdf, reportlab, pillow（Python 3.12，本地 `.venv` 虚拟环境）
PDF 工具：`~/.agents/skills/lovstudio-any2pdf/scripts/md2pdf.py`

## 规则文档

`docs/报告生成规则说明.md` — 完整的业务规则定义（数据源、匹配规则、风险判定、板块结构）
`docs/字段映射表.md` — 全字段来源、优先级和输出位置映射
