"""Nitter (X/Twitter scraping best-effort) — gratis pero frágil.

Las instancias Nitter sufren rate-limits y cierres. El sistema NO depende de esto;
funciona como bonus si las instancias responden.
"""
import requests
from bs4 import BeautifulSoup
from typing import Iterable, List
from .base import Signal, safe_text


def search_instance(instance: str, query: str, limit: int = 20) -> List[Signal]:
    url = f"{instance}/search?f=tweets&q={requests.utils.quote(query)}"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception:
        return []

    out: List[Signal] = []
    for div in soup.select(".timeline-item")[:limit]:
        content = div.select_one(".tweet-content")
        if not content:
            continue
        text = content.get_text(" ", strip=True)
        if not text:
            continue
        author_el = div.select_one(".username")
        author = author_el.get_text(strip=True) if author_el else ""
        stats = div.select(".tweet-stat")
        engagement = 0
        for s in stats:
            t = s.get_text(strip=True).replace(",", "").replace(".", "")
            try:
                engagement += int(t) if t.isdigit() else 0
            except Exception:
                pass
        out.append(Signal(
            source="nitter",
            title=safe_text(text.split("\n")[0], 200),
            text=safe_text(text, 1500),
            url=instance,
            author=author,
            engagement=engagement,
            lang="auto",
            raw_metadata={"query": query, "instance": instance},
        ))
    return out


def collect(instances: Iterable[str], queries: Iterable[str], per_query_limit: int = 20) -> List[Signal]:
    signals: List[Signal] = []
    instances = list(instances)
    for q in queries:
        for inst in instances:
            res = search_instance(inst, q, limit=per_query_limit)
            if res:
                signals.extend(res)
                break  # primera instancia que funcione, pasamos a siguiente query
    return signals
