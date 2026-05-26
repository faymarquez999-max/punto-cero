"""Narrative Potential Scorer V3.

Reemplaza el scorer anterior. Cambio fundamental:
- ANTES: comparaba la narrativa con casos pasados ("¿se parece a PNUT?")
- AHORA: evalúa si la narrativa tiene INGREDIENTES MEMETICOS desde principios

El LLM razona como un degen culturalmente despierto:
- ¿Qué emoción provoca?
- ¿Es memeable la frase/imagen/ticker?
- ¿Hay potencial visual?
- ¿Toca arquetipos culturales?
- ¿Es absurdo/polarizante/simple/viral?

Output: score 0-100 + tickers candidatos + duración watch + recomendación
"""
import os
import json
import yaml
import time
from typing import Dict, List, Optional

try:
    from groq import Groq
except Exception:
    Groq = None


def load_principles(path: str) -> Dict:
    """Carga los principios memetéticos desde YAML."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def build_system_prompt(principles: Dict) -> str:
    """Construye el system prompt con los principios memetéticos."""
    dims = principles.get("dimensions", {})
    dim_lines = []
    for name, info in dims.items():
        if isinstance(info, dict):
            dim_lines.append(f"  - {name} (peso {info.get('weight', 0)}): {info.get('description', '')}")

    archetypes = principles.get("archetypes", [])
    arch_lines = "\n".join(f"  - {a}" for a in archetypes[:18])

    red_flags = principles.get("red_flags", [])
    rf_lines = "\n".join(f"  - {r}" for r in red_flags)

    rules = principles.get("rules", [])
    rule_lines = "\n".join(f"  - {r}" for r in rules)

    return f"""Eres un detector de potencial memético. Tu trabajo: leer una narrativa fresca
(noticia, evento, declaración, leak, momento viral) y decidir si tiene ingredientes
para convertirse en memecoin VIRAL en horas o días.

NO COMPARES la narrativa con coins pasados concretos (PNUT, PEPE, etc.). Razona con
PRINCIPIOS, no con plantillas. Cada momento viral es único — buscas si tiene los
INGREDIENTES, no si se parece a algo.

DIMENSIONES A EVALUAR (cada una 0-10, pondéralas):
{chr(10).join(dim_lines)}

ARQUETIPOS QUE FUNCIONAN (úsalos para identificar patrón, no para casarte):
{arch_lines}

SEÑALES QUE BAJAN EL POTENCIAL (red flags):
{rf_lines}

REGLAS:
{rule_lines}

IMPORTANTE:
- Eventos programados rutinarios (UFC normal, NBA, partidos sports, lanzamientos
  conocidos sin twist) = SCORE BAJO.
- Frases/momentos de figuras top (Trump, Elon, etc.) tienen multiplicador SOLO si
  son ABSURDAS, IMPACTANTES o GENERAN DRAMA — no si son rutinarias.
- Animal + injusticia + foto = casi siempre dispara alto.
- Si requiere >2 frases para explicarlo, baja memeabilidad.

GENERA TICKERS CANDIDATOS (5-10): predice qué tickers podría crear un degen.
- Sé creativo, abreviado, memorable.
- No tickers ya muy explotados (TRUMP, PEPE, etc.) salvo que sean direct match.
- Combina: persona/lugar + tema, o palabras clave de la frase viral.

ESTIMA tiempo de ventana (cuándo será peak interest):
- Shock político/celebridad: 4-24h
- Momento viral absurdo: 12-72h
- Evento médico/salud: 24-168h
- Conspiración/leak: 48-168h
- Tendencia cultural lenta: 168-720h

OUTPUT EXCLUSIVAMENTE JSON VÁLIDO:
{{
  "score": 0-100,
  "memetic_dimensions": {{
    "emotional": 0-10,
    "memeable": 0-10,
    "visual": 0-10,
    "cultural_resonance": 0-10,
    "polarizing": 0-10,
    "absurdity": 0-10,
    "simplicity": 0-10,
    "velocity": 0-10
  }},
  "narrative_summary": "1-2 frases describiendo la narrativa",
  "why_memeable": "explicación corta de los ingredientes",
  "matched_archetype": "uno de los archetypes listed, o 'novel'",
  "category": "categoría libre que el LLM decida",
  "candidate_tickers": ["TICKER1", "TICKER2", ...],
  "time_window_hours": número estimado,
  "coin_emergence_probability_24h": "low | medium | high",
  "confidence": "low | medium | high",
  "recommendation": "STRONG_WATCH | WATCH | IGNORE",
  "watch_duration_hours": 48-168,
  "key_terms_for_dex_search": ["palabras", "para", "buscar", "en", "dexscreener"]
}}"""


def _build_user_prompt(cluster: Dict, pre_bonuses: Optional[Dict] = None) -> str:
    """Construye el prompt user con la info de la narrativa."""
    sample_signals = []
    for s in cluster.get("signals", [])[:5]:
        sample_signals.append({
            "source": getattr(s, "source", ""),
            "title": getattr(s, "title", ""),
            "engagement": getattr(s, "engagement", 0),
            "excerpt": (getattr(s, "text", "") or "")[:180],
            "url": getattr(s, "url", ""),
        })

    payload = {
        "narrative_cluster": {
            "top_title": cluster.get("top_title"),
            "key_terms": cluster.get("key_terms", [])[:15],
            "total_engagement": cluster.get("engagement_total"),
            "n_source_families": cluster.get("n_distinct_families"),
            "source_families": cluster.get("source_families"),
            "signal_count": cluster.get("signal_count"),
            "sample_signals": sample_signals,
        },
        "pre_bonuses": pre_bonuses or {},
    }
    return (
        "Evalúa esta narrativa según los principios memetéticos. "
        "Devuelve JSON exacto según el system prompt.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def score_narrative(cluster: Dict, principles: Dict,
                    api_key: Optional[str] = None,
                    model: str = "llama-3.3-70b-versatile",
                    fallback_model: str = "llama-3.1-8b-instant",
                    temperature: float = 0.4,
                    pre_bonuses: Optional[Dict] = None) -> Dict:
    """Llama al LLM para evaluar potencial memético."""
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key or Groq is None:
        return {"score": 0, "error": "no_groq_key_or_lib"}

    client = Groq(api_key=api_key)
    system_prompt = build_system_prompt(principles)
    user_prompt = _build_user_prompt(cluster, pre_bonuses)

    def _call(m: str, attempts: int = 3):
        last_err = None
        for i in range(attempts):
            try:
                return client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    max_tokens=900,
                )
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                if "rate" in msg or "429" in msg or "timeout" in msg:
                    time.sleep(2 + i * 2)
                    continue
                break
        raise last_err

    try:
        resp = _call(model)
    except Exception:
        try:
            resp = _call(fallback_model)
        except Exception as e:
            return {"score": 0, "error": f"groq_failure: {e}"}

    try:
        content = resp.choices[0].message.content
        parsed = json.loads(content)
    except Exception as e:
        return {"score": 0, "error": f"parse_failure: {e}"}

    # Aplica bonuses pre-LLM (cross-source momentum)
    base_score = int(parsed.get("score", 0))
    bonus = int((pre_bonuses or {}).get("total_bonus", 0))
    final_score = min(100, base_score + bonus)
    parsed["score_base"] = base_score
    parsed["score_bonus"] = bonus
    parsed["score"] = final_score
    parsed["bonus_reasons"] = (pre_bonuses or {}).get("reasons", [])
    return parsed
