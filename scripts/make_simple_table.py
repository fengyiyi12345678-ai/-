"""一次性脚本：把 5 个 football-data.co.uk CSV 整合成一张精简表。

输出列（用户需求）：
  比赛日期 (YYYY-MM-DD)
  开球时间
  联赛
  主队 (中文)
  客队 (中文)
  亚盘盘口 (主队让球，让=负)
  最终比分
  强队
  强队主客
  是否强队 vs 强队
  强队让球深度
  强队盘口结果 (全赢/半赢/走水/半输/全输)
  强队是否输盘
"""

from __future__ import annotations
import sys, glob
from pathlib import Path
import pandas as pd

# ---------- 全队中文映射（五大联赛 2023/24 + 2024/25 主流名）----------
TEAM_CN = {
    # EPL
    "Arsenal": "阿森纳", "Aston Villa": "阿斯顿维拉", "Bournemouth": "伯恩茅斯",
    "Brentford": "布伦特福德", "Brighton": "布莱顿", "Burnley": "伯恩利",
    "Chelsea": "切尔西", "Crystal Palace": "水晶宫", "Everton": "埃弗顿",
    "Fulham": "富勒姆", "Liverpool": "利物浦", "Luton": "卢顿",
    "Man City": "曼城", "Man United": "曼联", "Newcastle": "纽卡斯尔",
    "Nott'm Forest": "诺丁汉森林", "Sheffield United": "谢菲尔德联",
    "Tottenham": "热刺", "West Ham": "西汉姆联", "Wolves": "狼队",
    "Ipswich": "伊普斯维奇", "Leicester": "莱斯特城", "Southampton": "南安普顿",

    # La Liga
    "Alaves": "阿拉维斯", "Almeria": "阿尔梅里亚", "Ath Bilbao": "毕尔巴鄂竞技",
    "Ath Madrid": "马竞", "Barcelona": "巴萨", "Betis": "皇家贝蒂斯",
    "Cadiz": "加的斯", "Celta": "塞尔塔", "Getafe": "赫塔费",
    "Girona": "赫罗纳", "Granada": "格拉纳达", "Las Palmas": "拉斯帕尔马斯",
    "Mallorca": "马洛卡", "Osasuna": "奥萨苏纳", "Real Madrid": "皇马",
    "Sevilla": "塞维利亚", "Sociedad": "皇家社会", "Valencia": "瓦伦西亚",
    "Vallecano": "巴列卡诺", "Villarreal": "比利亚雷亚尔",
    "Leganes": "莱加内斯", "Valladolid": "巴利亚多利德", "Espanol": "西班牙人",

    # Bundesliga
    "Augsburg": "奥格斯堡", "Bayern Munich": "拜仁", "Bochum": "波鸿",
    "Darmstadt": "达姆施塔特", "Dortmund": "多特蒙德", "Ein Frankfurt": "法兰克福",
    "FC Koln": "科隆", "Freiburg": "弗赖堡", "Heidenheim": "海登海姆",
    "Hoffenheim": "霍芬海姆", "Leverkusen": "勒沃库森", "M'gladbach": "门兴格拉德巴赫",
    "Mainz": "美因茨", "RB Leipzig": "莱比锡", "Stuttgart": "斯图加特",
    "Union Berlin": "柏林联合", "Werder Bremen": "云达不莱梅", "Wolfsburg": "沃尔夫斯堡",
    "Holstein Kiel": "基尔", "St Pauli": "圣保利",

    # Serie A
    "Atalanta": "亚特兰大", "Bologna": "博洛尼亚", "Cagliari": "卡利亚里",
    "Empoli": "恩波利", "Fiorentina": "佛罗伦萨", "Frosinone": "弗洛西诺尼",
    "Genoa": "热那亚", "Inter": "国际米兰", "Juventus": "尤文图斯",
    "Lazio": "拉齐奥", "Lecce": "莱切", "Milan": "AC米兰",
    "Monza": "蒙扎", "Napoli": "那不勒斯", "Roma": "罗马",
    "Salernitana": "萨勒尼塔纳", "Sassuolo": "萨索洛", "Torino": "都灵",
    "Udinese": "乌迪内斯", "Verona": "维罗纳",
    "Como": "科莫", "Parma": "帕尔马", "Venezia": "威尼斯",

    # Ligue 1
    "Brest": "布雷斯特", "Clermont": "克莱蒙", "Le Havre": "勒阿弗尔",
    "Lens": "朗斯", "Lille": "里尔", "Lorient": "洛里昂",
    "Lyon": "里昂", "Marseille": "马赛", "Metz": "梅斯",
    "Monaco": "摩纳哥", "Montpellier": "蒙彼利埃", "Nantes": "南特",
    "Nice": "尼斯", "Paris SG": "巴黎圣日耳曼", "Reims": "兰斯",
    "Rennes": "雷恩", "Strasbourg": "斯特拉斯堡", "Toulouse": "图卢兹",
    "Auxerre": "欧塞尔", "Angers": "昂热", "St Etienne": "圣埃蒂安",
}

# ---------- 强队池（中文）----------
STRONG = {
    # EPL
    "曼城", "利物浦", "阿森纳", "曼联", "切尔西", "热刺", "纽卡斯尔",
    # La Liga
    "皇马", "巴萨", "马竞",
    # Bundesliga
    "拜仁", "多特蒙德", "莱比锡", "勒沃库森",
    # Serie A
    "国际米兰", "AC米兰", "尤文图斯", "那不勒斯", "罗马", "拉齐奥",
    # Ligue 1
    "巴黎圣日耳曼", "马赛", "摩纳哥", "里昂", "里尔",
}

LEAGUE_CN = {
    "E0": "英超", "SP1": "西甲", "D1": "德甲", "I1": "意甲", "F1": "法甲",
}


def classify_handicap(cover: float) -> str:
    """cover_value -> 全赢/半赢/走水/半输/全输"""
    if cover > 0.25 + 1e-3: return "全赢"
    if abs(cover - 0.25) < 1e-3: return "半赢"
    if abs(cover) < 1e-3: return "走水"
    if abs(cover + 0.25) < 1e-3: return "半输"
    if cover < -0.25 - 1e-3: return "全输"
    return "未知"


def process_one(csv_path: Path) -> pd.DataFrame:
    raw = pd.read_csv(csv_path)
    if "HomeTeam" not in raw.columns:
        return pd.DataFrame()

    # 联赛代码（E0/SP1/D1/I1/F1）
    div = raw["Div"].iloc[0] if "Div" in raw.columns else csv_path.stem.split("-")[-1]
    league_cn = LEAGUE_CN.get(div, div)

    # 中文队名
    home_cn = raw["HomeTeam"].map(lambda x: TEAM_CN.get(x, x))
    away_cn = raw["AwayTeam"].map(lambda x: TEAM_CN.get(x, x))

    # 日期 → YYYY-MM-DD
    date_iso = pd.to_datetime(raw["Date"], format="%d/%m/%Y", errors="coerce").dt.strftime("%Y-%m-%d")

    # 开球时间
    kickoff = raw.get("Time", pd.Series([""] * len(raw))).fillna("")

    # 亚盘（主队让球，让=负）：优先 closing AHCh，否则 AvgAHH，否则 AHh
    ah = raw.get("AHCh")
    if ah is None or ah.isna().all():
        ah = raw.get("AvgAHH")
    if ah is None or ah.isna().all():
        ah = raw.get("AHh")
    ah = pd.to_numeric(ah, errors="coerce")

    # 比分
    score = raw["FTHG"].astype("Int64").astype(str) + ":" + raw["FTAG"].astype("Int64").astype(str)

    # 强队识别
    home_strong = home_cn.isin(STRONG)
    away_strong = away_cn.isin(STRONG)
    contains_strong = home_strong | away_strong

    strong_name = pd.Series([""] * len(raw))
    strong_side = pd.Series([""] * len(raw))
    strong_depth = pd.Series([pd.NA] * len(raw), dtype="Float64")
    strong_cover = pd.Series([pd.NA] * len(raw), dtype="Float64")
    strong_result = pd.Series([""] * len(raw))
    is_lost = pd.Series([pd.NA] * len(raw), dtype="boolean")
    is_strong_vs_strong = home_strong & away_strong

    for i in range(len(raw)):
        if not contains_strong.iloc[i]:
            continue
        # 若两队都是强队，默认取主队为「强队视角」
        if home_strong.iloc[i]:
            strong_name.iloc[i] = home_cn.iloc[i]
            strong_side.iloc[i] = "主"
            depth = ah.iloc[i]   # 站点视角=主队让球，强队=主 ⇒ 同号
        else:
            strong_name.iloc[i] = away_cn.iloc[i]
            strong_side.iloc[i] = "客"
            depth = -ah.iloc[i] if pd.notna(ah.iloc[i]) else pd.NA
        strong_depth.iloc[i] = depth
        # 净胜球（强队角度）
        try:
            hg, ag = int(raw["FTHG"].iloc[i]), int(raw["FTAG"].iloc[i])
        except Exception:
            continue
        net = (hg - ag) if strong_side.iloc[i] == "主" else (ag - hg)
        if pd.notna(depth):
            cv = net + float(depth)
            strong_cover.iloc[i] = cv
            cls = classify_handicap(cv)
            strong_result.iloc[i] = cls
            is_lost.iloc[i] = cls in ("全输", "半输")

    out = pd.DataFrame({
        "比赛日期": date_iso,
        "开球时间": kickoff,
        "联赛": league_cn,
        "主队": home_cn,
        "客队": away_cn,
        "最终比分": score,
        "亚盘盘口(主队让球,负=让)": ah,
        "强队": strong_name,
        "强队主客": strong_side,
        "强队让球深度": strong_depth,
        "是否强队对阵强队": is_strong_vs_strong,
        "强队盘口结果": strong_result,
        "强队是否输盘": is_lost,
        "数据源": f"football-data.co.uk / {csv_path.name}",
    })
    return out


def main(input_dir: str, out_xlsx: str):
    paths = sorted(Path(input_dir).glob("*.csv"))
    parts = [process_one(p) for p in paths]
    parts = [p for p in parts if not p.empty]
    merged = pd.concat(parts, ignore_index=True)

    # 按日期+联赛排序
    merged = merged.sort_values(["比赛日期", "联赛", "开球时间"]).reset_index(drop=True)

    # 写出：1 张总表 + 1 张仅含强队 + 5 张分联赛
    Path(out_xlsx).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as w:
        merged.to_excel(w, sheet_name="全部比赛", index=False)
        merged[merged["强队"] != ""].to_excel(w, sheet_name="仅含强队比赛", index=False)
        for lg in ["英超", "西甲", "德甲", "意甲", "法甲"]:
            merged[merged["联赛"] == lg].to_excel(w, sheet_name=lg, index=False)
    print(f"saved {len(merged)} rows -> {out_xlsx}")


if __name__ == "__main__":
    in_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    out = sys.argv[2] if len(sys.argv) > 2 else "data/output/简表_对阵盘口.xlsx"
    main(in_dir, out)
