"""数据获取模块。

提供统一接口，可插拔的数据源：
- PublicDataProvider：尝试从公开数据源获取（仅在配置了 URL 且能访问时才真正调用，
  否则会返回缺失提示，绝不编造数据）
- UploadDataProvider：从用户上传的文件读取
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings
from src import upload_parser


@dataclass
class FetchResult:
    """数据获取结果。"""

    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    missing_fields: list[str] = field(default_factory=list)
    source: str = ""
    notes: list[str] = field(default_factory=list)
    ok: bool = True

    @property
    def is_empty(self) -> bool:
        return self.data is None or self.data.empty


REQUIRED_INCOME_FIELDS = [
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "operating_income",
    "net_income",
]
REQUIRED_BALANCE_FIELDS = [
    "cash",
    "total_debt",
    "total_assets",
    "total_liabilities",
    "shareholders_equity",
    "diluted_shares",
]
REQUIRED_CASHFLOW_FIELDS = ["operating_cash_flow", "capex"]


class FinancialDataProvider(ABC):
    """财务数据获取统一接口。"""

    name: str = "base"

    @abstractmethod
    def fetch_income_statement(self, ticker: str, market: str) -> pd.DataFrame: ...

    @abstractmethod
    def fetch_balance_sheet(self, ticker: str, market: str) -> pd.DataFrame: ...

    @abstractmethod
    def fetch_cash_flow(self, ticker: str, market: str) -> pd.DataFrame: ...

    @abstractmethod
    def fetch_price_data(self, ticker: str, market: str) -> pd.DataFrame: ...

    @abstractmethod
    def fetch_company_profile(self, ticker: str, market: str) -> dict: ...

    # -- 共享逻辑 -----------------------------------------------------------------
    @staticmethod
    def check_missing(df: pd.DataFrame, required: list[str]) -> list[str]:
        if df is None or df.empty:
            return list(required)
        cols = {c.lower() for c in df.columns}
        return [f for f in required if f not in cols]

    def save_raw(self, ticker: str, market: str, kind: str, df: pd.DataFrame) -> Path:
        """把原始数据保存到 data/raw/。"""
        if df is None or df.empty:
            return Path()
        out_dir = settings.RAW_DIR / f"{market}_{ticker}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{kind}.csv"
        try:
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
        except Exception:
            pass
        return out_path


class PublicDataProvider(FinancialDataProvider):
    """公开数据源获取器。

    严格策略：除非显式配置了 PUBLIC_DATA_PROVIDER_URL，并且请求返回真实数据，
    否则一律返回空 DataFrame + missing_fields 提示，而不是编造任何数字。
    """

    name = "public"

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.PUBLIC_DATA_PROVIDER_URL or "").rstrip("/")
        self.api_key = api_key or settings.PUBLIC_DATA_API_KEY or ""

    def _is_configured(self) -> bool:
        return bool(self.base_url)

    def _try_get_json(self, endpoint: str, params: dict[str, Any]) -> dict | None:
        if not self._is_configured():
            return None
        try:
            import urllib.parse
            import urllib.request

            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            if params:
                url += "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url)
            if self.api_key:
                req.add_header("Authorization", f"Bearer {self.api_key}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = resp.read().decode("utf-8")
                return json.loads(payload)
        except Exception:
            return None

    def _empty_with_notes(self, kind: str, required: list[str]) -> pd.DataFrame:
        # 调用方通过 check_missing 来判断缺失字段
        return pd.DataFrame()

    def fetch_income_statement(self, ticker: str, market: str) -> pd.DataFrame:
        payload = self._try_get_json(
            "income_statement", {"ticker": ticker, "market": market}
        )
        df = _payload_to_df(payload)
        if df.empty:
            return self._empty_with_notes("income_statement", REQUIRED_INCOME_FIELDS)
        self.save_raw(ticker, market, "income_statement", df)
        return df

    def fetch_balance_sheet(self, ticker: str, market: str) -> pd.DataFrame:
        payload = self._try_get_json(
            "balance_sheet", {"ticker": ticker, "market": market}
        )
        df = _payload_to_df(payload)
        if df.empty:
            return self._empty_with_notes("balance_sheet", REQUIRED_BALANCE_FIELDS)
        self.save_raw(ticker, market, "balance_sheet", df)
        return df

    def fetch_cash_flow(self, ticker: str, market: str) -> pd.DataFrame:
        payload = self._try_get_json(
            "cash_flow", {"ticker": ticker, "market": market}
        )
        df = _payload_to_df(payload)
        if df.empty:
            return self._empty_with_notes("cash_flow", REQUIRED_CASHFLOW_FIELDS)
        self.save_raw(ticker, market, "cash_flow", df)
        return df

    def fetch_price_data(self, ticker: str, market: str) -> pd.DataFrame:
        payload = self._try_get_json(
            "prices", {"ticker": ticker, "market": market}
        )
        df = _payload_to_df(payload)
        if not df.empty:
            self.save_raw(ticker, market, "prices", df)
        return df

    def fetch_company_profile(self, ticker: str, market: str) -> dict:
        payload = self._try_get_json(
            "profile", {"ticker": ticker, "market": market}
        )
        if isinstance(payload, dict):
            return payload
        return {}


class UploadDataProvider(FinancialDataProvider):
    """从用户上传文件读取数据。"""

    name = "upload"

    def __init__(self, uploaded_files: dict[str, Any] | None = None):
        # 期望的 key：income_statement, balance_sheet, cash_flow,
        # revenue_segments, peer_companies, profile, prices
        self.files = uploaded_files or {}

    def _read(self, key: str) -> pd.DataFrame:
        obj = self.files.get(key)
        if obj is None:
            return pd.DataFrame()
        return upload_parser.read_table(obj)

    def fetch_income_statement(self, ticker: str, market: str) -> pd.DataFrame:
        df = self._read("income_statement")
        if not df.empty:
            self.save_raw(ticker, market, "income_statement", df)
        return df

    def fetch_balance_sheet(self, ticker: str, market: str) -> pd.DataFrame:
        df = self._read("balance_sheet")
        if not df.empty:
            self.save_raw(ticker, market, "balance_sheet", df)
        return df

    def fetch_cash_flow(self, ticker: str, market: str) -> pd.DataFrame:
        df = self._read("cash_flow")
        if not df.empty:
            self.save_raw(ticker, market, "cash_flow", df)
        return df

    def fetch_price_data(self, ticker: str, market: str) -> pd.DataFrame:
        return self._read("prices")

    def fetch_company_profile(self, ticker: str, market: str) -> dict:
        obj = self.files.get("profile")
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        # 可以是一个简单的 csv：key,value
        df = upload_parser.read_table(obj)
        if df.empty:
            return {}
        if {"key", "value"}.issubset({c.lower() for c in df.columns}):
            d: dict[str, Any] = {}
            for _, row in df.iterrows():
                d[str(row["key"])] = row["value"]
            return d
        return {}


def _payload_to_df(payload: Any) -> pd.DataFrame:
    if payload is None:
        return pd.DataFrame()
    if isinstance(payload, list):
        try:
            return pd.DataFrame(payload)
        except Exception:
            return pd.DataFrame()
    if isinstance(payload, dict):
        for key in ("data", "items", "rows", "result"):
            if key in payload and isinstance(payload[key], list):
                try:
                    return pd.DataFrame(payload[key])
                except Exception:
                    return pd.DataFrame()
        try:
            return pd.DataFrame([payload])
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def make_provider(source: str, uploaded_files: dict[str, Any] | None = None) -> FinancialDataProvider:
    if source.lower() == "upload":
        return UploadDataProvider(uploaded_files)
    return PublicDataProvider()
