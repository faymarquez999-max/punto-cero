"""Formateadores Telegram HTML — 6 tipos de alerta + originales."""
from typing import Dict, List


def _esc(s) -> str:
    if s is None:
        return ""
    s = str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# === Original: NARRATIVE ALERT ===
def format_narrative_alert(narrative: Dict, cluster: Dict, coins: List[Dict]) -> str:
    score = narrative.get("score", 0)
    base = narrative.get("score_base", score)
    bonus = narrative.get("score_bonus", 0)
    cat = narrative.get("category", "unknown")
    summary = narrative.get("narrative_summary", "")
    why = narrative.get("why_viral", "")
    similar = narrative.get("similar_to_case", "none")
    emotions = ", ".join(narrative.get("emotional_drivers", []) or [])
    tickers = ", ".join(narrative.get("suggested_tickers", []) or [])
    risks = "\n".join(f"• {_esc(r)}" for r in (narrative.get("risk_flags") or []))
    window = narrative.get("time_window_hours")
    confidence = narrative.get("confidence", "")
    matched_event = narrative.get("matched_event")
    bonus_reasons = narrative.get("bonus_reasons", []) or []

    n_fams = cluster.get("n_distinct_families", 0)
    fams = ", ".join(cluster.get("source_families", []) or [])

    src_sample = cluster.get("signals", [])[:3]
    src_lines = []
    for s in src_sample:
        url = _esc(getattr(s, "url", "") or "")
        src = _esc(getattr(s, "source", "") or "")
        title = _esc((getattr(s, "title", "") or "")[:120])
        src_lines.append(f"• <a href=\"{url}\">{src}</a>: {title}")

    coin_lines = []
    for c in coins:
        mc = c.get("market_cap_usd") or 0
        ticker = _esc(c.get("ticker", "?"))
        name = _esc((c.get("name") or "")[:40])
        url = _esc(c.get("url", ""))
        match = c.get("match_score", 0)
        src = _esc(c.get("source", ""))
        warn = " ⚠️" if c.get("safety_warning") else ""
        safety = c.get("safety_score")
        safety_str = f" · safety {safety}" if safety is not None else ""
        coin_lines.append(
            f"• <b>${ticker}</b> ({name}) — MC ${mc:,.0f} · match {match}%{safety_str}{warn}\n"
            f"  <code>{src}</code> · <a href=\"{url}\">abrir</a>"
        )

    msg_parts = [
        f"🔥 <b>NARRATIVA DETECTADA</b> · Score <b>{score}</b>/100 ({base}+{bonus})",
        f"📂 {_esc(cat)} · confidence: {_esc(confidence)}",
        "",
        f"<b>{_esc(cluster.get('top_title',''))}</b>",
        "",
        f"💡 <b>Narrativa:</b> {_esc(summary)}",
        f"⚡ <b>Por qué viral:</b> {_esc(why)}",
        f"🔁 <b>Similar a caso:</b> <code>{_esc(similar)}</code>",
        f"💓 <b>Emociones:</b> {_esc(emotions)}",
        f"🎯 <b>Tickers sugeridos:</b> {_esc(tickers)}",
    ]
    if window is not None:
        msg_parts.append(f"⏱️ <b>Ventana estimada:</b> {window}h")
    if matched_event:
        msg_parts.append(f"📅 <b>Evento relacionado:</b> {_esc(matched_event)}")
    msg_parts.append(f"📡 <b>Cross-source:</b> {n_fams} familias ({_esc(fams)})")
    if bonus_reasons:
        msg_parts.append(f"🚀 <b>Boost momentum:</b> {'; '.join(_esc(r) for r in bonus_reasons)}")
    msg_parts.append("")

    if coin_lines:
        msg_parts.append("💎 <b>Coins encontradas:</b>")
        msg_parts.extend(coin_lines)
        msg_parts.append("")
    else:
        msg_parts.append("💎 <i>Sin coins relacionadas todavía — narrativa virgen.</i>")
        msg_parts.append("")

    if src_lines:
        msg_parts.append("📡 <b>Fuentes:</b>")
        msg_parts.extend(src_lines)
        msg_parts.append("")

    if risks:
        msg_parts.append(f"⚠️ <b>Riesgos:</b>\n{risks}")
        msg_parts.append("")

    msg_parts.append(f"🤖 <b>{_esc(narrative.get('recommendation','WATCH'))}</b>")
    return "\n".join(msg_parts)


# === Original: EVENT ANTICIPATION ===
def format_event_anticipation(event: Dict) -> str:
    days = event.get("days_to_event", 0)
    window = event.get("window_type", "")
    emoji = {"imminent": "🚨", "small": "⏰", "medium": "📅", "major": "🗓️"}.get(window, "📅")
    msg_parts = [
        f"{emoji} <b>EVENTO PRÓXIMO</b> · en <b>{days} días</b>",
        f"<b>{_esc(event.get('name',''))}</b>",
        "",
        f"📂 {_esc(event.get('category',''))}",
        f"💡 <b>Narrativa esperada:</b> {_esc(event.get('narrative',''))}",
        f"🎯 <b>Themes coin:</b> {', '.join(event.get('coin_themes',[]) or [])}",
    ]
    pat = event.get("historical_pattern")
    if pat:
        msg_parts.append(f"📈 <b>Patrón histórico:</b> {_esc(pat)}")
    priority = event.get("priority")
    if priority == "critical":
        msg_parts.append(f"🔥 <b>PRIORIDAD CRÍTICA</b>")
    return "\n".join(msg_parts)


# === NEW: EVENT-LINKED OPPORTUNITY ===
def format_event_linked_opportunity(coin: Dict) -> str:
    """Coin existente bien posicionada para evento futuro (DORMANT_PUMPER pattern)."""
    rr = coin.get("rr") or {}
    state = coin.get("lifecycle_state", "")
    days = coin.get("days_to_event")
    days_str = f"{days}d" if days is not None else "?"

    state_emoji = {
        "DORMANT_PUMPER": "💤",
        "RECOVERING": "📈",
        "FRESH_LAUNCH": "🆕",
        "ACTIVE": "🟢",
        "DEAD": "💀",
    }.get(state, "❓")

    msg_parts = [
        f"🎯 <b>EVENT-LINKED OPPORTUNITY</b>",
        f"<b>${_esc(coin.get('ticker',''))}</b> ({_esc(coin.get('name',''))})",
        "",
        f"📅 Evento: <b>{_esc(coin.get('event_name',''))}</b> en <b>{days_str}</b>",
        f"{state_emoji} Lifecycle: <code>{_esc(state)}</code>",
        f"📊 MC actual: ${rr.get('current_mc',0):,} · ATH: ${rr.get('peak_mc',0):,}",
        f"📉 Drawdown: <b>{rr.get('drawdown_pct',0):.1f}%</b> desde ATH",
        f"🚀 Upside al 50% ATH: <b>{rr.get('upside_to_50pct_ath_x',0)}x</b>",
        f"⭐ R/R score: <b>{rr.get('rr_score',0)}/10</b>",
        "",
    ]
    reasons = rr.get("rr_reasons") or []
    if reasons:
        msg_parts.append("<b>Razones R/R:</b>")
        for r in reasons:
            msg_parts.append(f"• {_esc(r)}")
        msg_parts.append("")
    url = _esc(coin.get("url", ""))
    if url:
        msg_parts.append(f"🔗 <a href=\"{url}\">abrir en explorer</a>")
    return "\n".join(msg_parts)


# === NEW: SMART MONEY CONFLUENCE ===
def format_confluence(confluence: Dict) -> str:
    mint = confluence.get("mint", "")
    buyers = confluence.get("buyers", [])
    n = confluence.get("buyer_count", len(buyers))
    msg_parts = [
        f"🐋 <b>SMART MONEY CONFLUENCE</b>",
        f"<b>{n}</b> wallets etiquetadas como smart money compraron la misma coin en las últimas horas.",
        "",
        f"🪙 Mint: <code>{_esc(mint[:20])}...</code>",
        "",
        "<b>Wallets:</b>",
    ]
    for b in buyers[:6]:
        addr = b.get("wallet", "")[:8]
        label = b.get("label", "")
        msg_parts.append(f"• <code>{_esc(addr)}...</code> {_esc(label)}")
    msg_parts.append("")
    msg_parts.append(f"🔗 <a href=\"https://dexscreener.com/solana/{_esc(mint)}\">DexScreener</a> · "
                     f"<a href=\"https://gmgn.ai/sol/token/{_esc(mint)}\">GMGN</a>")
    return "\n".join(msg_parts)


# === NEW: DORMANT WHALE WAKE-UP ===
def format_wake_up(wake: Dict) -> str:
    msg_parts = [
        f"💤 <b>DORMANT WHALE WAKE-UP</b>",
        f"Wallet smart money inactiva (>7 días) acaba de despertar y comprar.",
        "",
        f"🐋 Wallet: <code>{_esc(wake.get('wallet',''))[:20]}...</code>",
        f"🏷️ Label: {_esc(wake.get('label',''))}",
        f"🪙 Mint: <code>{_esc((wake.get('mint','') or '')[:20])}...</code>",
        "",
        f"🔗 <a href=\"https://gmgn.ai/sol/address/{_esc(wake.get('wallet',''))}\">ver wallet</a> · "
        f"<a href=\"https://dexscreener.com/solana/{_esc(wake.get('mint',''))}\">coin</a>",
    ]
    return "\n".join(msg_parts)


# === NEW: TICKER VELOCITY SPIKE ===
def format_velocity_spike(spike: Dict) -> str:
    ticker = spike.get("ticker", "")
    recent = spike.get("recent_mentions", 0)
    baseline = spike.get("baseline_per_window", 0)
    ratio = spike.get("spike_ratio", 0)
    msg_parts = [
        f"⚡ <b>TICKER VELOCITY SPIKE</b>",
        f"<b>${_esc(ticker)}</b> — mentions x<b>{ratio}</b> en la última hora",
        "",
        f"📊 Recent: {recent} mentions",
        f"📊 Baseline: {baseline} mentions/h promedio (24h)",
        "",
        f"<i>Social signal MUY temprano. Investiga.</i>",
        f"🔗 <a href=\"https://dexscreener.com/?q={_esc(ticker)}\">DexScreener</a> · "
        f"<a href=\"https://gmgn.ai/?q={_esc(ticker)}&chain=sol\">GMGN</a>",
    ]
    return "\n".join(msg_parts)


# === NEW: NEW LAUNCH FOR TRACKED EVENT ===
def format_new_launch_for_event(coin: Dict, event_name: str, matched_keywords: List[str]) -> str:
    msg_parts = [
        f"💎 <b>NEW LAUNCH PARA EVENTO TRACKED</b>",
        f"Acaba de lanzarse una coin que matchea el evento <b>{_esc(event_name)}</b>.",
        "",
        f"🪙 <b>${_esc(coin.get('ticker',''))}</b> ({_esc(coin.get('name',''))[:40]})",
        f"📊 MC: ${coin.get('market_cap_usd', 0):,.0f}",
        f"⏰ Edad: muy reciente",
        f"🔑 Matches: {', '.join(_esc(k) for k in matched_keywords[:5])}",
        "",
    ]
    desc = coin.get("description", "")[:200]
    if desc:
        msg_parts.append(f"📝 {_esc(desc)}")
        msg_parts.append("")
    socials = []
    if coin.get("twitter"): socials.append(f"<a href=\"{_esc(coin['twitter'])}\">Twitter</a>")
    if coin.get("telegram"): socials.append(f"<a href=\"{_esc(coin['telegram'])}\">Telegram</a>")
    if coin.get("website"): socials.append(f"<a href=\"{_esc(coin['website'])}\">Web</a>")
    if socials:
        msg_parts.append("🌐 " + " · ".join(socials))
    msg_parts.append(f"🔗 <a href=\"{_esc(coin.get('url',''))}\">pump.fun</a>")
    return "\n".join(msg_parts)


# === NEW: AI AGENT NARRATIVE EMERGING ===
def format_ai_agent_emerging(coin: Dict, evidence: List[str]) -> str:
    msg_parts = [
        f"🧠 <b>AI AGENT NARRATIVE EMERGING</b>",
        f"Detectada coin con perfil AI agent (meta 2026).",
        "",
        f"🪙 <b>${_esc(coin.get('ticker',''))}</b> ({_esc(coin.get('name',''))[:40]})",
        f"📊 MC: ${coin.get('market_cap_usd', 0):,.0f}",
    ]
    if evidence:
        msg_parts.append("")
        msg_parts.append("<b>Evidencia AI agent:</b>")
        for e in evidence[:5]:
            msg_parts.append(f"• {_esc(e)}")
    msg_parts.append("")
    msg_parts.append(f"🔗 <a href=\"{_esc(coin.get('url',''))}\">abrir</a>")
    return "\n".join(msg_parts)


def format_coin_watch(coin: Dict, reason: str) -> str:
    mc = coin.get("market_cap_usd") or 0
    return (
        f"👀 <b>COIN EN WATCH</b>\n"
        f"<b>${_esc(coin.get('ticker',''))}</b> ({_esc(coin.get('name',''))})\n"
        f"MC: ${mc:,.0f} · {_esc(coin.get('chain',''))} · {_esc(coin.get('source',''))}\n"
        f"📍 Razón: {_esc(reason)}\n"
        f"🔗 <a href=\"{_esc(coin.get('url',''))}\">abrir</a>"
    )
