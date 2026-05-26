"""Active Watch System — vigilancia persistente de narrativas.

Cuando una narrativa supera el umbral, se crea un Active Watch que:
- Persiste 48-168h
- Contiene tickers candidatos generados por el LLM
- Contiene key_terms para búsqueda DexScreener
- Cada ciclo lo procesa el dex_matcher para buscar coins matching
- Expira automáticamente cuando se cumple la duración o aparece coin matched

Estructura en disco (data/active_watches.json):
{
  "watches": [
    {
      "id": "abc123",
      "fingerprint": "...",
      "narrative_summary": "...",
      "category": "...",
      "candidate_tickers": ["X", "Y", "Z"],
      "key_terms": ["foo", "bar"],
      "score": 78,
      "confidence": "high",
      "started_at": "2026-...",
      "expires_at": "2026-...",
      "status": "active|coin_matched|expired",
      "matched_coin": null | {mint, ticker, ...}
    }
  ],
  "last_updated": "..."
}
"""
import os
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional


def _load(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(path: str, data: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, path)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _watch_fingerprint(narrative: Dict) -> str:
    """Fingerprint estable para dedup."""
    parts = [
        narrative.get("category", ""),
        narrative.get("narrative_summary", "")[:100].lower(),
        "::".join(sorted([t.upper() for t in narrative.get("candidate_tickers", [])][:3])),
    ]
    s = "::".join(p for p in parts if p)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def load_state(path: str) -> Dict:
    return _load(path)


def get_active(state: Dict) -> List[Dict]:
    """Devuelve solo watches con status='active' y no expirados."""
    now = _now()
    active = []
    for w in state.get("watches", []) or []:
        if w.get("status") != "active":
            continue
        try:
            expires = datetime.fromisoformat(w.get("expires_at", ""))
            if expires > now:
                active.append(w)
        except Exception:
            continue
    return active


def has_recent_watch(state: Dict, fingerprint: str, cooldown_hours: int = 24) -> bool:
    """Hay un watch reciente para este fingerprint?"""
    cutoff = _now() - timedelta(hours=cooldown_hours)
    for w in state.get("watches", []) or []:
        if w.get("fingerprint") != fingerprint:
            continue
        try:
            started = datetime.fromisoformat(w.get("started_at", ""))
            if started > cutoff:
                return True
        except Exception:
            pass
    return False


def create_watch(state: Dict, narrative: Dict, cluster_meta: Dict,
                 default_duration_hours: int = 72,
                 strong_duration_hours: int = 168) -> Dict:
    """Crea un Active Watch a partir de una narrativa scored."""
    fp = _watch_fingerprint(narrative)
    rec = narrative.get("recommendation", "WATCH")
    duration = strong_duration_hours if rec == "STRONG_WATCH" else default_duration_hours

    # Permitir override del LLM si especifica watch_duration_hours
    llm_duration = narrative.get("watch_duration_hours")
    if isinstance(llm_duration, (int, float)) and 24 <= llm_duration <= 240:
        duration = int(llm_duration)

    now = _now()
    expires = now + timedelta(hours=duration)

    watch = {
        "id": fp,
        "fingerprint": fp,
        "narrative_summary": narrative.get("narrative_summary", ""),
        "why_memeable": narrative.get("why_memeable", ""),
        "category": narrative.get("category", ""),
        "matched_archetype": narrative.get("matched_archetype", ""),
        "candidate_tickers": [t.upper() for t in (narrative.get("candidate_tickers") or [])][:10],
        "key_terms_for_dex_search": narrative.get("key_terms_for_dex_search") or narrative.get("candidate_tickers") or [],
        "score": int(narrative.get("score", 0)),
        "confidence": narrative.get("confidence", "medium"),
        "recommendation": rec,
        "coin_emergence_probability_24h": narrative.get("coin_emergence_probability_24h", "medium"),
        "time_window_hours": narrative.get("time_window_hours"),
        "memetic_dimensions": narrative.get("memetic_dimensions", {}),
        "started_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "duration_hours": duration,
        "status": "active",
        "matched_coin": None,
        "cluster_top_title": cluster_meta.get("top_title", ""),
        "cluster_sources": cluster_meta.get("source_families", []),
        "scan_attempts": 0,
    }

    state.setdefault("watches", []).append(watch)
    state["last_updated"] = now.isoformat()

    # Limita tamaño (max 50 active + algunos history)
    state["watches"] = state["watches"][-200:]
    return watch


def mark_watch_matched(state: Dict, watch_id: str, coin: Dict) -> None:
    """Cuando dex_matcher encuentra coin → marca el watch."""
    for w in state.get("watches", []) or []:
        if w.get("id") == watch_id:
            w["status"] = "coin_matched"
            w["matched_coin"] = coin
            w["matched_at"] = _now_iso()
            break
    state["last_updated"] = _now_iso()


def expire_old(state: Dict) -> int:
    """Marca como expirados los watches que pasaron expires_at. Devuelve cuántos."""
    now = _now()
    n = 0
    for w in state.get("watches", []) or []:
        if w.get("status") != "active":
            continue
        try:
            expires = datetime.fromisoformat(w.get("expires_at", ""))
            if expires <= now:
                w["status"] = "expired"
                w["expired_at"] = _now_iso()
                n += 1
        except Exception:
            pass
    return n


def increment_scan_attempts(state: Dict, watch_id: str) -> None:
    for w in state.get("watches", []) or []:
        if w.get("id") == watch_id:
            w["scan_attempts"] = int(w.get("scan_attempts", 0)) + 1
            break


def save_state(path: str, state: Dict) -> None:
    _save(path, state)


def watch_fingerprint(narrative: Dict) -> str:
    """Helper público para que main pueda calcular fingerprint."""
    return _watch_fingerprint(narrative)
