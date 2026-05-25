"""Reddit collector — JSON público con UA realista + retry + hot/rising."""
import time
import random
import requests
from typing import Iterable, List
from .base import Signal, safe_text

UA_POOL = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
]


def _ua() -> str:
    return random.choice(UA_POOL)


def _fetch(url: str, retries: int = 2) -> dict | None:
    last = None
    for i in range(retries + 1):
        try:
            r = requests.get(url, headers={"User-Agent": _ua(),
                                           "Accept": "application/json"},
                             timeout=12)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(2 + i * 2)
                continue
            return None
        except Exception as e:
            last = e
            time.sleep(1 + i)
    return None


def fetch_listing(subreddit: str, listing: str = "hot", limit: int = 25) -> List[Signal]:
    """listing: hot, rising, new, top"""
    url = f"https://www.reddit.com/r/{subreddit}/{listing}.json?limit={limit}"
    data = _fetch(url)
    if not data:
        return []

    out: List[Signal] = []
    for child in data.get("data", {}).get("children", []) or []:
        d = child.get("data", {}) or {}
        if d.get("stickied"):
            continue
        title = d.get("title", "")
        if not title:
            continue
        score = int(d.get("score", 0) or 0)
        comments = int(d.get("num_comments", 0) or 0)
        out.append(Signal(
            source=f"reddit/r/{subreddit}/{listing}",
            title=safe_text(title, 300),
            text=safe_text(d.get("selftext", ""), 1500),
            url="https://reddit.com" + d.get("permalink", ""),
            author=d.get("author", ""),
            engagement=score + comments * 2,    # comentarios pesan más para virales
            lang="en",
            raw_metadata={
                "score": score,
                "num_comments": comments,
                "subreddit": subreddit,
                "listing": listing,
                "created_utc": d.get("created_utc"),
                "upvote_ratio": d.get("upvote_ratio"),
            },
        ))
    return out


def collect(subreddits: Iterable[str], hot_limit: int = 30,
            min_score: int = 100, pause: float = 1.5,
            also_rising: bool = True) -> List[Signal]:
    signals: List[Signal] = []
    for sub in subreddits:
        # hot
        items = fetch_listing(sub, "hot", limit=hot_limit)
        for s in items:
            if s.engagement >= min_score:
                signals.append(s)
        time.sleep(pause)
        # rising (señal más temprana)
        if also_rising:
            items = fetch_listing(sub, "rising", limit=max(10, hot_limit // 2))
            for s in items:
                # rising posts pueden tener menos engagement pero son nuevos
                if s.engagement >= max(30, min_score // 3):
                    signals.append(s)
            time.sleep(pause)
    return signals
