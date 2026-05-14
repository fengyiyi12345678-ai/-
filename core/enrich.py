"""比赛级标签富化：
- 当天五大联赛总场次 / 强队比赛总场次
- 同时段（±15min）强队比赛数
- 是否同时段独占强队（即流量集中）
- 同时段是否有英超强队
- 是否强队深盘（已由 normalize 设置）
"""

from __future__ import annotations
from datetime import datetime, timedelta
import pandas as pd

from config.settings import SAME_SLOT_WINDOW_MIN


def _to_dt(d, t: str) -> datetime | None:
    if not isinstance(t, str) or ":" not in t:
        return None
    hh, mm = t.split(":")[:2]
    return datetime.combine(d, datetime.min.time()).replace(hour=int(hh), minute=int(mm))


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_dt"] = out.apply(lambda r: _to_dt(r["bj_date"], r["bj_kickoff"]), axis=1)

    # 当天五大联赛总场次
    day_total = out.groupby("bj_date").size().rename("day_total_top5")
    out = out.merge(day_total, left_on="bj_date", right_index=True, how="left")

    # 当天强队比赛总场次
    day_strong = out[out["contains_strong"]].groupby("bj_date").size().rename("day_total_strong")
    out = out.merge(day_strong, left_on="bj_date", right_index=True, how="left")
    out["day_total_strong"] = out["day_total_strong"].fillna(0).astype(int)

    # 同时段强队比赛数 + 是否同时段有英超强队
    same_slot = []
    epl_in_slot = []
    win = timedelta(minutes=SAME_SLOT_WINDOW_MIN)
    out_idx = out.reset_index(drop=True)
    for i, row in out_idx.iterrows():
        if row["_dt"] is None:
            same_slot.append(None)
            epl_in_slot.append(None)
            continue
        mask = (
            (out_idx["_dt"].notna())
            & (out_idx["bj_date"] == row["bj_date"])
            & (out_idx["contains_strong"])
            & (out_idx["_dt"].between(row["_dt"] - win, row["_dt"] + win))
        )
        slot_df = out_idx[mask]
        same_slot.append(len(slot_df))
        epl_in_slot.append(bool((slot_df["league"] == "EPL").any() and not (
            (row["league"] == "EPL") and len(slot_df) == 1
        )))
    out["same_slot_strong_count"] = same_slot
    out["epl_competing_in_slot"] = epl_in_slot
    out["is_solo_golden_strong"] = out["same_slot_strong_count"] == 1

    return out.drop(columns=["_dt"])
