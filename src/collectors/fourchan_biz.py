"""4chan /biz/ collector — JSON API público.

Por qué importa: Mechanism Capital declaró /biz/ "el mayor driver del mercado crypto".
MOG Coin nació aquí (+1800% en 2024). Ticker mentions en /biz/ son señales pre-mainstream.

API: https://github.com/4chan/4chan-API
Endpoint principal: https://a.4cdn.org/biz/catalog.json
Sin auth, gratis. Respeta rate-limit (1 req/sec).
"""
import re
import time
import requests
from collections import Counter
from typing import List, Dict
from .base import Signal, safe_text

UA = "Mozilla/5.0 (compatible; narrative-alpha-hunter/1.0)"

# Detecta tickers $XYZ (2-12 chars alphanum)
TICKER_RE = re.compile(r"(?<![A-Za-z])\$([A-Z][A-Z0-9]{1,11})\b")
# Detecta TICKER en mayúsculas pegado (sin $) — más ruido pero captura más
BARE_TICKER_RE = re.compile(r"\b([A-Z]{3,8})\b")


def _strip_html(s: str) -> str:
    """Quita tags HTML básicos sin lib pesada (4chan posts tienen <br>, <a>, etc.)."""
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&gt;", ">", s)
    s = re.sub(r"&lt;", "<", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&#039;", "'", s)
    s = re.sub(r"&quot;", '"', s)
    return s.strip()


def fetch_catalog(catalog_url: str) -> List[dict]:
    """Fetch /biz/ catalog (lista de threads activos con OP + últimas replies)."""
    try:
        r = requests.get(catalog_url, headers={"User-Agent": UA}, timeout=15)
        if r.status_code != 200:
            return []
        return r.json() or []
    except Exception:
        return []


def extract_threads(catalog: List[dict], max_threads: int = 60) -> List[dict]:
    """Devuelve threads activos del catálogo, ordenados por replies (más actividad primero)."""
    threads = []
    for page in catalog or []:
        for t in page.get("threads", []) or []:
            threads.append({
                "no": t.get("no"),
                "subject": _strip_html(t.get("sub", "")),
                "comment": _strip_html(t.get("com", "")),
                "replies": t.get("replies", 0),
                "images": t.get("images", 0),
                "time": t.get("time", 0),
                "last_modified": t.get("last_modified", 0),
            })
    threads.sort(key=lambda x: x["replies"], reverse=True)
    return threads[:max_threads]


def collect(catalog_url: str, max_threads: int = 60,
            min_ticker_mentions: int = 3,
            ignored_tickers: List[str] | None = None,
            pause: float = 1.0) -> List[Signal]:
    """Devuelve signals desde /biz/. Cada thread top genera 1 signal con OP + ticker counts."""
    ignored = set((ignored_tickers or []))
    catalog = fetch_catalog(catalog_url)
    if not catalog:
        return []
    threads = extract_threads(catalog, max_threads)

    # Agrega mention counts cross-thread para detectar tickers calientes
    global_ticker_counts = Counter()
    for t in threads:
        text = f"{t['subject']} {t['comment']}"
        for m in TICKER_RE.findall(text):
            if m not in ignored:
                global_ticker_counts[m] += 1

    out: List[Signal] = []
    # Genera 1 signal por thread popular
    for t in threads:
        text_combined = f"{t['subject']} {t['comment']}".strip()
        if not text_combined or len(text_combined) < 20:
            continue
        # Tickers en este thread
        thread_tickers = TICKER_RE.findall(text_combined)
        thread_tickers = [tk for tk in thread_tickers if tk not in ignored]
        title = t["subject"] or text_combined[:120]
        engagement = int(t.get("replies", 0)) * 2 + int(t.get("images", 0))
        out.append(Signal(
            source="4chan/biz",
            title=safe_text(title, 240),
            text=safe_text(text_combined, 1500),
            url=f"https://boards.4chan.org/biz/thread/{t['no']}",
            author="anon",
            engagement=engagement,
            lang="en",
            raw_metadata={
                "thread_id": t["no"],
                "replies": t["replies"],
                "images": t["images"],
                "tickers_in_thread": thread_tickers[:20],
                "time": t["time"],
            },
        ))

    # Aparte, genera signals de alta señal por TICKER caliente (≥min mentions)
    for ticker, count in global_ticker_counts.most_common(15):
        if count < min_ticker_mentions:
            continue
        out.append(Signal(
            source="4chan/biz/ticker",
            title=f"${ticker} — {count} mentions /biz/",
            text=f"Ticker ${ticker} mencionado {count} veces en threads activos de /biz/. Posible pre-mainstream alpha.",
            url=f"https://boards.4chan.org/biz/",
            engagement=count * 10,    # cada mention vale 10 (es señal alpha)
            lang="en",
            raw_metadata={"ticker": ticker, "mentions": count, "type": "ticker_velocity_biz"},
        ))

    time.sleep(pause)
    return out
