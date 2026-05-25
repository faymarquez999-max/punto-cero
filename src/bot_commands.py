"""Respuesta a comandos de Telegram via getUpdates polling.

En cada ciclo del main, pollea updates pendientes y responde a /status, /help, /events.
NO bloquea (timeout=0, long-poll desactivado).
"""
import json
import os
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from typing import List, Dict
from .alerts import telegram
from .intelligence.event_matcher import load_events, upcoming_events


OFFSET_FILE = "data/telegram_offset.json"


def _load_offset(path: str) -> int:
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int((json.load(f) or {}).get("offset", 0))
    except Exception:
        return 0


def _save_offset(path: str, offset: int) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"offset": offset}, f)


def handle_command(text: str, base_dir: Path, settings: dict, events: list) -> str:
    cmd = (text or "").strip().split()[0].lower() if text else ""
    if cmd == "/status":
        return _status_msg(base_dir, settings)
    if cmd == "/events":
        return _events_msg(events, settings)
    if cmd in ("/help", "/start"):
        return _help_msg()
    return ""


def _help_msg() -> str:
    return (
        "🤖 <b>Narrative Alpha Hunter</b> — comandos:\n\n"
        "/status — estado del sistema (último ciclo, salud)\n"
        "/events — próximos eventos del calendario\n"
        "/help — esta ayuda\n\n"
        "<i>Alertas STRONG llegan automáticamente cuando se detecta narrativa con score ≥ 83.</i>"
    )


def _status_msg(base_dir: Path, settings: dict) -> str:
    paths = settings.get("paths", {})
    health_path = base_dir / paths.get("health_state_file", "data/health.json")
    state = {}
    if health_path.exists():
        try:
            with open(health_path, "r", encoding="utf-8") as f:
                state = json.load(f) or {}
        except Exception:
            pass
    last = state.get("last_run_at", "n/a")
    try:
        ts = datetime.fromisoformat(last)
        mins = int((datetime.now(timezone.utc) - ts).total_seconds() / 60)
        last_h = f"hace {mins} min ({last})"
    except Exception:
        last_h = last
    signals = state.get("last_signal_count", "?")
    streak = state.get("zero_streak", 0)
    sources = state.get("sources_status", {}) or {}
    src_lines = "\n".join(f"  {'✅' if v > 0 else '❌'} {k}: {v}" for k, v in sources.items())
    return (
        f"✅ <b>Status:</b> vivo\n"
        f"🕐 Último ciclo: {last_h}\n"
        f"📡 Señales recolectadas: {signals}\n"
        f"⚠️ Zero-streak: {streak}\n\n"
        f"<b>Fuentes último ciclo:</b>\n{src_lines or '  (sin datos)'}"
    )


def _events_msg(events: list, settings: dict) -> str:
    windows = settings.get("anticipation_windows", {})
    upcoming = upcoming_events(
        events, today=date.today(),
        major_days=windows.get("major_event_days", 30),
        medium_days=windows.get("medium_event_days", 14),
        small_days=windows.get("small_event_days", 7),
        imminent_days=windows.get("imminent_event_days", 3),
    )
    if not upcoming:
        return "📅 No hay eventos en las ventanas de anticipación actuales."
    lines = ["📅 <b>Próximos eventos vigilados:</b>\n"]
    for e in upcoming[:10]:
        d = e.get("days_to_event", 0)
        lines.append(f"• <b>en {d}d</b> · {e.get('window_type','')} · {e.get('name','')}")
    return "\n".join(lines)


def process_pending(base_dir: Path, settings: dict, events: list) -> int:
    """Pollea updates pendientes una vez y responde. Devuelve nº mensajes procesados."""
    if not settings.get("telegram", {}).get("enable_status_command", True):
        return 0
    offset_path = str(base_dir / OFFSET_FILE)
    last_offset = _load_offset(offset_path)

    updates = telegram.get_updates(offset=last_offset + 1 if last_offset else None, timeout=0)
    if not updates:
        return 0

    handled = 0
    new_offset = last_offset
    for u in updates:
        upd_id = int(u.get("update_id", 0))
        if upd_id > new_offset:
            new_offset = upd_id
        msg = u.get("message") or u.get("channel_post") or {}
        text = msg.get("text", "")
        if not text or not text.startswith("/"):
            continue
        reply = handle_command(text, base_dir, settings, events)
        if reply:
            telegram.send(reply)
            handled += 1
    if new_offset != last_offset:
        _save_offset(offset_path, new_offset)
    return handled
