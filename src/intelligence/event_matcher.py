"""Matchea eventos del calendario para emitir alertas de anticipación."""
from datetime import datetime, date
from typing import List, Dict, Any
import yaml


def load_events(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("events", [])


def upcoming_events(events: List[Dict], today: date,
                    major_days: int, medium_days: int, small_days: int,
                    imminent_days: int) -> List[Dict]:
    """Devuelve eventos próximos con su 'window_type' (imminent/small/medium/major)."""
    out = []
    for e in events:
        d = e.get("date")
        if isinstance(d, str):
            try:
                d = datetime.fromisoformat(d).date()
            except Exception:
                continue
        elif isinstance(d, datetime):
            d = d.date()
        if not isinstance(d, date):
            continue
        delta = (d - today).days
        if delta < 0:
            continue
        if delta <= imminent_days:
            window = "imminent"
        elif delta <= small_days:
            window = "small"
        elif delta <= medium_days:
            window = "medium"
        elif delta <= major_days:
            window = "major"
        else:
            continue
        out.append({**e, "days_to_event": delta, "window_type": window})
    out.sort(key=lambda x: x["days_to_event"])
    return out


def match_cluster_to_event(cluster: Dict, events: List[Dict]) -> Dict | None:
    """Si un cluster de señales coincide con un evento conocido, devuelve el evento."""
    terms = set(t.lower() for t in cluster.get("key_terms", []))
    title = cluster.get("top_title", "").lower()
    best = None
    best_score = 0
    for e in events:
        kws = [k.lower() for k in (e.get("keywords") or [])]
        score = 0
        for kw in kws:
            if kw in title:
                score += 3
            for t in terms:
                if t and t in kw:
                    score += 1
        if score > best_score:
            best_score = score
            best = e
    if best_score >= 3:
        return best
    return None
