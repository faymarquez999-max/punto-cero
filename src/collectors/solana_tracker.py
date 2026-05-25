"""Solana Tracker collector — trending memecoins endpoint.

API: https://docs.solanatracker.io/
Free tier registrándose en solanatracker.io. Sin key funciona con rate limits muy bajos.
"""
import os
import time
import requests
from typing import List, Dict
from .base import Signal, safe_text


API_BASE = "https://data.solanatracker.io"


def _headers() -> dict:
    key = os.getenv("SOLANATRACKER_API_KEY", "")
    h = {"User-Agent": "Mozilla/5.0"}
    if key:
        h["x-api-key"] = key
    return h


def fetch_trending(timeframe: str = "1h", limit: int = 30) -> List[Dict]:
    """Trending tokens por volumen en timeframe (5m/1h/6h/24h)."""
    url = f"{API_BASE}/tokens/trending/{timeframe}"
    try:
        r = requests.get(url, headers=_headers(), timeout=15)
        if r.status_code != 200:
            return []
        data = r.json() or []
    except Exception:
        return []

    out = []
    for t in data[:limit]:
        token = t.get("token") or t
        pools = t.get("pools") or []
        pool = pools[0] if pools else {}
        events = t.get("events") or {}
        out.append({
            "ticker": safe_text(token.get("symbol", ""), 32),
            "name": safe_text(token.get("name", ""), 100),
            "mint": token.get("mint") or token.get("address", ""),
            "description": safe_text(token.get("description", ""), 300),
            "image": token.get("image", ""),
            "market_cap_usd": float(pool.get("marketCap", {}).get("usd", 0) or 0),
            "liquidity_usd": float(pool.get("liquidity", {}).get("usd", 0) or 0),
            "price_usd": float(pool.get("price", {}).get("usd", 0) or 0),
            "volume_24h": float(pool.get("txns", {}).get("volume", 0) or 0),
            "price_change_5m": float(events.get("5m", {}).get("priceChangePercentage", 0) or 0),
            "price_change_1h": float(events.get("1h", {}).get("priceChangePercentage", 0) or 0),
            "price_change_24h": float(events.get("24h", {}).get("priceChangePercentage", 0) or 0),
            "twitter": token.get("twitter", ""),
            "telegram": token.get("telegram", ""),
            "website": token.get("website", ""),
            "source": "solana_tracker",
            "chain": "solana",
            "url": f"https://www.solanatracker.io/coin/{token.get('mint','')}",
        })
    return out


def search_tokens(query: str, limit: int = 10) -> List[Dict]:
    """Búsqueda por texto/ticker. Útil para crypto_hunter event-linked search."""
    url = f"{API_BASE}/search"
    try:
        r = requests.get(url, params={"query": query, "limit": limit},
                         headers=_headers(), timeout=10)
        if r.status_code != 200:
            return []
        data = r.json() or []
    except Exception:
        return []
    return data if isinstance(data, list) else (data.get("data") or [])


def collect_as_signals(timeframe: str = "1h", limit: int = 30,
                       pause: float = 0.5,
                       max_mc_usd: float = 500000) -> List[Signal]:
    """Wrapper — surfacing SOLO coins early stage (MC < max_mc_usd).

    NO queremos surfacing FARTCOIN/GOAT/TROLL-tier consolidados. Solo early.
    """
    coins = fetch_trending(timeframe, limit)
    out = []
    for c in coins:
        ticker = c.get("ticker", "")
        if not ticker:
            continue
        mc = c.get("market_cap_usd", 0) or 0
        # FILTRO CLAVE: solo early stage (<500k por defecto)
        if mc > max_mc_usd:
            continue
        if mc < 1000:   # ignora dust
            continue
        change_1h = c.get("price_change_1h", 0)
        if abs(change_1h) < 10:   # solo movimiento real
            continue
        out.append(Signal(
            source="solana_tracker/trending",
            title=f"${ticker} trending — {change_1h:+.1f}% 1h",
            text=(c.get("description") or "")[:400] +
                 f" | MC ${c.get('market_cap_usd', 0):,.0f}",
            url=c.get("url", ""),
            engagement=int(max(0, change_1h) * 5),
            lang="en",
            raw_metadata={**c, "type": "trending_coin"},
        ))
    time.sleep(pause)
    return out
