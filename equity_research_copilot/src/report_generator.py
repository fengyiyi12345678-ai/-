"""Markdown 投研报告生成模块。"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import settings
from src.assumptions import FinancialAssumptions
from src.comparables import ComparablesResult
from src.dcf_model import DCFResult, implied_rating
from src.financial_normalizer import NormalizedFinancials
from src.revenue_cleaner import RevenueBreakdown, find_segment_highlights
from src.utils import MISSING, fmt_money, fmt_number, fmt_pct, is_missing


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html",)),
        keep_trailing_newline=True,
    )


def _scenario_str(res) -> str:
    if isinstance(res, str):
        return res
    fv = res.valuation.get("fair_value_per_share")
    return f"每股 {fmt_number(fv)}（EV={fmt_money(res.valuation.get('enterprise_value'))}）"


def _safety_margin_text(fair_value, current_price) -> str:
    if fair_value is None or current_price is None or current_price <= 0:
        return "暂无（缺少当前股价）"
    upside = (fair_value - current_price) / current_price
    if upside >= 0.15:
        return f"具备一定安全边际（隐含上行空间 {upside:.1%}）"
    if upside <= -0.15:
        return f"估值偏高（隐含下行空间 {upside:.1%}）"
    return f"安全边际有限（隐含上行空间 {upside:.1%}）"


def _top_issues(
    normalized: NormalizedFinancials,
    base_res: DCFResult | None,
    rb: RevenueBreakdown,
    current_price: float | None,
) -> list[str]:
    issues: list[str] = []
    inc = normalized.income
    if not inc.empty and "revenue" in inc.columns:
        s = inc.sort_values("year")["revenue"].pct_change().dropna()
        if not s.empty and s.iloc[-1] < 0.05:
            issues.append(f"**增长问题**：最新年度收入同比仅 {s.iloc[-1]:.1%}，增长动能放缓。")
    if not inc.empty and "operating_margin" in inc.columns:
        s = inc["operating_margin"].dropna()
        if not s.empty and s.iloc[-1] < 0.05:
            issues.append(f"**利润率问题**：最新年度经营利润率 {s.iloc[-1]:.1%}，盈利质量偏弱。")
    cf = normalized.cash_flow
    if not cf.empty and "free_cash_flow" in cf.columns:
        s = cf["free_cash_flow"].dropna()
        if not s.empty and s.iloc[-1] < 0:
            issues.append(f"**现金流问题**：最新年度自由现金流为负（{s.iloc[-1]:,.1f}）。")
    if base_res is not None and current_price is not None and current_price > 0:
        fv = base_res.valuation.get("fair_value_per_share")
        if fv is not None and fv < current_price * 0.8:
            issues.append(f"**估值问题**：DCF 公允价值 {fv:,.2f} 低于当前股价 {current_price:,.2f}。")
    if not rb.is_empty and not rb.share.empty:
        # 单一业务占比过高
        latest_year = rb.share.columns[-1]
        top_share = rb.share[latest_year].dropna().max()
        if top_share is not None and top_share > 0.7:
            issues.append(f"**竞争/集中度问题**：单一业务占比 {top_share:.1%}，业务多元化不足。")
    while len(issues) < 3:
        issues.append("（暂未识别其他显著问题）")
    return issues[:5]


def _format_per_share_range(d: dict | None) -> dict[str, str]:
    if not d:
        return {"low": MISSING, "median": MISSING, "high": MISSING}
    return {
        "low": fmt_number(d.get("low")),
        "median": fmt_number(d.get("median")),
        "high": fmt_number(d.get("high")),
    }


def build_report_context(
    company_name: str,
    ticker: str,
    market: str,
    normalized: NormalizedFinancials,
    history_summary: dict[str, Any],
    assumptions: FinancialAssumptions,
    base_result: DCFResult | None,
    scenarios: dict[str, Any] | None,
    sensitivity_results: dict[str, pd.DataFrame] | None,
    rev_breakdown: RevenueBreakdown,
    comparables_result: ComparablesResult,
    current_price: float | None,
    business_model: str | None,
    data_source_label: str,
    missing_field_warnings: list[str] | None = None,
) -> dict[str, Any]:
    fair_value = base_result.valuation.get("fair_value_per_share") if base_result else None
    fv_str = fmt_number(fair_value) if fair_value is not None else MISSING
    cp_str = fmt_number(current_price) if current_price is not None else MISSING
    rating = implied_rating(fair_value, current_price)

    upside_str = MISSING
    if fair_value is not None and current_price is not None and current_price > 0:
        upside = (fair_value - current_price) / current_price
        upside_str = f"{upside:.1%}"

    history = {
        "revenue_str": fmt_money(history_summary.get("revenue")),
        "gross_margin_str": fmt_pct(history_summary.get("gross_margin")),
        "operating_margin_str": fmt_pct(history_summary.get("operating_margin")),
        "net_margin_str": fmt_pct(history_summary.get("net_margin")),
        "operating_cash_flow_str": fmt_money(history_summary.get("operating_cash_flow")),
        "free_cash_flow_str": fmt_money(history_summary.get("free_cash_flow")),
        "cash_str": fmt_money(history_summary.get("cash")),
        "total_liabilities_str": fmt_money(history_summary.get("total_liabilities")),
        "total_assets_str": fmt_money(history_summary.get("total_assets")),
        "shareholders_equity_str": fmt_money(history_summary.get("shareholders_equity")),
    }

    scenario_strs = {"bull": MISSING, "base": MISSING, "bear": MISSING}
    if scenarios:
        for k, v in scenarios.items():
            scenario_strs[k] = _scenario_str(v)

    growth_series_str = ", ".join(
        f"{g:.2%}" for g in assumptions.aligned_growth()
    )

    segment_highlights = find_segment_highlights(rev_breakdown)
    revenue_note = rev_breakdown.note if rev_breakdown.is_empty else ""

    medians = comparables_result.multiples_median or {}
    medians_str = {
        "p_s": fmt_number(medians.get("p_s")),
        "p_e": fmt_number(medians.get("p_e")),
        "ev_sales": fmt_number(medians.get("ev_sales")),
        "ev_ebitda": fmt_number(medians.get("ev_ebitda")),
    }
    vr = comparables_result.valuation_range or {}
    comp_per_share = {
        "ps": _format_per_share_range(vr.get("per_share_by_ps")),
        "pe": _format_per_share_range(vr.get("per_share_by_pe")),
        "evsales": _format_per_share_range(vr.get("per_share_by_evsales")),
        "evebitda": _format_per_share_range(vr.get("per_share_by_evebitda")),
    }
    if vr:
        # 简短描述
        meds = []
        for k in ("per_share_by_ps", "per_share_by_pe", "per_share_by_evsales", "per_share_by_evebitda"):
            d = vr.get(k)
            if d and d.get("median") is not None:
                meds.append(float(d["median"]))
        if meds:
            comparables_range_text = (
                f"区间 {min(meds):,.2f} ~ {max(meds):,.2f}（每股）"
            )
        else:
            comparables_range_text = MISSING
    else:
        comparables_range_text = comparables_result.note or MISSING

    # 数据缺失提示
    warnings: list[str] = list(missing_field_warnings or [])
    for kind, miss in normalized.missing_fields.items():
        if miss:
            warnings.append(f"{kind} 缺少字段：{', '.join(miss)}")
    warnings.extend(normalized.warnings)
    warnings.extend(comparables_result.warnings)
    if comparables_result.note and not comparables_result.has_data:
        warnings.append(comparables_result.note)

    context = {
        "company_name": company_name or MISSING,
        "ticker": ticker or MISSING,
        "market": market or MISSING,
        "report_date": date.today().isoformat(),
        "current_price_str": cp_str,
        "fair_value_str": fv_str,
        "rating": rating,
        "upside_str": upside_str,
        "disclaimer": settings.DISCLAIMER,
        "safety_margin_text": _safety_margin_text(fair_value, current_price),
        "scenarios": scenario_strs,
        "comparables_range_text": comparables_range_text,
        "business_model": business_model,
        "latest_year": history_summary.get("latest_year", MISSING),
        "history": history,
        "data_warnings": warnings,
        "revenue_note": revenue_note,
        "segment_highlights": segment_highlights,
        "assumptions": assumptions,
        "growth_series_str": growth_series_str,
        "top_issues": _top_issues(normalized, base_result, rev_breakdown, current_price),
        "data_source_label": data_source_label,
        "missing_field_warnings": warnings,
        "comparables_note": comparables_result.note if not comparables_result.has_data else "",
        "medians": medians_str,
        "comp_per_share": comp_per_share,
        # 模板可用的格式化函数
        "pct": fmt_pct,
        "money": fmt_money,
    }
    return context


def generate_markdown_report(context: dict[str, Any]) -> str:
    env = _env()
    tmpl = env.get_template("equity_report.md.j2")
    return tmpl.render(**context)


def save_markdown_report(content: str, ticker: str) -> Path:
    out = settings.PROCESSED_DIR / f"{ticker}_report.md"
    out.write_text(content, encoding="utf-8")
    return out
