# Audit V2 — Bugs encontrados en revisión profunda
**Fecha:** 2026-05-25 (segunda revisión)

Tras leer cada módulo en detalle (no solo compile-check), estos son los bugs reales:

## 🔴 CRÍTICOS

### B1. `main.py:368` — función inexistente
`health.now_utc_iso()` no existe en `src/health.py`. Sí existe en `src/memory/store.py`.
- **Impacto:** AttributeError protegido por `hasattr(...)` → siempre devuelve `""`. El timestamp de sent_keys nunca se guarda. Funciona pero dedup pierde info temporal.
- **Fix:** usar `store.now_utc_iso()`.

### B2. `smart_money.py:222` — config en sitio equivocado
Código lee `settings.get("smart_money_rpc")` pero `smart_money_rpc` está en `sources.yaml`, no en `settings.yaml`. Siempre falla y usa default tx_limit=10.
- **Impacto:** ignora override del usuario. Funciona pero config muerta.
- **Fix:** pasar `sources_cfg` a `smart_money.run()` o mover la config a settings.

### B3. `pump_monitor.py:_matches` — matching demasiado loose
Substring match `"ufc" in haystack`. Para keyword "ufc" matchea "tufco", "ufcfighter", "ufcoin", etc.
- **Impacto:** falsos positivos masivos en eventos con keywords cortas.
- **Fix:** word-boundary regex en lugar de substring.

## 🟡 MEDIOS

### B4. `formatter.py:37` — None defense
`getattr(s, "title", "")[:120]` — si Signal.title es None (no debería pero defensivo), crashea.
- **Fix:** `(getattr(s, "title", "") or "")[:120]`.

### B5. `formatter.py:213` — URL DexScreener mal formada
`https://dexscreener.com/search?q={ticker}` no es el path correcto.
- **Fix:** `https://dexscreener.com/?q={ticker}` o `https://dexscreener.com/solana?q={ticker}`.

### B6. `hunter.py:102` — Pump.fun pull con filtros restrictivos por default
Llama a `pump_fun.fetch_new_coins(limit=100, min_mc=1000, max_mc=200000)` sin pasar `require_socials=False`. Usa default True → muchas coins sin socials se filtran fuera ANTES del matching.
- **Impacto:** menos candidates → menos hits del crypto hunter.
- **Fix:** pasar `require_socials=False, require_description=False` para que el matching luego decida.

### B7. `hunter.py:91` — parámetro muerto `min_holders`
Declarado pero nunca usado en la función.
- **Fix:** quitar para evitar confusión.

## 🟢 MINORES

### B8. `pump_monitor.py` seen_mints crece con coins no-matched
Una coin que no matcheaba un evento (pero podría matchearlo si se actualiza events.yaml) queda en seen_mints y nunca se re-evaluará.
- **Aceptable** para MVP — siempre se puede borrar el archivo si se quiere re-scan.

### B9. `event_watcher.py` — 50+ API calls a DexScreener por ciclo
14 eventos × ~4 known_coins = 56 calls. DexS rate limit es 60 req/min. Borde peligroso.
- **Fix:** cachear `_resolve_coin` resultados durante el ciclo (mismo ticker no re-busca).

### B10. `formatter.py:format_confluence` — wallet truncation pobre
Solo muestra primeros 8 chars. Difícil identificar la wallet.
- **Fix:** mostrar `addr[:6]...addr[-4:]`.

---

## ✅ Lo que está BIEN tras audit

- Ticker velocity logic: math correcta (window vs baseline)
- Momentum cross-source: correcto
- Event Coin Watcher lifecycle states: lógica sana
- RR score 0-10 con commentary: bien razonado
- Telegram chunking inteligente: respeta tags HTML
- Sent keys persistencia: dedup correcto
- Pump.fun multi-endpoint fallback: robusto
- 4chan /biz/ collector: scrape directo del JSON oficial
- Smart wallets YAML con `[]` literal: parseable

---

## Plan de fixes
Aplico los 7 bugs B1-B7 ahora. B8-B10 los dejo (no afectan funcionamiento, solo pulen).
