"""亚盘让球结果计算（站位：强队视角）。

口径（与需求文档一致）：
  设 strong_net = 强队净胜球（主队得分 − 客队得分；若强队为客则取反）
  设 depth     = 强队让球深度（让球为负）
  cover_value  = strong_net + depth
  分类：
    cover_value >  0.25  → 全赢
    cover_value == 0.25  → 半赢
    cover_value ==  0    → 走水
    cover_value == -0.25 → 半输
    cover_value <  -0.25 → 全输

  注：对于半球盘（如 -0.25），是 0/-0.5 的拆盘（两段：一段平手、一段半球），cover_value 落在 0.25 / -0.25 时
  实际投注按半赢/半输（0.5 单位）结算 — 本口径已自洽。
"""

from __future__ import annotations
import math
import pandas as pd


def _strong_net_goals(row) -> int | None:
    hg, ag = row.get("home_goals"), row.get("away_goals")
    if pd.isna(hg) or pd.isna(ag):
        return None
    if row["strong_side"] == "主":
        return int(hg) - int(ag)
    if row["strong_side"] == "客":
        return int(ag) - int(hg)
    return None


def _classify(cover: float) -> str:
    # 用 0.001 容差避免浮点抖动
    if cover > 0.25 + 1e-3:
        return "全赢"
    if abs(cover - 0.25) < 1e-3:
        return "半赢"
    if abs(cover) < 1e-3:
        return "走水"
    if abs(cover + 0.25) < 1e-3:
        return "半输"
    if cover < -0.25 - 1e-3:
        return "全输"
    # 兜底
    return "未知"


def compute_handicap_result(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    def _row(row):
        if row["strong_side"] not in ("主", "客"):
            return (None, None, None)
        net = _strong_net_goals(row)
        depth = row.get("strong_ah_depth")
        if net is None or depth is None or pd.isna(depth):
            return (None, None, None)
        cover = net + depth
        cls = _classify(cover)
        is_lost = cls in ("全输", "半输")
        return (cover, cls, is_lost)

    triples = out.apply(_row, axis=1)
    out["strong_ah_cover_value"] = triples.apply(lambda t: t[0])
    out["strong_ah_result"] = triples.apply(lambda t: t[1])
    out["is_lost_handicap"] = triples.apply(lambda t: t[2])
    return out
