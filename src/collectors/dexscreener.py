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
        price_change = p.get("priceChange") or {}
        volume = p.get("volume") or {}
        txns = p.get("txns") or {}
        out.append({
            "ticker": safe_text(base.get("symbol", ""), 32),
            "name": safe_text(base.get("name", ""), 100),
            "mint": base.get("address", ""),
            "chain": p.get("chainId", ""),
            "dex": p.get("dexId", ""),
            "market_cap_usd": float(p.get("marketCap") or p.get("fdv") or 0),
            "liquidity_usd": float((p.get("liquidity") or {}).get("usd") or 0),
            "price_usd": float(p.get("priceUsd") or 0),
            "volume_h24": float(volume.get("h24") or 0),
            "volume_h1": float(volume.get("h1") or 0),
            "volume_m5": float(volume.get("m5") or 0),
            "price_change_5m": float(price_change.get("m5") or 0),
            "price_change_1h": float(price_change.get("h1") or 0),
            "price_change_24h": float(price_change.get("h24") or 0),
            "txns_h1_buys": int((txns.get("h1") or {}).get("buys") or 0),
            "txns_h1_sells": int((txns.get("h1") or {}).get("sells") or 0),
            # created_ts: pairCreatedAt está en ms — normalizamos
            "created_ts": p.get("pairCreatedAt"),
            "pair_created_at": p.get("pairCreatedAt"),
            "url": p.get("url", ""),
            "source": "dexscreener",
        })
    return out
