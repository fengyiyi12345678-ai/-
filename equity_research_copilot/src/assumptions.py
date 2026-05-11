"""DCF 假设模型。"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator

from src.utils import avg_or_none, safe_div


class FinancialAssumptions(BaseModel):
    """DCF 估值假设。所有比率均为小数（0.10 = 10%）。"""

    forecast_years: int = Field(5, ge=1, le=15)
    revenue_growth_rates: list[float] = Field(default_factory=lambda: [0.10, 0.09, 0.08, 0.07, 0.06])
    gross_margin: float = 0.40
    operating_margin: float = 0.20
    tax_rate: float = 0.20
    depreciation_pct_revenue: float = 0.04
    capex_pct_revenue: float = 0.05
    nwc_pct_revenue: float = 0.05
    wacc: float = 0.09
    terminal_growth_rate: float = 0.025
    net_debt: float = 0.0
    diluted_shares: float = 1.0  # 单位：百万股

    @field_validator("revenue_growth_rates")
    @classmethod
    def _check_growth(cls, v: list[float], info) -> list[float]:
        if not v:
            raise ValueError("revenue_growth_rates 不能为空")
        return v

    def aligned_growth(self) -> list[float]:
        """把增速向量补齐 / 截断到 forecast_years 长度。"""
        g = list(self.revenue_growth_rates)
        if len(g) < self.forecast_years:
            last = g[-1] if g else 0.05
            g = g + [last] * (self.forecast_years - len(g))
        else:
            g = g[: self.forecast_years]
        return g


def assumptions_from_history(history_summary: dict[str, Any], normalized) -> FinancialAssumptions:
    """根据历史数据生成一组默认假设。

    - 增速：使用历史 revenue 的 yoy 均值
    - 利润率、税率、capex/depreciation/nwc 比率：使用历史均值
    - net_debt、diluted_shares：取最新一期
    """
    income = getattr(normalized, "income", pd.DataFrame())
    cf = getattr(normalized, "cash_flow", pd.DataFrame())
    bal = getattr(normalized, "balance", pd.DataFrame())

    growth: float | None = None
    if not income.empty and "revenue" in income.columns and "year" in income.columns:
        s = income.sort_values("year")["revenue"].pct_change().dropna()
        if not s.empty:
            growth = float(s.mean())

    gross_margin = None
    op_margin = None
    if not income.empty and "revenue" in income.columns:
        if "gross_margin" in income.columns:
            gross_margin = avg_or_none(income["gross_margin"].tolist())
        if "operating_margin" in income.columns:
            op_margin = avg_or_none(income["operating_margin"].tolist())

    # 折旧 / capex / nwc 占收入比
    dep_pct = None
    capex_pct = None
    if not cf.empty and not income.empty and "revenue" in income.columns:
        merged = income[["year", "revenue"]].merge(cf, on="year", how="left") if "year" in cf.columns else None
        if merged is not None:
            if "depreciation" in merged.columns:
                pct = (merged["depreciation"] / merged["revenue"]).dropna()
                if not pct.empty:
                    dep_pct = float(pct.mean())
            if "capex" in merged.columns:
                pct = (merged["capex"].abs() / merged["revenue"]).dropna()
                if not pct.empty:
                    capex_pct = float(pct.mean())

    diluted = history_summary.get("diluted_shares")
    if diluted is None or pd.isna(diluted) or diluted == 0:
        diluted = 1.0

    net_debt = history_summary.get("net_debt")
    if net_debt is None or (isinstance(net_debt, float) and np.isnan(net_debt)):
        net_debt = 0.0

    forecast_years = 5
    base_growth = growth if growth is not None else 0.08
    # 增速线性向永续增长率 2.5% 收敛
    growth_list = list(np.linspace(base_growth, max(0.025, base_growth * 0.5), forecast_years))

    return FinancialAssumptions(
        forecast_years=forecast_years,
        revenue_growth_rates=[float(round(x, 4)) for x in growth_list],
        gross_margin=float(round(gross_margin, 4)) if gross_margin is not None else 0.40,
        operating_margin=float(round(op_margin, 4)) if op_margin is not None else 0.20,
        tax_rate=0.20,
        depreciation_pct_revenue=float(round(dep_pct, 4)) if dep_pct is not None else 0.04,
        capex_pct_revenue=float(round(capex_pct, 4)) if capex_pct is not None else 0.05,
        nwc_pct_revenue=0.05,
        wacc=0.09,
        terminal_growth_rate=0.025,
        net_debt=float(net_debt),
        diluted_shares=float(diluted),
    )


def scenario_assumptions(base: FinancialAssumptions) -> dict[str, FinancialAssumptions]:
    """生成 bull/base/bear 情景。"""
    def shift(growths: list[float], delta: float) -> list[float]:
        return [g + delta for g in growths]

    bull = base.model_copy(update={
        "revenue_growth_rates": shift(base.aligned_growth(), 0.02),
        "operating_margin": base.operating_margin + 0.02,
        "terminal_growth_rate": min(base.terminal_growth_rate + 0.005, base.wacc - 0.005),
    })
    bear = base.model_copy(update={
        "revenue_growth_rates": shift(base.aligned_growth(), -0.02),
        "operating_margin": max(base.operating_margin - 0.02, 0.0),
        "terminal_growth_rate": max(base.terminal_growth_rate - 0.005, 0.0),
    })
    return {"bull": bull, "base": base, "bear": bear}
