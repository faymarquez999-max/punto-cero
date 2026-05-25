"""Ticker Velocity Engine.

Cada ciclo:
1. Extrae todos los tickers $XYZ de TODAS las señales recolectadas
2. Cuenta mentions por ticker en la última hora
3. Compara con baseline (media de últimas 24h)
4. Si velocity_x >= spike_multiplier (default 5x) y baseline >= 3 → SPIKE

Persiste historial en data/ticker_velocity.json (sliding window 24h).
"""
import re
import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from collections import Counter

TICKER_RE = re.compile(r"(?<![A-Za-z])\$([A-Z][A-Z0-9]{1,11})\b")
BARE_RE = re.compile(r"\b([A-Z]{3,10})\b")

# Tickers genéricos que NO contamos (ruido)
IGNORED = {
    "USDC", "USDT", "ETH", "BTC", "SOL", "USD", "EUR", "GBP",
    "WBTC", "WETH", "DAI", "BUSD", "MATIC", "AVAX",
    "API", "URL", "HTML", "CSS", "JSON", "XML", "PDF", "JPG", "PNG",
    "USA", "USB", "GTA", "UFC", "NBA", "NFL", "FBI", "CIA", "FAQ",
    "VIP", "RIP", "WTF", "LOL", "OMG", "TIL", "TBH", "IMO", "BTW",
    "GOAT", "WIF", "PEPE", "BONK", "TRUMP",   # ya son top, no contamos como spike
}


def extract_tickers(text: str) -> List[str]:
    """Devuelve lista de tickers únicos extraídos del texto (con $ pattern preferred)."""
    found = set()
    for m in TICKER_RE.findall(text or ""):
        if m not in IGNORED:
            found.add(m)
    # Bare tickers (sin $) — más ruido, solo si aparecen como standalone
    # for m in BARE_RE.findall(text or ""):
    #     if m not in IGNORED and len(m) >= 4:
    #         found.add(m)
    return list(found)


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


def count_tickers_from_signals(signals: List) -> Counter:
    counter = Counter()
    for s in signals:
        text = f"{getattr(s, 'title', '')} {getattr(s, 'text', '')}"
        for t in extract_tickers(text):
            counter[t] += 1
    return counter


def update_and_detect(state: dict, current_counts: Counter,
                     window_hours: int = 1,
                     baseline_hours: int = 24,
                     spike_multiplier: float = 5.0,
                     min_baseline: int = 3) -> tuple[dict, List[Dict]]:
    """Actualiza el state con counts actuales y detecta spikes.

    state structure: {tickers: {TICKER: [{ts, count}, ...sliding 24h]}}
    """
    now = datetime.now(timezone.utc)
    now_ts = now.timestamp()
    state = dict(state or {})
    state.setdefault("tickers", {})
    cutoff_ts = now_ts - baseline_hours * 3600

    # Append current observations
    for ticker, count in current_counts.items():
        hist = state["tickers"].setdefault(ticker, [])
        hist.append({"ts": now_ts, "count": count})
        # Purge old
        state["tickers"][ticker] = [h for h in hist if float(h["ts"]) > cutoff_ts]

    # Detect spikes
    spikes = []
    window_ts = now_ts - window_hours * 3600
    for ticker, hist in state["tickers"].items():
        recent = sum(h["count"] for h in hist if float(h["ts"]) > window_ts)
        baseline_total = sum(h["count"] for h in hist if float(h["ts"]) <= window_ts)
        baseline_periods = max(1, (baseline_hours - window_hours))
        baseline_per_window = baseline_total / baseline_periods if baseline_total > 0 else 0
        if baseline_per_window < min_baseline:
            continue
        ratio = recent / baseline_per_window if baseline_per_window > 0 else 0
        if ratio >= spike_multiplier:
            spikes.append({
                "ticker": ticker,
                "recent_mentions": recent,
                "baseline_per_window": round(baseline_per_window, 1),
                "spike_ratio": round(ratio, 1),
            })

    spikes.sort(key=lambda x: x["spike_ratio"], reverse=True)
    state["last_run"] = now.isoformat()
    return state, spikes


def run(signals: List, state_path: str, settings: dict) -> List[Dict]:
    cfg = settings.get("ticker_velocity", {})
    if not cfg.get("enabled", True):
        return []
    state = _load(state_path)
    counts = count_tickers_from_signals(signals)
    state, spikes = update_and_detect(
        state, counts,
        window_hours=int(cfg.get("window_hours", 1)),
        baseline_hours=int(cfg.get("baseline_window_hours", 24)),
        spike_multiplier=float(cfg.get("spike_multiplier", 5.0)),
        min_baseline=int(cfg.get("min_baseline_mentions", 3)),
    )
    _save(state_path, state)
    return spikes
