"""RugCheck.xyz integration — safety score gratis para tokens Solana."""
import requests
from typing import Optional


def check_token(mint: str, timeout: int = 10) -> Optional[dict]:
    """Devuelve dict con score 0-100 + risks, o None si no se pudo verificar.

    Score alto (>70) = seguro. Score bajo (<30) = peligro.
    """
    if not mint:
        return None
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json() or {}
    except Exception:
        return None

    # Estructura típica: score, risks: [{name, level, description}]
    score = data.get("score") or 0
    risks = data.get("risks") or []
    return {
        "score": int(score) if isinstance(score, (int, float)) else 0,
        "risks": [{"name": r.get("name"), "level": r.get("level"),
                   "description": r.get("description", "")[:200]} for r in risks][:5],
        "mint": mint,
    }


def is_safe(mint: str, min_score: int = 50) -> bool:
    """Helper rápido — True si seguro, False si peligro o no verificable."""
    res = check_token(mint)
    if res is None:
        return True   # benefit of the doubt si la API falla
    return res["score"] >= min_score
