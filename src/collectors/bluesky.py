"""Bluesky search público (gratis, sin auth)."""
import requests
from typing import Iterable, List
from .base import Signal, safe_text

API = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def search(query: str, limit: int = 25) -> List[Signal]:
    try:
        resp = requests.get(API, params={"q": query, "limit": limit}, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    out: List[Signal] = []
    for p in data.get("posts", []):
        rec = p.get("record", {}) or {}
        text = rec.get("text", "")
        if not text:
            continue
        author = (p.get("author") or {}).get("handle", "")
        out.append(Signal(
            source="bluesky",
            title=safe_text(text.split("\n")[0], 200),
            text=safe_text(text, 1500),
            url=f"https://bsky.app/profile/{author}",
            author=author,
            engagement=int(p.get("likeCount", 0)) + int(p.get("repostCount", 0)),
            lang="auto",
            raw_metadata={"query": query},
        ))
    return out


def collect(queries: Iterable[str], per_query_limit: int = 25) -> List[Signal]:
    signals: List[Signal] = []
    for q in queries:
        signals.extend(search(q, limit=per_query_limit))
    return signals
