"""强队池 + 队名标准化（中 / 英 / 简繁 / 媒体口径）。

任何抓取来的 home/away 字符串都要先过 `normalize_team_name` 才能与强队池匹配。
"""

from __future__ import annotations

# ---------------- 强队池（按联赛） ----------------

STRONG_TEAMS_BY_LEAGUE: dict[str, list[str]] = {
    "EPL": ["曼城", "利物浦", "阿森纳", "曼联", "切尔西", "热刺", "纽卡斯尔"],
    "LaLiga": ["皇马", "巴萨", "马竞"],
    "Bundesliga": ["拜仁", "多特蒙德", "莱比锡", "勒沃库森"],
    "SerieA": ["国际米兰", "AC米兰", "尤文图斯", "那不勒斯", "罗马", "拉齐奥"],
    "Ligue1": ["巴黎圣日耳曼", "马赛", "摩纳哥", "里昂", "里尔"],
}

STRONG_TEAMS: set[str] = {t for v in STRONG_TEAMS_BY_LEAGUE.values() for t in v}


# ---------------- 名称别名映射 ----------------
# key = 任意可能出现的原始字符串（小写后比对），value = 标准强队名

ALIASES: dict[str, str] = {
    # EPL
    "manchester city": "曼城", "man city": "曼城", "mci": "曼城", "曼彻斯特城": "曼城",
    "liverpool": "利物浦", "lfc": "利物浦",
    "arsenal": "阿森纳", "ars": "阿森纳", "阿仙奴": "阿森纳",
    "manchester united": "曼联", "man utd": "曼联", "man united": "曼联", "曼彻斯特联": "曼联",
    "chelsea": "切尔西", "che": "切尔西", "车路士": "切尔西",
    "tottenham": "热刺", "tottenham hotspur": "热刺", "spurs": "热刺", "托特纳姆热刺": "热刺",
    "newcastle": "纽卡斯尔", "newcastle united": "纽卡斯尔", "纽卡素": "纽卡斯尔",

    # LaLiga
    "real madrid": "皇马", "皇家马德里": "皇马",
    "barcelona": "巴萨", "巴塞罗那": "巴萨", "fc barcelona": "巴萨",
    "atletico madrid": "马竞", "atlético madrid": "马竞", "马德里竞技": "马竞",

    # Bundesliga
    "bayern munich": "拜仁", "bayern münchen": "拜仁", "拜仁慕尼黑": "拜仁", "fc bayern": "拜仁",
    "dortmund": "多特蒙德", "bvb": "多特蒙德", "borussia dortmund": "多特蒙德",
    "rb leipzig": "莱比锡", "leipzig": "莱比锡", "rb莱比锡": "莱比锡",
    "leverkusen": "勒沃库森", "bayer leverkusen": "勒沃库森", "勒沃": "勒沃库森",

    # Serie A
    "inter": "国际米兰", "internazionale": "国际米兰", "inter milan": "国际米兰", "国米": "国际米兰",
    "ac milan": "AC米兰", "milan": "AC米兰", "米兰": "AC米兰",
    "juventus": "尤文图斯", "尤文": "尤文图斯", "juve": "尤文图斯",
    "napoli": "那不勒斯", "ssc napoli": "那不勒斯",
    "as roma": "罗马", "roma": "罗马",
    "lazio": "拉齐奥", "ss lazio": "拉齐奥",

    # Ligue 1
    "psg": "巴黎圣日耳曼", "paris saint-germain": "巴黎圣日耳曼", "paris sg": "巴黎圣日耳曼", "巴黎": "巴黎圣日耳曼",
    "marseille": "马赛", "om": "马赛", "olympique marseille": "马赛",
    "monaco": "摩纳哥", "as monaco": "摩纳哥",
    "lyon": "里昂", "ol": "里昂", "olympique lyonnais": "里昂",
    "lille": "里尔", "losc": "里尔", "losc lille": "里尔",
}


def normalize_team_name(raw: str) -> str:
    """把抓到的任意写法映射到标准队名；非强队原样返回（去空白）。"""
    if not raw:
        return ""
    s = raw.strip()
    # 直接命中标准名
    if s in STRONG_TEAMS:
        return s
    # 小写别名匹配
    return ALIASES.get(s.lower(), s)


def is_strong_team(name: str) -> bool:
    return normalize_team_name(name) in STRONG_TEAMS


def league_of_team(name: str) -> str | None:
    n = normalize_team_name(name)
    for lg, lst in STRONG_TEAMS_BY_LEAGUE.items():
        if n in lst:
            return lg
    return None
