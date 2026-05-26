"""Nitter (X/Twitter) — modos: búsqueda + timeline cuentas específicas.

Frágil. Las instancias suelen estar rate-limited. Se intenta rotando.
Cuentas: Elon, Trump, periodistas, breaking news accounts.
"""
import requests
from bs4 import BeautifulSoup
from typing import Iterable, List, Dict
from .base import Signal, safe_text


def _try_instance(instance: str, path: str, timeout: int = 10) -> str | None:
    url = f"{instance.rstrip('/')}{path}"
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        return r.text
    except Exception:
        return None


def _parse_tweets(html: str, instance: str, source_label: str,
                  query_or_user: str, limit: int = 20) -> List[Signal]:
    """Parsea HTML Nitter para extraer tweets."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return []
    out = []
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
            t = s.get_text(strip=True).replace(",", "").replace(".", "").replace("K", "000").replace("M", "000000")
            try:
                if t.isdigit():
                    engagement += int(t)
            except Exception:
                pass
        date_el = div.select_one(".tweet-date a")
        href = date_el.get("href", "") if date_el else ""
        tweet_url = f"{instance}{href}" if href else instance
        out.append(Signal(
            source=f"nitter/{source_label}",
            title=safe_text(text.split("\n")[0], 240),
            text=safe_text(text, 1500),
            url=tweet_url,
            author=author,
            engagement=engagement,
            lang="auto",
            raw_metadata={"target": query_or_user, "source_label": source_label},
        ))
    return out


def fetch_account_timeline(instance: str, username: str, limit: int = 20) -> List[Signal]:
    """Pulla timeline de una cuenta concreta."""
    html = _try_instance(instance, f"/{username}")
    if not html:
        return []
    return _parse_tweets(html, instance, f"@{username}", username, limit)


def fetch_search(instance: str, query: str, limit: int = 20) -> List[Signal]:
    """Búsqueda."""
    enc = requests.utils.quote(query)
    html = _try_instance(instance, f"/search?f=tweets&q={enc}")
    if not html:
        return []
    return _parse_tweets(html, instance, "search", query, limit)


def collect_accounts(instances: Iterable[str], accounts: Iterable[str],
                     per_account_limit: int = 15) -> List[Signal]:
    """Pulla timelines de las cuentas usando la primera instancia que funcione."""
    signals = []
    instances = list(instances)
    for user in accounts:
        for inst in instances:
            res = fetch_account_timeline(inst, user, per_account_limit)
            if res:
                signals.extend(res)
                break
    return signals


def collect_searches(instances: Iterable[str], queries: Iterable[str],
                     per_query_limit: int = 20) -> List[Signal]:
    signals = []
    instances = list(instances)
    for q in queries:
        for inst in instances:
            res = fetch_search(inst, q, per_query_limit)
            if res:
                signals.extend(res)
                break
    return signals


def collect(instances: Iterable[str], queries: Iterable[str] = (),
            accounts: Iterable[str] = (),
            per_query_limit: int = 20,
            per_account_limit: int = 15) -> List[Signal]:
    """Backwards-compat + nuevo modo accounts."""
    out = []
    if accounts:
        out.extend(collect_accounts(instances, accounts, per_account_limit))
    if queries:
        out.extend(collect_searches(instances, queries, per_query_limit))
    return out
