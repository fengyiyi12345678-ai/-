"""赛季划分：把任意 2024 自然年比赛归到 2023/24 后半段 或 2024/25 前半段。"""

from __future__ import annotations
from datetime import date


# 经验切分（五大联赛 2024 夏歇期普遍 5/26 – 8/15 之间）
SEASON_BOUNDARY_2024 = date(2024, 7, 1)  # 简单口径：7/1 之前算 2023/24，之后算 2024/25


def season_of(d: date) -> str:
    if d < SEASON_BOUNDARY_2024:
        return "2023/24"
    return "2024/25"


def is_h2_2023_24(d: date) -> bool:
    return d < SEASON_BOUNDARY_2024 and d.year == 2024


def is_h1_2024_25(d: date) -> bool:
    return d >= SEASON_BOUNDARY_2024 and d.year == 2024
