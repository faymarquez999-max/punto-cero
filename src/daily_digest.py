"""Daily digest V3 — resumen 24h + watches activos."""
import os
import sys
import json
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.alerts import telegram


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _esc(s):
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_digest(base_dir, settings):
    paths = settings.get("paths", {})
    alerts_path = str(base_dir / paths.get("alerts_log", "data/alerts_log.json"))
    aw_path = str(base_dir / paths.get("active_watches_file", "data/active_watches.json"))

    now = datetime.now(timezone.utc)
    yesterday_iso = (now - timedelta(hours=24)).isoformat()

    alerts_data = _load_json(alerts_path)
    alerts = [a for a in alerts_data.get("alerts", []) if a.get("ts", "") >= yesterday_iso]

    by_kind = {}
    for a in alerts:
        by_kind.setdefault(a.get("kind", "unknown"), []).append(a)

    parts = [f"🌅 <b>DAILY DIGEST</b> · {now.strftime('%Y-%m-%d')}\n",
             "<i>Resumen últimas 24h</i>\n"]

    # Counts
    parts.append("\n📊 <b>Alertas 24h:</b>")
    parts.append(f"• 🚨 Narrativas potenciales: {len(by_kind.get('potential_narrative', []))}")
    parts.append(f"• 💎 Coins matched: {len(by_kind.get('coin_matched', []))}")
    parts.append(f"• 🎯 Event-linked: {len(by_kind.get('event_linked', []))}")
    parts.append(f"• 🌑 Shadow (score 50-69): {len(by_kind.get('shadow', []))}")

    # Top narrativas
    pots = by_kind.get("potential_narrative", [])[:5]
    if pots:
        parts.append("\n\n🚨 <b>Top narrativas detectadas:</b>")
        for a in pots[-5:]:
            p = a.get("payload", {})
            parts.append(f"• <b>{p.get('score', 0)}</b> · {_esc(p.get('category', ''))} · {_esc((p.get('title', '') or '')[:90])}")

    # Coins matched
    matched = by_kind.get("coin_matched", [])
    if matched:
        parts.append("\n\n💎 <b>Coins matched 24h:</b>")
        for a in matched[-5:]:
            p = a.get("payload", {})
            parts.append(f"• <b>${_esc(p.get('ticker', ''))}</b> · MC ${p.get('mc', 0):,.0f}")

    # Active watches
    aw_state = _load_json(aw_path)
    active = [w for w in aw_state.get("watches", []) or [] if w.get("status") == "active"]
    if active:
        parts.append(f"\n\n🔭 <b>Watches activos ahora ({len(active)}):</b>")
        for w in active[:5]:
            parts.append(f"• <b>{w.get('score', 0)}</b> · {_esc(w.get('category', ''))} · {_esc((w.get('narrative_summary', '') or '')[:90])}")

    parts.append("\n\n🤖 <i>Bot vigilando. /watches para ver más detalle.</i>")
    return "\n".join(parts)


def main():
    load_dotenv(BASE_DIR / ".env")
    settings = _load_yaml(BASE_DIR / "config" / "settings.yaml")
    if not settings.get("daily_digest", {}).get("enabled", True):
        print("Daily digest disabled.")
        return
    msg = build_digest(BASE_DIR, settings)
    ok = telegram.send(msg)
    print(f"Daily digest sent: {ok}")


if __name__ == "__main__":
    main()
