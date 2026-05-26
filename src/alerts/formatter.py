"""Alert formatters V3 — 4 tipos nuevos enfocados a narrativas.

1. 🚨 POTENTIAL NARRATIVE — narrativa detectada, posiblemente coin en 24h
2. 💎 COIN MATCHED ACTIVE WATCH — apareció coin matching un watch
3. 🎯 EVENT-LINKED OPPORTUNITY — coin existente con catalizador futuro inferido
4. ⚡ ESCALATION — narrativa watched está creciendo
"""
from typing import Dict, List


def _esc(s) -> str:
    if s is None:
        return ""
    s = str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ====== 1. POTENTIAL NARRATIVE ======
def format_potential_narrative(narrative: Dict, cluster: Dict, watch: Dict) -> str:
    score = narrative.get("score", 0)
    base = narrative.get("score_base", score)
    bonus = narrative.get("score_bonus", 0)
    category = narrative.get("category", "?")
    summary = narrative.get("narrative_summary", "")
    why = narrative.get("why_memeable", "")
    archetype = narrative.get("matched_archetype", "")
    tickers = ", ".join((narrative.get("candidate_tickers") or [])[:8])
    time_window = narrative.get("time_window_hours", "?")
    coin_prob = narrative.get("coin_emergence_probability_24h", "?")
    confidence = narrative.get("confidence", "?")
    duration = watch.get("duration_hours", 72)

    dims = narrative.get("memetic_dimensions", {})
    dim_str = " · ".join([
        f"emo {dims.get('emotional',0)}",
        f"meme {dims.get('memeable',0)}",
        f"visual {dims.get('visual',0)}",
        f"abs {dims.get('absurdity',0)}",
        f"vel {dims.get('velocity',0)}",
    ])

    n_fams = cluster.get("n_distinct_families", 0)
    fams = ", ".join(cluster.get("source_families", []) or [])

    src_sample = cluster.get("signals", [])[:3]
    src_lines = []
    for s in src_sample:
        url = _esc(getattr(s, "url", "") or "")
        src = _esc(getattr(s, "source", "") or "")
        title = _esc((getattr(s, "title", "") or "")[:140])
        src_lines.append(f"• <a href=\"{url}\">{src}</a>: {title}")

    bonus_reasons = narrative.get("bonus_reasons", []) or []

    msg = [
        f"🚨 <b>NARRATIVA POTENCIAL</b> · Score <b>{score}</b>/100",
        f"📂 {_esc(category)} · arquetipo: <code>{_esc(archetype)}</code>",
        "",
        f"<b>{_esc(cluster.get('top_title', summary[:80]))}</b>",
        "",
        f"💡 <b>Resumen:</b> {_esc(summary)}",
        f"⚡ <b>Por qué memeable:</b> {_esc(why)}",
        "",
        f"🎯 <b>Tickers candidatos:</b> {_esc(tickers)}",
        f"⏱️ <b>Ventana estimada:</b> {time_window}h · prob coin 24h: {_esc(coin_prob)}",
        f"🔭 <b>Watch activo:</b> {duration}h · confianza: {_esc(confidence)}",
        "",
        f"📊 Dimensiones: {dim_str}",
        f"📡 Cross-source: {n_fams} familias ({_esc(fams)})",
    ]
    if bonus_reasons:
        msg.append(f"🚀 Boost: {'; '.join(_esc(r) for r in bonus_reasons)}")
    msg.append("")
    if src_lines:
        msg.append("📰 <b>Fuentes:</b>")
        msg.extend(src_lines)
        msg.append("")
    msg.append("<i>El bot vigila DexScreener por si alguien lanza una coin matching. Te aviso al instante.</i>")
    return "\n".join(msg)


# ====== 2. COIN MATCHED ACTIVE WATCH ======
def format_coin_matched(coin: Dict, watch: Dict) -> str:
    ticker = _esc(coin.get("ticker", "?"))
    name = _esc((coin.get("name") or "")[:60])
    mc = coin.get("market_cap_usd", 0) or 0
    liq = coin.get("liquidity_usd", 0) or 0
    vol = coin.get("volume_h24", 0) or coin.get("volume_24h", 0) or 0
    pc_1h = coin.get("price_change_1h", 0)
    pc_24h = coin.get("price_change_24h", 0)
    match_score = coin.get("match_score", 0)
    match_reason = _esc(coin.get("match_reason", ""))
    safety = coin.get("safety_score")
    warn = " ⚠️" if coin.get("safety_warning") else ""
    url = _esc(coin.get("url", ""))
    mint = coin.get("mint", "")

    safety_line = ""
    if safety is not None:
        safety_line = f"🛡️ Safety: <b>{safety}</b>/100{warn}"

    msg = [
        f"💎 <b>COIN MATCHED — WATCH ACTIVO</b>",
        f"<b>${ticker}</b> ({name})",
        "",
        f"🪙 MC: <b>${mc:,.0f}</b>",
        f"💧 Liquidez: ${liq:,.0f} · Vol 24h: ${vol:,.0f}",
        f"📊 1h: {pc_1h:+.1f}% · 24h: {pc_24h:+.1f}%",
    ]
    if safety_line:
        msg.append(safety_line)
    msg.extend([
        "",
        f"🎯 Match: <b>{match_score}%</b> — {match_reason}",
        f"📡 Narrativa vinculada: {_esc(watch.get('narrative_summary', '')[:140])}",
        f"💡 Por qué memeable: {_esc(watch.get('why_memeable', '')[:140])}",
        "",
        f"🔗 <a href=\"https://dexscreener.com/solana/{_esc(mint)}\">DexScreener</a> · "
        f"<a href=\"https://gmgn.ai/sol/token/{_esc(mint)}\">GMGN</a> · "
        f"<a href=\"{url}\">abrir</a>",
    ])
    return "\n".join(msg)


# ====== 3. EVENT-LINKED OPPORTUNITY ======
def format_event_linked(coin: Dict, evaluation: Dict) -> str:
    ticker = _esc(coin.get("ticker", "?"))
    name = _esc((coin.get("name") or "")[:60])
    mc = coin.get("market_cap_usd", 0) or 0
    liq = coin.get("liquidity_usd", 0) or 0
    pc_24h = coin.get("price_change_24h", 0)

    catalyst = _esc(evaluation.get("catalyst_description", ""))
    cat_date = _esc(evaluation.get("catalyst_estimated_date", ""))
    days = evaluation.get("days_to_catalyst")
    rr = evaluation.get("rr_score", 0)
    rr_reason = _esc(evaluation.get("rr_reasoning", ""))
    meme_potential = evaluation.get("memetic_potential_when_catalyst_hits", 0)
    theme = _esc(evaluation.get("theme", ""))
    url = _esc(coin.get("url", ""))
    mint = coin.get("mint", "")

    days_str = f"{days}d" if days is not None else cat_date

    msg = [
        f"🎯 <b>EVENT-LINKED OPPORTUNITY</b>",
        f"<b>${ticker}</b> ({name})",
        "",
        f"📊 MC: <b>${mc:,.0f}</b> · Liq ${liq:,.0f} · 24h {pc_24h:+.1f}%",
        f"🎬 Tema: <i>{theme}</i>",
        "",
        f"⚡ <b>Catalizador:</b> {catalyst}",
        f"📅 Estimado: {days_str}",
        f"⭐ R/R: <b>{rr}/10</b>",
        f"🧠 Potencial memético al hit: <b>{meme_potential}/10</b>",
        "",
        f"📝 Razonamiento: {rr_reason}",
        "",
        f"🔗 <a href=\"https://dexscreener.com/solana/{_esc(mint)}\">DexScreener</a> · "
        f"<a href=\"https://gmgn.ai/sol/token/{_esc(mint)}\">GMGN</a> · "
        f"<a href=\"{url}\">abrir</a>",
    ]
    return "\n".join(msg)


# ====== 4. ESCALATION ======
def format_escalation(watch: Dict, growth_data: Dict) -> str:
    msg = [
        f"⚡ <b>NARRATIVA ESCALANDO</b>",
        f"Una narrativa que estaba en watch está creciendo en menciones.",
        "",
        f"📝 {_esc(watch.get('narrative_summary', '')[:200])}",
        f"📂 {_esc(watch.get('category', ''))}",
        "",
        f"📈 Crecimiento: {_esc(str(growth_data.get('description', '')))}",
        f"📡 Fuentes nuevas: {growth_data.get('new_sources', 0)}",
        "",
        f"🎯 Tickers candidatos: {_esc(', '.join((watch.get('candidate_tickers') or [])[:6]))}",
        f"<i>Watch sigue activo. Vigilando DexScreener.</i>",
    ]
    return "\n".join(msg)


# ====== HEALTH ALERT ======
def format_health_alert(state: Dict) -> str:
    sources = state.get("sources_status", {}) or {}
    lines = [
        "🚨 <b>HEALTH ALERT</b>",
        f"{state.get('zero_streak', 0)} ciclos consecutivos sin señales.",
        "",
        "<b>Estado fuentes:</b>",
    ]
    for k, v in sources.items():
        emoji = "✅" if v > 0 else "❌"
        lines.append(f"{emoji} {k}: {v}")
    lines.append("")
    lines.append("<i>Posibles causas: APIs caídas, rate-limit, endpoints rotos.</i>")
    return "\n".join(lines)
