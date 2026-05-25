"""Momentum y velocity tracking.

Dos boosts pre-LLM (no cuestan tokens):
1. Cross-source: cluster con N+ fuentes distintas (familias) = boost
2. Velocity: cluster que sube vs ciclo anterior = boost

Si un cluster tiene boost suficiente, lo PRIORIZAMOS para LLM (top-N selection).
Si no, lo skipeamos. Esto ahorra Groq tokens.
"""
import json
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_history(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def cluster_signature(cluster: Dict) -> str:
    """Firma para trackear el mismo cluster entre ciclos."""
    import hashlib
    terms = sorted(cluster.get("key_terms", []))[:6]
    h = hashlib.sha1("::".join(terms).encode("utf-8")).hexdigest()[:12]
    return h


def compute_momentum_boost(cluster: Dict, history: dict,
                           multi_source_threshold: int = 3,
                           multi_source_bonus: int = 8,
                           velocity_window_hours: int = 2,
                           velocity_x2_bonus: int = 5) -> Dict:
    """Devuelve dict con bonos calculados y razones explicables."""
    n_families = cluster.get("n_distinct_families", 0)
    multi_source = n_families >= multi_source_threshold
    multi_source_b = multi_source_bonus if multi_source else 0

    sig = cluster_signature(cluster)
    now_ts = now_utc().timestamp()
    prev = (history.get("clusters") or {}).get(sig, {})
    prev_count = int(prev.get("signal_count", 0))
    prev_ts = float(prev.get("last_seen_ts", 0))
    cur_count = int(cluster.get("signal_count", 0))

    velocity_b = 0
    velocity_reason = None
    if prev_count > 0 and prev_ts > 0:
        hours_since = (now_ts - prev_ts) / 3600.0
        if hours_since <= velocity_window_hours and cur_count >= max(2, prev_count * 2):
            velocity_b = velocity_x2_bonus
            velocity_reason = f"x2+ menciones en {hours_since:.1f}h (de {prev_count} a {cur_count})"

    reasons = []
    if multi_source:
        reasons.append(f"{n_families} familias de fuentes (cross-source)")
    if velocity_reason:
        reasons.append(velocity_reason)

    return {
        "sig": sig,
        "multi_source": multi_source,
        "multi_source_bonus": multi_source_b,
        "velocity_bonus": velocity_b,
        "total_bonus": multi_source_b + velocity_b,
        "reasons": reasons,
    }


def update_history(history: dict, clusters: List[Dict]) -> dict:
    """Actualiza historial con clusters del ciclo actual."""
    history = dict(history or {})
    history.setdefault("clusters", {})
    cutoff_ts = (now_utc() - timedelta(days=2)).timestamp()
    # Purga antiguos
    history["clusters"] = {
        k: v for k, v in history["clusters"].items()
        if float(v.get("last_seen_ts", 0)) > cutoff_ts
    }
    # Update
    for c in clusters:
        sig = cluster_signature(c)
        history["clusters"][sig] = {
            "signal_count": c.get("signal_count", 0),
            "engagement_total": c.get("engagement_total", 0),
            "n_distinct_families": c.get("n_distinct_families", 0),
            "top_title": c.get("top_title", "")[:160],
            "last_seen_ts": now_utc().timestamp(),
        }
    history["last_updated"] = now_utc().isoformat()
    return history
