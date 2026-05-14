"""从「简表_对阵盘口.xlsx」中切片，找反强队 A / B / C 级候选条件。

切片维度：
  1. 联赛
  2. 强队
  3. 北京时间开球时段（粗）
  4. 北京时间开球时间桶（精确到 30 分钟）
  5. 周几 / 是否周末
  6. 让球深度桶
  7. 联赛 × 让球深度
  8. 联赛 × 时段
  9. 强队 × 主客场
  10. 北京时段 × 让球深度
  11. 周末 × 让球深度

阈值：
  A 级：样本 ≥ 10 且 有效输盘率 ≥ 65%
  B 级：样本 ≥ 10 且 60% ≤ 有效输盘率 < 65%
  C 级：5 ≤ 样本 < 10 且 有效输盘率 ≥ 65%
  禁止：有效输盘率 < 54.05%

走水不计入分母；
英国时间 → 北京时间换算（含夏令时，3 月最后周日 ~ 10 月最后周日 = +7，否则 +8）。
"""

from __future__ import annotations
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd


# ---------- 时区换算 ----------

def uk_to_beijing(date_str: str, time_str: str) -> tuple[str, str]:
    """date_str: YYYY-MM-DD; time_str: HH:MM (UK 本地时间)。"""
    if not isinstance(time_str, str) or ":" not in time_str:
        time_str = "20:00"
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except Exception:
        return date_str, time_str
    y = dt.year
    # 粗略 BST：3/31 ~ 10/27（实际是 3 月最后周日 ~ 10 月最后周日，差异 ≤1 天可接受）
    in_bst = datetime(y, 3, 31) <= dt <= datetime(y, 10, 27)
    bj = dt + timedelta(hours=7 if in_bst else 8)
    return bj.strftime("%Y-%m-%d"), bj.strftime("%H:%M")


# ---------- 桶 ----------

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def kickoff_bucket(t: str) -> str:
    if not isinstance(t, str) or ":" not in t:
        return "未知"
    hh, mm = t.split(":")[:2]
    try:
        h, m = int(hh), int(mm)
    except ValueError:
        return "未知"
    minute = 0 if m < 15 else (30 if m < 45 else 0)
    hour = h if m < 45 else (h + 1) % 24
    return f"{hour:02d}:{minute:02d}"


def coarse_bucket(t: str) -> str:
    if not isinstance(t, str) or ":" not in t:
        return "未知"
    h = int(t.split(":")[0])
    if 0 <= h < 6:  return "凌晨 00-06"
    if 6 <= h < 12: return "上午 06-12"
    if 12 <= h < 18: return "下午 12-18"
    return "晚间 18-24"


def depth_bucket(d) -> str:
    if pd.isna(d): return "未知"
    d = float(d)
    if d >= 0:                return "平手 / 受让"
    if -0.375 < d < -0.125:   return "让 0.25"
    if -0.625 < d <= -0.375:  return "让 0.5"
    if -0.875 < d <= -0.625:  return "让 0.75"
    if -1.125 < d <= -0.875:  return "让 1"
    if -1.375 < d <= -1.125:  return "让 1.25"
    if -1.625 < d <= -1.375:  return "让 1.5"
    return "让 ≥1.75"


# ---------- 汇总 ----------

def summarize(sub: pd.DataFrame, label: str) -> dict:
    sub = sub[sub["强队盘口结果"].isin(["全赢", "半赢", "走水", "半输", "全输"])]
    n = len(sub)
    push = int((sub["强队盘口结果"] == "走水").sum())
    fl = int((sub["强队盘口结果"] == "全输").sum())
    hl = int((sub["强队盘口结果"] == "半输").sum())
    fw = int((sub["强队盘口结果"] == "全赢").sum())
    hw = int((sub["强队盘口结果"] == "半赢").sum())
    denom = n - push
    eff = (fl + 0.5 * hl) / denom if denom > 0 else None
    return {
        "维度": label, "样本": n,
        "全赢": fw, "半赢": hw, "走水": push, "半输": hl, "全输": fl,
        "有效输盘率": round(eff, 4) if eff is not None else None,
    }


def tier(n, eff):
    if eff is None: return "—"
    if eff < 0.5405: return "禁止"
    if n >= 10 and eff >= 0.65: return "A"
    if n >= 10 and 0.60 <= eff < 0.65: return "B"
    if 5 <= n < 10 and eff >= 0.65: return "C"
    return "未达"


# ---------- 主流程 ----------

def main(in_xlsx: str, out_xlsx: str):
    df = pd.read_excel(in_xlsx, sheet_name="仅含强队比赛")

    # 加北京时间字段
    bj = df.apply(lambda r: uk_to_beijing(str(r["比赛日期"])[:10], str(r["开球时间"])), axis=1)
    df["北京日期"] = bj.apply(lambda x: x[0])
    df["北京开球"] = bj.apply(lambda x: x[1])
    df["北京时段"] = df["北京开球"].apply(coarse_bucket)
    df["北京开球桶"] = df["北京开球"].apply(kickoff_bucket)
    df["让球深度桶"] = df["强队让球深度"].apply(depth_bucket)
    df["周几"] = pd.to_datetime(df["北京日期"]).dt.weekday.map(lambda i: WEEKDAY_CN[i])
    df["是否周末"] = df["周几"].isin(["周六", "周日"])

    rows = []

    # 1. 联赛
    for lg, g in df.groupby("联赛"):
        rows.append({**summarize(g, f"联赛={lg}"), "维度类别": "联赛"})

    # 2. 球队
    for tm, g in df.groupby("强队"):
        if not tm: continue
        rows.append({**summarize(g, f"球队={tm}"), "维度类别": "球队"})

    # 3. 北京时段
    for b, g in df.groupby("北京时段"):
        rows.append({**summarize(g, f"北京时段={b}"), "维度类别": "时段"})

    # 4. 北京开球时间桶
    for b, g in df.groupby("北京开球桶"):
        rows.append({**summarize(g, f"北京开球={b}"), "维度类别": "开球时间"})

    # 5. 周几
    for w, g in df.groupby("周几"):
        rows.append({**summarize(g, f"周几={w}"), "维度类别": "周几"})
    rows.append({**summarize(df[df["是否周末"]], "周末合计"), "维度类别": "周末"})
    rows.append({**summarize(df[~df["是否周末"]], "非周末合计"), "维度类别": "周末"})

    # 6. 深度桶
    for b, g in df.groupby("让球深度桶"):
        rows.append({**summarize(g, f"深度={b}"), "维度类别": "盘口深度"})
    rows.append({**summarize(df[df["强队让球深度"] <= -1.0], "强队让 ≥1 球"), "维度类别": "盘口深度阈值"})
    rows.append({**summarize(df[df["强队让球深度"] <= -1.5], "强队让 ≥1.5 球"), "维度类别": "盘口深度阈值"})

    # 7. 联赛 × 深度阈值
    for lg in ["英超", "西甲", "德甲", "意甲", "法甲"]:
        sub_lg = df[df["联赛"] == lg]
        rows.append({**summarize(sub_lg[sub_lg["强队让球深度"] <= -1.0], f"{lg} + 让 ≥1"), "维度类别": "联赛×深度"})
        rows.append({**summarize(sub_lg[sub_lg["强队让球深度"] <= -1.5], f"{lg} + 让 ≥1.5"), "维度类别": "联赛×深度"})

    # 8. 联赛 × 北京时段
    for lg in ["英超", "西甲", "德甲", "意甲", "法甲"]:
        for b in ["凌晨 00-06", "晚间 18-24"]:
            g = df[(df["联赛"] == lg) & (df["北京时段"] == b)]
            rows.append({**summarize(g, f"{lg} + {b}"), "维度类别": "联赛×时段"})

    # 9. 强队 × 主客场
    for tm, g in df.groupby("强队"):
        if not tm: continue
        for side in ["主", "客"]:
            rows.append({**summarize(g[g["强队主客"] == side], f"球队={tm} {side}场"), "维度类别": "球队×主客"})

    # 10. 北京时段 × 让球深度
    for b in ["凌晨 00-06", "晚间 18-24"]:
        for label, mask in [
            ("让 ≥1", df["强队让球深度"] <= -1.0),
            ("让 ≥1.5", df["强队让球深度"] <= -1.5),
        ]:
            g = df[(df["北京时段"] == b) & mask]
            rows.append({**summarize(g, f"{b} + 强队{label}"), "维度类别": "时段×深度"})

    # 11. 周末 × 让球深度
    we_night = df[df["是否周末"] & (df["北京时段"] == "晚间 18-24")]
    rows.append({**summarize(we_night[we_night["强队让球深度"] <= -1.0], "周末晚间 + 让 ≥1"), "维度类别": "周末×深度"})
    rows.append({**summarize(we_night[we_night["强队让球深度"] <= -1.5], "周末晚间 + 让 ≥1.5"), "维度类别": "周末×深度"})

    # 12. 北京 21:00-22:00 段 (黄金档) × 深度
    golden = df[df["北京开球桶"].isin(["21:00", "21:30", "22:00", "22:30", "23:00"])]
    rows.append({**summarize(golden, "北京 21:00-23:00 黄金档"), "维度类别": "黄金档"})
    rows.append({**summarize(golden[golden["强队让球深度"] <= -1.0], "黄金档 + 让 ≥1"), "维度类别": "黄金档×深度"})
    rows.append({**summarize(golden[golden["强队让球深度"] <= -1.5], "黄金档 + 让 ≥1.5"), "维度类别": "黄金档×深度"})

    out = pd.DataFrame(rows)
    out["等级"] = out.apply(lambda r: tier(r["样本"], r["有效输盘率"]), axis=1)
    out["样本提醒"] = out["样本"].apply(lambda n: "样本不足，不能过度推断" if n < 5 else "")

    # 排序：先按等级 (A>B>C>未达>禁止>—)，再按输盘率
    tier_order = {"A": 0, "B": 1, "C": 2, "未达": 3, "禁止": 4, "—": 5}
    out["_t"] = out["等级"].map(tier_order)
    out = out.sort_values(["_t", "有效输盘率"], ascending=[True, False]).drop(columns=["_t"])

    # 拆分输出
    Path(out_xlsx).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as w:
        out.to_excel(w, sheet_name="全部维度", index=False)
        out[out["等级"] == "A"].to_excel(w, sheet_name="A 级候选", index=False)
        out[out["等级"] == "B"].to_excel(w, sheet_name="B 级候选", index=False)
        out[out["等级"] == "C"].to_excel(w, sheet_name="C 级观察", index=False)
        out[out["等级"] == "禁止"].to_excel(w, sheet_name="禁止反强队", index=False)
        out[out["样本"] >= 5].to_excel(w, sheet_name="可参考(样本≥5)", index=False)

    # 控制台摘要
    print(f"=== 数据：{len(df)} 场强队比赛（含盘口） ===\n")
    for tier_name in ["A", "B", "C"]:
        sub = out[out["等级"] == tier_name]
        print(f"\n--- {tier_name} 级条件（{len(sub)} 条）---")
        if sub.empty:
            print("（无）")
        else:
            print(sub[["维度", "样本", "有效输盘率", "等级"]].to_string(index=False))

    print(f"\nsaved -> {out_xlsx}")


if __name__ == "__main__":
    in_xlsx = sys.argv[1] if len(sys.argv) > 1 else "data/output/简表_对阵盘口.xlsx"
    out_xlsx = sys.argv[2] if len(sys.argv) > 2 else "data/output/反强队候选名单.xlsx"
    main(in_xlsx, out_xlsx)
