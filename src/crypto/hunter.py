"""Crypto Hunter — dada una narrativa scored, busca coins relacionadas.

Mejoras:
- Term filtering más estricto (≥3 chars, sin stopwords)
- RugCheck integration (opcional)
- Mejor scoring: bonus por socials presentes
- Filtro de edad mínima/máxima del token
"""
from typing import List, Dict
from datetime import datetime, timezone
from rapidfuzz import fuzz
from ..collectors import pump_fun, dexscreener
from . import rugcheck as rc


# Stopwords que NUNCA buscamos (ruido)
NEVER_SEARCH = {
    "the","new","says","said","more","just","this","that","with","from",
    "memecoin","crypto","coin","token","solana","pump","fun",
    "viral","breaking","news","today","reports", "según", "dijo",
}


def _candidate_terms(narrative: Dict, cluster: Dict) -> List[str]:
    terms = []
    seen = set()
    # LLM tickers primero (más fiable)
    for t in narrative.get("suggested_tickers", []) or []:
        if t and len(str(t)) >= 2:
            up = str(t).upper().strip("$")
            if up not in seen and up.lower() not in NEVER_SEARCH:
                terms.append(up)
                seen.add(up)
    # luego key terms (más ruidosos)
    for t in cluster.get("key_terms", []) or []:
        s = str(t).strip("$")
        if len(s) < 3:
            continue
        up = s.upper()
        if up.lower() in NEVER_SEARCH:
            continue
        if up not in seen:
            terms.append(up)
            seen.add(up)
    return terms[:15]


def _score_match(coin: Dict, terms: List[str]) -> float:
    ticker = (coin.get("ticker") or "").upper()
    name = (coin.get("name") or "").upper()
    desc = (coin.get("description") or "").upper()
    best = 0.0
    for t in terms:
        if not t:
            continue
        s_ticker = fuzz.ratio(t, ticker)
        s_name = fuzz.partial_ratio(t, name) if name else 0
        s_desc = fuzz.partial_ratio(t, desc) * 0.5 if desc else 0
        s = max(s_ticker, s_name, s_desc)
        if t == ticker or (len(t) >= 4 and t in ticker) or (len(ticker) >= 4 and ticker in t):
            s = max(s, 95)
        if s > best:
            best = s

    # Bonus si tiene socials presentes (señal de equipo serio)
    if coin.get("source") == "pump.fun":
        socials_count = sum(1 for k in ("twitter", "telegram", "website") if coin.get(k))
        if socials_count >= 2:
            best = min(100, best + 3)

    return best


def _token_age_minutes(coin: Dict) -> float | None:
    ts = coin.get("created_ts")
    if not ts:
        return None
    try:
        ts = float(ts)
        if ts > 1e12:
            ts = ts / 1000.0   # ms → s
        return (datetime.now(timezone.utc).timestamp() - ts) / 60.0
    except Exception:
        return None


def hunt(narrative: Dict, cluster: Dict,
         fuzzy_threshold: float = 0.65,
         max_coins: int = 5,
         min_liquidity: float = 500,
         min_age_minutes: float = 5,
         max_age_hours: float = 168,
         use_rugcheck: bool = True,
         min_safety_score: int = 50,
         **_ignored) -> List[Dict]:
    """Hunt early-stage coins matching narrativa. Ignora kwargs extra (e.g. min_holders).

    NOTA: para hunting, pulimos Pump.fun con filtros PERMISIVOS (sin require_socials)
    porque queremos candidates amplios y luego scoreamos con match_score + rugcheck.
    """
    terms = _candidate_terms(narrative, cluster)
    if not terms:
        return []

    candidates: List[Dict] = []
    try:
        # Filtros permisivos: queremos broad recall, no precision
        pf = pump_fun.fetch_new_coins(
            limit=100, min_mc=1000, max_mc=200000,
            require_socials=False, require_description=False, min_description_chars=0,
        )
    except Exception:
        pf = []
    candidates.extend(pf)

    seen_mints = set(c.get("mint", "") for c in candidates if c.get("mint"))
    # solo searches con primer 6 terms (más relevantes)
    for t in terms[:6]:
        try:
            ds = dexscreener.search_pairs(t)
        except Exception:
            ds = []
        for c in ds:
            if not c.get("mint") or c["mint"] in seen_mints:
                continue
            if (c.get("liquidity_usd") or 0) < min_liquidity:
                continue
            seen_mints.add(c["mint"])
            candidates.append(c)

    # Filtros de edad y scoring
    scored = []
    threshold_pct = fuzzy_threshold * 100
    for c in candidates:
        age = _token_age_minutes(c)
        if age is not None:
            if age < min_age_minutes:
                continue
            if age > max_age_hours * 60:
                continue
        s = _score_match(c, terms)
        if s >= threshold_pct:
            c["match_score"] = round(s, 1)
            scored.append(c)

    # Ordena
    scored.sort(key=lambda x: (x["match_score"], -1 * (x.get("market_cap_usd") or 1e12)),
                reverse=True)

    # RugCheck para top-N (no hagas calls innecesarios)
    final = []
    for c in scored:
        if len(final) >= max_coins:
            break
        if use_rugcheck and c.get("chain") == "solana" and c.get("mint"):
            try:
                rc_res = rc.check_token(c["mint"])
                if rc_res is not None:
                    c["safety_score"] = rc_res["score"]
                    c["safety_risks"] = rc_res["risks"]
                    if rc_res["score"] < min_safety_score:
                        c["match_score"] = c["match_score"] * 0.5  # penaliza pero no excluye
                        c["safety_warning"] = True
            except Exception:
                pass
        final.append(c)

    return final
