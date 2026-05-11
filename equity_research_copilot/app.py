"""Equity Research Copilot - Streamlit 主入口。

运行方式:
    streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from src import (  # noqa: E402
    assumptions as assumptions_mod,
    comparables as comparables_mod,
    data_provider as dp_mod,
    dcf_model as dcf_mod,
    excel_exporter,
    financial_normalizer as norm_mod,
    report_generator,
    revenue_cleaner,
    sensitivity as sens_mod,
    upload_parser,
)
from src.utils import MISSING, fmt_money, fmt_number, fmt_pct, is_missing  # noqa: E402


st.set_page_config(
    page_title=settings.APP_TITLE,
    page_icon=":bar_chart:",
    layout="wide",
)


# ---------- Sidebar -----------------------------------------------------------
def render_sidebar() -> dict:
    st.sidebar.title(settings.APP_TITLE)
    st.sidebar.caption("本地运行的中文投研建模工具")

    ticker = st.sidebar.text_input("股票代码", value="DEMO")
    market = st.sidebar.selectbox(
        "市场", options=settings.SUPPORTED_MARKETS,
        index=settings.SUPPORTED_MARKETS.index(settings.DEFAULT_MARKET)
        if settings.DEFAULT_MARKET in settings.SUPPORTED_MARKETS else 0,
    )
    source = st.sidebar.radio("数据来源", options=["Upload", "Public"], index=0,
                              help="Upload：上传 Excel / CSV；Public：尝试公开数据源（需在 .env 配置）")
    current_price = st.sidebar.number_input(
        "当前股价（用于评级）", min_value=0.0, value=0.0, step=0.01,
        help="如不填则不输出投资评级"
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("上传财报数据")
    income_file = st.sidebar.file_uploader("利润表 (CSV/XLSX)", type=["csv", "xlsx", "xls"], key="inc")
    balance_file = st.sidebar.file_uploader("资产负债表 (CSV/XLSX)", type=["csv", "xlsx", "xls"], key="bal")
    cash_file = st.sidebar.file_uploader("现金流量表 (CSV/XLSX)", type=["csv", "xlsx", "xls"], key="cf")
    seg_file = st.sidebar.file_uploader("收入分部表 (CSV/XLSX)", type=["csv", "xlsx", "xls"], key="seg")
    peers_file = st.sidebar.file_uploader("可比公司表 (CSV/XLSX)", type=["csv", "xlsx", "xls"], key="peers")

    st.sidebar.markdown("---")
    business_model = st.sidebar.text_area("公司商业模式描述（可选）", value="", height=120)

    generate = st.sidebar.button("生成模型", type="primary", use_container_width=True)
    export_excel = st.sidebar.button("导出 Excel", use_container_width=True)
    export_md = st.sidebar.button("导出 Markdown 报告", use_container_width=True)

    return {
        "ticker": ticker.strip().upper() or "DEMO",
        "market": market,
        "source": source.lower(),
        "current_price": current_price if current_price > 0 else None,
        "income_file": income_file,
        "balance_file": balance_file,
        "cash_file": cash_file,
        "seg_file": seg_file,
        "peers_file": peers_file,
        "business_model": business_model.strip(),
        "generate": generate,
        "export_excel": export_excel,
        "export_md": export_md,
    }


# ---------- 数据加载 ----------------------------------------------------------
def load_data(cfg: dict) -> dict:
    files = {
        "income_statement": cfg["income_file"],
        "balance_sheet": cfg["balance_file"],
        "cash_flow": cfg["cash_file"],
    }
    provider = dp_mod.make_provider(cfg["source"], uploaded_files=files)

    inc = provider.fetch_income_statement(cfg["ticker"], cfg["market"])
    bal = provider.fetch_balance_sheet(cfg["ticker"], cfg["market"])
    cf = provider.fetch_cash_flow(cfg["ticker"], cfg["market"])
    profile = provider.fetch_company_profile(cfg["ticker"], cfg["market"])

    inc_missing = dp_mod.FinancialDataProvider.check_missing(inc, dp_mod.REQUIRED_INCOME_FIELDS)
    bal_missing = dp_mod.FinancialDataProvider.check_missing(bal, dp_mod.REQUIRED_BALANCE_FIELDS)
    cf_missing = dp_mod.FinancialDataProvider.check_missing(cf, dp_mod.REQUIRED_CASHFLOW_FIELDS)

    rev_seg = upload_parser.read_table(cfg["seg_file"]) if cfg["seg_file"] is not None else pd.DataFrame()
    peers = upload_parser.read_table(cfg["peers_file"]) if cfg["peers_file"] is not None else pd.DataFrame()

    return {
        "provider": provider,
        "income": inc,
        "balance": bal,
        "cash_flow": cf,
        "profile": profile,
        "missing": {"income": inc_missing, "balance": bal_missing, "cash_flow": cf_missing},
        "revenue_segments": rev_seg,
        "peers": peers,
    }


# ---------- 主面板 ------------------------------------------------------------
def render_company_overview(cfg, data, normalized):
    st.subheader("公司概览")
    profile = data.get("profile") or {}
    cols = st.columns(4)
    cols[0].metric("代码", cfg["ticker"])
    cols[1].metric("市场", cfg["market"])
    cols[2].metric("数据来源", cfg["source"].upper())
    cols[3].metric("当前股价", fmt_number(cfg["current_price"]) if cfg["current_price"] else MISSING)

    if profile:
        st.write("**公司资料：**")
        st.json(profile, expanded=False)
    elif cfg["business_model"]:
        st.write("**用户提供的商业模式描述：**")
        st.info(cfg["business_model"])
    else:
        st.warning("暂无公司资料，可在左侧填写商业模式描述。")


def render_financials(data, normalized):
    st.subheader("财报数据（标准化后）")
    miss = data.get("missing", {})
    for k, v in miss.items():
        if v:
            st.warning(f"{k} 缺少字段：{', '.join(v)}（缺失字段将以 N/A 处理，不影响其他模块）")
    for w in normalized.warnings:
        st.error(w)

    tabs = st.tabs(["利润表", "资产负债表", "现金流量表", "合并视图"])
    with tabs[0]:
        if normalized.income.empty:
            st.warning("未提供利润表数据。")
        else:
            st.dataframe(normalized.income, use_container_width=True)
            if "revenue" in normalized.income.columns and "year" in normalized.income.columns:
                fig = px.line(normalized.income.sort_values("year"), x="year", y="revenue",
                              markers=True, title="历史收入")
                st.plotly_chart(fig, use_container_width=True)
    with tabs[1]:
        if normalized.balance.empty:
            st.warning("未提供资产负债表数据。")
        else:
            st.dataframe(normalized.balance, use_container_width=True)
    with tabs[2]:
        if normalized.cash_flow.empty:
            st.warning("未提供现金流量表数据。")
        else:
            st.dataframe(normalized.cash_flow, use_container_width=True)
            if "free_cash_flow" in normalized.cash_flow.columns and "year" in normalized.cash_flow.columns:
                fig = px.bar(normalized.cash_flow.sort_values("year"), x="year", y="free_cash_flow",
                             title="自由现金流")
                st.plotly_chart(fig, use_container_width=True)
    with tabs[3]:
        if normalized.combined.empty:
            st.warning("无合并视图。")
        else:
            st.dataframe(normalized.combined, use_container_width=True)


def render_revenue(rev: revenue_cleaner.RevenueBreakdown):
    st.subheader("收入结构")
    if rev.is_empty:
        st.warning(rev.note or "暂无分部收入数据")
        return
    st.write("**分部收入明细：**")
    st.dataframe(rev.by_segment_year, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        if not rev.share.empty:
            share_long = rev.share.reset_index().melt(id_vars="segment", var_name="year", value_name="share")
            fig = px.bar(share_long, x="year", y="share", color="segment",
                         title="各业务收入占比", barmode="stack")
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        if not rev.growth.empty:
            growth_long = rev.growth.reset_index().melt(id_vars="segment", var_name="year", value_name="growth")
            growth_long = growth_long.dropna()
            if not growth_long.empty:
                fig = px.line(growth_long, x="year", y="growth", color="segment",
                              markers=True, title="各业务收入增速")
                fig.update_yaxes(tickformat=".0%")
                st.plotly_chart(fig, use_container_width=True)
    if not rev.gross_margin.empty:
        margin_long = rev.gross_margin.reset_index().melt(id_vars="segment", var_name="year", value_name="gross_margin")
        margin_long = margin_long.dropna()
        if not margin_long.empty:
            fig = px.line(margin_long, x="year", y="gross_margin", color="segment",
                          markers=True, title="各业务毛利率")
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)


def render_assumptions(a: assumptions_mod.FinancialAssumptions) -> assumptions_mod.FinancialAssumptions:
    st.subheader("假设设置")
    st.info(settings.ASSUMPTION_NOTICE)

    c1, c2, c3 = st.columns(3)
    with c1:
        years = st.number_input("预测年数", 1, 10, value=int(a.forecast_years))
        gross = st.number_input("毛利率", 0.0, 1.0, value=float(a.gross_margin), step=0.01, format="%.4f")
        op = st.number_input("经营利润率", -1.0, 1.0, value=float(a.operating_margin), step=0.01, format="%.4f")
        tax = st.number_input("税率", 0.0, 1.0, value=float(a.tax_rate), step=0.01, format="%.4f")
    with c2:
        dep = st.number_input("折旧/收入", 0.0, 1.0, value=float(a.depreciation_pct_revenue), step=0.005, format="%.4f")
        capex = st.number_input("Capex/收入", 0.0, 1.0, value=float(a.capex_pct_revenue), step=0.005, format="%.4f")
        nwc = st.number_input("NWC/收入", -1.0, 1.0, value=float(a.nwc_pct_revenue), step=0.005, format="%.4f")
    with c3:
        wacc = st.number_input("WACC", 0.0, 1.0, value=float(a.wacc), step=0.005, format="%.4f")
        tg = st.number_input("永续增长率", -0.05, 0.10, value=float(a.terminal_growth_rate), step=0.0025, format="%.4f")
        net_debt = st.number_input("净负债（百万）", value=float(a.net_debt), step=10.0, format="%.2f")
        shares = st.number_input("稀释股本（百万股）", 0.0001, 1e9, value=float(a.diluted_shares), step=1.0, format="%.4f")

    # 增速序列
    st.write("**未来收入增速（每年，单位：小数）：**")
    growths_default = a.aligned_growth()[:years] + [a.aligned_growth()[-1]] * max(0, years - len(a.aligned_growth()))
    cols = st.columns(int(years))
    growths: list[float] = []
    for i, c in enumerate(cols):
        with c:
            growths.append(
                st.number_input(f"Y{i+1}", -1.0, 5.0, value=float(growths_default[i]), step=0.01, format="%.4f", key=f"g_{i}")
            )

    return assumptions_mod.FinancialAssumptions(
        forecast_years=int(years),
        revenue_growth_rates=growths,
        gross_margin=float(gross),
        operating_margin=float(op),
        tax_rate=float(tax),
        depreciation_pct_revenue=float(dep),
        capex_pct_revenue=float(capex),
        nwc_pct_revenue=float(nwc),
        wacc=float(wacc),
        terminal_growth_rate=float(tg),
        net_debt=float(net_debt),
        diluted_shares=float(shares),
    )


def render_dcf(a, base_revenue):
    st.subheader("DCF 估值")
    try:
        res = dcf_mod.run_dcf(a, base_revenue)
    except ValueError as e:
        st.error(f"估值失败：{e}")
        return None
    v = res.valuation
    c = st.columns(4)
    c[0].metric("每股公允价值", fmt_number(v["fair_value_per_share"]))
    c[1].metric("企业价值（百万）", fmt_number(v["enterprise_value"]))
    c[2].metric("PV(FCF) 合计", fmt_number(v["sum_pv_fcf"]))
    c[3].metric("PV(终值)", fmt_number(v["pv_terminal"]))

    st.write("**未来 5 年财务预测：**")
    st.dataframe(res.forecast, use_container_width=True)

    fig = px.bar(res.forecast, x="year_index", y="free_cash_flow", title="预测自由现金流（百万）")
    st.plotly_chart(fig, use_container_width=True)
    return res


def render_scenarios(a, base_revenue):
    st.subheader("Bull / Base / Bear 三情景估值")
    scenarios = assumptions_mod.scenario_assumptions(a)
    rows = []
    for name, sa in scenarios.items():
        try:
            r = dcf_mod.run_dcf(sa, base_revenue)
            rows.append({
                "情景": name,
                "收入增速(均)": float(sum(sa.aligned_growth()) / len(sa.aligned_growth())),
                "经营利润率": sa.operating_margin,
                "永续增长率": sa.terminal_growth_rate,
                "每股公允价值": r.valuation["fair_value_per_share"],
                "EV": r.valuation["enterprise_value"],
            })
        except Exception as e:
            rows.append({"情景": name, "每股公允价值": None, "EV": None, "error": str(e)})
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    return scenarios


def render_sensitivity(a, base_revenue):
    st.subheader("敏感性分析")
    try:
        m1 = sens_mod.sensitivity_wacc_terminal(a, base_revenue)
        st.write("**每股公允价值 — WACC × 永续增长率：**")
        st.dataframe(m1.style.background_gradient(cmap="RdYlGn", axis=None).format("{:,.2f}"),
                     use_container_width=True)
    except Exception as e:
        st.error(f"WACC × 永续增长率敏感性失败：{e}")
        m1 = pd.DataFrame()
    try:
        m2 = sens_mod.sensitivity_growth_margin(a, base_revenue)
        st.write("**每股公允价值 — 收入增速 × 经营利润率：**")
        st.dataframe(m2.style.background_gradient(cmap="RdYlGn", axis=None).format("{:,.2f}"),
                     use_container_width=True)
    except Exception as e:
        st.error(f"增速 × 利润率敏感性失败：{e}")
        m2 = pd.DataFrame()
    return m1, m2


def render_comparables(peers_df, target_metrics):
    st.subheader("可比公司估值")
    if peers_df is None or peers_df.empty:
        st.warning("未上传可比公司数据。")
        return comparables_mod.ComparablesResult(note="未上传可比公司数据")
    res = comparables_mod.compute_comparables(peers_df, target_metrics)
    if not res.has_data:
        st.warning(res.note)
        return res
    for w in res.warnings:
        st.warning(w)

    st.dataframe(res.table, use_container_width=True)
    st.write("**中位数估值倍数：**")
    medians_df = pd.DataFrame(list(res.multiples_median.items()), columns=["multiple", "median"])
    st.dataframe(medians_df, use_container_width=True)
    if res.valuation_range:
        st.write("**目标公司每股估值区间（基于可比中位数）：**")
        rows = []
        for k, d in res.valuation_range.items():
            rows.append({"倍数": k, "低位": d.get("low"), "中位": d.get("median"), "高位": d.get("high")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    return res


def render_conclusion(cfg, base_res, comp_res):
    st.subheader("投资结论")
    fv = base_res.valuation["fair_value_per_share"] if base_res else None
    cp = cfg["current_price"]
    rating = dcf_mod.implied_rating(fv, cp)
    c = st.columns(4)
    c[0].metric("当前股价", fmt_number(cp) if cp else MISSING)
    c[1].metric("DCF 公允价值", fmt_number(fv) if fv else MISSING)
    if fv and cp:
        c[2].metric("隐含上行空间", f"{(fv - cp) / cp:.1%}")
    else:
        c[2].metric("隐含上行空间", MISSING)
    c[3].metric("初步评级", rating)
    if rating == "暂无评级":
        st.info("缺少当前股价或公允价值，无法给出评级。")


def render_risks(normalized, comp_res):
    st.subheader("风险提示")
    st.markdown("- **数据源风险**：数据来自用户上传或公开接口，可能存在缺失或口径差异。")
    st.markdown("- **财务预测风险**：所有预测均为线性外推，未来实际业绩可能偏离。")
    st.markdown("- **估值假设风险**：WACC、永续增长率、利润率小幅变化都会显著改变估值。")
    st.markdown("- **行业竞争与监管风险**：未在模型内显式建模，需结合定性研究。")
    st.markdown("- **宏观与利率风险**：利率上行将提升 WACC，并直接压制 DCF 估值。")
    miss_flat = []
    for k, v in normalized.missing_fields.items():
        if v:
            miss_flat.append(f"{k}: {', '.join(v)}")
    if miss_flat:
        st.warning("**数据缺失提示：**\n\n" + "\n".join(f"- {m}" for m in miss_flat))


# ---------- 主流程 ------------------------------------------------------------
def main() -> None:
    cfg = render_sidebar()

    # 始终加载数据（即使没点生成按钮，也展示已有上传内容）
    data = load_data(cfg)
    normalized = norm_mod.normalize_all(data["income"], data["balance"], data["cash_flow"])
    history = norm_mod.derive_history_summary(normalized)
    rev = revenue_cleaner.clean_revenue_segments(data["revenue_segments"])

    # 默认假设
    if "assumptions" not in st.session_state or cfg["generate"]:
        st.session_state["assumptions"] = assumptions_mod.assumptions_from_history(history, normalized)

    tabs = st.tabs([
        "公司概览", "财报数据", "收入结构", "假设设置", "DCF估值",
        "敏感性分析", "可比公司估值", "投资结论", "风险提示",
    ])
    with tabs[0]:
        render_company_overview(cfg, data, normalized)
    with tabs[1]:
        render_financials(data, normalized)
    with tabs[2]:
        render_revenue(rev)
    with tabs[3]:
        st.session_state["assumptions"] = render_assumptions(st.session_state["assumptions"])

    a = st.session_state["assumptions"]
    base_revenue = history.get("revenue")
    if base_revenue is None or (isinstance(base_revenue, float) and base_revenue != base_revenue) or base_revenue <= 0:
        with tabs[4]:
            st.error("无法运行 DCF：缺少最新一期收入数据，请上传利润表。")
        base_res = None
        scenarios = None
        sens1 = pd.DataFrame()
        sens2 = pd.DataFrame()
    else:
        with tabs[4]:
            base_res = render_dcf(a, float(base_revenue))
            scenarios = render_scenarios(a, float(base_revenue))
        with tabs[5]:
            sens1, sens2 = render_sensitivity(a, float(base_revenue))

    target_metrics = {
        "revenue": history.get("revenue"),
        "net_income": history.get("net_income"),
        "ebitda": (history.get("operating_income") or 0) + (history.get("depreciation") or 0)
        if history.get("operating_income") is not None else None,
        "net_debt": history.get("net_debt") or 0.0,
        "diluted_shares": history.get("diluted_shares") or a.diluted_shares,
    }
    with tabs[6]:
        comp_res = render_comparables(data["peers"], target_metrics)
    with tabs[7]:
        render_conclusion(cfg, base_res, comp_res)
    with tabs[8]:
        render_risks(normalized, comp_res)

    # ---------- 导出 ----------
    if cfg["export_excel"]:
        try:
            out = excel_exporter.export_workbook(
                ticker=cfg["ticker"],
                raw_income=data["income"],
                raw_balance=data["balance"],
                raw_cashflow=data["cash_flow"],
                normalized_combined=normalized.combined,
                revenue_segments=data["revenue_segments"],
                assumptions=a,
                dcf_result=base_res,
                sens_wacc_term=sens1 if isinstance(sens1, pd.DataFrame) else pd.DataFrame(),
                sens_growth_margin=sens2 if isinstance(sens2, pd.DataFrame) else pd.DataFrame(),
                comparables_table=comp_res.table if comp_res.has_data else pd.DataFrame(),
            )
            st.sidebar.success(f"Excel 已导出：{out}")
            with open(out, "rb") as f:
                st.sidebar.download_button("下载 Excel", data=f.read(),
                                           file_name=out.name,
                                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception as e:
            st.sidebar.error(f"导出 Excel 失败：{e}")

    if cfg["export_md"]:
        try:
            ctx = report_generator.build_report_context(
                company_name=(data.get("profile") or {}).get("company_name") or cfg["ticker"],
                ticker=cfg["ticker"],
                market=cfg["market"],
                normalized=normalized,
                history_summary=history,
                assumptions=a,
                base_result=base_res,
                scenarios=scenarios,
                sensitivity_results={"wacc_term": sens1, "growth_margin": sens2},
                rev_breakdown=rev,
                comparables_result=comp_res,
                current_price=cfg["current_price"],
                business_model=cfg["business_model"],
                data_source_label="用户上传文件" if cfg["source"] == "upload" else "公开数据接口",
            )
            md = report_generator.generate_markdown_report(ctx)
            out = report_generator.save_markdown_report(md, cfg["ticker"])
            st.sidebar.success(f"报告已导出：{out}")
            st.sidebar.download_button("下载 Markdown 报告", data=md.encode("utf-8"),
                                       file_name=out.name, mime="text/markdown")
        except Exception as e:
            st.sidebar.error(f"导出报告失败：{e}")

    st.caption(settings.DISCLAIMER)


if __name__ == "__main__":
    main()
