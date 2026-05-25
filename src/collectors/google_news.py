"""Google News RSS — multi-feed con scoring de novedad + cross-feed."""
import feedparser
from datetime import datetime, timezone
from typing import Iterable, List
from .base import Signal, safe_text


def _parse_pub(entry) -> float:
    """Unix timestamp del entry o 0."""
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return float(datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).timestamp())
    except Exception:
        pass
    return 0.0


def fetch_feed(url: str, limit: int = 30) -> List[Signal]:
    try:
        d = feedparser.parse(url)
    except Exception:
        return []
    now = datetime.now(timezone.utc).timestamp()
    out: List[Signal] = []
    for entry in d.entries[:limit]:
        title = getattr(entry, "title", "")
        if not title:
            continue
        pub_ts = _parse_pub(entry)
        # Score base: novedad — items <2h tienen score alto, decae después
        age_h = max(0.1, (now - pub_ts) / 3600.0) if pub_ts else 6.0
        engagement = max(10, int(120 / age_h))    # 120 si <1h, baja gradual
        source_name = ""
        try:
            src = getattr(entry, "source", None)
            if src:
                source_name = getattr(src, "title", "") or src.get("title", "") if hasattr(src, "get") else ""
        except Exception:
            pass
        out.append(Signal(
            source="google_news",
            title=safe_text(title, 300),
            text=safe_text(getattr(entry, "summary", ""), 1500),
            url=getattr(entry, "link", ""),
            author=source_name,
            engagement=engagement,
            lang="auto",
            raw_metadata={
                "published": getattr(entry, "published", ""),
                "published_ts": pub_ts,
                "feed_url": url,
            },
        ))
    return out


def collect(feeds: Iterable[str], per_feed_limit: int = 30) -> List[Signal]:
    signals: List[Signal] = []
    seen_urls = set()
    for url in feeds:
        for s in fetch_feed(url, limit=per_feed_limit):
            if s.url and s.url in seen_urls:
                continue
            seen_urls.add(s.url)
            signals.append(s)
    return signals
