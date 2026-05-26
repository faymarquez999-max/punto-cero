"""Event-Linked Radar V3 — caza coins EXISTENTES con catalizador futuro.

A diferencia del antiguo event_watcher (que tenía calendario hardcoded UFC/GTA/etc.),
este motor:

1. Scrape DexScreener Solana de coins low/mid-cap (10k-500k MC)
2. Filtra a las que tienen tickers/nombres temáticos (no genéricos)
3. Envía top-N al LLM con la pregunta: "¿Hay catalizador futuro conocido para esta coin?"
4. El LLM razona usando su conocimiento del mundo + identifica fecha esperada
5. Si R/R es bueno (drawdown + catalizador <60d) → alerta

NO requiere calendario hardcoded. El LLM infiere catalizadores dinámicamente.
"""
import os
import json
import time
import yaml
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

try:
    from groq import Groq
except Exception:
    Groq = None

from ..collectors import dexscreener, solana_tracker


# Tickers/nombres que ignoramos (consolidados, genéricos, basura común)
IGNORE_TICKERS = {
    "USDC", "USDT", "WSOL", "SOL", "ETH", "BTC", "WBTC", "WETH", "DAI",
    "PEPE", "WIF", "BONK", "TRUMP", "MELANIA", "FARTCOIN", "GOAT", "MOG",
    "DOGE", "SHIB", "TROLL", "PUDGY", "PENGU", "BOME", "POPCAT", "MEW",
    "MOTHER", "HAWK", "LIBRA", "SLERF", "PNUT", "MOODENG", "RETARDIO",
    "RAY", "JUP", "JTO",
}


def _load_settings(settings: Dict) -> Dict:
    return settings.get("event_radar", {})


def _load_state(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_state(path: str, data: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, path)


def discover_candidate_coins(min_mc: float, max_mc: float, max_coins: int = 25) -> List[Dict]:
    """Pull DexScreener boosted + Solana Tracker trending, filtra a coins low-mid cap.

    Devuelve coins normalizadas con campos: ticker, name, mint, market_cap_usd, etc.
    """
    candidates = []
    seen_mints = set()

    # Solana Tracker trending (1h, mejor para early stage)
    try:
        st_coins = solana_tracker.fetch_trending(timeframe="1h", limit=50)
        for c in st_coins:
            mint = c.get("mint")
            if not mint or mint in seen_mints:
                continue
            ticker = (c.get("ticker") or "").upper()
            if ticker in IGNORE_TICKERS:
                continue
            mc = float(c.get("market_cap_usd", 0) or 0)
            if mc < min_mc or mc > max_mc:
                continue
            seen_mints.add(mint)
            candidates.append(c)
    except Exception:
        pass

    # DexScreener boosted como segundo source
    try:
        ds_coins = dexscreener.trending_solana(limit=50, min_mc=int(min_mc), max_mc=int(max_mc))
        for c in ds_coins:
            mint = c.get("mint")
            if not mint or mint in seen_mints:
                continue
            ticker = (c.get("ticker") or "").upper()
            if ticker in IGNORE_TICKERS:
                continue
            seen_mints.add(mint)
            candidates.append(c)
    except Exception:
        pass

    # Score "thematicness" — preferimos coins con ticker no genérico
    def _thematic_score(c: Dict) -> float:
        ticker = (c.get("ticker") or "").upper()
        name = (c.get("name") or "")
        if len(ticker) < 3 or len(ticker) > 12:
            return 0.0
        score = 0.0
        # Ticker memorable (no es solo abreviatura)
        if len(ticker) >= 4 and ticker.isalpha():
            score += 2
        # Tiene name no vacío y >4 chars
        if name and len(name) > 4:
            score += 1
        # MC en rango ideal
        mc = float(c.get("market_cap_usd", 0) or 0)
        if 20000 <= mc <= 200000:
            score += 2
        elif 10000 <= mc <= 500000:
            score += 1
        return score

    candidates.sort(key=_thematic_score, reverse=True)
    return candidates[:max_coins]


def _llm_evaluate_catalyst(coins: List[Dict], api_key: str, model: str,
                          temperature: float = 0.3) -> List[Dict]:
    """Envía coins al LLM para identificar catalizadores futuros."""
    if Groq is None or not coins:
        return []

    client = Groq(api_key=api_key)

    system_prompt = """Eres un analista experto en memecoins. Te paso una lista de coins
listadas en DexScreener (Solana, low/mid cap). Tu trabajo: para cada coin, identificar
si hay un CATALIZADOR FUTURO conocido que pueda hacer que pumpee.

Razona usando tu conocimiento del mundo (fechas conocidas, eventos esperados,
lanzamientos, aniversarios, ciclos culturales). NO uses un calendario externo.

CRITERIOS:
- ¿El ticker/nombre/descripción te dice de qué temática es la coin?
- ¿Hay algún evento futuro CONFIRMADO o muy probable relacionado con esa temática?
- ¿Está la coin en MC bajo / con drawdown que permita buen R/R?
- ¿La narrativa del catalizador tiene chicha memética?

DEVUELVE EXCLUSIVAMENTE JSON:
{
  "evaluations": [
    {
      "mint": "...",
      "ticker": "...",
      "theme": "qué es la coin",
      "catalyst_identified": true|false,
      "catalyst_description": "descripción del evento esperado",
      "catalyst_estimated_date": "YYYY-MM-DD o 'unknown'",
      "days_to_catalyst": número o null,
      "rr_score": 0-10,
      "rr_reasoning": "por qué este R/R",
      "memetic_potential_when_catalyst_hits": 0-10,
      "recommendation": "ALERT | WATCH | IGNORE"
    },
    ...
  ]
}

REGLAS:
- Si NO identificas catalizador claro → recommendation=IGNORE
- Si catalyst >90 días: rr_score baja
- Si catalyst desconocido pero coin tematica fuerte: recommendation=WATCH (no ALERT)
- Solo ALERT si: catalizador claro + <60d + memetic potential >=7
- Sé conservador. Mejor IGNORE que falso positivo.
"""

    coin_payload = []
    for c in coins[:25]:
        coin_payload.append({
            "mint": c.get("mint", "")[:44],
            "ticker": c.get("ticker", ""),
            "name": c.get("name", ""),
            "description": (c.get("description") or "")[:200],
            "market_cap_usd": c.get("market_cap_usd", 0),
            "liquidity_usd": c.get("liquidity_usd", 0),
            "price_change_24h": c.get("price_change_24h", 0),
        })

    user_prompt = (
        "Evalúa cada coin. Identifica catalizadores futuros usando tu conocimiento del mundo.\n\n"
        + json.dumps({"coins": coin_payload, "today": datetime.now(timezone.utc).date().isoformat()},
                     ensure_ascii=False, indent=2)
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=2000,
        )
        content = resp.choices[0].message.content
        parsed = json.loads(content)
        return parsed.get("evaluations", []) or []
    except Exception as e:
        print(f"[event_radar] LLM error: {e}")
        return []


def get_alert_candidates(evaluations: List[Dict], coins_by_mint: Dict,
                         min_rr: float = 6.5) -> List[Dict]:
    """Filtra evaluaciones que merecen alerta y junta data de la coin."""
    out = []
    for ev in evaluations:
        if not ev.get("catalyst_identified"):
            continue
        if ev.get("recommendation") != "ALERT":
            continue
        rr = float(ev.get("rr_score", 0))
        if rr < min_rr:
            continue
        mint = ev.get("mint", "")
        coin_data = coins_by_mint.get(mint, {})
        if not coin_data:
            continue
        out.append({
            "coin": coin_data,
            "evaluation": ev,
        })
    out.sort(key=lambda x: float(x["evaluation"].get("rr_score", 0)), reverse=True)
    return out


def run(settings: Dict, state_path: str) -> List[Dict]:
    """Pipeline completo. Devuelve lista de alert candidates."""
    cfg = _load_settings(settings)
    if not cfg.get("enabled", True):
        return []

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return []

    min_mc = float(cfg.get("mc_range_min", 10000))
    max_mc = float(cfg.get("mc_range_max", 500000))
    max_eval = int(cfg.get("max_coins_to_evaluate", 25))
    min_rr = float(cfg.get("min_rr_score", 6.5))
    cooldown_h = int(cfg.get("cooldown_hours", 48))

    # State para dedup
    state = _load_state(state_path)
    state.setdefault("evaluated", {})
    now_iso = datetime.now(timezone.utc).isoformat()
    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(hours=cooldown_h)

    # Discovery
    coins = discover_candidate_coins(min_mc, max_mc, max_coins=max_eval)
    if not coins:
        return []

    coins_by_mint = {c.get("mint", ""): c for c in coins if c.get("mint")}

    # Filtra los ya evaluados recientemente
    to_evaluate = []
    for c in coins:
        mint = c.get("mint", "")
        prev = state["evaluated"].get(mint)
        if prev:
            try:
                last_ts = datetime.fromisoformat(prev.get("ts", ""))
                if last_ts > cooldown_cutoff:
                    continue
            except Exception:
                pass
        to_evaluate.append(c)

    if not to_evaluate:
        # Persist no-op
        state["last_run"] = now_iso
        _save_state(state_path, state)
        return []

    # LLM evaluation
    model = settings.get("scoring", {}).get("llm_model_primary", "llama-3.3-70b-versatile")
    temperature = float(settings.get("scoring", {}).get("llm_temperature", 0.3))
    evaluations = _llm_evaluate_catalyst(to_evaluate, api_key, model, temperature)

    # Persiste evaluaciones (para cooldown)
    for ev in evaluations:
        mint = ev.get("mint", "")
        if mint:
            state["evaluated"][mint] = {
                "ts": now_iso,
                "catalyst_identified": ev.get("catalyst_identified", False),
                "rr_score": ev.get("rr_score", 0),
                "recommendation": ev.get("recommendation", "IGNORE"),
            }

    # Purge evaluated entries >7 days old
    cutoff_7d = (now - timedelta(days=7)).isoformat()
    state["evaluated"] = {
        m: v for m, v in state["evaluated"].items()
        if v.get("ts", "") > cutoff_7d
    }
    state["last_run"] = now_iso
    _save_state(state_path, state)

    return get_alert_candidates(evaluations, coins_by_mint, min_rr=min_rr)
