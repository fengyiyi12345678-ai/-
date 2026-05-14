"""生成中文复盘报告 Markdown。

报告会引用 aggregator 算出的 21 个 sheet 中的数字；若某条结论的样本不足，
统一替换为「样本不足，不能过度推断」。
"""

from __future__ import annotations
import pandas as pd
from datetime import datetime


def _row_by_label(df: pd.DataFrame, label: str) -> dict | None:
    if "维度" not in df.columns:
        return None
    hit = df[df["维度"] == label]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


def _pct(x):
    if x is None or pd.isna(x):
        return "—"
    return f"{x*100:.2f}%"


def _safe_row_desc(row: dict | None, prefix: str) -> str:
    if not row:
        return f"- {prefix}：数据缺失"
    n = row.get("样本数", 0)
    eff = row.get("有效输盘率")
    if n < 5:
        return f"- {prefix}：样本 {n} 场 — 样本不足，不能过度推断"
    return (f"- {prefix}：样本 {n} 场，有效输盘率 {_pct(eff)}，"
            f"等级 {row.get('等级','—')}")


def build_report(sheets: dict[str, pd.DataFrame]) -> str:
    s5 = sheets["Sheet5_按联赛"]
    s7 = sheets["Sheet7_按开球时间"]
    s8 = sheets["Sheet8_按时段"]
    s9 = sheets["Sheet9_按周几"]
    s10 = sheets["Sheet10_按盘口深度"]
    s11 = sheets["Sheet11_黄金时间x深盘"]
    s12 = sheets["Sheet12_当天比赛稀缺度"]
    s13 = sheets["Sheet13_同时段强队数"]
    s14 = sheets["Sheet14_英超抢流量"]
    s21 = sheets["Sheet21_赛季对比"]
    s15 = sheets["Sheet15_输盘率≥65%条件"]
    s16 = sheets["Sheet16_禁止反强队条件"]
    s19 = sheets["Sheet19_样本不足提醒"]

    total = _row_by_label(sheets["Sheet4_整体输盘率"], "总体") or {}
    n_strong_match = total.get("样本数", 0)

    lines = []
    lines.append(f"# 2024 五大联赛强队盘口输盘复盘报告\n")
    lines.append(f"_生成时间：{datetime.now():%Y-%m-%d %H:%M}（北京时间）_\n")
    lines.append("> 研究主题：强队作为流量品牌，在热门时间 / 周末晚间 / 当天比赛稀缺时，"
                 "是否更容易因「盘口被市场买热抬深」而出现「赢球但输盘」/「热门强队输盘」。\n")

    lines.append("## 1. 数据来源与统计口径\n")
    lines.append("- 数据源：live.nowscore.com（脚本抓取，原始 HTML 落地于 data/raw/nowscore/）")
    lines.append("- 时间窗口：2024-01-01 ~ 2024-12-31，统一北京时间")
    lines.append("- 联赛：英超、西甲、德甲、意甲、法甲")
    lines.append("- 赛季拆分：2023/24 后半段（2024-01-01 ~ 2024-06-30）+ 2024/25 前半段（2024-07-01 ~ 2024-12-31）")
    lines.append("- 输盘率口径：`(全输 + 0.5×半输) / (总盘口场次 − 走水场次)`，走水不计入分母")
    lines.append("- 盈亏平衡线 54.05%（水位 0.85），样本 < 5 标注「样本不足」\n")

    lines.append("## 2. 总量\n")
    lines.append(f"- 2024 自然年强队相关比赛：{n_strong_match} 场")
    lines.append(f"- 走水 {total.get('走水','—')} 场（不计入分母）")
    lines.append(f"- 全输 {total.get('全输','—')} / 半输 {total.get('半输','—')} / "
                 f"半赢 {total.get('半赢','—')} / 全赢 {total.get('全赢','—')}")
    lines.append(f"- 整体有效输盘率：{_pct(total.get('有效输盘率'))}\n")

    lines.append("## 3. 按联赛\n")
    for lg in ["EPL", "LaLiga", "Bundesliga", "SerieA", "Ligue1"]:
        lines.append(_safe_row_desc(_row_by_label(s5, lg), lg))
    lines.append("")

    lines.append("## 4. 按北京开球时间（黄金档）\n")
    for k in ["20:30", "21:00", "21:30", "22:00", "22:30", "23:00", "23:30",
              "00:30", "01:30", "02:30", "03:30", "04:30"]:
        lines.append(_safe_row_desc(_row_by_label(s7, k), f"北京 {k}"))
    lines.append("")

    lines.append("## 5. 时段（凌晨 / 上午 / 下午 / 晚间）\n")
    for b in ["凌晨 00-06", "上午 06-12", "下午 12-18", "晚间 18-24", "周末晚间", "工作日晚间"]:
        lines.append(_safe_row_desc(_row_by_label(s8, b), b))
    lines.append("")

    lines.append("## 6. 按周几\n")
    for w in ["周六", "周日", "周末合计", "非周末合计"]:
        lines.append(_safe_row_desc(_row_by_label(s9, w), w))
    lines.append("")

    lines.append("## 7. 按盘口深度\n")
    for d in ["让 0.25", "让 0.5", "让 0.75", "让 1", "让 1.25", "让 1.5", "让 ≥1.75",
              "强队让 ≥1 球", "强队让 ≥1.5 球"]:
        lines.append(_safe_row_desc(_row_by_label(s10, d), d))
    lines.append("")

    lines.append("## 8. 黄金时间 × 深盘组合\n")
    for label in ["北京 21:30 + 强队让球", "北京 21:30 + 强队让 ≥1", "北京 21:30 + 强队让 ≥1.5",
                  "周六 21:30 + 强队让球", "周日 21:30 + 强队让球",
                  "周末晚间 + 强队让 ≥1", "周末晚间 + 强队让 ≥1.5"]:
        lines.append(_safe_row_desc(_row_by_label(s11, label), label))
    lines.append("")

    lines.append("## 9. 当天比赛稀缺度\n")
    for label in ["当天五大联赛 ≤3 场", "当天 4-6 场", "当天 7-10 场", "当天 >10 场",
                  "当天只有 1 场强队", "当天 2-3 场强队", "当天 ≥4 场强队"]:
        lines.append(_safe_row_desc(_row_by_label(s12, label), label))
    lines.append("")

    lines.append("## 10. 同时段强队数量\n")
    for label in ["同时段仅 1 场强队", "同时段 2 场强队", "同时段 ≥3 场强队"]:
        lines.append(_safe_row_desc(_row_by_label(s13, label), label))
    lines.append("")

    lines.append("## 11. 是否有英超强队抢流量（非英超强队视角）\n")
    for label in ["同时段有英超强队抢流量（非英超强队视角）", "同时段无英超强队（非英超强队视角）"]:
        lines.append(_safe_row_desc(_row_by_label(s14, label), label))
    lines.append("")

    lines.append("## 12. 赛季对比\n")
    for label in ["2023/24 后半段", "2024/25 前半段", "2024 自然年合计"]:
        lines.append(_safe_row_desc(_row_by_label(s21, label), label))
    lines.append("")

    lines.append("## 13. 高输盘率（≥65%）条件汇总\n")
    if s15.empty:
        lines.append("- 暂无满足条件的组合。")
    else:
        lines.append(f"- 共 {len(s15)} 条，详见 Excel 的 Sheet15。")
    lines.append("")

    lines.append("## 14. 禁止反强队（<54.05%）条件汇总\n")
    if s16.empty:
        lines.append("- 暂无明确禁止条件。")
    else:
        lines.append(f"- 共 {len(s16)} 条，详见 Excel 的 Sheet16。")
    lines.append("")

    lines.append("## 15. 样本不足提醒\n")
    lines.append(f"- 共 {len(s19)} 条维度样本 < 5，详见 Excel 的 Sheet19。")
    lines.append("")

    lines.append("## 16. 资金测算（水位 0.85，每场 1000 元）\n")
    lines.append("| 命中率 | 单场期望 | 20 场 | 30 场 | 50 场 | 100 场 |")
    lines.append("|---|---|---|---|---|---|")
    for hit in [0.55, 0.60, 0.65, 0.70]:
        ev = 1000 * (hit * 0.85 - (1 - hit))
        lines.append(f"| {int(hit*100)}% | {ev:+.1f} | {ev*20:+.0f} | {ev*30:+.0f} | {ev*50:+.0f} | {ev*100:+.0f} |")
    lines.append("\n- 盈亏平衡命中率 = 1 / (1 + 0.85) = **54.05%**。\n")

    lines.append("## 17. 后续如何持续更新该模型\n")
    lines.append("1. 每周日深夜执行 `python run.py scrape --start <last_sun> --end <this_sat>`，增量抓取。")
    lines.append("2. 跑 `python run.py analyze` 重新生成 Excel + 报告；用 Sheet21 看赛季对比是否漂移。")
    lines.append("3. 实盘跟踪表（output/tracking_template.xlsx）每场填一行，月底滚动校准 A/B/C 级阈值。")
    lines.append("4. 当某条 A 级条件的近 20 场实盘 ROI 跌破 5%，立刻降级或淘汰。")
    return "\n".join(lines)
