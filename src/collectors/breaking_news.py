"""Breaking news collector — Reuters, AP, BBC, Bloomberg, TMZ, etc.

Pull de RSS feeds especializados en breaking news. Mejor que Google News para velocidad.
Cada feed se etiqueta con su nombre para que el clustering identifique cross-source rápido.
"""
import feedparser
from datetime import datetime, timezone
from typing import List, Dict
from .base import Signal, safe_text


def _parse_pub(entry) -> float:
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return float(datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).timestamp())
    except Exception:
        pass
    return 0.0


def fetch_feed(url: str, source_name: str, limit: int = 30) -> List[Signal]:
    try:
        d = feedparser.parse(url)
    except Exception:
        return []
    now_ts = datetime.now(timezone.utc).timestamp()
    out: List[Signal] = []
    for entry in d.entries[:limit]:
        title = getattr(entry, "title", "")
        if not title:
            continue
        pub_ts = _parse_pub(entry)
        # Breaking news → engagement decae con edad
        age_h = max(0.1, (now_ts - pub_ts) / 3600.0) if pub_ts else 6.0
        # Engagement base más alto (estas fuentes son señales fuertes)
        engagement = max(15, int(200 / age_h))
        out.append(Signal(
            source=f"breaking_news/{source_name}",
            title=safe_text(title, 300),
            text=safe_text(getattr(entry, "summary", ""), 1500),
            url=getattr(entry, "link", ""),
            author=source_name,
            engagement=engagement,
            lang="en",
            raw_metadata={
                "published": getattr(entry, "published", ""),
                "published_ts": pub_ts,
                "feed_source": source_name,
            },
        ))
    return out


def collect(feed_configs: List[Dict], per_feed_limit: int = 25) -> List[Signal]:
    """feed_configs: lista de {url, name}"""
    signals: List[Signal] = []
    seen_urls = set()
    for cfg in feed_configs or []:
        url = cfg.get("url") if isinstance(cfg, dict) else cfg
        name = cfg.get("name", "unknown") if isinstance(cfg, dict) else "unknown"
        for s in fetch_feed(url, name, limit=per_feed_limit):
            if s.url and s.url in seen_urls:
                continue
            seen_urls.add(s.url)
            signals.append(s)
    return signals
