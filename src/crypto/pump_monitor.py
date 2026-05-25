"""Pump.fun continuous monitor.

Cada ciclo fetch las últimas N coins de Pump.fun y matchea contra:
- TODOS los keywords/coin_themes de eventos activos
- TODOS los keywords de active_watch (narrativas STRONG recientes)

Match positive → alerta independiente NEW LAUNCH FOR TRACKED EVENT.
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple
from ..collectors import pump_fun


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


def _collect_event_keywords(events: List[Dict]) -> Dict[str, List[str]]:
    """Devuelve dict {event_id: [keywords + themes lowercased]}"""
    out = {}
    for ev in events:
        ev_id = ev.get("id")
        if not ev_id:
            continue
        terms = []
        for k in (ev.get("keywords") or []):
            terms.append(str(k).lower())
        for k in (ev.get("coin_themes") or []):
            terms.append(str(k).lower())
        out[ev_id] = list(set(terms))
    return out


def _word_match(term: str, haystack: str) -> bool:
    """Match con word boundaries para evitar falsos positivos.

    "ufc" matchea "ufc fighter" pero NO "tufcoin" ni "stuff".
    Para multi-word terms (e.g. "white house") usa contención exacta.
    """
    if not term or not haystack:
        return False
    term = term.strip().lower()
    if not term:
        return False
    # Multi-word: substring exacto (con espacios alrededor o en bordes)
    if " " in term:
        return term in haystack
    # Single word: regex con word boundaries
    try:
        return re.search(rf"\b{re.escape(term)}\b", haystack) is not None
    except Exception:
        return term in haystack


def _matches(coin: Dict, terms: List[str]) -> List[str]:
    """Devuelve qué terms matchean (word-boundary aware)."""
    haystack_parts = [
        (coin.get("ticker") or "").lower(),
        (coin.get("name") or "").lower(),
        (coin.get("description") or "").lower(),
    ]
    haystack = " ".join(haystack_parts)
    out = []
    for t in terms:
        if not t:
            continue
        if _word_match(t, haystack) or _ticker_match(coin, t):
            out.append(t)
    return out


def _ticker_match(coin: Dict, term: str) -> bool:
    """Match exacto del ticker (no contiene)."""
    ticker = (coin.get("ticker") or "").lower()
    term_lc = term.lower().strip("$")
    if not ticker or not term_lc:
        return False
    return ticker == term_lc


def scan(events: List[Dict], settings: dict, state_path: str,
        active_watch_path: str) -> List[Dict]:
    """Devuelve lista de matches: [{coin, event_id, event_name, matched_terms}]"""
    cfg = settings.get("pump_monitor", {})
    if not cfg.get("enabled", True):
        return []

    pf_cfg = settings.get("crypto_hunter", {})
    limit = int(cfg.get("fetch_limit_per_cycle", 50))

    try:
        coins = pump_fun.fetch_new_coins(
            limit=limit,
            min_mc=1000,
            max_mc=500000,
            require_socials=False,    # más permisivo aquí — queremos catch al vuelo
            require_description=False,
            min_description_chars=0,
        )
    except Exception:
        coins = []
    if not coins:
        return []

    # State para dedup
    state = _load(state_path)
    seen_mints = set(state.get("seen_mints", []))

    # Event keywords
    event_terms_map = _collect_event_keywords(events)
    event_name_map = {ev["id"]: ev.get("name", ev["id"]) for ev in events if ev.get("id")}

    # Active watch (keywords de narrativas STRONG recientes)
    active = _load(active_watch_path)
    active_terms = []
    now = datetime.now(timezone.utc)
    active_kept = []
    for w in active.get("watches", []):
        try:
            until = datetime.fromisoformat(w.get("until", ""))
            if until > now:
                active_terms.extend([t.lower() for t in (w.get("terms") or [])])
                active_kept.append(w)
        except Exception:
            continue
    active["watches"] = active_kept
    _save(active_watch_path, active)

    matches = []
    new_seen = set()
    for coin in coins:
        mint = coin.get("mint")
        if not mint or mint in seen_mints:
            continue
        new_seen.add(mint)

        # Match contra eventos
        matched_events = []
        all_matched_terms = []
        for ev_id, terms in event_terms_map.items():
            mt = _matches(coin, terms)
            if mt:
                matched_events.append(ev_id)
                all_matched_terms.extend(mt)

        # Match contra active_watch (narrativas STRONG recientes)
        active_matches = _matches(coin, active_terms) if active_terms else []

        if matched_events or active_matches:
            matches.append({
                "coin": coin,
                "matched_event_ids": matched_events,
                "matched_event_names": [event_name_map.get(e, e) for e in matched_events],
                "matched_terms": list(set(all_matched_terms + active_matches))[:8],
                "active_watch_match": bool(active_matches),
            })

    # Update state
    seen_mints.update(new_seen)
    # Keep only last 2000 mints to avoid file growth
    if len(seen_mints) > 2000:
        seen_mints = set(list(seen_mints)[-2000:])
    state["seen_mints"] = list(seen_mints)
    state["last_scan"] = now.isoformat()
    _save(state_path, state)

    return matches


def add_active_watch(active_watch_path: str, terms: List[str], hours: int = 48) -> None:
    """Tras una narrativa STRONG, activa watch agresivo de keywords en Pump.fun."""
    data = _load(active_watch_path)
    data.setdefault("watches", [])
    now = datetime.now(timezone.utc)
    until = now + timedelta(hours=hours)
    data["watches"].append({
        "terms": [t.lower() for t in terms if t],
        "added": now.isoformat(),
        "until": until.isoformat(),
    })
    _save(active_watch_path, data)
