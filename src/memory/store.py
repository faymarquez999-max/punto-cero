"""Persistencia en JSON — narrativas, coins, alertas. Sin base de datos."""
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List


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
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, path)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def remember_narrative(path: str, fingerprint: str, narrative: Dict, cluster_meta: Dict) -> None:
    data = _load(path)
    data.setdefault("narratives", {})
    data["narratives"][fingerprint] = {
        "first_seen": data["narratives"].get(fingerprint, {}).get("first_seen") or now_utc_iso(),
        "last_seen": now_utc_iso(),
        "narrative": narrative,
        "cluster_meta": cluster_meta,
        "alert_count": data["narratives"].get(fingerprint, {}).get("alert_count", 0),
    }
    _save(path, data)


def increment_alert_count(path: str, fingerprint: str) -> None:
    data = _load(path)
    n = data.setdefault("narratives", {}).get(fingerprint)
    if n:
        n["alert_count"] = int(n.get("alert_count", 0)) + 1
        n["last_alert_at"] = now_utc_iso()
        _save(path, data)


def was_recently_alerted(path: str, fingerprint: str, cooldown_hours: int) -> bool:
    data = _load(path)
    n = data.get("narratives", {}).get(fingerprint)
    if not n or not n.get("last_alert_at"):
        return False
    try:
        last = datetime.fromisoformat(n["last_alert_at"])
        return datetime.now(timezone.utc) - last < timedelta(hours=cooldown_hours)
    except Exception:
        return False


def remember_coins(path: str, coins: List[Dict], narrative_fp: str) -> None:
    data = _load(path)
    data.setdefault("coins", {})
    for c in coins:
        mint = c.get("mint")
        if not mint:
            continue
        existing = data["coins"].get(mint, {})
        data["coins"][mint] = {
            **existing,
            **c,
            "first_seen": existing.get("first_seen") or now_utc_iso(),
            "last_seen": now_utc_iso(),
            "linked_narratives": list(set((existing.get("linked_narratives") or []) + [narrative_fp])),
        }
    _save(path, data)


def log_alert(path: str, kind: str, payload: Dict) -> None:
    data = _load(path)
    data.setdefault("alerts", [])
    data["alerts"].append({
        "ts": now_utc_iso(),
        "kind": kind,
        "payload": payload,
    })
    # keep last 2000
    data["alerts"] = data["alerts"][-2000:]
    _save(path, data)
