#!/usr/bin/env bash
# 下载 football-data.co.uk 五大联赛 2023/24 + 2024/25 共 10 个 CSV。
# 运行：bash scripts/download_football_data.sh

set -euo pipefail
ROOT="data/raw/football_data"
mkdir -p "$ROOT/2324" "$ROOT/2425"

LEAGUES=(E0 SP1 D1 I1 F1)

for season in 2324 2425; do
  for lg in "${LEAGUES[@]}"; do
    url="https://www.football-data.co.uk/mmz4281/${season}/${lg}.csv"
    out="${ROOT}/${season}/${lg}.csv"
    echo "GET $url"
    curl -fsSL "$url" -o "$out"
  done
done

echo "Done. Now run:"
echo "  python -c \"from scraper.football_data_loader import build_unified; build_unified('data/raw/football_data','data/raw/matches_2024.parquet')\""
echo "  python run.py analyze --in data/raw/matches_2024.parquet --out data/output/2024.xlsx --report data/output/2024.md"
