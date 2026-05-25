"""Dexscreener — coins trending y búsqueda por texto.

API gratis: https://docs.dexscreener.com/api/reference
"""
import requests
from typing import List
from .base import safe_text


def search_pairs(query: str) -> List[dict]:
    """Busca pares por texto (ticker/name). Útil para crypto_hunter."""
    url = f"https://api.dexscreener.com/latest/dex/search?q={requests.utils.quote(query)}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []
    return _normalize_pairs(data.get("pairs") or [])


def trending_solana(limit: int = 30, min_mc: int = 5000, max_mc: int = 500000) -> List[dict]:
    """Aproxima 'trending' Solana usando boosts endpoint."""
    url = "https://api.dexscreener.com/token-boosts/top/v1"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return []
        boosts = resp.json() or []
    except Exception:
        return []

    out: List[dict] = []
    for b in boosts[:limit * 2]:
        if (b.get("chainId") or "").lower() != "solana":
            continue
        addr = b.get("tokenAddress")
        if not addr:
            continue
        try:
            r2 = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}", timeout=10)
            if r2.status_code != 200:
                continue
            d2 = r2.json()
            pairs = _normalize_pairs(d2.get("pairs") or [])
        except Exception:
            continue
        for p in pairs:
            mc = p.get("market_cap_usd") or 0
            if min_mc <= mc <= max_mc:
                out.append(p)
                break
        if len(out) >= limit:
            break
    return out


def _normalize_pairs(pairs: List[dict]) -> List[dict]:
    out = []
    for p in pairs:
        if not p:
            continue
        base = p.get("baseToken") or {}
        out.append({
            "ticker": safe_text(base.get("symbol", ""), 32),
            "name": safe_text(base.get("name", ""), 100),
            "mint": base.get("address", ""),
            "chain": p.get("chainId", ""),
            "dex": p.get("dexId", ""),
            "market_cap_usd": float(p.get("marketCap") or p.get("fdv") or 0),
            "liquidity_usd": float((p.get("liquidity") or {}).get("usd") or 0),
            "price_usd": float(p.get("priceUsd") or 0),
            "volume_h24": float((p.get("volume") or {}).get("h24") or 0),
            "url": p.get("url", ""),
            "source": "dexscreener",
        })
    return out
