"""财务数据标准化模块。

将不同来源的财报字段映射到统一的字段名，并自动计算关键比率。
保留原始字段映射，以便审计和追溯。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.utils import safe_div, to_numeric


# 列名同义词映射：标准字段 -> 候选列名（小写）
INCOME_ALIASES: dict[str, list[str]] = {
    "year": ["year", "fiscal_year", "fy", "period", "date"],
    "revenue": [
        "revenue",
        "total_revenue",
        "sales",
        "net_sales",
        "营业收入",
        "营业总收入",
    ],
    "cost_of_revenue": [
        "cost_of_revenue",
        "cost_of_sales",
        "cogs",
        "营业成本",
    ],
    "gross_profit": ["gross_profit", "毛利"],
    "operating_income": [
        "operating_income",
        "operating_profit",
        "ebit",
        "营业利润",
    ],
    "net_income": [
        "net_income",
        "net_profit",
        "profit",
        "净利润",
        "归母净利润",
    ],
}

BALANCE_ALIASES: dict[str, list[str]] = {
    "year": ["year", "fiscal_year", "fy", "period", "date"],
    "cash": [
        "cash",
        "cash_and_equivalents",
        "cash_and_short_term_investments",
        "货币资金",
    ],
    "total_debt": [
        "total_debt",
        "short_long_term_debt_total",
        "debt",
        "长期借款+短期借款",
    ],
    "total_assets": ["total_assets", "资产总计"],
    "total_liabilities": ["total_liabilities", "负债合计"],
    "shareholders_equity": [
        "shareholders_equity",
        "total_equity",
        "equity",
        "所有者权益",
        "股东权益",
    ],
    "diluted_shares": [
        "diluted_shares",
        "shares_outstanding",
        "weighted_average_shares_diluted",
        "稀释股本",
        "diluted_shares_outstanding",
    ],
}

CASHFLOW_ALIASES: dict[str, list[str]] = {
    "year": ["year", "fiscal_year", "fy", "period", "date"],
    "operating_cash_flow": [
        "operating_cash_flow",
        "cash_from_operations",
        "cfo",
        "经营活动产生的现金流量净额",
    ],
    "capex": [
        "capex",
        "capital_expenditure",
        "capital_expenditures",
        "投资活动产生的现金流量净额",
    ],
    "depreciation": [
        "depreciation",
        "depreciation_amortization",
        "d_a",
        "折旧与摊销",
    ],
}


@dataclass
class NormalizedFinancials:
    income: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance: pd.DataFrame = field(default_factory=pd.DataFrame)
    cash_flow: pd.DataFrame = field(default_factory=pd.DataFrame)
    combined: pd.DataFrame = field(default_factory=pd.DataFrame)
    field_map: dict[str, dict[str, str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    missing_fields: dict[str, list[str]] = field(default_factory=dict)


def _match_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    cols = {str(c).lower(): c for c in df.columns}
    for a in aliases:
        a_l = a.lower()
        if a_l in cols:
            return cols[a_l]
    return None


def _build_mapping(df: pd.DataFrame, alias_map: dict[str, list[str]]) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    missing: list[str] = []
    for standard, aliases in alias_map.items():
        col = _match_column(df, aliases)
        if col is None:
            missing.append(standard)
        else:
            mapping[standard] = col
    return mapping, missing


def _apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    for std, raw in mapping.items():
        out[std] = df[raw]
    # 保留没用上的原始列，加 raw_ 前缀
    for c in df.columns:
        if c not in mapping.values():
            out[f"raw_{c}"] = df[c]
    return out


def _coerce_numeric(df: pd.DataFrame, except_cols: tuple[str, ...] = ("year",)) -> pd.DataFrame:
    if df.empty:
        return df
    for c in df.columns:
        if c in except_cols or c.startswith("raw_"):
            continue
        df[c] = to_numeric(df[c])
    return df


def normalize_income(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    if df is None or df.empty:
        return pd.DataFrame(), {}, list(INCOME_ALIASES.keys())
    mapping, missing = _build_mapping(df, INCOME_ALIASES)
    out = _apply_mapping(df, mapping)
    out = _coerce_numeric(out)
    # 缺失的毛利可以由 revenue - cost_of_revenue 推导
    if "gross_profit" not in out.columns and "revenue" in out.columns and "cost_of_revenue" in out.columns:
        out["gross_profit"] = out["revenue"] - out["cost_of_revenue"]
        missing = [m for m in missing if m != "gross_profit"]
    # 利润率
    if "revenue" in out.columns:
        if "gross_profit" in out.columns:
            out["gross_margin"] = out.apply(lambda r: safe_div(r.get("gross_profit"), r.get("revenue")), axis=1)
        if "operating_income" in out.columns:
            out["operating_margin"] = out.apply(lambda r: safe_div(r.get("operating_income"), r.get("revenue")), axis=1)
        if "net_income" in out.columns:
            out["net_margin"] = out.apply(lambda r: safe_div(r.get("net_income"), r.get("revenue")), axis=1)
    return out, mapping, missing


def normalize_balance(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    if df is None or df.empty:
        return pd.DataFrame(), {}, list(BALANCE_ALIASES.keys())
    mapping, missing = _build_mapping(df, BALANCE_ALIASES)
    out = _apply_mapping(df, mapping)
    out = _coerce_numeric(out)
    if "total_debt" in out.columns and "cash" in out.columns:
        out["net_debt"] = out["total_debt"] - out["cash"]
    return out, mapping, missing


def normalize_cashflow(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    if df is None or df.empty:
        return pd.DataFrame(), {}, list(CASHFLOW_ALIASES.keys())
    mapping, missing = _build_mapping(df, CASHFLOW_ALIASES)
    out = _apply_mapping(df, mapping)
    out = _coerce_numeric(out)
    if "operating_cash_flow" in out.columns and "capex" in out.columns:
        # capex 通常是负数（投资支出），取其绝对值再减
        out["free_cash_flow"] = out["operating_cash_flow"] - out["capex"].abs()
    return out, mapping, missing


def detect_outliers(income: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    for col in ("gross_margin", "operating_margin", "net_margin"):
        if col in income.columns:
            for _, row in income.iterrows():
                v = row.get(col)
                if v is None or pd.isna(v):
                    continue
                if v > 1 or v < -1:
                    year = row.get("year", "?")
                    warnings.append(f"{year} 年 {col} 异常：{v:.2%}（绝对值超过100%）")
    return warnings


def normalize_all(
    income_df: pd.DataFrame | None,
    balance_df: pd.DataFrame | None,
    cashflow_df: pd.DataFrame | None,
) -> NormalizedFinancials:
    inc, inc_map, inc_missing = normalize_income(income_df if income_df is not None else pd.DataFrame())
    bal, bal_map, bal_missing = normalize_balance(balance_df if balance_df is not None else pd.DataFrame())
    cf, cf_map, cf_missing = normalize_cashflow(cashflow_df if cashflow_df is not None else pd.DataFrame())

    warnings = detect_outliers(inc)

    # 合并到一张表
    combined = pd.DataFrame()
    if not inc.empty:
        combined = inc.copy()
    if not bal.empty and "year" in bal.columns:
        if combined.empty:
            combined = bal.copy()
        else:
            combined = combined.merge(bal, on="year", how="outer", suffixes=("", "_bal"))
    if not cf.empty and "year" in cf.columns:
        if combined.empty:
            combined = cf.copy()
        else:
            combined = combined.merge(cf, on="year", how="outer", suffixes=("", "_cf"))
    if not combined.empty and "year" in combined.columns:
        combined = combined.sort_values("year").reset_index(drop=True)

    return NormalizedFinancials(
        income=inc,
        balance=bal,
        cash_flow=cf,
        combined=combined,
        field_map={
            "income_statement": inc_map,
            "balance_sheet": bal_map,
            "cash_flow": cf_map,
        },
        warnings=warnings,
        missing_fields={
            "income_statement": inc_missing,
            "balance_sheet": bal_missing,
            "cash_flow": cf_missing,
        },
    )


def derive_history_summary(nf: NormalizedFinancials) -> dict[str, Any]:
    """汇总最新一期的关键指标，用作 UI 与报告。"""
    summary: dict[str, Any] = {}
    if nf.income is not None and not nf.income.empty and "year" in nf.income.columns:
        last = nf.income.sort_values("year").iloc[-1]
        summary["latest_year"] = last.get("year")
        for k in ("revenue", "gross_profit", "operating_income", "net_income",
                  "gross_margin", "operating_margin", "net_margin"):
            if k in nf.income.columns:
                summary[k] = last.get(k)
    if nf.cash_flow is not None and not nf.cash_flow.empty:
        last_cf = nf.cash_flow.sort_values("year").iloc[-1] if "year" in nf.cash_flow.columns else nf.cash_flow.iloc[-1]
        for k in ("operating_cash_flow", "capex", "free_cash_flow", "depreciation"):
            if k in nf.cash_flow.columns:
                summary[k] = last_cf.get(k)
    if nf.balance is not None and not nf.balance.empty:
        last_b = nf.balance.sort_values("year").iloc[-1] if "year" in nf.balance.columns else nf.balance.iloc[-1]
        for k in ("cash", "total_debt", "total_assets", "total_liabilities",
                  "shareholders_equity", "diluted_shares", "net_debt"):
            if k in nf.balance.columns:
                summary[k] = last_b.get(k)
    return summary
