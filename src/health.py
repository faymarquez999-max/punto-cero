"""Health check — detecta cuando el sistema lleva ciclos en blanco."""
import json
import os
from datetime import datetime, timezone


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
        json.dump(data, f, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def record_cycle(path: str, total_signals: int, sources_status: dict) -> dict:
    """Devuelve estado actualizado. Si zero_streak alcanza umbral, marca need_alert."""
    state = _load(path)
    state.setdefault("zero_streak", 0)
    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    state["last_signal_count"] = total_signals
    state["sources_status"] = sources_status

    if total_signals == 0:
        state["zero_streak"] = int(state.get("zero_streak", 0)) + 1
    else:
        state["zero_streak"] = 0

    _save(path, state)
    return state


def should_alert(state: dict, threshold: int = 3) -> bool:
    return int(state.get("zero_streak", 0)) == threshold


def build_health_message(state: dict) -> str:
    sources = state.get("sources_status", {})
    lines = [f"🚨 <b>HEALTH ALERT</b>",
             f"El sistema ha registrado <b>{state.get('zero_streak', 0)} ciclos consecutivos sin señales</b>.",
             "",
             "<b>Estado fuentes último ciclo:</b>"]
    for src, val in sources.items():
        emoji = "✅" if val > 0 else "❌"
        lines.append(f"{emoji} {src}: {val}")
    lines.append("")
    lines.append("<i>Posibles causas: APIs caídas, rate-limit, cambio de endpoints. Revisar logs en GitHub Actions.</i>")
    return "\n".join(lines)
