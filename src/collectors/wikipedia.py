"""Wikipedia Recent Changes — detector pre-mainstream.

Cuando pasa algo importante con una figura pública o tema, los editores de Wikipedia
actualizan en MINUTOS. Es señal alpha.

Estrategia:
1. Para una lista de páginas "high value" (Trump, Musk, etc.), pollea revisions recientes
2. Si una página recibe ≥N ediciones en ≤30min → algo está pasando
3. Genera signal con título de la página + nº de ediciones + summary del último edit
4. También: recent changes globales filtrando a páginas trending

API gratis: https://www.mediawiki.org/wiki/API:Main_page
"""
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from .base import Signal, safe_text


WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_PAGE_URL = "https://en.wikipedia.org/wiki/"


def fetch_revisions(page_title: str, since_minutes: int = 30, limit: int = 20) -> List[Dict]:
    """Devuelve las revisiones recientes de una página."""
    rvstart = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "titles": page_title,
        "rvprop": "timestamp|user|comment|size",
        "rvlimit": limit,
        "rvend": rvstart,
        "rvdir": "older",
    }
    try:
        r = requests.get(WIKI_API, params=params, timeout=12,
                         headers={"User-Agent": "punto-cero-bot/1.0"})
        if r.status_code != 200:
            return []
        data = r.json()
        pages = (data.get("query") or {}).get("pages") or {}
        all_revs = []
        for _pid, page in pages.items():
            revs = page.get("revisions") or []
            all_revs.extend(revs)
        return all_revs
    except Exception:
        return []


def fetch_recent_changes_global(limit: int = 50, since_minutes: int = 30) -> List[Dict]:
    """Pull recent changes globales (filtrando minor edits, bots)."""
    rcstart = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rcend = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "action": "query",
        "format": "json",
        "list": "recentchanges",
        "rcnamespace": 0,  # solo artículos
        "rcprop": "title|timestamp|user|comment|sizes",
        "rcshow": "!minor|!bot|!anon",
        "rclimit": limit,
        "rcstart": rcstart,
        "rcend": rcend,
        "rcdir": "older",
    }
    try:
        r = requests.get(WIKI_API, params=params, timeout=12,
                         headers={"User-Agent": "punto-cero-bot/1.0"})
        if r.status_code != 200:
            return []
        return (r.json() or {}).get("query", {}).get("recentchanges", []) or []
    except Exception:
        return []


def collect(watched_pages: List[str], edit_spike_threshold: int = 5,
            check_global: bool = True, pause: float = 0.5) -> List[Signal]:
    """Devuelve signals para páginas con picos de edición + global trending."""
    import time
    signals: List[Signal] = []

    # 1. Watched pages — buscar spikes
    for page in watched_pages:
        revs = fetch_revisions(page, since_minutes=30, limit=20)
        if len(revs) >= edit_spike_threshold:
            # Spike detectado
            last_comments = [r.get("comment", "")[:120] for r in revs[:5] if r.get("comment")]
            display_title = page.replace("_", " ")
            signals.append(Signal(
                source="wikipedia/spike",
                title=f"Wiki edit spike: {display_title} ({len(revs)} edits en 30min)",
                text=f"Página '{display_title}' recibió {len(revs)} ediciones en últimos 30 minutos. "
                     f"Algo está pasando. Comments recientes: {' | '.join(last_comments)}",
                url=WIKI_PAGE_URL + page,
                author="wiki-editors",
                engagement=len(revs) * 15,  # heavy weight, es señal pre-mainstream
                lang="en",
                raw_metadata={
                    "page": page,
                    "edit_count_30min": len(revs),
                    "type": "edit_spike",
                },
            ))
        time.sleep(pause)

    # 2. Global recent changes — agregamos titles con engagement masivo
    if check_global:
        rc = fetch_recent_changes_global(limit=80, since_minutes=20)
        if rc:
            # Agrupar por title — el mismo article con varios edits es spike
            title_counts = {}
            title_comments = {}
            for r in rc:
                title = r.get("title", "")
                if not title:
                    continue
                title_counts[title] = title_counts.get(title, 0) + 1
                if r.get("comment"):
                    title_comments.setdefault(title, []).append(r["comment"][:100])

            for title, count in title_counts.items():
                if count >= 3:    # threshold para trending global
                    # Skip si ya estaba en watched (evitar duplicados)
                    norm = title.replace(" ", "_")
                    if norm in watched_pages:
                        continue
                    comments = title_comments.get(title, [])[:3]
                    signals.append(Signal(
                        source="wikipedia/trending",
                        title=f"Wiki trending: {title} ({count} edits)",
                        text=f"Artículo '{title}' recibió {count} ediciones recientes. "
                             f"Comments: {' | '.join(comments)}",
                        url=WIKI_PAGE_URL + norm,
                        author="wiki-editors",
                        engagement=count * 10,
                        lang="en",
                        raw_metadata={
                            "page": title,
                            "edit_count": count,
                            "type": "global_trending",
                        },
                    ))

    return signals
