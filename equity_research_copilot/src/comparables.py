"""可比公司估值模块。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.upload_parser import normalize_columns
from src.utils import safe_div


REQUIRED_COLS = ["ticker", "market_cap", "revenue", "net_income"]
OPTIONAL_COLS = ["company_name", "ebitda", "ev"]


@dataclass
class ComparablesResult:
    table: pd.DataFrame = field(default_factory=pd.DataFrame)
    multiples_median: dict[str, float | None] = field(default_factory=dict)
    target_implied: dict[str, dict[str, float | None]] = field(default_factory=dict)
    valuation_range: dict[str, dict[str, float | None]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def has_data(self) -> bool:
        return not self.table.empty


def _compute_multiples(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["p_s"] = df.apply(lambda r: safe_div(r.get("market_cap"), r.get("revenue")), axis=1)
    df["p_e"] = df.apply(
        lambda r: safe_div(r.get("market_cap"), r.get("net_income"))
        if pd.notna(r.get("net_income")) and r.get("net_income") > 0
        else None,
        axis=1,
    )
    if "ev" in df.columns:
        df["ev_sales"] = df.apply(lambda r: safe_div(r.get("ev"), r.get("revenue")), axis=1)
    if "ev" in df.columns and "ebitda" in df.columns:
        df["ev_ebitda"] = df.apply(
            lambda r: safe_div(r.get("ev"), r.get("ebitda"))
            if pd.notna(r.get("ebitda")) and r.get("ebitda") > 0
            else None,
            axis=1,
        )
    return df


def _flag_outliers(series: pd.Series, k: float = 3.0) -> pd.Series:
    """基于 MAD 标注极端值。"""
    s = series.dropna()
    if s.empty:
        return pd.Series(False, index=series.index)
    med = s.median()
    mad = (s - med).abs().median()
    if mad == 0 or pd.isna(mad):
        return pd.Series(False, index=series.index)
    z = (series - med).abs() / (mad * 1.4826)
    return z > k


def compute_comparables(
    peers_df: pd.DataFrame | None,
    target_metrics: dict[str, float | None] | None = None,
) -> ComparablesResult:
    if peers_df is None or peers_df.empty:
        return ComparablesResult(note="未提供可比公司数据")
    df = normalize_columns(peers_df)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return ComparablesResult(note=f"可比公司数据缺少列：{missing}")

    for c in ("market_cap", "revenue", "net_income", "ebitda", "ev"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df = _compute_multiples(df)

    warnings: list[str] = []
    if len(df) < 3:
        warnings.append("可比样本不足（少于 3 家公司），估值参考意义有限。")

    # 标注极端值
    outlier_flags = pd.DataFrame(index=df.index)
    for col in ("p_s", "p_e", "ev_sales", "ev_ebitda"):
        if col in df.columns:
            outlier_flags[col] = _flag_outliers(df[col])
    df["is_outlier"] = outlier_flags.any(axis=1) if not outlier_flags.empty else False

    # 中位数（排除极端值后计算）
    clean = df[~df["is_outlier"]] if "is_outlier" in df.columns else df
    medians: dict[str, float | None] = {}
    for col in ("p_s", "p_e", "ev_sales", "ev_ebitda"):
        if col in clean.columns:
            med = clean[col].dropna()
            medians[col] = float(med.median()) if not med.empty else None
        else:
            medians[col] = None

    # 用中位数反推目标公司估值
    target_implied: dict[str, dict[str, float | None]] = {}
    valuation_range: dict[str, dict[str, float | None]] = {}
    if target_metrics:
        rev = target_metrics.get("revenue")
        ni = target_metrics.get("net_income")
        ebitda = target_metrics.get("ebitda")
        net_debt = target_metrics.get("net_debt", 0.0) or 0.0
        shares = target_metrics.get("diluted_shares") or None

        def _implied(metric_value: float | None, multiple: float | None) -> float | None:
            if metric_value is None or multiple is None:
                return None
            try:
                return float(metric_value) * float(multiple)
            except Exception:
                return None

        target_implied["equity_value_by_ps"] = {
            "low": _implied(rev, _percentile(clean.get("p_s"), 25)),
            "median": _implied(rev, medians.get("p_s")),
            "high": _implied(rev, _percentile(clean.get("p_s"), 75)),
        }
        target_implied["equity_value_by_pe"] = {
            "low": _implied(ni, _percentile(clean.get("p_e"), 25)),
            "median": _implied(ni, medians.get("p_e")),
            "high": _implied(ni, _percentile(clean.get("p_e"), 75)),
        }
        target_implied["ev_by_evsales"] = {
            "low": _implied(rev, _percentile(clean.get("ev_sales"), 25)),
            "median": _implied(rev, medians.get("ev_sales")),
            "high": _implied(rev, _percentile(clean.get("ev_sales"), 75)),
        }
        target_implied["ev_by_evebitda"] = {
            "low": _implied(ebitda, _percentile(clean.get("ev_ebitda"), 25)),
            "median": _implied(ebitda, medians.get("ev_ebitda")),
            "high": _implied(ebitda, _percentile(clean.get("ev_ebitda"), 75)),
        }

        if shares and shares > 0:
            def _per_share(equity_value: float | None) -> float | None:
                if equity_value is None:
                    return None
                return float(equity_value) / float(shares)

            def _ev_to_per_share(ev_val: float | None) -> float | None:
                if ev_val is None:
                    return None
                return float(ev_val - net_debt) / float(shares)

            valuation_range["per_share_by_ps"] = {
                k: _per_share(v) for k, v in target_implied["equity_value_by_ps"].items()
            }
            valuation_range["per_share_by_pe"] = {
                k: _per_share(v) for k, v in target_implied["equity_value_by_pe"].items()
            }
            valuation_range["per_share_by_evsales"] = {
                k: _ev_to_per_share(v) for k, v in target_implied["ev_by_evsales"].items()
            }
            valuation_range["per_share_by_evebitda"] = {
                k: _ev_to_per_share(v) for k, v in target_implied["ev_by_evebitda"].items()
            }

    return ComparablesResult(
        table=df,
        multiples_median=medians,
        target_implied=target_implied,
        valuation_range=valuation_range,
        warnings=warnings,
    )


def _percentile(series: pd.Series | None, q: float) -> float | None:
    if series is None:
        return None
    s = series.dropna()
    if s.empty:
        return None
    return float(np.percentile(s, q))
