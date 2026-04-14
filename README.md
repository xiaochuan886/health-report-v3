# 综合健康检测报告 v3.0

一个面向客户健康检测报告的脚本化项目，目标是替代原先依赖 Power BI 的生成方式，改为：

- 从客户检测 `xls` 和标准规则库 `xlsx` 抽取结构化结果
- 生成中间结果 JSON
- 组装 Markdown 报告
- 调用 `md2pdf` 生成首版 PDF

## 当前能力

第一阶段已完成：

- 兼容新旧 `xls` 字段
- 指标白名单匹配
- 参考值解析
- 风险判定
- 癌筛 / 心筛 / 大营养板块中间结果导出

第二阶段已完成首版：

- 从中间 JSON 组装报告上下文
- 生成 `report.md`
- 调用本地 `md2pdf` 输出 `report.pdf`

## 目录结构

- `src/report_pipeline/`
  核心代码
- `tests/`
  自动化测试
- `docs/`
  规则说明、字段映射、spec 和实现计划
- `output/`
  运行输出和首版报告产物

## 核心脚本说明

### 数据抽取层

- `src/report_pipeline/sources.py`
  负责统一客户检测 `xls` 的新旧字段，把不同版本 Excel 的列名映射成内部标准字段。

- `src/report_pipeline/whitelist.py`
  负责白名单匹配。按性别过滤 `指标明细` 后，优先用 `指标简称` 匹配，未命中时再回退到 `上海指标码`。

- `src/report_pipeline/reference_parser.py`
  负责解析 `xls` 中的 `参考值` 字段，支持普通区间、单边阈值、定性结果和多段规则。

- `src/report_pipeline/risk.py`
  负责根据“检测结果 + 参考值解析结果”输出风险状态，如 `above`、`near_upper`、`不足`、`normal`。

- `src/report_pipeline/sections.py`
  负责将匹配后的明细整理成报告板块数据，生成 `summary_sections` 和 `nutrition_sections`。

- `src/report_pipeline/pipeline.py`
  第一阶段总控脚本。串联字段归一化、白名单匹配、参考值解析、风险判定、癌种映射和说明字段补充，最终导出中间结果 JSON。

### 报告组装层

- `src/report_pipeline/render_inputs.py`
  负责读取第一阶段导出的 JSON，并组织成 Markdown 模板直接可用的报告上下文。

- `src/report_pipeline/report_styles.py`
  负责渲染层的小工具，如状态文案映射、风险刻度条、空值显示格式。

- `src/report_pipeline/markdown_report.py`
  负责生成 `report.md`，把报告固定结构输出成 Markdown。

- `src/report_pipeline/pdf_export.py`
  负责调用本地 `md2pdf` 脚本生成 PDF，并注入本地 `.vendor` 依赖环境。

### 命令入口层

- `src/report_pipeline/cli.py`
  项目命令行入口。当前提供：
  - `extract`：生成第一阶段中间结果
  - `render`：生成 Markdown 和 PDF
  - `assemble`：预留命令，暂未实现

## 常用命令

### 1. 运行测试

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
/opt/anaconda3/bin/python -m pytest -q
```

### 2. 生成中间结果

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
PYTHONPATH=src /opt/anaconda3/bin/python -m report_pipeline.cli extract \
  --lab-xls '/path/to/customer.xls' \
  --standard-xlsx '/path/to/standard.xlsx' \
  --output-dir output/customer-run
```

### 3. 生成 Markdown 和 PDF

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
PYTHONPATH=src /opt/anaconda3/bin/python -m report_pipeline.cli render \
  --input-dir output/customer-run \
  --markdown-output output/customer-run/report.md \
  --pdf-output output/customer-run/report.pdf
```

## 当前首版输出

真实客户首版报告当前位于：

- `output/customer-run/report.md`
- `output/customer-run/report.pdf`

## 依赖说明

项目运行依赖：

- Python 3.11
- `pandas`
- `openpyxl`
- `pypdf`

PDF 渲染额外依赖：

- `reportlab`

当前仓库内已使用本地目录 `.vendor/` 安装 `reportlab`，供 `md2pdf` 调用。

## 当前限制

- 视觉风格是“结构沿用、视觉简化”，不是复刻 Power BI
- 趋势图尚未接入
- 医学名词释义和健康生活指南目前是精简版
- `md2pdf` 仅稳定支持到三级标题，模板需避免四级标题
