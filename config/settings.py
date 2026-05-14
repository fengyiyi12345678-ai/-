"""全局常量。"""

from __future__ import annotations
import pytz

BEIJING = pytz.timezone("Asia/Shanghai")

# 研究主窗口（核心结论必须基于此窗口）
WINDOW_START = "2024-01-01"
WINDOW_END = "2024-12-31"

# 扩展数据参考窗口（可选）
EXT_WINDOW_START = "2023-08-01"
EXT_WINDOW_END = "2024-12-31"

# 阈值
BREAKEVEN_RATE = 0.5405      # 水位 0.85 对应的盈亏平衡线
TIER_A_MIN_RATE = 0.65       # A 级
TIER_B_MIN_RATE = 0.60       # B 级下限
MIN_SAMPLE_FOR_TIER_AB = 10
MIN_SAMPLE_FOR_TIER_C = 5
SMALL_SAMPLE_FLAG = 5        # < 5 必须标注样本不足

# 水位（默认 0.85，可在跟踪表里逐场覆盖）
DEFAULT_PAYOUT_RATE = 0.85

# 同时段窗口（±分钟数，用于判定「同一北京时间段强队数」）
SAME_SLOT_WINDOW_MIN = 15

LEAGUE_CODES = ["EPL", "LaLiga", "Bundesliga", "SerieA", "Ligue1"]
