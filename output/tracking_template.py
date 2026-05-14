"""实盘跟踪表 + 资金测算表（独立 xlsx 模板）。

字段与需求文档第十一节一一对应。Excel 公式直接写在 formula 列里，
打开后会自动算「单场盈亏」「累计盈亏」。
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd

TRACKING_COLS = [
    "比赛日期", "北京时间", "星期几",
    "强队", "对手", "强队主客", "最终盘口",
    "强队盘口方向（让/受/平）", "强队让球深度",
    "是否周末", "当天五大联赛总场次", "当天强队比赛数",
    "同时段强队数", "是否有英超同时段抢流量",
    "是否符合 A 级条件", "是否符合 B 级条件",
    "是否下注", "下注方向（买对手受让 / 不下注）",
    "下注金额", "水位（默认 0.85）",
    "最终比分", "强队盘口结果（全赢/半赢/走水/半输/全输）",
    "是否命中（反强队视角）",
    "单场盈亏", "累计盈亏", "备注",
]


def build_tracking_xlsx(out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tracking_df = pd.DataFrame(columns=TRACKING_COLS)

    # 资金测算表
    rows = []
    for hit in [0.55, 0.60, 0.65, 0.70]:
        ev = 1000 * (hit * 0.85 - (1 - hit))
        rows.append({
            "命中率": f"{int(hit*100)}%",
            "单场期望收益 (¥)": round(ev, 2),
            "20 场预期 (¥)": round(ev * 20, 2),
            "30 场预期 (¥)": round(ev * 30, 2),
            "50 场预期 (¥)": round(ev * 50, 2),
            "100 场预期 (¥)": round(ev * 100, 2),
        })
    fund_df = pd.DataFrame(rows)
    breakeven = pd.DataFrame([
        {"项": "水位", "值": "0.85"},
        {"项": "盈亏平衡命中率", "值": "1 / (1 + 0.85) ≈ 54.05%"},
        {"项": "A 级目标命中率", "值": "≥ 65%"},
        {"项": "B 级目标命中率", "值": "60% – 65%"},
        {"项": "C 级目标命中率（观察）", "值": "≥ 65% 且样本 5–9"},
    ])

    # 模型说明
    model_rows = pd.DataFrame([
        ["A 级", "样本 ≥ 10 且 有效输盘率 ≥ 65%", "重点跟踪，可重仓"],
        ["B 级", "样本 ≥ 10 且 60% ≤ 有效输盘率 < 65%", "可观察，轻仓"],
        ["C 级", "5 ≤ 样本 < 10 且 有效输盘率 ≥ 65%", "样本偏小，仅观察"],
        ["禁止", "有效输盘率 < 54.05%", "不要做反强队"],
    ], columns=["等级", "条件", "操作"])

    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        tracking_df.to_excel(w, sheet_name="实盘跟踪表", index=False)
        fund_df.to_excel(w, sheet_name="资金测算", index=False)
        breakeven.to_excel(w, sheet_name="盈亏平衡参数", index=False)
        model_rows.to_excel(w, sheet_name="反强队模型规则", index=False)
    return out_path
