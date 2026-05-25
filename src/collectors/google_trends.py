"""Google Trends — detecta picos súbitos de búsqueda (señal temprana fuerte)."""
from typing import Iterable, List
from .base import Signal, safe_text

try:
    from pytrends.request import TrendReq
except Exception:
    TrendReq = None


GEO_PYTRENDS = {
    "US": "united_states",
    "ES": "spain",
    "GB": "united_kingdom",
    "WORLDWIDE": "",
}


def fetch_trending(geo: str = "US") -> List[Signal]:
    """Fetch top daily trending searches para una región."""
    if TrendReq is None:
        return []
    try:
        py = TrendReq(hl="en-US", tz=0, retries=2, backoff_factor=0.3)
        pn_geo = GEO_PYTRENDS.get(geo, "united_states")
        df = py.trending_searches(pn=pn_geo)
    except Exception:
        return []

    out: List[Signal] = []
    if df is None or df.empty:
        return out
    for term in df[0].tolist():
        out.append(Signal(
            source=f"google_trends/{geo}",
            title=safe_text(str(term), 200),
            text=f"Trending search en {geo}: {term}",
            url=f"https://trends.google.com/trends/explore?q={term}",
            engagement=100,  # señal fuerte por defecto (es trending)
            lang="auto",
            raw_metadata={"geo": geo},
        ))
    return out


def collect(geos: Iterable[str]) -> List[Signal]:
    signals: List[Signal] = []
    for g in geos:
        signals.extend(fetch_trending(g))
    return signals
