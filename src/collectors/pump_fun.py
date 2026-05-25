"""Pump.fun — coins ultra-tempranas en Solana.

Pump.fun ha segmentado sus endpoints; intentamos varios con fallback.
También aplicamos filtros de calidad (anti-rug, anti-spam).
"""
import requests
import time
from typing import List
from .base import safe_text


ENDPOINTS = [
    "https://frontend-api-v3.pump.fun/coins",
    "https://advanced-api-v2.pump.fun/coins/list",
    "https://frontend-api-v2.pump.fun/coins",
    "https://frontend-api.pump.fun/coins",
]

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def _try_endpoint(url: str, params: dict, timeout: int = 12):
    try:
        resp = requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": UA, "Accept": "application/json"})
        if resp.status_code == 200:
            data = resp.json()
            # algunas variantes devuelven {"coins": [...]}, otras lista directa
            if isinstance(data, dict) and "coins" in data:
                return data["coins"]
            if isinstance(data, list):
                return data
        return None
    except Exception:
        return None


def fetch_new_coins(limit: int = 100, min_mc: int = 1000, max_mc: int = 200000,
                    require_socials: bool = True,
                    require_description: bool = True,
                    min_description_chars: int = 20) -> List[dict]:
    """Devuelve coins nuevas (sorted by created_timestamp DESC) con filtros de calidad."""
    params = {
        "offset": 0,
        "limit": min(limit, 100),
        "sort": "created_timestamp",
        "order": "DESC",
        "includeNsfw": "false",
    }

    raw = None
    for ep in ENDPOINTS:
        raw = _try_endpoint(ep, params)
        if raw is not None and len(raw) > 0:
            break
        time.sleep(0.4)

    if not raw:
        return []

    out: List[dict] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        mc = c.get("usd_market_cap") or c.get("market_cap") or c.get("marketCap") or 0
        try:
            mc = float(mc)
        except Exception:
            mc = 0
        if mc < min_mc or mc > max_mc:
            continue

        twitter = c.get("twitter") or ""
        telegram = c.get("telegram") or ""
        website = c.get("website") or ""
        description = safe_text(c.get("description", ""), 500)

        if require_socials and not (twitter or telegram or website):
            continue
        if require_description and (not description or len(description) < min_description_chars):
            continue

        out.append({
            "ticker": safe_text(c.get("symbol") or c.get("ticker", ""), 32),
            "name": safe_text(c.get("name", ""), 100),
            "mint": c.get("mint") or c.get("address", ""),
            "description": description,
            "market_cap_usd": mc,
            "twitter": twitter,
            "telegram": telegram,
            "website": website,
            "image": c.get("image_uri") or c.get("image") or "",
            "created_ts": c.get("created_timestamp") or c.get("createdAt"),
            "creator": c.get("creator") or "",
            "source": "pump.fun",
            "chain": "solana",
            "url": f"https://pump.fun/coin/{c.get('mint') or c.get('address','')}",
        })
    return out
