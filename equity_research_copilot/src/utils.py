"""通用工具函数。"""
from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
import pandas as pd

MISSING = "N/A"


def safe_div(numerator: float, denominator: float) -> float | None:
    """安全除法。分母为 0 / None / NaN 时返回 None。"""
    try:
        if numerator is None or denominator is None:
            return None
        if isinstance(numerator, float) and math.isnan(numerator):
            return None
        if isinstance(denominator, float) and math.isnan(denominator):
            return None
        if denominator == 0:
            return None
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def fmt_money(v: Any, unit: str = "百万") -> str:
    """格式化金额，缺失返回 N/A。"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return MISSING
    try:
        return f"{float(v):,.2f} {unit}"
    except (TypeError, ValueError):
        return MISSING


def fmt_pct(v: Any, digits: int = 2) -> str:
    """格式化百分比，缺失返回 N/A。"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return MISSING
    try:
        return f"{float(v) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return MISSING


def fmt_number(v: Any, digits: int = 2) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return MISSING
    try:
        return f"{float(v):,.{digits}f}"
    except (TypeError, ValueError):
        return MISSING


def coalesce(*values: Any) -> Any:
    """返回第一个非空非 NaN 的值。"""
    for v in values:
        if v is None:
            continue
        if isinstance(v, float) and math.isnan(v):
            continue
        return v
    return None


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def avg_or_none(values: Iterable[Any]) -> float | None:
    vs = [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vs:
        return None
    return float(np.mean(vs))


def yoy_growth(series: pd.Series) -> pd.Series:
    """计算同比增速。"""
    return series.pct_change()


def is_missing(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and v.strip() in {"", MISSING}:
        return True
    return False


def ensure_dataframe(obj: Any) -> pd.DataFrame:
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        return obj
    try:
        return pd.DataFrame(obj)
    except Exception:
        return pd.DataFrame()
