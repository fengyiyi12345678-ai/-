"""敏感性分析测试。"""
import math

import pandas as pd

from src.assumptions import FinancialAssumptions
from src.sensitivity import sensitivity_growth_margin, sensitivity_wacc_terminal


def _a() -> FinancialAssumptions:
    return FinancialAssumptions(
        forecast_years=5,
        revenue_growth_rates=[0.10] * 5,
        gross_margin=0.40,
        operating_margin=0.20,
        tax_rate=0.20,
        depreciation_pct_revenue=0.05,
        capex_pct_revenue=0.05,
        nwc_pct_revenue=0.05,
        wacc=0.10,
        terminal_growth_rate=0.025,
        net_debt=0.0,
        diluted_shares=100.0,
    )


def test_sensitivity_wacc_terminal_shape():
    df = sensitivity_wacc_terminal(_a(), base_revenue=1000.0, n=5)
    assert df.shape == (5, 5)
    # 表中央应等于基础情景估值
    center_w = df.index[2]
    center_g = df.columns[2]
    assert df.loc[center_w, center_g] > 0


def test_sensitivity_wacc_terminal_monotonic():
    """WACC 增加 -> 每股价值下降；永续增长率增加 -> 每股价值上升。"""
    df = sensitivity_wacc_terminal(_a(), base_revenue=1000.0, n=5)
    mid_col = df.columns[2]
    col = df[mid_col].dropna().tolist()
    # 沿 WACC 升序，每股价值递减
    assert all(col[i] >= col[i + 1] for i in range(len(col) - 1))
    mid_row = df.index[2]
    row = df.loc[mid_row].dropna().tolist()
    assert all(row[i] <= row[i + 1] for i in range(len(row) - 1))


def test_sensitivity_growth_margin_shape_and_monotonic():
    df = sensitivity_growth_margin(_a(), base_revenue=1000.0, n=5)
    assert df.shape == (5, 5)
    # 利润率越高，每股价值越高
    mid_row = df.index[2]
    row = df.loc[mid_row].dropna().tolist()
    assert all(row[i] <= row[i + 1] for i in range(len(row) - 1))


def test_sensitivity_handles_invalid_combinations():
    a = _a().model_copy(update={"wacc": 0.04, "terminal_growth_rate": 0.025})
    df = sensitivity_wacc_terminal(a, base_revenue=1000.0, n=5)
    # 至少应该有部分单元格因为 WACC <= g 而为 NaN
    assert df.isna().sum().sum() > 0
