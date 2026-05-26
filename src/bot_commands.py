"""Bot commands V3 — /status, /watches, /help."""
import json
import os
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from typing import List, Dict
from .alerts import telegram


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


def _load_json(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def handle_command(text: str, base_dir: Path, settings: dict, events: list) -> str:
    cmd = (text or "").strip().split()[0].lower() if text else ""
    if cmd == "/status":
        return _status_msg(base_dir, settings)
    if cmd == "/watches":
        return _watches_msg(base_dir, settings)
    if cmd in ("/help", "/start"):
        return _help_msg()
    return ""


def _help_msg() -> str:
    return (
        "🤖 <b>Punto Cero</b> — comandos:\n\n"
        "/status — estado del sistema (último ciclo, fuentes activas)\n"
        "/watches — narrativas en watch activo ahora mismo\n"
        "/help — esta ayuda\n\n"
        "<i>Las alertas llegan automáticamente:\n"
        "🚨 NARRATIVA POTENCIAL · 💎 COIN MATCHED · 🎯 EVENT-LINKED · ⚡ ESCALATION</i>"
    )


def _status_msg(base_dir: Path, settings: dict) -> str:
    paths = settings.get("paths", {})
    health_path = base_dir / paths.get("health_state_file", "data/health.json")
    state = _load_json(str(health_path))
    last = state.get("last_run_at", "n/a")
    try:
        ts = datetime.fromisoformat(last)
        mins = int((datetime.now(timezone.utc) - ts).total_seconds() / 60)
        last_h = f"hace {mins} min ({last[:19]})"
    except Exception:
        last_h = last
    sources = state.get("sources_status", {}) or {}
    src_lines = "\n".join(f"  {'✅' if v > 0 else '❌'} {k}: {v}" for k, v in sources.items())

    # Active watches count
    aw_path = base_dir / paths.get("active_watches_file", "data/active_watches.json")
    aw_state = _load_json(str(aw_path))
    active = [w for w in aw_state.get("watches", []) or [] if w.get("status") == "active"]

    return (
        f"✅ <b>Status:</b> vivo\n"
        f"🕐 Último ciclo: {last_h}\n"
        f"📡 Señales: {state.get('last_signal_count', '?')}\n"
        f"⚠️ Zero-streak: {state.get('zero_streak', 0)}\n"
        f"🔭 Watches activos: {len(active)}\n\n"
        f"<b>Fuentes último ciclo:</b>\n{src_lines or '  (sin datos)'}"
    )


def _watches_msg(base_dir: Path, settings: dict) -> str:
    paths = settings.get("paths", {})
    aw_path = base_dir / paths.get("active_watches_file", "data/active_watches.json")
    state = _load_json(str(aw_path))
    active = [w for w in state.get("watches", []) or [] if w.get("status") == "active"]

    if not active:
        return "🔭 No hay watches activos. El bot espera nuevas narrativas."

    lines = [f"🔭 <b>Watches activos ({len(active)}):</b>\n"]
    for w in active[:15]:
        score = w.get("score", 0)
        cat = w.get("category", "?")
        summary = (w.get("narrative_summary", "") or "")[:80]
        try:
            expires = datetime.fromisoformat(w.get("expires_at", ""))
            hours_left = max(0, int((expires - datetime.now(timezone.utc)).total_seconds() / 3600))
            exp_str = f"{hours_left}h"
        except Exception:
            exp_str = "?"
        tickers = ", ".join((w.get("candidate_tickers") or [])[:5])
        lines.append(f"• <b>{score}</b> · {cat} · expira {exp_str}\n  {summary}\n  🎯 {tickers}")
    return "\n".join(lines)


def process_pending(base_dir: Path, settings: dict, events: list) -> int:
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
