"""收入结构清洗模块。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.upload_parser import normalize_columns
from src.utils import safe_div


@dataclass
class RevenueBreakdown:
    by_segment_year: pd.DataFrame = field(default_factory=pd.DataFrame)
    share: pd.DataFrame = field(default_factory=pd.DataFrame)
    growth: pd.DataFrame = field(default_factory=pd.DataFrame)
    gross_margin: pd.DataFrame = field(default_factory=pd.DataFrame)
    note: str = ""

    @property
    def is_empty(self) -> bool:
        return self.by_segment_year.empty


def clean_revenue_segments(df: pd.DataFrame | None) -> RevenueBreakdown:
    if df is None or df.empty:
        return RevenueBreakdown(note="暂无分部收入数据")
    df = normalize_columns(df)
    required = {"year", "segment", "revenue"}
    if not required.issubset(set(df.columns)):
        return RevenueBreakdown(
            note=f"分部收入数据缺少必要列：{sorted(required - set(df.columns))}"
        )

    df = df.copy()
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
    if "gross_profit" in df.columns:
        df["gross_profit"] = pd.to_numeric(df["gross_profit"], errors="coerce")
    if "operating_profit" in df.columns:
        df["operating_profit"] = pd.to_numeric(df["operating_profit"], errors="coerce")
    df = df.dropna(subset=["year", "segment", "revenue"])
    df["year"] = df["year"].astype(int, errors="ignore") if df["year"].dtype != object else df["year"]

    # 按年份汇总
    yearly_total = df.groupby("year")["revenue"].sum().rename("total_revenue")
    df = df.merge(yearly_total, on="year", how="left")
    df["share"] = df.apply(lambda r: safe_div(r["revenue"], r["total_revenue"]), axis=1)

    # 收入占比表（透视：行 segment，列 year）
    share_pivot = df.pivot_table(index="segment", columns="year", values="share", aggfunc="mean").sort_index()
    revenue_pivot = df.pivot_table(index="segment", columns="year", values="revenue", aggfunc="sum").sort_index()

    # 同比增速
    growth_pivot = revenue_pivot.pct_change(axis=1)

    # 毛利率
    margin_pivot = pd.DataFrame()
    if "gross_profit" in df.columns:
        gp_pivot = df.pivot_table(index="segment", columns="year", values="gross_profit", aggfunc="sum").sort_index()
        margin_pivot = gp_pivot / revenue_pivot.replace(0, np.nan)

    return RevenueBreakdown(
        by_segment_year=df.sort_values(["year", "segment"]).reset_index(drop=True),
        share=share_pivot,
        growth=growth_pivot,
        gross_margin=margin_pivot,
        note="",
    )


def find_segment_highlights(rb: RevenueBreakdown) -> dict[str, str]:
    """挑出增长最快 / 拖累 / 高毛利的业务，用于报告。"""
    res: dict[str, str] = {}
    if rb.is_empty:
        return res
    if not rb.growth.empty and rb.growth.shape[1] >= 1:
        latest_year = rb.growth.columns[-1]
        latest_growth = rb.growth[latest_year].dropna()
        if not latest_growth.empty:
            res["fastest_growing"] = (
                f"{latest_growth.idxmax()}（{latest_year} 年同比 {latest_growth.max():.1%}）"
            )
            res["slowest_growing"] = (
                f"{latest_growth.idxmin()}（{latest_year} 年同比 {latest_growth.min():.1%}）"
            )
    if not rb.gross_margin.empty:
        latest_year = rb.gross_margin.columns[-1]
        latest_margin = rb.gross_margin[latest_year].dropna()
        if not latest_margin.empty:
            res["highest_margin"] = (
                f"{latest_margin.idxmax()}（{latest_year} 年毛利率 {latest_margin.max():.1%}）"
            )
    if not rb.share.empty:
        latest_year = rb.share.columns[-1]
        latest_share = rb.share[latest_year].dropna()
        if not latest_share.empty:
            res["largest_segment"] = (
                f"{latest_share.idxmax()}（{latest_year} 年占比 {latest_share.max():.1%}）"
            )
    return res
