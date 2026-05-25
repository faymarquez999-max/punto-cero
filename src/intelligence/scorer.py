"""Scoring narrativo con Groq.

Mejoras:
- Pre-filtra casos históricos por categoría/keywords antes de mandar al LLM
- Retry con backoff en rate-limit
- Devuelve también `confidence` y `time_window_hours`
- Acepta `pre_score_bonuses` del momentum tracker
"""
import os
import json
import yaml
import time
from typing import Dict, List, Any, Optional

try:
    from groq import Groq
except Exception:
    Groq = None


SYSTEM_PROMPT = """Eres un analista experto en narrativas virales y memecoins de Solana.

OBJETIVO CRÍTICO: detectar narrativas FRESCAS (primeras horas) con potencial de generar
memecoins explosivas en EARLY STAGE (MC <100k). NO surfacing coins ya consolidadas
(FARTCOIN, GOAT, PEPE, TRUMP, WIF, etc. ya están — esos no nos interesan).

Tu trabajo: leer una narrativa emergente y decidir si:
(a) Es candidata a generar una NUEVA memecoin pumpeable
(b) Si ya hay coin temprana matching (MC <100k), o probablemente la habrá pronto
(c) Si tiene el patrón "evento futuro + dormant coin existente" (event-linked dormant pumper)

Razona con sentido común. Sé CONSERVADOR: mejor decir score bajo que falso positivo.

Compara SIEMPRE con los CASOS HISTÓRICOS que te paso. Los casos son PATRONES de aprendizaje,
no targets. Si la narrativa nueva matchea el patrón de PNUT (animal+injusticia),
WIF (foto absurda), TRUMP-gala (evento+dormant whale), etc. → sube score.

CRITERIOS QUE SUBEN SCORE:
- Injusticia clara con villano/víctima identificable (multiplica)
- Animal involucrado (ardilla, perro, gato, etc.) — multiplica
- Frase o imagen muy memeable (corta, pegadiza, no técnica)
- Atleta nacional + victoria épica + país que celebra
- Anticipación a evento UFC/gaming/Mundial confirmado
- Figura política polarizante + shock real (no rumor)
- Tema tabú con reconocimiento oficial (UFO disclosure, conspiración real)
- Nombre o ticker MUY concreto y único (no genérico)
- Múltiples fuentes distintas hablan del tema (ya pre-calculado, ver `pre_bonuses`)

CRITERIOS QUE BAJAN SCORE:
- Narrativa demasiado genérica
- Tema sin emocionalidad ni meme potential
- Noticia técnica/financiera seca
- Repetición de algo ya muy explotado (fatiga)
- Solo una fuente / una comunidad nicho
- Copycat de tendencia caliente (peligroso, score moderado)

`time_window_hours` = cuántas horas estimas que dura la ventana de entrada óptima.
  - Eventos lentos (gaming launch): 168-720h
  - Sports/UFC fight: 24-72h
  - Shock político: 4-24h
  - Celebrity launch directo: 0.5-4h

Responde EXCLUSIVAMENTE JSON válido:
{
  "score": 0-100,
  "category": "emotional_injustice | absurd_humor | ufc_victory | ufc_return | gaming_anticipation | sports_national | political_shock | mystery_conspiracy | pandemic_fear | celebrity_endorsement | meme_classic_revival | viral_moment | noise",
  "narrative_summary": "1-2 frases",
  "why_viral": "explicación corta del potencial",
  "similar_to_case": "id del caso histórico más parecido, o 'none'",
  "emotional_drivers": ["lista", "de", "emociones"],
  "suggested_tickers": ["POSIBLES", "TICKERS"],
  "risk_flags": ["lista de riesgos"],
  "time_window_hours": 24,
  "confidence": "low | medium | high",
  "recommendation": "STRONG_ALERT | WATCH | IGNORE"
}
"""


def load_historical_cases(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("historical_cases", [])


def _select_relevant_cases(cluster: Dict, historical: List[Dict], top_n: int = 5) -> List[Dict]:
    """Pre-selecciona casos históricos más probables vía keyword overlap."""
    terms = set((t or "").lower().strip("$") for t in cluster.get("key_terms", []))
    title = (cluster.get("top_title") or "").lower()
    scored = []
    for case in historical:
        text = " ".join([
            case.get("name", ""), case.get("category", ""),
            case.get("why_viral", ""), case.get("pattern_signature", ""),
            " ".join(case.get("emotional_drivers", []) or []),
        ]).lower()
        score = 0
        for t in terms:
            if t and t in text:
                score += 2
        # categoría hint
        for cat_hint in ("ufc", "gta", "world cup", "mundial", "topuria", "trump",
                         "pepe", "doge", "ufo", "virus"):
            if cat_hint in title and cat_hint in text:
                score += 3
        scored.append((score, case))
    scored.sort(key=lambda x: x[0], reverse=True)
    # incluir top_n con score>0, y rellena con genéricos si no llega
    selected = [c for s, c in scored if s > 0][:top_n]
    if len(selected) < top_n:
        for s, c in scored:
            if c not in selected:
                selected.append(c)
            if len(selected) >= top_n:
                break
    return selected


def _build_user_prompt(cluster: Dict, historical_cases: List[Dict],
                      pre_bonuses: Optional[Dict] = None) -> str:
    cases_short = []
    for c in historical_cases:
        cases_short.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "category": c.get("category"),
            "why_viral": c.get("why_viral"),
            "pattern_signature": c.get("pattern_signature"),
            "multiplier": c.get("multiplier"),
        })
    sample_signals = []
    for s in cluster.get("signals", [])[:5]:
        sample_signals.append({
            "source": s.source,
            "title": s.title,
            "engagement": s.engagement,
            "excerpt": (s.text or "")[:160],
        })
    payload = {
        "narrative_cluster": {
            "top_title": cluster.get("top_title"),
            "key_terms": cluster.get("key_terms"),
            "total_engagement": cluster.get("engagement_total"),
            "n_source_families": cluster.get("n_distinct_families"),
            "source_families": cluster.get("source_families"),
            "signal_count": cluster.get("signal_count"),
            "sample_signals": sample_signals,
        },
        "pre_bonuses": pre_bonuses or {},
        "historical_cases_reference": cases_short,
    }
    return (
        "Analiza esta narrativa comparándola con los casos históricos. "
        "Devuelve JSON exacto según el system prompt.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def score_cluster(cluster: Dict, historical_cases: List[Dict],
                  api_key: Optional[str] = None,
                  model: str = "llama-3.3-70b-versatile",
                  fallback_model: str = "llama-3.1-8b-instant",
                  temperature: float = 0.3,
                  pre_bonuses: Optional[Dict] = None) -> Dict[str, Any]:
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key or Groq is None:
        return {"score": 0, "error": "no_groq_key_or_lib"}

    client = Groq(api_key=api_key)
    # Pre-filtra casos: top 5 más relevantes en vez de los 18+ completos
    relevant = _select_relevant_cases(cluster, historical_cases, top_n=5)
    user_prompt = _build_user_prompt(cluster, relevant, pre_bonuses)

    def _call(m: str, attempts: int = 3):
        last_err = None
        for i in range(attempts):
            try:
                return client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    max_tokens=700,
                )
            except Exception as e:
                last_err = e
                # rate limit → backoff
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

    # Aplica bonuses pre-LLM si vinieron
    base_score = int(parsed.get("score", 0))
    bonus = int((pre_bonuses or {}).get("total_bonus", 0))
    final_score = min(100, base_score + bonus)
    parsed["score_base"] = base_score
    parsed["score_bonus"] = bonus
    parsed["score"] = final_score
    parsed["bonus_reasons"] = (pre_bonuses or {}).get("reasons", [])
    return parsed
