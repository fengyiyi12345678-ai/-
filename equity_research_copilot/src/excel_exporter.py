"""Excel 导出模块。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from config import settings
from src.assumptions import FinancialAssumptions
from src.dcf_model import DCFResult


PCT_COLUMNS = {
    "revenue_growth",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "tax_rate",
    "wacc",
    "terminal_growth_rate",
    "depreciation_pct_revenue",
    "capex_pct_revenue",
    "nwc_pct_revenue",
    "share",
    "discount_factor",
}


def _write_sheet(writer, name: str, df: pd.DataFrame | None) -> None:
    name = name[:31]  # Excel sheet 名长度上限
    if df is None or df.empty:
        pd.DataFrame({"info": ["暂无数据 / N/A"]}).to_excel(writer, sheet_name=name, index=False)
        return
    out = df.copy()
    if out.index.name or not isinstance(out.index, pd.RangeIndex):
        out = out.reset_index()
    out.to_excel(writer, sheet_name=name, index=False)
    _format_sheet(writer, name, out)


def _format_sheet(writer, sheet_name: str, df: pd.DataFrame) -> None:
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": "#1F2937",
        "font_color": "white",
        "border": 1,
        "align": "center",
        "valign": "vcenter",
    })
    money_fmt = workbook.add_format({"num_format": "#,##0.00"})
    pct_fmt = workbook.add_format({"num_format": "0.00%"})

    for col_idx, col in enumerate(df.columns):
        worksheet.write(0, col_idx, str(col), header_fmt)
        max_len = max(
            [len(str(col))]
            + [len(str(v)) for v in df[col].astype(str).head(50).tolist()]
        )
        worksheet.set_column(col_idx, col_idx, min(max_len + 4, 30))
        if str(col).lower() in PCT_COLUMNS or "_pct_" in str(col).lower() or str(col).lower().endswith("_margin"):
            worksheet.set_column(col_idx, col_idx, min(max_len + 4, 18), pct_fmt)
        else:
            # 数值列
            if pd.api.types.is_numeric_dtype(df[col]):
                worksheet.set_column(col_idx, col_idx, min(max_len + 4, 22), money_fmt)


def assumptions_to_df(a: FinancialAssumptions) -> pd.DataFrame:
    rows = [
        ("forecast_years", a.forecast_years),
        ("revenue_growth_rates", ", ".join(f"{g:.4f}" for g in a.aligned_growth())),
        ("gross_margin", a.gross_margin),
        ("operating_margin", a.operating_margin),
        ("tax_rate", a.tax_rate),
        ("depreciation_pct_revenue", a.depreciation_pct_revenue),
        ("capex_pct_revenue", a.capex_pct_revenue),
        ("nwc_pct_revenue", a.nwc_pct_revenue),
        ("wacc", a.wacc),
        ("terminal_growth_rate", a.terminal_growth_rate),
        ("net_debt", a.net_debt),
        ("diluted_shares", a.diluted_shares),
    ]
    return pd.DataFrame(rows, columns=["assumption", "value"])


def valuation_to_df(res: DCFResult | None) -> pd.DataFrame:
    if res is None:
        return pd.DataFrame()
    return pd.DataFrame(list(res.valuation.items()), columns=["metric", "value"])


def export_workbook(
    ticker: str,
    raw_income: pd.DataFrame | None,
    raw_balance: pd.DataFrame | None,
    raw_cashflow: pd.DataFrame | None,
    normalized_combined: pd.DataFrame | None,
    revenue_segments: pd.DataFrame | None,
    assumptions: FinancialAssumptions,
    dcf_result: DCFResult | None,
    sens_wacc_term: pd.DataFrame | None,
    sens_growth_margin: pd.DataFrame | None,
    comparables_table: pd.DataFrame | None,
) -> Path:
    out_path = settings.PROCESSED_DIR / f"{ticker}_model.xlsx"
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        _write_sheet(writer, "Raw_Income_Statement", raw_income)
        _write_sheet(writer, "Raw_Balance_Sheet", raw_balance)
        _write_sheet(writer, "Raw_Cash_Flow", raw_cashflow)
        _write_sheet(writer, "Normalized_Financials", normalized_combined)
        _write_sheet(writer, "Revenue_Segments", revenue_segments)
        _write_sheet(writer, "Assumptions", assumptions_to_df(assumptions))
        _write_sheet(writer, "DCF_Forecast", dcf_result.forecast if dcf_result else None)
        _write_sheet(writer, "Sensitivity_WACC_TermG", sens_wacc_term)
        _write_sheet(writer, "Sensitivity_Growth_Margin", sens_growth_margin)
        _write_sheet(writer, "Comparables", comparables_table)
        _write_sheet(writer, "Valuation_Summary", valuation_to_df(dcf_result))
    return out_path
