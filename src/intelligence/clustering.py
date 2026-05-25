"""Agrupa señales similares en 'narrativas' candidatas.

Ajustes:
- Threshold subido: min_overlap=3, title_similarity=80
- Normalización acentos español
- Tokens también incluyen tickers $XYZ
- Boost de prioridad para clusters con múltiples fuentes distintas
"""
from typing import List, Dict, Iterable
import unicodedata
from rapidfuzz import fuzz
from ..collectors.base import Signal


STOPWORDS = {
    "the","a","an","and","or","of","to","in","on","for","is","are","was","were","be",
    "el","la","los","las","un","una","de","del","y","o","en","es","son","fue","fueron",
    "this","that","with","from","by","at","it","as","into","but","not","new","just",
    "what","why","how","when","who","which","says","said","more","most","than","also",
    "esto","eso","sobre","tras","tras","entre","desde","sin","con","por","para","muy",
    "i","you","we","they","he","she","my","your","his","her","its","our","their",
    "como","cuando","donde","quien","cual","cuanto"
}


def _normalize(s: str) -> str:
    """Lowercase + remove accents."""
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def _tokens(text: str) -> set:
    toks = set()
    text_norm = _normalize(text)
    # Captura tickers $XYZ antes de strip
    for w in text_norm.split():
        # ticker $abc → ABC
        if w.startswith("$") and len(w) >= 2:
            t = "".join(c for c in w[1:] if c.isalnum()).upper()
            if 2 <= len(t) <= 12:
                toks.add(f"${t}")
                continue
        w = "".join(c for c in w if c.isalnum())
        if w and len(w) > 2 and w not in STOPWORDS:
            toks.add(w)
    return toks


def cluster_signals(signals: List[Signal], min_overlap: int = 3,
                    title_similarity: int = 80) -> List[Dict]:
    """Devuelve clusters ordenados por (n_fuentes_distintas, engagement_total)."""
    clusters: List[Dict] = []

    for sig in signals:
        tokens = _tokens(sig.title + " " + sig.text[:300])
        if not tokens:
            continue
        placed = False
        for c in clusters:
            shared = tokens & c["_tokens"]
            sim = fuzz.token_set_ratio(_normalize(sig.title), _normalize(c["top_title"]))
            if len(shared) >= min_overlap or sim >= title_similarity:
                c["signals"].append(sig)
                c["_tokens"] |= tokens
                c["engagement_total"] += sig.engagement
                c["sources"].add(sig.source)
                if sig.engagement > c["_top_eng"]:
                    c["_top_eng"] = sig.engagement
                    c["top_title"] = sig.title
                placed = True
                break
        if not placed:
            clusters.append({
                "_tokens": set(tokens),
                "_top_eng": sig.engagement,
                "top_title": sig.title,
                "signals": [sig],
                "engagement_total": sig.engagement,
                "sources": {sig.source},
            })

    result = []
    for c in clusters:
        if not c["signals"]:
            continue
        # Distintos "source families" (reddit, google_news, bluesky...) son la métrica clave
        source_families = set()
        for s in c["sources"]:
            family = s.split("/")[0] if "/" in s else s
            source_families.add(family)

        result.append({
            "key_terms": sorted(c["_tokens"])[:15],
            "top_title": c["top_title"],
            "signals": c["signals"],
            "engagement_total": c["engagement_total"],
            "sources": sorted(c["sources"]),
            "source_families": sorted(source_families),
            "signal_count": len(c["signals"]),
            "n_distinct_families": len(source_families),
        })
    # Ordena: más familias distintas primero (cross-source > engagement)
    result.sort(key=lambda x: (x["n_distinct_families"], x["engagement_total"]), reverse=True)
    return result
