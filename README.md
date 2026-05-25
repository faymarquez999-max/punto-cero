# Narrative Alpha Hunter 1

Sistema autónomo que detecta narrativas virales con potencial memecoin **antes** que el mercado y avisa por Telegram. Corre en GitHub Actions gratis, sin servidor.

## Lo que hace

1. **Monitoriza cada 15 min** — Reddit (hot + rising, 20 subreddits ES/EN), Google News (12 feeds bilingües), Trends, Bluesky, Nitter, Pump.fun, Dexscreener.
2. **Clusteriza** señales similares en narrativas candidatas (normalización de acentos, tickers $XYZ).
3. **Boost momentum pre-LLM** — cross-source (≥3 familias distintas) y velocity (x2 menciones en 2h).
4. **Puntúa con IA** — Groq Llama 3.3 70B compara contra 18 casos históricos pre-filtrados (PNUT, TRUMP, WIF, LIBRA, PEPE, Topuria, etc.).
5. **Si score ≥ 83** → busca coins en Pump.fun (filtros de calidad: socials, edad, descripción) y Dexscreener. RugCheck obligatorio para Solana.
6. **Alerta Telegram HTML** con score, narrativa, fuentes, coins, ventana temporal, similitud histórica, momentum reasons.
7. **Anticipación de eventos** — calendario con UFC Casa Blanca 14 jun, GTA VI 19 nov, Mundial, NBA Finals, McGregor.
8. **Daily digest** cada mañana a las 9:00 Madrid.
9. **Health-check** si las APIs caen, **shadow log** de scores 60-82 para calibrar, comandos bot `/status` `/events` `/help`.
10. **Dashboard HTML** estático opcional vía GitHub Pages.

## Tipos de alertas

- 🔥 **NARRATIVA DETECTADA** (score ≥ 83) — con cross-source + similar_to_case + coins + tickers
- 🚨/⏰/📅/🗓️ **EVENTO PRÓXIMO** (imminent/small/medium/major según ventana)
- 🌅 **DAILY DIGEST** (resumen 24h + eventos próximos)
- 🚨 **HEALTH ALERT** (si 3 ciclos consecutivos con 0 signals)

## Setup

→ Lee [SETUP_PARA_TI.md](SETUP_PARA_TI.md). 25-40 min, una sola vez, sin programar.

→ Lee [AUDIT_REPORT.md](AUDIT_REPORT.md) para entender las decisiones de diseño.

## Estructura

```
src/
  main.py                 # orquestador principal
  daily_digest.py         # script del digest matinal
  bot_commands.py         # /status, /events, /help via getUpdates polling
  health.py               # tracking de ciclos en blanco
  collectors/             # 7 fuentes con retry, UA rotation, multi-endpoint fallback
  intelligence/
    clustering.py         # acentos, tickers, cross-family detection
    momentum.py           # cross-source + velocity boosts pre-LLM
    scorer.py             # Groq con casos pre-filtrados
    event_matcher.py      # match con calendario
  crypto/
    hunter.py             # term filtering, edad, socials bonus
    rugcheck.py           # safety score Solana
  alerts/
    telegram.py           # chunking inteligente HTML, retry 429
    formatter.py          # HTML con todas las señales
  memory/store.py         # persistencia JSON atómica (.tmp + replace)
config/
  events.yaml             # 14 eventos verificados (UFC, GTA, Mundial, etc.)
  historical_cases.yaml   # 18 casos históricos con multipliers
  sources.yaml            # 20+ subreddits ES/EN, 12 feeds news
  settings.yaml           # umbrales, momentum, ventanas, dedup
data/                     # auto-commit por workflow
  narratives.json
  coins_tracked.json
  alerts_log.json
  sent_keys.json
  signals_history.json
  health.json
  telegram_offset.json
dashboard/index.html      # dashboard estático (GitHub Pages)
.github/workflows/
  run.yml                 # cron */15 (ajustable a */5 si público)
  daily_digest.yml        # cron 07:00 UTC
```
