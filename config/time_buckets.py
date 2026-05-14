"""北京时间黄金档 / 时段桶定义。"""

from __future__ import annotations
from datetime import time

# 重点开球时间点（北京时间）—— 用作精确桶
GOLDEN_KICKOFF_HHMM: list[str] = [
    "20:00", "20:30", "21:00", "21:30", "22:00", "22:30",
    "23:00", "23:30", "00:30", "01:30", "02:30",
    "03:00", "03:30", "04:00", "04:30",
]

# 粗时段桶
def coarse_bucket(t: time) -> str:
    h = t.hour
    if 0 <= h < 6:
        return "凌晨 00-06"
    if 6 <= h < 12:
        return "上午 06-12"
    if 12 <= h < 18:
        return "下午 12-18"
    return "晚间 18-24"


def kickoff_bucket(t: time) -> str:
    """把任意开球时间归到最近的整/半点桶。"""
    minute = 0 if t.minute < 15 else (30 if t.minute < 45 else 0)
    hour = t.hour if t.minute < 45 else (t.hour + 1) % 24
    return f"{hour:02d}:{minute:02d}"


# 让球深度桶（强队视角，负值为让球）
DEPTH_BUCKETS = [
    ("平手 / 受让", lambda d: d >= 0),
    ("让 0.25",   lambda d: -0.375 < d < -0.125),
    ("让 0.5",    lambda d: -0.625 < d <= -0.375),
    ("让 0.75",   lambda d: -0.875 < d <= -0.625),
    ("让 1",      lambda d: -1.125 < d <= -0.875),
    ("让 1.25",   lambda d: -1.375 < d <= -1.125),
    ("让 1.5",    lambda d: -1.625 < d <= -1.375),
    ("让 ≥1.75",  lambda d: d <= -1.625),
]


def depth_bucket(strong_ah_depth: float) -> str:
    for name, pred in DEPTH_BUCKETS:
        if pred(strong_ah_depth):
            return name
    return "未知"
