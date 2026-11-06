"""情绪调色板与情绪地图。

打卡时用户挑一个情绪（网页上的小鸟），存进 moods 表：score 用于趋势，words 以情绪名开头。
情绪地图按情绪名统计次数，每种情绪对应一只小鸟。
"""

from __future__ import annotations

import collections
import datetime as dt

# 名字: (分数 1–10, 颜色, 表情类型)
PALETTE: dict[str, tuple[int, str, str]] = {
    "开心": (9, "#F6C453", "happy"),
    "期待": (8, "#F4A6B7", "happy"),
    "平静": (7, "#7FCFAF", "calm"),
    "疲惫": (4, "#B4AEC8", "tired"),
    "焦虑": (3, "#F2A65A", "anxious"),
    "委屈": (3, "#C39BD3", "sad"),
    "生气": (3, "#E57B6F", "angry"),
    "难过": (2, "#7FA7D9", "sad"),
}


# 与随包的小鸟素材清单对应，桃脸牡丹鹦鹉用作品牌图标。
MOOD_BIRDS = {
    "期待": "mandarin-duck",
    "平静": "green-white-eye",
    "疲惫": "owl",
    "焦虑": "cockatiel",
    "委屈": "white-bush-tit",
    "生气": "java-sparrow",
    "开心": "rainbow-swallow",
    "难过": "blue-tit",
}


def palette() -> list[dict]:
    return [
        {"name": name, "score": score, "color": color, "face": face, "bird": MOOD_BIRDS[name]}
        for name, (score, color, face) in PALETTE.items()
    ]


def name_of(words: str) -> str | None:
    """打卡记录对应的情绪名：取 words 里第一个出现的调色板情绪。"""
    hits = [(words.find(k), k) for k in PALETTE if k in (words or "")]
    return min(hits)[1] if hits else None


def from_score(score: int) -> str:
    """没有情绪名的打卡（如 IM 里的 /mood 7），按分数归到最近的情绪。"""
    return min(PALETTE, key=lambda k: (abs(PALETTE[k][0] - score), -PALETTE[k][0]))


def emotion_map(store, today: str, days: int = 30) -> dict:
    end = dt.date.fromisoformat(today)
    start = (end - dt.timedelta(days=days - 1)).isoformat()
    rows = store.moods(start, today)
    counts: collections.Counter = collections.Counter()
    by_day: dict[str, list[str]] = collections.defaultdict(list)
    for r in rows:
        name = name_of(r["words"]) or from_score(r["score"])
        counts[name] += 1
        by_day[r["date"]].append(name)
    bubbles = [{"name": k, "count": n, "color": PALETTE[k][1], "score": PALETTE[k][0]} for k, n in counts.most_common()]
    days_out = [{"date": d, "emotion": collections.Counter(v).most_common(1)[0][0],
                 "color": PALETTE[collections.Counter(v).most_common(1)[0][0]][1], "count": len(v)}
                for d, v in sorted(by_day.items())]
    return {"start": start, "end": today, "total": len(rows), "bubbles": bubbles, "days": days_out,
            "recent": [{**r, "emotion": name_of(r["words"]) or from_score(r["score"])} for r in rows[-12:]][::-1]}
