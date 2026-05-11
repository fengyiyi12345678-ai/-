"""敏感性分析模块。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.assumptions import FinancialAssumptions
from src.dcf_model import run_dcf


def _grid(center: float, half_range: float, n: int = 5) -> np.ndarray:
    return np.linspace(center - half_range, center + half_range, n)


def sensitivity_wacc_terminal(
    assumptions: FinancialAssumptions,
    base_revenue: float,
    n: int = 5,
) -> pd.DataFrame:
    """WACC vs 永续增长率 -> 每股合理价值矩阵。"""
    waccs = _grid(assumptions.wacc, 0.015, n)
    gs = _grid(assumptions.terminal_growth_rate, 0.010, n)
    out = pd.DataFrame(index=[f"{w:.2%}" for w in waccs], columns=[f"{g:.2%}" for g in gs], dtype=float)
    out.index.name = "WACC"
    out.columns.name = "永续增长率"
    for w in waccs:
        for g in gs:
            updated = assumptions.model_copy(update={"wacc": float(w), "terminal_growth_rate": float(g)})
            try:
                res = run_dcf(updated, base_revenue)
                out.loc[f"{w:.2%}", f"{g:.2%}"] = res.valuation["fair_value_per_share"]
            except Exception:
                out.loc[f"{w:.2%}", f"{g:.2%}"] = np.nan
    return out


def sensitivity_growth_margin(
    assumptions: FinancialAssumptions,
    base_revenue: float,
    n: int = 5,
) -> pd.DataFrame:
    """收入增速 vs 经营利润率 -> 每股合理价值矩阵。

    用前一年的平均增速 + delta 作为五年增速的统一调整。
    """
    base_growth = float(np.mean(assumptions.aligned_growth()))
    growths = _grid(base_growth, 0.03, n)
    margins = _grid(assumptions.operating_margin, 0.03, n)
    out = pd.DataFrame(
        index=[f"{g:.2%}" for g in growths],
        columns=[f"{m:.2%}" for m in margins],
        dtype=float,
    )
    out.index.name = "收入增速"
    out.columns.name = "经营利润率"
    n_years = assumptions.forecast_years
    for g in growths:
        for m in margins:
            updated = assumptions.model_copy(update={
                "revenue_growth_rates": [float(g)] * n_years,
                "operating_margin": float(m),
            })
            try:
                res = run_dcf(updated, base_revenue)
                out.loc[f"{g:.2%}", f"{m:.2%}"] = res.valuation["fair_value_per_share"]
            except Exception:
                out.loc[f"{g:.2%}", f"{m:.2%}"] = np.nan
    return out
