"""把抓取的原始数据转成统一 schema 的 DataFrame。

输出 schema（37 列，对应需求文档第四节）：
  league, season, match_date_local, bj_date, bj_kickoff, weekday, is_weekend,
  home, away, contains_strong, strong_name, strong_side, opponent,
  score_full, score_half, home_goals, away_goals, result,
  ah_open, ah_live, ah_final,
  strong_ah_direction, strong_ah_depth, strong_ah_result, is_lost_handicap,
  ou_final, eu_home, eu_draw, eu_away,
  day_total_top5, day_total_strong, same_slot_strong_count,
  is_solo_golden_strong, is_strong_home, is_deep_handicap,
  source_url, note
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Iterable

import pandas as pd

from config.teams import normalize_team_name, is_strong_team, STRONG_TEAMS
from core.season import season_of


WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _parse_score(s: str) -> tuple[int, int]:
    if not isinstance(s, str) or ":" not in s:
        return (None, None)
    a, b = s.split(":", 1)
    try:
        return (int(a), int(b))
    except ValueError:
        return (None, None)


def _result(home_g, away_g):
    if home_g is None or away_g is None:
        return None
    if home_g > away_g:
        return "主胜"
    if home_g < away_g:
        return "客胜"
    return "平局"


def normalize_matches(df: pd.DataFrame) -> pd.DataFrame:
    """把任意来源（nowscore / CSV）的 DataFrame 标准化为分析 schema。"""
    out = df.copy()
    out["home"] = out["home"].apply(normalize_team_name)
    out["away"] = out["away"].apply(normalize_team_name)

    out["bj_date"] = pd.to_datetime(out["bj_date"]).dt.date
    out["season"] = out["bj_date"].apply(season_of)
    out["weekday"] = out["bj_date"].apply(lambda d: WEEKDAY_CN[d.weekday()])
    out["is_weekend"] = out["weekday"].isin(["周六", "周日"])

    scores = out["score_full"].apply(_parse_score)
    out["home_goals"] = scores.apply(lambda x: x[0])
    out["away_goals"] = scores.apply(lambda x: x[1])
    out["result"] = out.apply(lambda r: _result(r["home_goals"], r["away_goals"]), axis=1)

    home_strong = out["home"].isin(STRONG_TEAMS)
    away_strong = out["away"].isin(STRONG_TEAMS)
    out["contains_strong"] = home_strong | away_strong
    out["strong_name"] = out.apply(
        lambda r: r["home"] if r["home"] in STRONG_TEAMS else (r["away"] if r["away"] in STRONG_TEAMS else None),
        axis=1,
    )
    out["strong_side"] = out.apply(
        lambda r: "主" if r["home"] in STRONG_TEAMS else ("客" if r["away"] in STRONG_TEAMS else None),
        axis=1,
    )
    out["opponent"] = out.apply(
        lambda r: r["away"] if r["strong_side"] == "主" else (r["home"] if r["strong_side"] == "客" else None),
        axis=1,
    )
    out["is_strong_home"] = out["strong_side"] == "主"

    # 注意：ah_final 是站点视角 = 主队让球深度（让=负）。
    # 强队让球深度从「强队角度」推导：
    #   若强队=主：strong_ah_depth = ah_final
    #   若强队=客：strong_ah_depth = -ah_final
    def _strong_depth(row):
        if pd.isna(row.get("ah_final")):
            return None
        if row["strong_side"] == "主":
            return float(row["ah_final"])
        if row["strong_side"] == "客":
            return -float(row["ah_final"])
        return None

    out["strong_ah_depth"] = out.apply(_strong_depth, axis=1)
    out["strong_ah_direction"] = out["strong_ah_depth"].apply(
        lambda d: None if d is None or pd.isna(d) else ("让球" if d < 0 else ("受让" if d > 0 else "平手"))
    )
    out["is_deep_handicap"] = out["strong_ah_depth"].apply(lambda d: (d is not None) and (d <= -1.0))

    out["note"] = ""
    out.loc[out["ah_final"].isna(), "note"] = "盘口缺失（不计入输盘率分母）"

    return out
