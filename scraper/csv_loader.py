"""CSV 兜底入口：把任意符合 schema 的 CSV 读成统一 DataFrame。

期望列（顺序无关，缺列以 NaN 填充）：
  league, season, match_date_local, bj_date, bj_kickoff, home, away,
  score_full, score_half, ah_open, ah_live, ah_final, ah_water_home, ah_water_away,
  ou_final, eu_home, eu_draw, eu_away, source_url

亚盘以主队视角的让球深度（让球为负）。
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path

REQUIRED = [
    "league", "bj_date", "bj_kickoff", "home", "away",
    "score_full", "ah_final", "source_url",
]

OPTIONAL = [
    "season", "match_date_local", "score_half",
    "ah_open", "ah_live", "ah_water_home", "ah_water_away",
    "ou_final", "eu_home", "eu_draw", "eu_away",
]


def load_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"CSV 缺少必需列：{missing}")
    for c in OPTIONAL:
        if c not in df.columns:
            df[c] = pd.NA
    return df
