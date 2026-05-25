"""GMGN.ai scraper — trending tokens página pública.

GMGN tiene API gratis (registrar pubkey) pero también podemos scrape la web pública
de trending. Útil para discovery cross-chain rápido.
"""
import re
import time
import requests
from typing import List
from .base import Signal, safe_text

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36"

# El endpoint público que su frontend usa (no oficial, puede cambiar)
PUBLIC_API = "https://gmgn.ai/api/v1/token_list/sol/trend/{timeframe}"


def fetch_trending(timeframe: str = "1h", limit: int = 20) -> List[dict]:
    """Trending tokens de GMGN para Solana."""
    url = PUBLIC_API.format(timeframe=timeframe)
    try:
        r = requests.get(url, headers={"User-Agent": UA,
                                       "Accept": "application/json"},
                         timeout=15)
        if r.status_code != 200:
            return []
        data = r.json() or {}
        rank = (data.get("data") or {}).get("rank") or []
    except Exception:
        return []

    out = []
    for t in rank[:limit]:
        mint = t.get("address", "")
        if not mint:
            continue
        out.append({
            "ticker": safe_text(t.get("symbol", ""), 32),
            "name": safe_text(t.get("name", ""), 100),
            "mint": mint,
            "market_cap_usd": float(t.get("market_cap", 0) or 0),
            "liquidity_usd": float(t.get("liquidity", 0) or 0),
            "price_usd": float(t.get("price", 0) or 0),
            "price_change_1h": float(t.get("price_change_percent1h", 0) or 0),
            "price_change_24h": float(t.get("price_change_percent24h", 0) or 0),
            "volume_24h": float(t.get("volume_24h", 0) or 0),
            "holders": int(t.get("holder_count", 0) or 0),
            "smart_money_buy_count": int(t.get("smart_buy_24h", 0) or 0),
            "smart_money_sell_count": int(t.get("smart_sell_24h", 0) or 0),
            "source": "gmgn",
            "chain": "solana",
            "url": f"https://gmgn.ai/sol/token/{mint}",
        })
    return out


def collect_as_signals(timeframe: str = "1h", limit: int = 20,
                       pause: float = 0.5,
                       max_mc_usd: float = 500000) -> List[Signal]:
    """Discovery SOLO early stage (MC < max_mc_usd). NO surfacing consolidadas."""
    coins = fetch_trending(timeframe, limit)
    out = []
    for c in coins:
        ticker = c.get("ticker", "")
        if not ticker:
            continue
        mc = c.get("market_cap_usd", 0) or 0
        # Filtro clave: solo early stage
        if mc > max_mc_usd or mc < 1000:
            continue
        smart_buys = c.get("smart_money_buy_count", 0)
        smart_sells = c.get("smart_money_sell_count", 0)
        smart_net = smart_buys - smart_sells
        # Solo si smart money compra O movimiento fuerte (>15%)
        if smart_net <= 0 and abs(c.get("price_change_1h", 0)) < 15:
            continue
        engagement = int(abs(c.get("price_change_1h", 0)) * 3 + smart_net * 20)
        out.append(Signal(
            source="gmgn/trending",
            title=f"${ticker} GMGN — {c['price_change_1h']:+.1f}% 1h · smart buys {smart_buys}/{smart_sells}",
            text=f"MC ${c['market_cap_usd']:,.0f} · holders {c['holders']} · vol24h ${c['volume_24h']:,.0f}",
            url=c.get("url", ""),
            engagement=engagement,
            lang="en",
            raw_metadata={**c, "type": "gmgn_trending"},
        ))
    time.sleep(pause)
    return out
