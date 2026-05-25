"""Daily digest — corre cada mañana a las 09:00 Madrid (07:00 UTC).

Lee los datos de memoria de últimas 24h y manda un resumen amable.
"""
import os
import sys
import json
import yaml
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.alerts import telegram
from src.intelligence.event_matcher import load_events, upcoming_events


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


def _esc(s: str) -> str:
    if not s:
        return ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_digest(narratives_path, alerts_path, events, windows, top_n_narratives=5, top_n_events=3):
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)

    data = _load_json(narratives_path)
    recent = []
    for fp, n in (data.get("narratives") or {}).items():
        last = n.get("last_alert_at") or n.get("last_seen")
        if not last:
            continue
        try:
            ts = datetime.fromisoformat(last)
        except Exception:
            continue
        if ts >= yesterday:
            recent.append((ts, fp, n))
    recent.sort(key=lambda x: x[0], reverse=True)

    upcoming = upcoming_events(
        events,
        today=date.today(),
        major_days=windows.get("major_event_days", 30),
        medium_days=windows.get("medium_event_days", 14),
        small_days=windows.get("small_event_days", 7),
        imminent_days=windows.get("imminent_event_days", 3),
    )[:top_n_events]

    parts = [f"🌅 <b>DAILY DIGEST</b> · {now.strftime('%Y-%m-%d')}\n"]
    parts.append(f"<i>Resumen últimas 24h + próximos eventos</i>\n")

    if recent:
        parts.append(f"\n📰 <b>Top narrativas detectadas ({len(recent)} en 24h):</b>")
        for ts, fp, n in recent[:top_n_narratives]:
            nar = n.get("narrative") or {}
            cm = n.get("cluster_meta") or {}
            score = nar.get("score", 0)
            title = cm.get("top_title", "")[:100]
            cat = nar.get("category", "")
            parts.append(f"• <b>{score}</b> · {_esc(cat)} · {_esc(title)}")
    else:
        parts.append("\n📰 <i>Sin alertas STRONG en las últimas 24h — mercado tranquilo.</i>")

    if upcoming:
        parts.append(f"\n\n📅 <b>Próximos eventos a vigilar:</b>")
        for e in upcoming:
            d = e.get("days_to_event", 0)
            parts.append(f"• <b>en {d}d</b> · {_esc(e.get('name',''))}")

    # Total alertas log
    alerts_data = _load_json(alerts_path)
    alerts = alerts_data.get("alerts", []) or []
    last24_alerts = [a for a in alerts if a.get("ts", "") >= yesterday.isoformat()]
    parts.append(f"\n\n📊 <b>Stats 24h:</b> {len(last24_alerts)} alertas enviadas")

    parts.append("\n\n🤖 <i>Sistema corriendo cada 15 min. Manda /status si quieres confirmar que estoy vivo.</i>")
    return "\n".join(parts)


def main():
    load_dotenv(BASE_DIR / ".env")
    settings = _load_yaml(BASE_DIR / "config" / "settings.yaml")
    events = load_events(str(BASE_DIR / "config" / "events.yaml"))

    paths = settings.get("paths", {})
    narratives_path = str(BASE_DIR / paths.get("narratives_file", "data/narratives.json"))
    alerts_path = str(BASE_DIR / paths.get("alerts_log", "data/alerts_log.json"))
    windows = settings.get("anticipation_windows", {})
    digest_cfg = settings.get("daily_digest", {})

    if not digest_cfg.get("enabled", True):
        print("Daily digest disabled.")
        return

    msg = build_digest(narratives_path, alerts_path, events, windows,
                       top_n_narratives=digest_cfg.get("include_top_n_narratives", 5),
                       top_n_events=digest_cfg.get("include_top_n_events", 3))
    ok = telegram.send(msg)
    print(f"Daily digest sent: {ok}")


if __name__ == "__main__":
    main()
