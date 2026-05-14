"""跨平台下载 football-data.co.uk 五大联赛 CSV（Windows / Mac / Linux 都能用）。

用法：
    python scripts/download_football_data.py
"""
from __future__ import annotations
import urllib.request
from pathlib import Path

LEAGUES = ["E0", "SP1", "D1", "I1", "F1"]
SEASONS = ["2324", "2425"]
ROOT = Path("data/raw/football_data")


def main():
    for season in SEASONS:
        (ROOT / season).mkdir(parents=True, exist_ok=True)
        for lg in LEAGUES:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{lg}.csv"
            out = ROOT / season / f"{lg}.csv"
            print(f"GET {url}")
            try:
                urllib.request.urlretrieve(url, out)
                print(f"   -> {out} ({out.stat().st_size} bytes)")
            except Exception as e:
                print(f"   FAILED: {e}")
    print("\nDone. Next run:")
    print("  python -c \"from scraper.football_data_loader import build_unified; "
          "build_unified('data/raw/football_data','data/raw/matches_2024.parquet')\"")
    print("  python run.py analyze --in data/raw/matches_2024.parquet "
          "--out data/output/2024.xlsx --report data/output/2024.md")


if __name__ == "__main__":
    main()
