"""nowscore.com 抓取骨架。

⚠️ 注意：
  - nowscore 是动态站点，页面结构和 API 端点会变。本文件给出的是「可工作的骨架 + 落地结构」。
  - 你在第一次跑之前，必须根据当前真实页面，补完所有标 `# TODO: confirm` 的地方。
  - 抓取频率：默认每请求 sleep 1.0–2.0 秒，请勿压站。
  - 数据落地：每个比赛日的原始 HTML / JSON 都保存在 data/raw/nowscore/<date>/，便于复核。

输出结构（每场比赛一条 dict，由 run.py 收集后转 DataFrame）：
  {
    "league": "EPL",
    "season": "2024/25",
    "match_date_local": "2024-10-19",
    "bj_date": "2024-10-19",
    "bj_kickoff": "22:30",
    "weekday": "周六",
    "is_weekend": True,
    "home": "曼城",
    "away": "南安普顿",
    "score_full": "1:0",
    "score_half": "0:0",
    "home_goals": 1,
    "away_goals": 0,
    "result": "主胜",
    "ah_open": -1.75,
    "ah_live": -1.5,
    "ah_final": -1.5,           # 临场盘 / 最终盘
    "ah_water_home": 0.85,
    "ah_water_away": 1.00,
    "ou_final": 2.5,
    "eu_home": 1.20, "eu_draw": 7.50, "eu_away": 13.00,
    "source_url": "https://live.nowscore.com/match/h2h-2143215",
    "raw_match_id": "2143215",
  }
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator, Optional

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

BASE = "https://live.nowscore.com"

# TODO: confirm — nowscore 历史比分列表可能用 schedule/h2h/league 端点之一
SCHEDULE_URL = BASE + "/football/schedule"            # ?date=YYYY-MM-DD
MATCH_DETAIL_URL = BASE + "/match/h2h-{match_id}"
ODDS_AH_URL = BASE + "/match/odds-asia-{match_id}"
ODDS_EU_URL = BASE + "/match/odds-eu-{match_id}"

# TODO: confirm — nowscore 的联赛中文名 (站内显示) ↔ 我们的 league code
LEAGUE_NAME_MAP = {
    "英超": "EPL", "英格兰超级联赛": "EPL",
    "西甲": "LaLiga", "西班牙甲组联赛": "LaLiga",
    "德甲": "Bundesliga", "德国甲组联赛": "Bundesliga",
    "意甲": "SerieA", "意大利甲组联赛": "SerieA",
    "法甲": "Ligue1", "法国甲组联赛": "Ligue1",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


@dataclass
class RawMatch:
    league: str
    bj_date: str
    bj_kickoff: str
    home_raw: str
    away_raw: str
    score_full: Optional[str]
    score_half: Optional[str]
    match_id: str
    source_url: str
    # odds 通过 odds_detail() 补
    ah_open: Optional[float] = None
    ah_live: Optional[float] = None
    ah_final: Optional[float] = None
    ah_water_home: Optional[float] = None
    ah_water_away: Optional[float] = None
    ou_final: Optional[float] = None
    eu_home: Optional[float] = None
    eu_draw: Optional[float] = None
    eu_away: Optional[float] = None


class NowscoreClient:
    def __init__(self, raw_dir: Path = Path("data/raw/nowscore"), throttle_s: float = 1.2):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.throttle_s = throttle_s

    # ---------------- 列表抓取 ----------------

    def iter_dates(self, start: date, end: date) -> Iterator[date]:
        d = start
        while d <= end:
            yield d
            d += timedelta(days=1)

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=16))
    def _get(self, url: str, **params) -> str:
        log.debug("GET %s %s", url, params)
        r = self.session.get(url, params=params, timeout=20)
        r.raise_for_status()
        time.sleep(self.throttle_s)
        return r.text

    def schedule_html(self, d: date) -> str:
        html = self._get(SCHEDULE_URL, date=d.isoformat())
        out = self.raw_dir / d.isoformat()
        out.mkdir(parents=True, exist_ok=True)
        (out / "schedule.html").write_text(html, encoding="utf-8")
        return html

    def parse_schedule(self, html: str, d: date) -> list[RawMatch]:
        """从日程页解析出当日五大联赛比赛。

        TODO: confirm — 真实 nowscore 日程页结构。当前实现假设：
          - 每场比赛在 <tr class="match-row"> 中
          - 联赛名在 <td class="league">、开球时间 <td class="time">
          - 主客队在 <td class="home"> / <td class="away">、比分 <td class="score">
          - data-mid 是 nowscore 比赛 id
        请在第一次跑通后用 BeautifulSoup 实际验证，并改这里。
        """
        soup = BeautifulSoup(html, "lxml")
        rows: list[RawMatch] = []
        for tr in soup.select("tr.match-row"):
            league_cn = (tr.select_one("td.league") or {}).get_text(strip=True) if tr.select_one("td.league") else ""
            league = LEAGUE_NAME_MAP.get(league_cn)
            if not league:
                continue
            kickoff = tr.select_one("td.time").get_text(strip=True)  # "HH:MM"
            home = tr.select_one("td.home").get_text(strip=True)
            away = tr.select_one("td.away").get_text(strip=True)
            score = (tr.select_one("td.score") or {}).get_text(strip=True) if tr.select_one("td.score") else None
            half = tr.get("data-half-score")
            mid = tr.get("data-mid") or tr.get("data-match-id") or ""
            rows.append(RawMatch(
                league=league,
                bj_date=d.isoformat(),
                bj_kickoff=kickoff,
                home_raw=home,
                away_raw=away,
                score_full=score,
                score_half=half,
                match_id=mid,
                source_url=MATCH_DETAIL_URL.format(match_id=mid),
            ))
        return rows

    # ---------------- 单场赔率 ----------------

    def odds_detail(self, match: RawMatch) -> RawMatch:
        """补齐亚盘初盘/即时盘/最终盘 + 大小球 + 欧赔。

        nowscore 的赔率页通常分公司展示（澳门、Bet365、Pinnacle 等）。
        ⚠ 「最终盘」请明确选定一家公司作为基准（建议 Pinnacle 或 澳门盘平均），
           在 run.py 中通过 --book pinnacle 切换。这里默认取 Pinnacle。
        """
        try:
            ah_html = self._get(ODDS_AH_URL.format(match_id=match.match_id))
            eu_html = self._get(ODDS_EU_URL.format(match_id=match.match_id))
        except Exception as e:
            log.warning("odds fetch failed for %s: %s", match.match_id, e)
            return match

        match = self._parse_ah(ah_html, match)
        match = self._parse_eu(eu_html, match)

        out = self.raw_dir / match.bj_date / match.match_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "ah.html").write_text(ah_html, encoding="utf-8")
        (out / "eu.html").write_text(eu_html, encoding="utf-8")
        return match

    def _parse_ah(self, html: str, m: RawMatch) -> RawMatch:
        """解析亚盘 — 取初盘 / 即时 / 最终盘 + 双边水位。

        TODO: confirm — nowscore 亚盘表行结构。当前实现假设：
          每行 tr.book-row 含: data-book (公司), td.open-line, td.live-line, td.final-line,
                                td.home-water, td.away-water。
        """
        soup = BeautifulSoup(html, "lxml")
        target_book = "Pinnacle"  # TODO: confirm 公司名
        row = soup.select_one(f'tr.book-row[data-book="{target_book}"]') \
              or soup.select_one("tr.book-row")  # fallback 第一家
        if not row:
            return m

        def f(sel: str) -> Optional[float]:
            el = row.select_one(sel)
            if not el:
                return None
            txt = el.get_text(strip=True).replace("／", "/")
            return _parse_handicap_token(txt)

        m.ah_open = f("td.open-line")
        m.ah_live = f("td.live-line")
        m.ah_final = f("td.final-line")
        # water 直接保留为 float
        try:
            m.ah_water_home = float(row.select_one("td.home-water").get_text(strip=True))
            m.ah_water_away = float(row.select_one("td.away-water").get_text(strip=True))
        except Exception:
            pass
        return m

    def _parse_eu(self, html: str, m: RawMatch) -> RawMatch:
        """解析欧赔 — 1X2 终盘。"""
        soup = BeautifulSoup(html, "lxml")
        row = soup.select_one('tr.book-row[data-book="Pinnacle"]') or soup.select_one("tr.book-row")
        if not row:
            return m
        try:
            m.eu_home = float(row.select_one("td.eu-home").get_text(strip=True))
            m.eu_draw = float(row.select_one("td.eu-draw").get_text(strip=True))
            m.eu_away = float(row.select_one("td.eu-away").get_text(strip=True))
        except Exception:
            pass
        return m


# ---------------- 亚盘字符串解析 ----------------

_HANDI_TOKEN = re.compile(r"^-?\d+(?:\.\d+)?$")


def _parse_handicap_token(s: str) -> Optional[float]:
    """把 nowscore 亚盘字串转 float（强队/主队视角的让球深度，让球为负数）。

    支持：
      "-1"            -> -1.0
      "-1.5"          -> -1.5
      "-1/-1.5"       -> -1.25   （等价于 -1.25）
      "0/0.5"         -> -0.25   （主队让半球 / 平手半球，等价 -0.25）
      "+0.5"          -> 0.5
      "0"             -> 0.0
    nowscore 站内常用「主队角度的让球」展示，对盘口公司而言负数=让球。
    """
    if not s:
        return None
    s = s.replace(" ", "").replace("受让", "+").replace("让", "-")
    if "/" in s:
        a, b = s.split("/", 1)
        va = _parse_handicap_token(a)
        vb = _parse_handicap_token(b)
        if va is None or vb is None:
            return None
        return (va + vb) / 2.0
    s = s.replace("+", "")
    if _HANDI_TOKEN.match(s):
        return float(s)
    return None
