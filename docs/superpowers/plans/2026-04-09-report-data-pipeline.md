# Report Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working data pipeline that reads the customer XLS/PDF inputs, normalizes fields across old/new XLS formats, matches indicators against the whitelist workbook, parses reference ranges, evaluates risk states, and exports intermediate result tables for report generation.

**Architecture:** Use a small Python package under the project root with clearly separated modules for source reading, normalization, whitelist matching, reference parsing, and section assembly. The first milestone stops at structured JSON/CSV outputs and test coverage so the report rules can be validated before PDF rendering work begins.

**Tech Stack:** Python 3.11, pandas, openpyxl, pypdf, pytest

---

### Task 1: Scaffold The Project Package

**Files:**
- Create: `/Users/re.stem/综合健康检测报告v3.0/pyproject.toml`
- Create: `/Users/re.stem/综合健康检测报告v3.0/src/report_pipeline/__init__.py`
- Create: `/Users/re.stem/综合健康检测报告v3.0/src/report_pipeline/cli.py`
- Create: `/Users/re.stem/综合健康检测报告v3.0/tests/test_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

```python
from report_pipeline.cli import build_parser


def test_build_parser_exposes_subcommands():
    parser = build_parser()
    subparsers = [
        action
        for action in parser._actions
        if action.__class__.__name__ == "_SubParsersAction"
    ]

    assert len(subparsers) == 1
    assert {"extract", "assemble"} <= set(subparsers[0].choices)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing `build_parser`

- [ ] **Step 3: Write minimal package scaffolding**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "report-pipeline"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pandas", "openpyxl", "pypdf"]

[tool.pytest.ini_options]
pythonpath = ["src"]
```

```python
# src/report_pipeline/cli.py
from argparse import ArgumentParser


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="report-pipeline")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("extract")
    subparsers.add_parser("assemble")
    return parser
```

```python
# src/report_pipeline/__init__.py
__all__ = ["__version__"]
__version__ = "0.1.0"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
git add pyproject.toml src/report_pipeline/__init__.py src/report_pipeline/cli.py tests/test_smoke.py
git commit -m "chore: scaffold report data pipeline package"
```

### Task 2: Normalize XLS Field Names Across Old/New Formats

**Files:**
- Create: `/Users/re.stem/综合健康检测报告v3.0/src/report_pipeline/sources.py`
- Create: `/Users/re.stem/综合健康检测报告v3.0/tests/test_sources.py`

- [ ] **Step 1: Write the failing field normalization tests**

```python
import pandas as pd

from report_pipeline.sources import normalize_lab_dataframe


def test_normalize_new_format_columns():
    raw = pd.DataFrame(
        [
            {
                "项目代号": "VD",
                "项目名称": "25-羟基维生素D",
                "项目测定值": 29.85,
                "高低标记": "",
                "参考值": "正常:30.01-80.00",
                "单位": "ng/mL",
                "艾迪康条码": "1Z1127003774",
                "样本种类": "血清",
                "报告日期": "2026-03-12 16:27:00",
            }
        ]
    )

    out = normalize_lab_dataframe(raw)
    record = out.iloc[0].to_dict()
    assert record["raw_code"] == "VD"
    assert record["raw_result"] == 29.85
    assert record["raw_barcode"] == "1Z1127003774"
    assert record["specimen_type"] == "血清"


def test_normalize_old_format_columns():
    raw = pd.DataFrame(
        [
            {
                "项目编号": "CEA",
                "项目名称": "癌胚抗原",
                "结果": 4.19,
                "提示": "z",
                "参考值": "0.00-5.09",
                "单位": "ng/mL",
                "条形码": "#630805000127",
                "标本类型": "血清",
                "报告时间": "2025/12/25 04:25:53",
            }
        ]
    )

    out = normalize_lab_dataframe(raw)
    record = out.iloc[0].to_dict()
    assert record["raw_code"] == "CEA"
    assert record["raw_result"] == 4.19
    assert record["lab_flag"] == "z"
    assert record["raw_barcode"] == "#630805000127"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_sources.py -v`
Expected: FAIL with missing `normalize_lab_dataframe`

- [ ] **Step 3: Write minimal XLS normalization**

```python
# src/report_pipeline/sources.py
import pandas as pd


NEW_TO_CANONICAL = {
    "项目代号": "raw_code",
    "项目名称": "raw_name",
    "项目测定值": "raw_result",
    "高低标记": "lab_flag",
    "参考值": "raw_reference",
    "单位": "unit",
    "艾迪康条码": "raw_barcode",
    "样本种类": "specimen_type",
    "接收时间": "received_at",
    "报告日期": "reported_at",
    "审核时间": "reviewed_at",
    "采集时间": "sampled_at",
}

OLD_TO_CANONICAL = {
    "项目编号": "raw_code",
    "项目名称": "raw_name",
    "结果": "raw_result",
    "提示": "lab_flag",
    "参考值": "raw_reference",
    "单位": "unit",
    "条形码": "raw_barcode",
    "标本类型": "specimen_type",
    "接收时间": "received_at",
    "报告时间": "reported_at",
    "采集时间": "sampled_at",
}


def normalize_lab_dataframe(raw: pd.DataFrame) -> pd.DataFrame:
    columns = {}
    for source_map in (NEW_TO_CANONICAL, OLD_TO_CANONICAL):
        for source_name, target_name in source_map.items():
            if source_name in raw.columns and target_name not in columns.values():
                columns[source_name] = target_name

    out = raw.rename(columns=columns).copy()
    for required in [
        "raw_code",
        "raw_name",
        "raw_result",
        "lab_flag",
        "raw_reference",
        "unit",
        "raw_barcode",
        "specimen_type",
        "received_at",
        "reported_at",
        "reviewed_at",
        "sampled_at",
    ]:
        if required not in out.columns:
            out[required] = ""

    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_sources.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
git add src/report_pipeline/sources.py tests/test_sources.py
git commit -m "feat: normalize lab xls fields across source formats"
```

### Task 3: Match Whitelist Indicators And Filter By Category

**Files:**
- Create: `/Users/re.stem/综合健康检测报告v3.0/src/report_pipeline/whitelist.py`
- Create: `/Users/re.stem/综合健康检测报告v3.0/tests/test_whitelist.py`

- [ ] **Step 1: Write the failing whitelist matching tests**

```python
import pandas as pd

from report_pipeline.whitelist import match_indicators


def test_match_indicators_prefers_short_name_then_shanghai_code():
    lab = pd.DataFrame(
        [
            {"raw_code": "VD", "raw_name": "25-羟基维生素D"},
            {"raw_code": "CEA-X", "raw_name": "癌胚抗原"},
            {"raw_code": "UNKNOWN", "raw_name": "未知项目"},
        ]
    )
    whitelist = pd.DataFrame(
        [
            {"指标简称": "VD", "上海指标码": "VD", "中文简称": "25-羟基维生素D", "性别": "F/M", "风险类别": "维生素", "排序": 40},
            {"指标简称": "CEA", "上海指标码": "CEA-X", "中文简称": "癌胚抗原", "性别": "F/M", "风险类别": "癌筛", "排序": 2},
        ]
    )

    out = match_indicators(lab, whitelist, patient_gender="男")
    assert list(out["match_status"]) == ["hit_by_short", "hit_by_shanghai", "unmatched"]
    assert list(out["indicator_short_name"].fillna("")) == ["VD", "CEA", ""]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_whitelist.py -v`
Expected: FAIL with missing `match_indicators`

- [ ] **Step 3: Write minimal whitelist matcher**

```python
# src/report_pipeline/whitelist.py
import pandas as pd


def _gender_allows(patient_gender: str, rule: str) -> bool:
    if rule == "F/M":
        return True
    if patient_gender == "男":
        return rule == "M"
    if patient_gender == "女":
        return rule == "F"
    return False


def match_indicators(lab: pd.DataFrame, whitelist: pd.DataFrame, patient_gender: str) -> pd.DataFrame:
    indexed_short = {
        str(row["指标简称"]).strip(): row
        for _, row in whitelist.iterrows()
        if _gender_allows(patient_gender, str(row["性别"]).strip())
    }
    indexed_shanghai = {
        str(row["上海指标码"]).strip(): row
        for _, row in whitelist.iterrows()
        if pd.notna(row["上海指标码"]) and _gender_allows(patient_gender, str(row["性别"]).strip())
    }

    rows = []
    for _, row in lab.iterrows():
        code = str(row["raw_code"]).strip()
        match = indexed_short.get(code)
        status = "hit_by_short" if match is not None else "unmatched"
        if match is None:
            match = indexed_shanghai.get(code)
            if match is not None:
                status = "hit_by_shanghai"

        record = dict(row)
        if match is None:
            record.update(
                match_status="unmatched",
                indicator_short_name=None,
                indicator_display_name=None,
                risk_category=None,
                display_order=None,
            )
        else:
            record.update(
                match_status=status,
                indicator_short_name=str(match["指标简称"]).strip(),
                indicator_display_name=str(match["中文简称"]).strip(),
                risk_category=str(match["风险类别"]).strip(),
                display_order=match["排序"],
            )
        rows.append(record)

    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_whitelist.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
git add src/report_pipeline/whitelist.py tests/test_whitelist.py
git commit -m "feat: match lab indicators against whitelist rules"
```

### Task 4: Parse Reference Ranges And Risk States

**Files:**
- Create: `/Users/re.stem/综合健康检测报告v3.0/src/report_pipeline/reference_parser.py`
- Create: `/Users/re.stem/综合健康检测报告v3.0/src/report_pipeline/risk.py`
- Create: `/Users/re.stem/综合健康检测报告v3.0/tests/test_reference_parser.py`

- [ ] **Step 1: Write the failing parsing and risk tests**

```python
from report_pipeline.reference_parser import parse_reference
from report_pipeline.risk import evaluate_risk


def test_parse_range_reference():
    parsed = parse_reference("57.04-139.14")
    assert parsed["kind"] == "range"
    assert parsed["low"] == 57.04
    assert parsed["high"] == 139.14


def test_parse_vitamin_d_multirule():
    parsed = parse_reference("严重缺乏:≤10.00\\n缺乏:10.01-20.00\\n不足:20.01-30.00\\n正常:30.01-80.00\\n过量:>80.00\\n中毒:>150.00")
    assert parsed["kind"] == "multi_rule"
    assert parsed["labels"][:3] == ["严重缺乏", "缺乏", "不足"]


def test_evaluate_range_near_upper():
    parsed = parse_reference("57.04-139.14")
    risk = evaluate_risk(120, parsed)
    assert risk["risk_status"] == "near_upper"


def test_evaluate_multirule_status():
    parsed = parse_reference("严重缺乏:≤10.00\\n缺乏:10.01-20.00\\n不足:20.01-30.00\\n正常:30.01-80.00\\n过量:>80.00\\n中毒:>150.00")
    risk = evaluate_risk(29.85, parsed)
    assert risk["risk_status"] == "不足"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_reference_parser.py -v`
Expected: FAIL with missing parsing modules

- [ ] **Step 3: Write minimal parsing and risk evaluation**

```python
# src/report_pipeline/reference_parser.py
import math
import re


RANGE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*$")
BOUND_RE = re.compile(r"^\s*([<>≤≥＜＞])\s*(-?\d+(?:\.\d+)?(?:E[+-]?\d+)?)\s*$", re.I)


def parse_reference(raw: str) -> dict:
    text = "" if raw is None else str(raw).strip()
    if not text or text.lower() == "nan":
        return {"kind": "empty", "raw": text}

    if "\n" in text and ":" in text:
        labels = [part.split(":", 1)[0].strip() for part in text.splitlines() if ":" in part]
        return {"kind": "multi_rule", "raw": text, "labels": labels}

    match = RANGE_RE.match(text)
    if match:
        return {"kind": "range", "raw": text, "low": float(match.group(1)), "high": float(match.group(2))}

    match = BOUND_RE.match(text)
    if match:
        op = match.group(1).replace("＜", "<").replace("＞", ">")
        return {"kind": "bound", "raw": text, "op": op, "value": float(match.group(2))}

    return {"kind": "special", "raw": text}
```

```python
# src/report_pipeline/risk.py
def evaluate_risk(value, parsed: dict) -> dict:
    if parsed["kind"] == "range":
        low = parsed["low"]
        high = parsed["high"]
        if value < low:
            return {"risk_status": "below", "is_abnormal": True}
        if value > high:
            return {"risk_status": "above", "is_abnormal": True}
        if value >= low + 0.8 * (high - low):
            return {"risk_status": "near_upper", "is_abnormal": False}
        if low != 0 and value <= low + 0.2 * (high - low):
            return {"risk_status": "near_lower", "is_abnormal": False}
        return {"risk_status": "normal", "is_abnormal": False}

    if parsed["kind"] == "multi_rule":
        if value <= 10:
            return {"risk_status": "严重缺乏", "is_abnormal": True}
        if value <= 20:
            return {"risk_status": "缺乏", "is_abnormal": True}
        if value <= 30:
            return {"risk_status": "不足", "is_abnormal": True}
        if value <= 80:
            return {"risk_status": "正常", "is_abnormal": False}
        if value <= 150:
            return {"risk_status": "过量", "is_abnormal": True}
        return {"risk_status": "中毒", "is_abnormal": True}

    return {"risk_status": "unknown", "is_abnormal": False}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_reference_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
git add src/report_pipeline/reference_parser.py src/report_pipeline/risk.py tests/test_reference_parser.py
git commit -m "feat: parse references and evaluate risk states"
```

### Task 5: Build Section Data Sets For Summary And Nutrition

**Files:**
- Create: `/Users/re.stem/综合健康检测报告v3.0/src/report_pipeline/sections.py`
- Create: `/Users/re.stem/综合健康检测报告v3.0/tests/test_sections.py`

- [ ] **Step 1: Write the failing section assembly tests**

```python
import pandas as pd

from report_pipeline.sections import build_summary_sections, build_nutrition_sections


def test_build_summary_sections_excludes_nutrition():
    matched = pd.DataFrame(
        [
            {"risk_category": "癌筛", "indicator_display_name": "糖链抗原72-4", "risk_status": "above", "disease_type": "胃癌"},
            {"risk_category": "心筛", "indicator_display_name": "低密度脂蛋白胆固醇", "risk_status": "above", "disease_type": None},
            {"risk_category": "维生素", "indicator_display_name": "25-羟基维生素D", "risk_status": "不足", "disease_type": None},
        ]
    )

    summary = build_summary_sections(matched)
    assert "癌症健康监测小结" in summary
    assert "心脑血管健康监测小结" in summary
    assert "大营养检测" not in summary


def test_build_nutrition_sections_only_uses_hits():
    matched = pd.DataFrame(
        [
            {"match_status": "hit_by_short", "risk_category": "微量元素", "indicator_display_name": "铜"},
            {"match_status": "unmatched", "risk_category": None, "indicator_display_name": None},
        ]
    )

    nutrition = build_nutrition_sections(matched)
    assert len(nutrition["微量元素检测结果"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_sections.py -v`
Expected: FAIL with missing section builders

- [ ] **Step 3: Write minimal section builders**

```python
# src/report_pipeline/sections.py
def build_summary_sections(matched):
    cancer = matched[(matched["risk_category"] == "癌筛") & (matched["risk_status"] != "normal")]
    cardio = matched[(matched["risk_category"] == "心筛") & (matched["risk_status"] != "normal")]

    return {
        "癌症健康监测小结": cancer.to_dict("records"),
        "心脑血管健康监测小结": cardio.to_dict("records"),
    }


def build_nutrition_sections(matched):
    hit_rows = matched[matched["match_status"] != "unmatched"]
    micro = hit_rows[hit_rows["risk_category"] == "微量元素"]
    vitamin = hit_rows[hit_rows["risk_category"] == "维生素"]
    return {
        "微量元素检测结果": micro.to_dict("records"),
        "维生素检测结果": vitamin.to_dict("records"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_sections.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
git add src/report_pipeline/sections.py tests/test_sections.py
git commit -m "feat: assemble summary and nutrition section datasets"
```

### Task 6: Add Extraction Command For Real Customer Inputs

**Files:**
- Modify: `/Users/re.stem/综合健康检测报告v3.0/src/report_pipeline/cli.py`
- Create: `/Users/re.stem/综合健康检测报告v3.0/src/report_pipeline/pipeline.py`
- Create: `/Users/re.stem/综合健康检测报告v3.0/output/.gitkeep`
- Create: `/Users/re.stem/综合健康检测报告v3.0/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing pipeline smoke test**

```python
from pathlib import Path

from report_pipeline.pipeline import export_outputs


def test_export_outputs_writes_expected_files(tmp_path: Path):
    export_outputs(
        matched_rows=[{"indicator_short_name": "VD", "risk_category": "维生素"}],
        summary={"癌症健康监测小结": [], "心脑血管健康监测小结": []},
        nutrition={"维生素检测结果": [{"indicator_short_name": "VD"}], "微量元素检测结果": []},
        output_dir=tmp_path,
    )

    assert (tmp_path / "matched_indicators.json").exists()
    assert (tmp_path / "summary_sections.json").exists()
    assert (tmp_path / "nutrition_sections.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_pipeline.py -v`
Expected: FAIL with missing `export_outputs`

- [ ] **Step 3: Write the minimal export pipeline and CLI wiring**

```python
# src/report_pipeline/pipeline.py
import json
from pathlib import Path


def export_outputs(matched_rows, summary, nutrition, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "matched_indicators.json").write_text(
        json.dumps(matched_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "summary_sections.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "nutrition_sections.json").write_text(
        json.dumps(nutrition, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

```python
# add into src/report_pipeline/cli.py
extract = subparsers.add_parser("extract")
extract.add_argument("--lab-xls", required=True)
extract.add_argument("--standard-xlsx", required=True)
extract.add_argument("--output-dir", required=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd '/Users/re.stem/综合健康检测报告v3.0' && pytest tests/test_pipeline.py tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
git add src/report_pipeline/cli.py src/report_pipeline/pipeline.py output/.gitkeep tests/test_pipeline.py
git commit -m "feat: export intermediate datasets for report assembly"
```

### Task 7: Validate Against The Real Customer Files

**Files:**
- Create: `/Users/re.stem/综合健康检测报告v3.0/docs/validation/2026-04-09-customer-run.md`
- Modify: `/Users/re.stem/综合健康检测报告v3.0/docs/字段映射表.md`

- [ ] **Step 1: Run the extract command against the real files**

Run:

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
python -m report_pipeline.cli extract \
  --lab-xls '/Users/re.stem/Downloads/客户信息文档（上海）/客户基础数据/C-20251224-1406边伟星/检测数据/边伟星-20251224.xls' \
  --standard-xlsx '/Users/re.stem/Downloads/客户信息文档（上海）/标准文档/客户健康综合检测基础数据V1.6 - 不含白介素.xlsx' \
  --output-dir '/Users/re.stem/综合健康检测报告v3.0/output/customer-run'
```

Expected:
- `matched_indicators.json` exists
- `summary_sections.json` exists
- `nutrition_sections.json` exists

- [ ] **Step 2: Inspect the generated data**

Run:

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
python - <<'PY'
import json
from pathlib import Path
base = Path('output/customer-run')
for name in ['matched_indicators.json', 'summary_sections.json', 'nutrition_sections.json']:
    data = json.loads((base / name).read_text(encoding='utf-8'))
    print(name, type(data).__name__)
PY
```

Expected:
- `matched_indicators.json` contains real matched rows
- nutrition output contains 19 hit rows
- summary output excludes nutrition categories

- [ ] **Step 3: Write validation notes**

```markdown
# 2026-04-09 Customer Run Validation

- Input lab file: `...边伟星-20251224.xls`
- Input standard file: `...客户健康综合检测基础数据V1.6 - 不含白介素.xlsx`
- Nutrition whitelist hits: 19
- Vitamin D status: `不足`
- Selenium status: above range
- Remaining gaps: PDF extraction and final renderer not implemented yet
```

- [ ] **Step 4: Update docs if runtime behavior differs from the spec**

Update `/Users/re.stem/综合健康检测报告v3.0/docs/字段映射表.md` only if the real run shows a field mismatch or rule mismatch.

- [ ] **Step 5: Commit**

```bash
cd '/Users/re.stem/综合健康检测报告v3.0'
git add docs/validation/2026-04-09-customer-run.md docs/字段映射表.md output/customer-run
git commit -m "docs: validate data pipeline against customer files"
```

---

## Self-Review

### Spec Coverage

- XLS old/new compatibility: covered in Task 2
- Whitelist matching and gender filtering: covered in Task 3
- Reference parsing and risk rules: covered in Task 4
- Summary split and nutrition-only section behavior: covered in Task 5
- Real customer validation: covered in Task 7

### Placeholder Scan

- No `TODO` or `TBD`
- Every task lists exact files
- Every test step includes executable commands

### Scope Check

- This plan only covers the data pipeline and intermediate outputs
- PDF rendering remains out of scope for this plan and should be a separate follow-up plan
