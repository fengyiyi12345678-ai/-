"""DCF 估值模型。

所有金额单位：百万（与假设保持一致）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.assumptions import FinancialAssumptions
from src.utils import safe_div


@dataclass
class DCFResult:
    forecast: pd.DataFrame
    valuation: dict[str, float]
    assumptions: FinancialAssumptions

    @property
    def fair_value_per_share(self) -> float | None:
        return self.valuation.get("fair_value_per_share")


def run_dcf(assumptions: FinancialAssumptions, base_revenue: float) -> DCFResult:
    """运行 DCF 估值。

    Args:
        assumptions: FinancialAssumptions
        base_revenue: 最近一期收入（单位百万）

    Returns:
        DCFResult: forecast + valuation
    """
    if assumptions.wacc <= assumptions.terminal_growth_rate:
        raise ValueError(
            f"WACC（{assumptions.wacc:.2%}）必须大于永续增长率"
            f"（{assumptions.terminal_growth_rate:.2%}），否则估值发散。"
        )
    if base_revenue is None or base_revenue <= 0:
        raise ValueError("base_revenue 必须为正数（单位：百万）")
    if assumptions.diluted_shares is None or assumptions.diluted_shares <= 0:
        raise ValueError("diluted_shares 必须为正数（单位：百万股）")

    growths = assumptions.aligned_growth()
    years = list(range(1, assumptions.forecast_years + 1))

    revenue: list[float] = []
    prev_rev = float(base_revenue)
    for g in growths:
        prev_rev = prev_rev * (1 + g)
        revenue.append(prev_rev)

    revenue_arr = np.array(revenue)
    gross_profit = revenue_arr * assumptions.gross_margin
    operating_income = revenue_arr * assumptions.operating_margin
    tax = operating_income * assumptions.tax_rate
    nopat = operating_income - tax
    depreciation = revenue_arr * assumptions.depreciation_pct_revenue
    capex = revenue_arr * assumptions.capex_pct_revenue

    # 营运资本变动：以收入增量乘以 nwc_pct_revenue
    revenue_growth_amount = np.diff(np.concatenate([[base_revenue], revenue_arr]))
    change_in_nwc = revenue_growth_amount * assumptions.nwc_pct_revenue

    fcf = nopat + depreciation - capex - change_in_nwc

    # 折现
    discount_factors = np.array([(1 + assumptions.wacc) ** t for t in years])
    pv_fcf = fcf / discount_factors

    # 终值
    terminal_value = fcf[-1] * (1 + assumptions.terminal_growth_rate) / (
        assumptions.wacc - assumptions.terminal_growth_rate
    )
    pv_terminal = terminal_value / discount_factors[-1]

    enterprise_value = float(pv_fcf.sum() + pv_terminal)
    equity_value = enterprise_value - float(assumptions.net_debt)
    fair_value_per_share = equity_value / float(assumptions.diluted_shares)

    forecast = pd.DataFrame({
        "year_index": years,
        "revenue": revenue_arr,
        "revenue_growth": growths,
        "gross_profit": gross_profit,
        "operating_income": operating_income,
        "tax": tax,
        "nopat": nopat,
        "depreciation": depreciation,
        "capex": capex,
        "change_in_nwc": change_in_nwc,
        "free_cash_flow": fcf,
        "discount_factor": discount_factors,
        "pv_free_cash_flow": pv_fcf,
    })

    valuation = {
        "base_revenue": float(base_revenue),
        "sum_pv_fcf": float(pv_fcf.sum()),
        "terminal_value": float(terminal_value),
        "pv_terminal": float(pv_terminal),
        "enterprise_value": enterprise_value,
        "net_debt": float(assumptions.net_debt),
        "equity_value": equity_value,
        "diluted_shares": float(assumptions.diluted_shares),
        "fair_value_per_share": fair_value_per_share,
        "wacc": float(assumptions.wacc),
        "terminal_growth_rate": float(assumptions.terminal_growth_rate),
    }
    return DCFResult(forecast=forecast, valuation=valuation, assumptions=assumptions)


def run_scenarios(
    scenarios: dict[str, FinancialAssumptions], base_revenue: float
) -> dict[str, DCFResult | str]:
    """对 bull/base/bear 三个情景分别估值。出错则返回错误字符串。"""
    results: dict[str, DCFResult | str] = {}
    for name, a in scenarios.items():
        try:
            results[name] = run_dcf(a, base_revenue)
        except Exception as e:  # 包含 wacc <= g 等
            results[name] = f"估值失败：{e}"
    return results


def implied_rating(fair_value: float | None, current_price: float | None) -> str:
    """根据 DCF 公允价值与当前股价计算评级。"""
    if fair_value is None or current_price is None or current_price <= 0:
        return "暂无评级"
    upside = (fair_value - current_price) / current_price
    if upside >= 0.30:
        return "买入"
    if upside >= 0.10:
        return "增持"
    if upside >= -0.10:
        return "中性"
    if upside >= -0.30:
        return "减持"
    return "卖出"
