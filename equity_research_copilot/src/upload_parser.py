"""上传文件解析模块。

支持 CSV / Excel；接受文件路径、Streamlit UploadedFile、bytes、DataFrame。
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_FILES = {
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "revenue_segments",
    "peer_companies",
    "profile",
    "prices",
}


def read_table(obj: Any) -> pd.DataFrame:
    """统一的读表函数。

    obj 可以是：
    - pandas.DataFrame
    - 文件路径字符串 / Path
    - Streamlit UploadedFile（有 .read 和 .name）
    - bytes
    """
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        return obj.copy()
    if isinstance(obj, (str, Path)):
        path = Path(obj)
        if not path.exists():
            return pd.DataFrame()
        suffix = path.suffix.lower()
        try:
            if suffix in (".xlsx", ".xls"):
                return pd.read_excel(path)
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    # Streamlit UploadedFile 风格
    name = getattr(obj, "name", "") or ""
    suffix = Path(str(name)).suffix.lower()
    try:
        if hasattr(obj, "read"):
            content = obj.read()
            if isinstance(content, str):
                content = content.encode("utf-8")
            obj_io: io.BytesIO = io.BytesIO(content)
            if suffix in (".xlsx", ".xls"):
                return pd.read_excel(obj_io)
            return pd.read_csv(obj_io)
        if isinstance(obj, (bytes, bytearray)):
            obj_io = io.BytesIO(bytes(obj))
            try:
                return pd.read_csv(obj_io)
            except Exception:
                obj_io.seek(0)
                return pd.read_excel(obj_io)
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def validate_revenue_segments(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """校验 revenue_segments 列。"""
    required = {"year", "segment", "revenue"}
    cols = {c.lower() for c in df.columns}
    missing = [c for c in required if c not in cols]
    return (len(missing) == 0, missing)


def validate_peer_companies(df: pd.DataFrame) -> tuple[bool, list[str]]:
    required = {"ticker", "market_cap", "revenue", "net_income"}
    cols = {c.lower() for c in df.columns}
    missing = [c for c in required if c not in cols]
    return (len(missing) == 0, missing)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """统一列名为小写下划线。"""
    if df is None or df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df
