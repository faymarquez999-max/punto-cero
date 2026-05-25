"""Event Coin Watcher — el motor proactivo.

Para cada evento del calendario activo:
1. Lee `known_coins` y `coin_themes` del evento
2. Cada ciclo escanea Dexscreener + Solana Tracker para cada coin
3. Trackea lifecycle state en data/event_coins.json (peak_mc, drawdown, etc.)
4. Si state == DORMANT_PUMPER y rr_score ≥ alert_min_rr_score y evento ≤30d → alerta
"""
import json
import os
from datetime import datetime, timezone, date
from pathlib import Path
from typing import List, Dict, Optional

from ..collectors import dexscreener, solana_tracker
from . import lifecycle


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str, indent=2)
    os.replace(tmp, path)


def _resolve_coin(query: str) -> Optional[Dict]:
    """Busca un coin por ticker/mint en Dexscreener primero, luego Solana Tracker."""
    if not query:
        return None
    # Si parece mint Solana (32-44 chars base58)
    if len(query) >= 32 and len(query) <= 44 and query.isalnum():
        try:
            pairs = dexscreener.search_pairs(query)
            if pairs:
                return pairs[0]
        except Exception:
            pass

    # Búsqueda por ticker
    try:
        pairs = dexscreener.search_pairs(query)
        if pairs:
            # Filtra a Solana solo + por ticker exact match preferido
            sol = [p for p in pairs if (p.get("chain") or "").lower() == "solana"]
            exact = [p for p in sol if (p.get("ticker") or "").upper() == query.upper()]
            if exact:
                return exact[0]
            if sol:
                return sol[0]
    except Exception:
        pass

    # Fallback a Solana Tracker
    try:
        results = solana_tracker.search_tokens(query, limit=3)
        if results and isinstance(results, list):
            first = results[0]
            return {
                "ticker": (first.get("symbol") or "").upper(),
                "name": first.get("name", ""),
                "mint": first.get("mint", ""),
                "market_cap_usd": float(first.get("marketCap", 0) or 0),
                "liquidity_usd": 0,
                "volume_24h": 0,
                "chain": "solana",
                "url": f"https://www.solanatracker.io/coin/{first.get('mint','')}",
                "source": "solana_tracker_search",
            }
    except Exception:
        pass
    return None


def update_event_coins(events: List[Dict], state: dict,
                      lifecycle_cfg: dict, today: date | None = None) -> dict:
    """Actualiza el estado de cada coin event-linked. Devuelve state actualizado."""
    today = today or date.today()
    state = dict(state or {})
    state.setdefault("events", {})
    now_iso = datetime.now(timezone.utc).isoformat()

    # Cache de resoluciones para ahorrar API calls en el mismo ciclo
    resolve_cache: dict = {}

    def _resolve_cached(q: str):
        key = (q or "").upper()
        if key in resolve_cache:
            return resolve_cache[key]
        c = _resolve_coin(q)
        resolve_cache[key] = c
        return c

    for ev in events:
        ev_id = ev.get("id")
        if not ev_id:
            continue
        # solo eventos futuros o always_active
        ev_date = ev.get("date")
        always = ev.get("always_active", False)
        days_to = None
        if isinstance(ev_date, date):
            days_to = (ev_date - today).days
        elif isinstance(ev_date, str):
            try:
                days_to = (datetime.fromisoformat(ev_date).date() - today).days
            except Exception:
                days_to = None
        if not always and (days_to is None or days_to < -7 or days_to > 90):
            continue   # ya pasó hace más de 7 días o demasiado lejano (>90d)

        known = ev.get("known_coins", []) or []
        if not known:
            continue

        ev_state = state["events"].setdefault(ev_id, {"coins": {}, "name": ev.get("name", "")})
        for ticker_or_mint in known:
            coin = _resolve_cached(ticker_or_mint)
            if not coin:
                continue
            key = (coin.get("mint") or ticker_or_mint).strip()
            prev = ev_state["coins"].get(key, {})

            # Trackea peak_mc
            current_mc = float(coin.get("market_cap_usd", 0) or 0)
            peak_mc = max(float(prev.get("peak_mc_usd", 0) or 0), current_mc)

            lifecycle_state = lifecycle.classify(
                {**coin, "peak_mc_usd": peak_mc},
                days_to_event=days_to,
                fresh_max_age_hours=lifecycle_cfg.get("fresh_max_age_hours", 24),
                dead_min_drawdown_pct=lifecycle_cfg.get("dead_min_drawdown_pct", 95),
            )
            rr = lifecycle.compute_rr(
                {**coin, "peak_mc_usd": peak_mc},
                days_to_event=days_to,
                smart_money_signal=float(prev.get("smart_money_signal", 0)),
            )

            ev_state["coins"][key] = {
                **coin,
                "peak_mc_usd": peak_mc,
                "lifecycle_state": lifecycle_state,
                "days_to_event": days_to,
                "last_seen": now_iso,
                "rr": rr,
                "first_seen": prev.get("first_seen") or now_iso,
                "smart_money_signal": prev.get("smart_money_signal", 0),
            }
    state["last_updated"] = now_iso
    return state


def get_alert_candidates(state: dict, rr_threshold: float = 6.0,
                        days_to_event_max: int = 30,
                        min_drawdown_pct: float = 70) -> List[Dict]:
    """Devuelve coins que cumplen criterios para alerta EVENT-LINKED OPPORTUNITY."""
    candidates = []
    for ev_id, ev_data in (state.get("events") or {}).items():
        ev_name = ev_data.get("name", ev_id)
        for mint, coin in (ev_data.get("coins") or {}).items():
            rr = coin.get("rr", {}) or {}
            score = float(rr.get("rr_score", 0))
            days_to = coin.get("days_to_event")
            ls = coin.get("lifecycle_state", "")
            drawdown = float(rr.get("drawdown_pct", 0))

            # Filtros
            if score < rr_threshold:
                continue
            if days_to is not None and days_to > days_to_event_max:
                continue
            if ls in ("DEAD",):
                continue
            if ls == "DORMANT_PUMPER" and drawdown < min_drawdown_pct:
                continue

            candidates.append({
                **coin,
                "event_id": ev_id,
                "event_name": ev_name,
            })
    candidates.sort(key=lambda x: float(x.get("rr", {}).get("rr_score", 0)), reverse=True)
    return candidates


def run(events: List[Dict], state_path: str, settings: dict) -> tuple[dict, List[Dict]]:
    """Update state y devuelve candidates para alertar. (state, candidates)"""
    cfg = settings.get("event_coin_watcher", {})
    if not cfg.get("enabled", True):
        return _load(state_path), []
    lc_cfg = cfg.get("lifecycle_states", {})
    rr_cfg = cfg.get("rr_thresholds", {})

    state = _load(state_path)
    state = update_event_coins(events, state, lc_cfg)
    _save(state_path, state)

    candidates = get_alert_candidates(
        state,
        rr_threshold=float(cfg.get("alert_min_rr_score", 6)),
        days_to_event_max=int(rr_cfg.get("days_to_event_max", 30)),
        min_drawdown_pct=float(rr_cfg.get("high_rr_min_drawdown_pct", 70)),
    )
    return state, candidates
