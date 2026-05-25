"""Lifecycle states de un coin event-linked.

Estados:
- FRESH_LAUNCH: <24h, todavía explorando
- ACTIVE: tradeando con volumen, no extremo
- DORMANT_PUMPER: tuvo ATH alto, ahora drawdown ≥70%, evento por venir → buen R/R
- RECOVERING: subiendo desde un valle reciente
- DEAD: drawdown ≥95% Y sin volumen reciente

R/R score (0-10): combinación de drawdown + días al evento + smart money + holders + liquidity.
"""
from typing import Dict, Optional
from datetime import datetime, timezone


def _age_hours(coin: Dict) -> Optional[float]:
    """Edad en horas (None si desconocida)."""
    ts = coin.get("created_ts") or coin.get("first_seen_ts")
    if not ts:
        return None
    try:
        ts = float(ts)
        if ts > 1e12:
            ts = ts / 1000.0
        return (datetime.now(timezone.utc).timestamp() - ts) / 3600.0
    except Exception:
        return None


def classify(coin: Dict, days_to_event: Optional[int] = None,
             fresh_max_age_hours: float = 24,
             dead_min_drawdown_pct: float = 95) -> str:
    """Devuelve uno de: FRESH_LAUNCH, ACTIVE, DORMANT_PUMPER, RECOVERING, DEAD."""
    age = _age_hours(coin)
    mc = coin.get("market_cap_usd", 0) or 0
    peak_mc = coin.get("peak_mc_usd", mc) or mc
    drawdown_pct = 0.0
    if peak_mc > 0:
        drawdown_pct = max(0.0, (peak_mc - mc) / peak_mc * 100.0)
    vol_24h = coin.get("volume_24h", 0) or 0
    price_change_1h = coin.get("price_change_1h", 0) or 0
    price_change_24h = coin.get("price_change_24h", 0) or 0

    # FRESH
    if age is not None and age < fresh_max_age_hours:
        return "FRESH_LAUNCH"

    # DEAD: enorme drawdown Y sin volumen
    if drawdown_pct >= dead_min_drawdown_pct and vol_24h < 1000:
        return "DEAD"

    # RECOVERING: subiendo fuerte 24h desde un drawdown
    if price_change_24h >= 30 and drawdown_pct >= 50:
        return "RECOVERING"

    # DORMANT_PUMPER: drawdown alto + estable + algo de volumen + evento futuro
    if drawdown_pct >= 70 and vol_24h >= 1000:
        return "DORMANT_PUMPER"

    return "ACTIVE"


def compute_rr(coin: Dict, days_to_event: Optional[int],
               smart_money_signal: float = 0.0) -> Dict:
    """Calcula R/R score 0-10 y commentary.

    R/R alto si:
    - Drawdown grande desde ATH (más espacio para subir)
    - Evento confirmado <30 días
    - Liquidez suficiente para entrada/salida
    - Smart money detectado
    - Holders distribuidos (no concentrado)
    """
    mc = coin.get("market_cap_usd", 0) or 0
    peak_mc = coin.get("peak_mc_usd", mc) or mc
    drawdown_pct = 0.0
    if peak_mc > 0:
        drawdown_pct = max(0.0, (peak_mc - mc) / peak_mc * 100.0)
    liquidity = coin.get("liquidity_usd", 0) or 0

    score = 0.0
    reasons = []

    # Drawdown bonus (más espacio para subir)
    if drawdown_pct >= 80:
        score += 3.5
        reasons.append(f"drawdown {drawdown_pct:.0f}% desde ATH — espacio grande para re-pump")
    elif drawdown_pct >= 60:
        score += 2.0
        reasons.append(f"drawdown {drawdown_pct:.0f}% desde ATH — espacio decente")
    elif drawdown_pct >= 30:
        score += 0.8

    # Evento próximo bonus
    if days_to_event is not None:
        if 1 <= days_to_event <= 7:
            score += 3.0
            reasons.append(f"evento en {days_to_event}d — ventana imminente")
        elif 8 <= days_to_event <= 21:
            score += 2.2
            reasons.append(f"evento en {days_to_event}d — buena anticipación")
        elif 22 <= days_to_event <= 45:
            score += 1.3
            reasons.append(f"evento en {days_to_event}d — anticipación media")
        elif days_to_event <= 0:
            score += 1.5
            reasons.append("evento en curso o reciente")

    # Liquidez (necesaria para entrar/salir)
    if liquidity >= 30000:
        score += 1.5
    elif liquidity >= 5000:
        score += 0.7
    elif liquidity < 500:
        score -= 1.0
        reasons.append(f"⚠️ liquidez baja ${liquidity:,.0f} — slippage alto")

    # Smart money bonus
    if smart_money_signal > 0:
        score += min(2.0, smart_money_signal)
        reasons.append(f"smart money activo (+{smart_money_signal:.1f})")

    # Drawdown extremo (>95%) puede ser DEAD, penaliza
    if drawdown_pct >= 95 and (coin.get("volume_24h", 0) or 0) < 500:
        score -= 2.0
        reasons.append("drawdown extremo + sin volumen — riesgo DEAD")

    score = max(0.0, min(10.0, score))

    # Multiplier potencial (cuánto puede subir si pumpea al 50% de ATH)
    target_mc = peak_mc * 0.5
    upside_x = (target_mc / mc) if mc > 0 else 0.0

    return {
        "rr_score": round(score, 1),
        "rr_reasons": reasons,
        "drawdown_pct": round(drawdown_pct, 1),
        "upside_to_50pct_ath_x": round(upside_x, 1),
        "target_mc_50pct_ath": int(target_mc),
        "current_mc": int(mc),
        "peak_mc": int(peak_mc),
    }
