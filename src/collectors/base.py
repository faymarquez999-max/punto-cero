"""Tipos comunes para los collectors."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import hashlib


@dataclass
class Signal:
    """Una señal recolectada de cualquier fuente. Unidad atómica de información."""
    source: str                       # "reddit", "google_news", "bluesky", etc.
    title: str
    text: str = ""
    url: str = ""
    author: str = ""
    engagement: int = 0               # upvotes, likes, comments
    lang: str = "en"
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_metadata: dict = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Hash estable para deduplicar la misma señal entre ciclos."""
        h = hashlib.sha1()
        h.update(self.source.encode())
        h.update(self.title[:200].lower().encode())
        h.update(self.url.encode())
        return h.hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self)


def safe_text(s: Optional[str], max_len: int = 1500) -> str:
    if not s:
        return ""
    return s.replace("\x00", "").strip()[:max_len]
