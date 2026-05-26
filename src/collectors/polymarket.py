"""Polymarket collector — cambios de probabilidad como señal anticipatoria.

Cuando algo está a punto de pasar (rumor, leak), los mercados de predicción
mueven probabilidades ANTES de que las noticias mainstream lo confirmen.
Captar deltas grandes = early signal.

API gratis: https://gamma-api.polymarket.com
"""
import requests
from datetime import datetime, timezone
from typing import List, Dict
from .base import Signal, safe_text


API_BASE = "https://gamma-api.polymarket.com"


def fetch_markets(limit: int = 100) -> List[Dict]:
    """Pull markets actuales con probabilidades. Filtra a activos."""
    try:
        r = requests.get(f"{API_BASE}/markets",
                         params={"limit": limit, "active": "true", "closed": "false",
                                 "order": "volumeNum", "ascending": "false"},
                         timeout=15)
        if r.status_code != 200:
            return []
        return r.json() or []
    except Exception:
        return []


def collect(min_change_pct: float = 10.0, max_markets: int = 50,
            state: Dict | None = None) -> tuple[List[Signal], Dict]:
    """Devuelve signals para mercados con cambio de probabilidad >= min_change_pct vs ciclo previo.

    state: dict con last_probabilities por market id. Se actualiza y devuelve.
    """
    state = dict(state or {})
    state.setdefault("markets", {})

    markets = fetch_markets(limit=max_markets * 2)
    signals: List[Signal] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for m in markets[:max_markets]:
        mkt_id = str(m.get("id") or m.get("conditionId") or "")
        if not mkt_id:
            continue
        question = safe_text(m.get("question", ""), 240)
        if not question:
            continue
        # Polymarket markets binarios tienen outcomePrices (str de array)
        try:
            prices = m.get("outcomePrices")
            if isinstance(prices, str):
                import json as _json
                prices = _json.loads(prices)
            current_prob = float(prices[0]) if prices else None
        except Exception:
            current_prob = None
        if current_prob is None:
            continue
        current_pct = current_prob * 100

        # Compara con previo
        prev = state["markets"].get(mkt_id)
        delta = None
        if prev and "prob" in prev:
            delta = current_pct - prev["prob"]
            if abs(delta) >= min_change_pct:
                direction = "📈 SUBE" if delta > 0 else "📉 BAJA"
                volume = float(m.get("volumeNum", 0) or 0)
                signals.append(Signal(
                    source="polymarket",
                    title=f"{direction} {abs(delta):.0f}pp: {question[:120]}",
                    text=f"Polymarket — probabilidad pasó de {prev['prob']:.1f}% a {current_pct:.1f}% "
                         f"({delta:+.1f}pp). Volumen: ${volume:,.0f}. "
                         f"Algo está pasando que el mercado de predicción está pricing.",
                    url=f"https://polymarket.com/event/{m.get('slug', '')}",
                    engagement=int(abs(delta) * 5 + min(50, volume/1000)),
                    lang="en",
                    raw_metadata={
                        "market_id": mkt_id,
                        "prev_prob": prev["prob"],
                        "current_prob": current_pct,
                        "delta_pp": delta,
                        "volume": volume,
                        "question": question,
                    },
                ))

        # Actualiza state
        state["markets"][mkt_id] = {
            "prob": current_pct,
            "question": question[:200],
            "updated": now_iso,
        }

    state["last_run"] = now_iso
    # Purge stale (markets no actualizados en este pull — probablemente cerraron)
    fresh_ids = {str(m.get("id") or m.get("conditionId") or "") for m in markets}
    state["markets"] = {k: v for k, v in state["markets"].items() if k in fresh_ids}
    return signals, state
