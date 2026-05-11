"""DCF 模型测试。"""
import math

import pytest

from src.assumptions import FinancialAssumptions
from src.dcf_model import implied_rating, run_dcf


def _basic_assumptions(**override) -> FinancialAssumptions:
    base = dict(
        forecast_years=5,
        revenue_growth_rates=[0.10, 0.10, 0.10, 0.10, 0.10],
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
    base.update(override)
    return FinancialAssumptions(**base)


def test_dcf_basic_run():
    a = _basic_assumptions()
    res = run_dcf(a, base_revenue=1000.0)
    assert len(res.forecast) == 5
    # 收入按 10% 复合增长
    assert math.isclose(res.forecast["revenue"].iloc[0], 1100.0, rel_tol=1e-6)
    assert math.isclose(res.forecast["revenue"].iloc[4], 1000.0 * (1.10 ** 5), rel_tol=1e-6)
    # 经营利润率 = 20%
    assert math.isclose(
        res.forecast["operating_income"].iloc[0],
        res.forecast["revenue"].iloc[0] * 0.20,
        rel_tol=1e-6,
    )
    # NOPAT 公式
    assert math.isclose(
        res.forecast["nopat"].iloc[0],
        res.forecast["operating_income"].iloc[0] * (1 - 0.20),
        rel_tol=1e-6,
    )
    # FCF = NOPAT + D&A - capex - ΔNWC
    expected_fcf_0 = (
        res.forecast["nopat"].iloc[0]
        + res.forecast["depreciation"].iloc[0]
        - res.forecast["capex"].iloc[0]
        - res.forecast["change_in_nwc"].iloc[0]
    )
    assert math.isclose(res.forecast["free_cash_flow"].iloc[0], expected_fcf_0, rel_tol=1e-9)
    # 估值结果为正数
    assert res.valuation["enterprise_value"] > 0
    assert res.valuation["fair_value_per_share"] > 0


def test_wacc_must_exceed_terminal_growth():
    a = _basic_assumptions(wacc=0.05, terminal_growth_rate=0.05)
    with pytest.raises(ValueError):
        run_dcf(a, base_revenue=1000.0)
    a2 = _basic_assumptions(wacc=0.04, terminal_growth_rate=0.05)
    with pytest.raises(ValueError):
        run_dcf(a2, base_revenue=1000.0)


def test_invalid_base_revenue():
    a = _basic_assumptions()
    with pytest.raises(ValueError):
        run_dcf(a, base_revenue=0.0)
    with pytest.raises(ValueError):
        run_dcf(a, base_revenue=-100.0)


def test_growth_alignment_extends():
    a = _basic_assumptions(forecast_years=5, revenue_growth_rates=[0.10, 0.08])
    growths = a.aligned_growth()
    assert len(growths) == 5
    # 后面用最后一个值填充
    assert growths == [0.10, 0.08, 0.08, 0.08, 0.08]


def test_terminal_value_formula():
    a = _basic_assumptions()
    res = run_dcf(a, base_revenue=1000.0)
    final_fcf = res.forecast["free_cash_flow"].iloc[-1]
    expected_tv = final_fcf * (1 + 0.025) / (0.10 - 0.025)
    assert math.isclose(res.valuation["terminal_value"], expected_tv, rel_tol=1e-9)


def test_implied_rating_thresholds():
    assert implied_rating(130, 100) == "买入"
    assert implied_rating(115, 100) == "增持"
    assert implied_rating(100, 100) == "中性"
    assert implied_rating(85, 100) == "减持"
    assert implied_rating(60, 100) == "卖出"
    assert implied_rating(None, 100) == "暂无评级"
    assert implied_rating(100, None) == "暂无评级"
