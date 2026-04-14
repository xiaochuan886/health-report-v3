from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "raw_code": ("项目代号", "项目编号"),
    "raw_name": ("项目名称",),
    "raw_result": ("项目测定值", "结果"),
    "lab_flag": ("高低标记", "提示"),
    "raw_reference": ("参考值",),
    "unit": ("单位",),
    "raw_barcode": ("艾迪康条码", "条形码"),
    "specimen_type": ("样本种类", "标本类型"),
    "received_at": ("接收时间",),
    "reported_at": ("报告日期", "报告时间"),
    "reviewed_at": ("审核时间",),
    "sampled_at": ("采集时间",),
}

REQUIRED_CANONICAL_COLUMNS = tuple(FIELD_ALIASES)


def _first_existing_column(columns: Iterable[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def normalize_lab_dataframe(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()

    for canonical_name, candidates in FIELD_ALIASES.items():
        if canonical_name in out.columns:
            continue

        source_name = _first_existing_column(out.columns, candidates)
        if source_name is not None:
            out = out.rename(columns={source_name: canonical_name})

    for column in REQUIRED_CANONICAL_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA

    return out
