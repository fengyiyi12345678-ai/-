"""把已富化、已计算盘口结果的 DataFrame 切成 21 个分析 Sheet。

每个 Sheet 返回一个 DataFrame。汇总入口：build_all_sheets(df) -> dict[str, DataFrame]
"""

from __future__ import annotations

import pandas as pd

from config.settings import LEAGUE_CODES
from config.time_buckets import GOLDEN_KICKOFF_HHMM, coarse_bucket, kickoff_bucket, depth_bucket
from analysis.thresholds import tier_of, small_sample_flag


# ---------- 通用：把强队盘口子集汇总成一行 ----------

def _summary_row(sub: pd.DataFrame, label: str) -> dict:
    sub = sub[sub["strong_ah_result"].notna()]
    n_all = len(sub)
    n_push = int((sub["strong_ah_result"] == "走水").sum())
    n_full_loss = int((sub["strong_ah_result"] == "全输").sum())
    n_half_loss = int((sub["strong_ah_result"] == "半输").sum())
    n_full_win = int((sub["strong_ah_result"] == "全赢").sum())
    n_half_win = int((sub["strong_ah_result"] == "半赢").sum())
    denom = n_all - n_push
    eff = (n_full_loss + 0.5 * n_half_loss) / denom if denom > 0 else None
    rough = (n_full_loss + n_half_loss) / denom if denom > 0 else None
    return {
        "维度": label,
        "样本数": n_all,
        "全赢": n_full_win, "半赢": n_half_win, "走水": n_push,
        "半输": n_half_loss, "全输": n_full_loss,
        "有效输盘率": round(eff, 4) if eff is not None else None,
        "粗略输盘率": round(rough, 4) if rough is not None else None,
        ">54.05%": "是" if (eff is not None and eff > 0.5405) else "否",
        ">60%": "是" if (eff is not None and eff >= 0.60) else "否",
        ">65%": "是" if (eff is not None and eff >= 0.65) else "否",
        "等级": tier_of(n_all, eff),
        "样本提醒": small_sample_flag(n_all),
    }


# ---------- Sheet 构造 ----------

def s1_raw_matches(df: pd.DataFrame) -> pd.DataFrame:
    return df.copy()


def s2_strong_matches(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["contains_strong"]].copy()


def s3_strong_handicap_detail(df: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "league", "season", "bj_date", "bj_kickoff", "weekday", "is_weekend",
        "home", "away", "strong_name", "strong_side", "opponent",
        "score_full", "score_half", "result",
        "ah_open", "ah_live", "ah_final", "strong_ah_direction", "strong_ah_depth",
        "strong_ah_cover_value", "strong_ah_result", "is_lost_handicap",
        "ou_final", "eu_home", "eu_draw", "eu_away",
        "day_total_top5", "day_total_strong", "same_slot_strong_count",
        "is_solo_golden_strong", "epl_competing_in_slot", "is_strong_home", "is_deep_handicap",
        "source_url", "note",
    ]
    return df[df["contains_strong"]][[c for c in keep if c in df.columns]].copy()


def s4_overall_loss_ranking(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]]
    rows = [_summary_row(sub, "总体")]
    return pd.DataFrame(rows)


def s5_by_league(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for lg in LEAGUE_CODES:
        rows.append(_summary_row(df[df["league"] == lg], lg))
    rows.append(_summary_row(df[df["contains_strong"]], "总计"))
    return pd.DataFrame(rows)


def s6_by_team(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]]
    rows = []
    for team, g in sub.groupby("strong_name"):
        if not team:
            continue
        rows.append(_summary_row(g, team))
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["有效输盘率"], ascending=False, na_position="last")
    return out


def s7_by_kickoff(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]].copy()
    sub["kickoff_bucket"] = sub["bj_kickoff"].apply(
        lambda s: kickoff_bucket(_t(s)) if _t(s) else None
    )
    rows = []
    for k in GOLDEN_KICKOFF_HHMM:
        rows.append(_summary_row(sub[sub["kickoff_bucket"] == k], k))
    return pd.DataFrame(rows)


def s8_by_coarse(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]].copy()
    sub["coarse_bucket"] = sub["bj_kickoff"].apply(
        lambda s: coarse_bucket(_t(s)) if _t(s) else None
    )
    rows = []
    for b in ["凌晨 00-06", "上午 06-12", "下午 12-18", "晚间 18-24"]:
        rows.append(_summary_row(sub[sub["coarse_bucket"] == b], b))
    # 加：周末晚间 vs 非周末晚间
    night = sub[sub["coarse_bucket"] == "晚间 18-24"]
    rows.append(_summary_row(night[night["is_weekend"]], "周末晚间"))
    rows.append(_summary_row(night[~night["is_weekend"]], "工作日晚间"))
    rows.append(_summary_row(sub[sub["coarse_bucket"] == "凌晨 00-06"], "凌晨（对比）"))
    return pd.DataFrame(rows)


def s9_by_weekday(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]]
    rows = []
    for wd in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
        rows.append(_summary_row(sub[sub["weekday"] == wd], wd))
    rows.append(_summary_row(sub[sub["is_weekend"]], "周末合计"))
    rows.append(_summary_row(sub[~sub["is_weekend"]], "非周末合计"))
    return pd.DataFrame(rows)


def s10_by_depth(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"] & df["strong_ah_depth"].notna()].copy()
    sub["depth_bucket"] = sub["strong_ah_depth"].apply(depth_bucket)
    rows = []
    for b in ["平手 / 受让", "让 0.25", "让 0.5", "让 0.75", "让 1", "让 1.25", "让 1.5", "让 ≥1.75"]:
        rows.append(_summary_row(sub[sub["depth_bucket"] == b], b))
    # 阈值汇总
    rows.append(_summary_row(sub[sub["strong_ah_depth"] <= -1.0], "强队让 ≥1 球"))
    rows.append(_summary_row(sub[sub["strong_ah_depth"] <= -1.5], "强队让 ≥1.5 球"))
    return pd.DataFrame(rows)


def s11_golden_x_depth(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]].copy()
    sub["kickoff_bucket"] = sub["bj_kickoff"].apply(
        lambda s: kickoff_bucket(_t(s)) if _t(s) else None
    )
    rows = []
    at_2130 = sub[sub["kickoff_bucket"] == "21:30"]
    rows.append(_summary_row(at_2130[at_2130["strong_ah_direction"] == "让球"], "北京 21:30 + 强队让球"))
    rows.append(_summary_row(at_2130[at_2130["strong_ah_depth"] <= -1.0], "北京 21:30 + 强队让 ≥1"))
    rows.append(_summary_row(at_2130[at_2130["strong_ah_depth"] <= -1.5], "北京 21:30 + 强队让 ≥1.5"))
    sat_2130 = at_2130[at_2130["weekday"] == "周六"]
    sun_2130 = at_2130[at_2130["weekday"] == "周日"]
    rows.append(_summary_row(sat_2130[sat_2130["strong_ah_direction"] == "让球"], "周六 21:30 + 强队让球"))
    rows.append(_summary_row(sun_2130[sun_2130["strong_ah_direction"] == "让球"], "周日 21:30 + 强队让球"))
    we_night = sub[sub["is_weekend"]].copy()
    we_night["coarse"] = we_night["bj_kickoff"].apply(lambda s: coarse_bucket(_t(s)) if _t(s) else None)
    we_night = we_night[we_night["coarse"] == "晚间 18-24"]
    rows.append(_summary_row(we_night[we_night["strong_ah_depth"] <= -1.0], "周末晚间 + 强队让 ≥1"))
    rows.append(_summary_row(we_night[we_night["strong_ah_depth"] <= -1.5], "周末晚间 + 强队让 ≥1.5"))
    return pd.DataFrame(rows)


def s12_day_scarcity(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]].copy()
    rows = []
    rows.append(_summary_row(sub[sub["day_total_top5"] <= 3], "当天五大联赛 ≤3 场"))
    rows.append(_summary_row(sub[(sub["day_total_top5"] >= 4) & (sub["day_total_top5"] <= 6)], "当天 4-6 场"))
    rows.append(_summary_row(sub[(sub["day_total_top5"] >= 7) & (sub["day_total_top5"] <= 10)], "当天 7-10 场"))
    rows.append(_summary_row(sub[sub["day_total_top5"] > 10], "当天 >10 场"))
    rows.append(_summary_row(sub[sub["day_total_strong"] == 1], "当天只有 1 场强队"))
    rows.append(_summary_row(sub[(sub["day_total_strong"] >= 2) & (sub["day_total_strong"] <= 3)], "当天 2-3 场强队"))
    rows.append(_summary_row(sub[sub["day_total_strong"] >= 4], "当天 ≥4 场强队"))
    return pd.DataFrame(rows)


def s13_same_slot(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]].copy()
    rows = []
    rows.append(_summary_row(sub[sub["same_slot_strong_count"] == 1], "同时段仅 1 场强队"))
    rows.append(_summary_row(sub[sub["same_slot_strong_count"] == 2], "同时段 2 场强队"))
    rows.append(_summary_row(sub[sub["same_slot_strong_count"] >= 3], "同时段 ≥3 场强队"))
    return pd.DataFrame(rows)


def s14_epl_competing(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"] & (df["league"] != "EPL")].copy()
    rows = []
    rows.append(_summary_row(sub[sub["epl_competing_in_slot"] == True], "同时段有英超强队抢流量（非英超强队视角）"))
    rows.append(_summary_row(sub[sub["epl_competing_in_slot"] == False], "同时段无英超强队（非英超强队视角）"))
    # 按联赛拆细
    for lg in ["LaLiga", "Bundesliga", "SerieA", "Ligue1"]:
        lg_sub = sub[sub["league"] == lg]
        rows.append(_summary_row(lg_sub[lg_sub["epl_competing_in_slot"] == True], f"{lg} - 同时段有英超"))
        rows.append(_summary_row(lg_sub[lg_sub["epl_competing_in_slot"] == False], f"{lg} - 同时段无英超"))
    return pd.DataFrame(rows)


def s15_high_loss_conditions(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """从其他 sheet 收集所有有效输盘率 ≥65% 的条件汇总。"""
    rows = []
    for name, sh in sheets.items():
        if "有效输盘率" not in sh.columns:
            continue
        for _, r in sh.iterrows():
            if pd.notna(r.get("有效输盘率")) and r["有效输盘率"] >= 0.65 and r["样本数"] >= 5:
                rows.append({"来源 Sheet": name, **r.to_dict()})
    return pd.DataFrame(rows)


def s16_forbidden_conditions(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, sh in sheets.items():
        if "有效输盘率" not in sh.columns:
            continue
        for _, r in sh.iterrows():
            if pd.notna(r.get("有效输盘率")) and r["有效输盘率"] < 0.5405 and r["样本数"] >= 5:
                rows.append({"来源 Sheet": name, **r.to_dict()})
    return pd.DataFrame(rows)


def s17_strong_win_but_lose_handicap(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]]
    strong_won = (
        ((sub["strong_side"] == "主") & (sub["result"] == "主胜")) |
        ((sub["strong_side"] == "客") & (sub["result"] == "客胜"))
    )
    out = sub[strong_won & sub["is_lost_handicap"].fillna(False)]
    return out.copy()


def s18_strong_lost_match_and_handicap(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]]
    strong_lost = (
        ((sub["strong_side"] == "主") & (sub["result"] == "客胜")) |
        ((sub["strong_side"] == "客") & (sub["result"] == "主胜"))
    )
    out = sub[strong_lost & sub["is_lost_handicap"].fillna(False)]
    return out.copy()


def s19_small_sample(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, sh in sheets.items():
        if "样本数" not in sh.columns:
            continue
        for _, r in sh.iterrows():
            if r["样本数"] < 5:
                rows.append({"来源 Sheet": name, **r.to_dict()})
    return pd.DataFrame(rows)


def s20_final_conclusion(df: pd.DataFrame) -> pd.DataFrame:
    """Sheet20 是放结论摘要表（中文报告的速查版）。run.py 会把 markdown 报告并行写出。"""
    sub = df[df["contains_strong"]]
    rows = [
        ["数据窗口", "2024-01-01 ~ 2024-12-31（北京时间）"],
        ["统计场次（强队）", str(len(sub))],
        ["统计场次（含盘口）", str(int(sub["strong_ah_result"].notna().sum()))],
        ["走水场次", str(int((sub["strong_ah_result"] == "走水").sum()))],
        ["盈亏平衡线", "54.05%（水位 0.85）"],
        ["A 级阈值", "样本≥10 且 有效输盘率≥65%"],
        ["B 级阈值", "样本≥10 且 60%≤有效输盘率<65%"],
        ["C 级阈值", "5≤样本<10 且 有效输盘率≥65%（仅观察）"],
        ["禁止条件", "有效输盘率 < 54.05%"],
    ]
    return pd.DataFrame(rows, columns=["项", "值"])


def s21_season_compare(df: pd.DataFrame) -> pd.DataFrame:
    sub = df[df["contains_strong"]]
    rows = [
        _summary_row(sub[sub["season"] == "2023/24"], "2023/24 后半段"),
        _summary_row(sub[sub["season"] == "2024/25"], "2024/25 前半段"),
        _summary_row(sub, "2024 自然年合计"),
    ]
    return pd.DataFrame(rows)


# ---------- 辅助 ----------

def _t(s):
    if not isinstance(s, str) or ":" not in s:
        return None
    from datetime import time
    hh, mm = s.split(":")[:2]
    try:
        return time(int(hh), int(mm))
    except ValueError:
        return None


# ---------- 统一入口 ----------

def build_all_sheets(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sheets: dict[str, pd.DataFrame] = {}
    sheets["Sheet1_原始匹配"] = s1_raw_matches(df)
    sheets["Sheet2_强队比赛筛选"] = s2_strong_matches(df)
    sheets["Sheet3_强队盘口明细"] = s3_strong_handicap_detail(df)
    sheets["Sheet4_整体输盘率"] = s4_overall_loss_ranking(df)
    sheets["Sheet5_按联赛"] = s5_by_league(df)
    sheets["Sheet6_按球队"] = s6_by_team(df)
    sheets["Sheet7_按开球时间"] = s7_by_kickoff(df)
    sheets["Sheet8_按时段"] = s8_by_coarse(df)
    sheets["Sheet9_按周几"] = s9_by_weekday(df)
    sheets["Sheet10_按盘口深度"] = s10_by_depth(df)
    sheets["Sheet11_黄金时间x深盘"] = s11_golden_x_depth(df)
    sheets["Sheet12_当天比赛稀缺度"] = s12_day_scarcity(df)
    sheets["Sheet13_同时段强队数"] = s13_same_slot(df)
    sheets["Sheet14_英超抢流量"] = s14_epl_competing(df)
    # 15/16/19 需要在其他 sheet 都生成后再聚合
    sheets["Sheet15_输盘率≥65%条件"] = s15_high_loss_conditions(sheets)
    sheets["Sheet16_禁止反强队条件"] = s16_forbidden_conditions(sheets)
    sheets["Sheet17_强队赢球但输盘"] = s17_strong_win_but_lose_handicap(df)
    sheets["Sheet18_强队输球且输盘"] = s18_strong_lost_match_and_handicap(df)
    sheets["Sheet19_样本不足提醒"] = s19_small_sample(sheets)
    sheets["Sheet20_最终复盘结论"] = s20_final_conclusion(df)
    sheets["Sheet21_赛季对比"] = s21_season_compare(df)
    return sheets
