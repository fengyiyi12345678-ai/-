"""主入口：scrape / load-csv / analyze 三个子命令。

典型流程：
  1. python run.py scrape --start 2024-01-01 --end 2024-12-31
     # 抓取 nowscore，落地 data/raw/nowscore/<date>/ + 汇总 parquet
  2. python run.py analyze --in data/raw/matches_2024.parquet \
                           --out data/output/2024_strong_team_handicap.xlsx \
                           --report data/output/2024_report.md
  3. python run.py tracking --out data/output/live_tracking_template.xlsx
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from scraper.nowscore_client import NowscoreClient, RawMatch
from scraper.csv_loader import load_csv
from core.normalize import normalize_matches
from core.handicap import compute_handicap_result
from core.enrich import enrich
from analysis.aggregator import build_all_sheets
from analysis.report import build_report
from output.excel_writer import write_xlsx
from output.tracking_template import build_tracking_xlsx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("run")


def _to_dataframe(matches: list[RawMatch]) -> pd.DataFrame:
    rows = []
    for m in matches:
        rows.append({
            "league": m.league,
            "bj_date": m.bj_date,
            "bj_kickoff": m.bj_kickoff,
            "home": m.home_raw,
            "away": m.away_raw,
            "score_full": m.score_full,
            "score_half": m.score_half,
            "ah_open": m.ah_open,
            "ah_live": m.ah_live,
            "ah_final": m.ah_final,
            "ah_water_home": m.ah_water_home,
            "ah_water_away": m.ah_water_away,
            "ou_final": m.ou_final,
            "eu_home": m.eu_home,
            "eu_draw": m.eu_draw,
            "eu_away": m.eu_away,
            "source_url": m.source_url,
        })
    return pd.DataFrame(rows)


def cmd_scrape(args):
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    cli = NowscoreClient()
    all_matches: list[RawMatch] = []
    for d in cli.iter_dates(start, end):
        try:
            html = cli.schedule_html(d)
            day_matches = cli.parse_schedule(html, d)
        except Exception as e:
            log.warning("schedule fetch failed %s: %s", d, e)
            continue
        for m in day_matches:
            try:
                m = cli.odds_detail(m)
            except Exception as e:
                log.warning("odds fetch failed %s %s: %s", d, m.match_id, e)
            all_matches.append(m)
        log.info("%s: %d matches collected", d, len(day_matches))
    df = _to_dataframe(all_matches)
    out = Path(args.out or "data/raw/matches.parquet")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out) if str(out).endswith(".parquet") else df.to_csv(out, index=False)
    log.info("saved %d rows -> %s", len(df), out)


def cmd_load_csv(args):
    df = load_csv(args.path)
    out = Path(args.out or "data/raw/matches.parquet")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    log.info("loaded %d rows -> %s", len(df), out)


def cmd_analyze(args):
    in_path = Path(args.inp)
    if in_path.suffix == ".csv":
        df = pd.read_csv(in_path)
    else:
        df = pd.read_parquet(in_path)
    df = normalize_matches(df)
    df = enrich(df)
    df = compute_handicap_result(df)

    sheets = build_all_sheets(df)
    xlsx = write_xlsx(sheets, args.out)
    log.info("wrote excel -> %s (%d sheets)", xlsx, len(sheets))

    report_md = build_report(sheets)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(report_md, encoding="utf-8")
    log.info("wrote report -> %s", args.report)


def cmd_tracking(args):
    out = build_tracking_xlsx(args.out)
    log.info("wrote tracking template -> %s", out)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("scrape", help="抓取 nowscore")
    pa.add_argument("--start", required=True)
    pa.add_argument("--end", required=True)
    pa.add_argument("--leagues", default="epl,laliga,bundesliga,seriea,ligue1")
    pa.add_argument("--out", default=None)
    pa.set_defaults(func=cmd_scrape)

    pl = sub.add_parser("load-csv", help="从 CSV 兜底加载")
    pl.add_argument("--path", required=True)
    pl.add_argument("--out", default=None)
    pl.set_defaults(func=cmd_load_csv)

    pn = sub.add_parser("analyze", help="生成 21 Sheet Excel + 中文报告")
    pn.add_argument("--in", dest="inp", required=True)
    pn.add_argument("--out", required=True)
    pn.add_argument("--report", required=True)
    pn.set_defaults(func=cmd_analyze)

    pt = sub.add_parser("tracking", help="生成实盘跟踪表模板")
    pt.add_argument("--out", required=True)
    pt.set_defaults(func=cmd_tracking)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
