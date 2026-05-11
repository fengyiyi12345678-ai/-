"""可比公司估值测试。"""
import math

import pandas as pd

from src.comparables import compute_comparables


def _peers():
    return pd.DataFrame([
        {"ticker": "AAA", "company_name": "Alpha", "market_cap": 1000, "revenue": 200, "net_income": 50, "ebitda": 80, "ev": 1050},
        {"ticker": "BBB", "company_name": "Beta",  "market_cap": 800,  "revenue": 160, "net_income": 40, "ebitda": 64, "ev": 850},
        {"ticker": "CCC", "company_name": "Gamma", "market_cap": 1200, "revenue": 240, "net_income": -30, "ebitda": 90, "ev": 1300},
        {"ticker": "DDD", "company_name": "Delta", "market_cap": 1500, "revenue": 300, "net_income": 60, "ebitda": 110, "ev": 1600},
    ])


def test_negative_net_income_excluded_from_pe():
    res = compute_comparables(_peers())
    assert res.has_data
    # 净利润为负的公司 P/E 应为 None
    ccc_row = res.table[res.table["ticker"] == "CCC"].iloc[0]
    assert ccc_row["p_e"] is None or pd.isna(ccc_row["p_e"])
    # 其它公司 P/E 应该有值
    aaa_row = res.table[res.table["ticker"] == "AAA"].iloc[0]
    assert math.isclose(aaa_row["p_e"], 1000 / 50)


def test_multiples_calculations():
    res = compute_comparables(_peers())
    aaa_row = res.table[res.table["ticker"] == "AAA"].iloc[0]
    assert math.isclose(aaa_row["p_s"], 1000 / 200)
    assert math.isclose(aaa_row["ev_sales"], 1050 / 200)
    assert math.isclose(aaa_row["ev_ebitda"], 1050 / 80)


def test_insufficient_sample_warning():
    res = compute_comparables(_peers().head(2))
    assert any("样本不足" in w for w in res.warnings)


def test_target_implied_per_share():
    target = {
        "revenue": 100.0,
        "net_income": 20.0,
        "ebitda": 30.0,
        "net_debt": 10.0,
        "diluted_shares": 10.0,
    }
    res = compute_comparables(_peers(), target_metrics=target)
    assert "per_share_by_ps" in res.valuation_range
    assert res.valuation_range["per_share_by_ps"]["median"] is not None
    assert res.valuation_range["per_share_by_pe"]["median"] is not None


def test_missing_or_empty_input_does_not_crash():
    res = compute_comparables(None)
    assert not res.has_data
    res = compute_comparables(pd.DataFrame())
    assert not res.has_data
    # 缺少必要列
    res = compute_comparables(pd.DataFrame({"ticker": ["X"], "market_cap": [100]}))
    assert not res.has_data
    assert "缺少列" in res.note
