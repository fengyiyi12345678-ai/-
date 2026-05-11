"""全局配置：从环境变量读取，不在代码中硬编码任何 API Key。"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLE_DIR = DATA_DIR / "sample"

for _p in (RAW_DIR, PROCESSED_DIR, SAMPLE_DIR):
    _p.mkdir(parents=True, exist_ok=True)

APP_TITLE = os.getenv("APP_TITLE", "Equity Research Copilot")
DEFAULT_MARKET = os.getenv("DEFAULT_MARKET", "US")
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "USD")

PUBLIC_DATA_PROVIDER_URL = os.getenv("PUBLIC_DATA_PROVIDER_URL", "")
PUBLIC_DATA_API_KEY = os.getenv("PUBLIC_DATA_API_KEY", "")

SUPPORTED_MARKETS = ["US", "HK", "CN"]

MISSING_PLACEHOLDER = "N/A"

DISCLAIMER = (
    "本工具仅用于研究分析，所有结果基于用户输入的数据与假设，"
    "不构成任何投资建议。投资有风险，入市需谨慎。"
)

ASSUMPTION_NOTICE = (
    "估值结果对增长率、利润率、WACC 和永续增长率高度敏感，不构成投资建议。"
)
