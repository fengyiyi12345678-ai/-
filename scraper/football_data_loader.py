"""football-data.co.uk CSV 适配器。

下载这 10 个文件放到 data/raw/football_data/ 下：
  2324/E0.csv  2324/SP1.csv  2324/D1.csv  2324/I1.csv  2324/F1.csv
  2425/E0.csv  2425/SP1.csv  2425/D1.csv  2425/I1.csv  2425/F1.csv

直链格式：https://www.football-data.co.uk/mmz4281/<2324|2425>/<E0|SP1|D1|I1|F1>.csv

用法：
  python -c "from scraper.football_data_loader import build_unified; \
             build_unified('data/raw/football_data', 'data/raw/matches_2024.parquet')"
然后跑：
  python run.py analyze --in data/raw/matches_2024.parquet \
                        --out data/output/2024.xlsx --report data/output/2024.md
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

LEAGUE_FILE_MAP = {
    "E0":  "EPL",
    "SP1": "LaLiga",
    "D1":  "Bundesliga",
    "I1":  "SerieA",
    "F1":  "Ligue1",
}

# 英国 -> 北京时差：3 月最后周日 ~ 10 月最后周日为 +7（夏令时），其余 +8
def _uk_to_beijing(date_str: str, time_str: str) -> tuple[str, str]:
    dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
    year = dt.year
    # 粗略夏令时：3/31 ~ 10/27 取 +7
    in_bst = datetime(year, 3, 31) <= dt <= datetime(year, 10, 27)
    delta = 7 if in_bst else 8
    bj = dt + timedelta(hours=delta)
    return bj.strftime("%Y-%m-%d"), bj.strftime("%H:%M")


def _pick(df: pd.DataFrame, *names) -> pd.Series:
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([pd.NA] * len(df))


def load_one(csv_path: Path, league_code: str, season_label: str) -> pd.DataFrame:
    raw = pd.read_csv(csv_path)
    if "Date" not in raw.columns:
        return pd.DataFrame()

    times = raw.get("Time", pd.Series(["20:00"] * len(raw)))
    bj = [_uk_to_beijing(d, t if isinstance(t, str) else "20:00")
          for d, t in zip(raw["Date"], times)]
    bj_date, bj_kickoff = zip(*bj)

    out = pd.DataFrame({
        "league": league_code,
        "season": season_label,
        "bj_date": bj_date,
        "bj_kickoff": bj_kickoff,
        "home": raw["HomeTeam"],
        "away": raw["AwayTeam"],
        "score_full": raw["FTHG"].astype(str) + ":" + raw["FTAG"].astype(str),
        "score_half": (raw.get("HTHG").astype("Int64").astype(str) + ":" +
                       raw.get("HTAG").astype("Int64").astype(str))
                       if "HTHG" in raw.columns else pd.NA,
        # 亚盘终盘：优先用 closing (AHCh)，否则平均 (AvgAHH/AHh)
        "ah_final": _pick(raw, "AHCh", "AvgAHH", "AHh").astype(float, errors="ignore"),
        "ah_open":  _pick(raw, "AHh", "AvgAHH").astype(float, errors="ignore"),
        "ah_live":  pd.NA,  # football-data 不提供
        "ou_final": _pick(raw, "Avg>2.5").astype(float, errors="ignore"),
        "eu_home":  _pick(raw, "AvgH", "B365H").astype(float, errors="ignore"),
        "eu_draw":  _pick(raw, "AvgD", "B365D").astype(float, errors="ignore"),
        "eu_away":  _pick(raw, "AvgA", "B365A").astype(float, errors="ignore"),
        "source_url": f"https://www.football-data.co.uk/mmz4281/{season_label.replace('/','')[2:]}/{csv_path.name}",
    })
    return out


def build_unified(root: str | Path, out_path: str | Path) -> Path:
    """读取 data/raw/football_data/{2324,2425}/*.csv 合并为统一 parquet。"""
    root = Path(root)
    parts = []
    for season_dir, season_label in [("2324", "2023/24"), ("2425", "2024/25")]:
        for code, lg in LEAGUE_FILE_MAP.items():
            p = root / season_dir / f"{code}.csv"
            if not p.exists():
                print(f"[skip] {p}")
                continue
            df = load_one(p, lg, season_label)
            print(f"[ok] {p}: {len(df)} rows")
            parts.append(df)
    if not parts:
        raise FileNotFoundError("没有读到任何 CSV，请先下载到 data/raw/football_data/")
    merged = pd.concat(parts, ignore_index=True)
    # 只保留 2024 自然年
    merged = merged[(merged["bj_date"] >= "2024-01-01") & (merged["bj_date"] <= "2024-12-31")].copy()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path)
    print(f"saved {len(merged)} rows -> {out_path}")
    return out_path
