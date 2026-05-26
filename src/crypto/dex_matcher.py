"""DEX Matcher V3 — busca coins matching active watches en DexScreener (no Pump.fun).

Cambios clave vs hunter.py viejo:
- SOLO usa DexScreener (filtro de calidad: coin tradeada de verdad)
- Filtros DUROS: MC 10k-500k, liquidez >$5k, holders >50, volumen 24h >$5k, edad >10min
- No surfacea coins consolidadas (>500k MC)
- Match preferente: ticker exacto en candidate_tickers del watch
- Match secundario: name/desc contiene key_terms del watch

Para cada Active Watch, busca DexScreener con cada candidate ticker → valida → si pasa filtros, devuelve match.
"""
from typing import List, Dict, Optional
from datetime import datetime, timezone
from rapidfuzz import fuzz
from ..collectors import dexscreener
from . import rugcheck as rc


def _token_age_minutes(coin: Dict) -> Optional[float]:
    """Edad en minutos desde created_ts si disponible."""
    ts = coin.get("created_ts") or coin.get("pairCreatedAt")
    if not ts:
        return None
    try:
        ts = float(ts)
        if ts > 1e12:
            ts = ts / 1000.0
        return (datetime.now(timezone.utc).timestamp() - ts) / 60.0
    except Exception:
        return None


def _passes_hard_filters(coin: Dict, cfg: Dict) -> tuple[bool, str]:
    """Aplica los filtros duros. Devuelve (ok, razón_si_falla)."""
    mc = float(coin.get("market_cap_usd", 0) or 0)
    liq = float(coin.get("liquidity_usd", 0) or 0)
    vol = float(coin.get("volume_h24", 0) or coin.get("volume_24h", 0) or 0)

    min_mc = float(cfg.get("min_mc_usd", 10000))
    max_mc = float(cfg.get("max_mc_usd", 500000))
    min_liq = float(cfg.get("min_liquidity_usd", 5000))
    min_vol = float(cfg.get("min_volume_24h_usd", 5000))
    min_age = float(cfg.get("min_age_minutes", 10))

    if mc < min_mc:
        return False, f"MC ${mc:,.0f} < min ${min_mc:,.0f}"
    if mc > max_mc:
        return False, f"MC ${mc:,.0f} > max ${max_mc:,.0f}"
    if liq < min_liq:
        return False, f"liquidez ${liq:,.0f} < ${min_liq:,.0f}"
    if vol < min_vol:
        return False, f"vol24h ${vol:,.0f} < ${min_vol:,.0f}"

    age = _token_age_minutes(coin)
    if age is not None and age < min_age:
        return False, f"edad {age:.0f}min < {min_age}min"

    return True, ""


def _score_match(coin: Dict, watch: Dict) -> tuple[float, str]:
    """Score 0-100 de cuán bien coincide la coin con el watch.

    Prioridad:
    1. Ticker exacto match con candidate_tickers → 95-100
    2. Ticker substring fuerte con candidates → 80-94
    3. Name/desc contiene key_term → 65-79
    """
    ticker = (coin.get("ticker") or "").upper()
    name = (coin.get("name") or "").upper()
    desc = (coin.get("description") or "").upper()

    candidates = [t.upper().strip("$") for t in (watch.get("candidate_tickers") or [])]
    key_terms = [t.upper().strip("$") for t in (watch.get("key_terms_for_dex_search") or [])]

    best = 0.0
    reason = ""

    # 1. Ticker exact match
    for c in candidates:
        if c and ticker == c:
            return 100.0, f"ticker exact: {ticker}=={c}"
        if c and len(c) >= 3 and (c in ticker or ticker in c):
            sim = fuzz.ratio(c, ticker)
            if sim >= 80 and sim > best:
                best = sim
                reason = f"ticker close: {ticker}~{c} ({sim}%)"

    # 2. Key terms in name or desc
    for t in key_terms + candidates:
        if not t or len(t) < 3:
            continue
        if t in name:
            score = max(70, fuzz.partial_ratio(t, name))
            if score > best:
                best = score
                reason = f"name match: {t} in {name[:30]}"
        elif t in desc:
            score = max(65, fuzz.partial_ratio(t, desc) - 5)
            if score > best:
                best = score
                reason = f"desc match: {t}"

    return best, reason


def find_matching_coin(watch: Dict, filters_cfg: Dict,
                       use_rugcheck: bool = True,
                       min_safety_score: int = 50,
                       fuzzy_threshold: float = 0.70) -> Optional[Dict]:
    """Busca en DexScreener una coin que matchee este watch. Devuelve la mejor o None."""
    candidates = (watch.get("candidate_tickers") or [])[:8]
    key_terms = (watch.get("key_terms_for_dex_search") or [])[:6]
    queries = list(dict.fromkeys([q for q in (candidates + key_terms) if q and len(q) >= 3]))

    if not queries:
        return None

    # Pull all candidates via DexScreener search
    all_pairs: List[Dict] = []
    seen_mints = set()
    for q in queries:
        try:
            results = dexscreener.search_pairs(q)
        except Exception:
            continue
        for p in results:
            if not p.get("mint") or p["mint"] in seen_mints:
                continue
            # Solo Solana
            if (p.get("chain") or "").lower() != "solana":
                continue
            seen_mints.add(p["mint"])
            all_pairs.append(p)

    if not all_pairs:
        return None

    # Score + filter
    threshold_pct = fuzzy_threshold * 100
    scored = []
    for coin in all_pairs:
        match_score, reason = _score_match(coin, watch)
        if match_score < threshold_pct:
            continue
        passes, fail_reason = _passes_hard_filters(coin, filters_cfg)
        if not passes:
            coin["_rejected"] = fail_reason
            continue
        coin["match_score"] = round(match_score, 1)
        coin["match_reason"] = reason
        scored.append(coin)

    if not scored:
        return None

    # Ordena: match_score desc, luego MC asc (preferir más bajos)
    scored.sort(key=lambda x: (x["match_score"], -1 * (x.get("market_cap_usd") or 1e12)),
                reverse=True)

    best = scored[0]

    # RugCheck del mejor (no de todos)
    if use_rugcheck and best.get("mint"):
        try:
            rc_res = rc.check_token(best["mint"])
            if rc_res is not None:
                best["safety_score"] = rc_res["score"]
                best["safety_risks"] = rc_res["risks"]
                if rc_res["score"] < min_safety_score:
                    best["safety_warning"] = True
                    # No descartamos, solo advertimos
        except Exception:
            pass

    return best
