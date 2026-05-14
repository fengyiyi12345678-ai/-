"""A / B / C / 禁止 等级评定。"""

from __future__ import annotations
from config.settings import (
    BREAKEVEN_RATE, TIER_A_MIN_RATE, TIER_B_MIN_RATE,
    MIN_SAMPLE_FOR_TIER_AB, MIN_SAMPLE_FOR_TIER_C, SMALL_SAMPLE_FLAG,
)


def small_sample_flag(n: int) -> str:
    return "样本不足，不能过度推断" if n < SMALL_SAMPLE_FLAG else ""


def tier_of(n: int, eff_loss_rate: float | None) -> str:
    if eff_loss_rate is None:
        return "数据不足"
    if eff_loss_rate < BREAKEVEN_RATE:
        return "禁止反强队"
    if n >= MIN_SAMPLE_FOR_TIER_AB and eff_loss_rate >= TIER_A_MIN_RATE:
        return "A 级"
    if n >= MIN_SAMPLE_FOR_TIER_AB and TIER_B_MIN_RATE <= eff_loss_rate < TIER_A_MIN_RATE:
        return "B 级"
    if MIN_SAMPLE_FOR_TIER_C <= n < MIN_SAMPLE_FOR_TIER_AB and eff_loss_rate >= TIER_A_MIN_RATE:
        return "C 级（观察）"
    return "未达级"
