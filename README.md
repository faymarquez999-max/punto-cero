# Punto Cero — Radar Cultural V3

Sistema autónomo que detecta narrativas frescas del mundo con potencial memético
y trackea coins existentes con catalizadores futuros. **Sin calendario hardcoded.**

## Filosofía

El bot lee el mundo entero, identifica cuándo algo tiene los ingredientes para
convertirse en memecoin, y avisa **antes de que exista coin**. Cuando aparezca
una coin matching, te avisa al instante.

## Cómo razona

El LLM (Groq Llama 3.3 70B) evalúa cada narrativa con principios memetéticos
abstractos: emocionalidad, memeabilidad, factor visual, resonancia cultural,
polarización, absurdidad, simplicidad, velocidad de propagación.

NO compara con casos pasados concretos. Razona sobre INGREDIENTES.

## Los 2 modos operativos

### 🆕 Modo 1 — Narrativa emergente
1. Detecta noticia/rumor/momento viral fresco
2. LLM evalúa potencial memético (score 0-100)
3. Si score ≥ 70 → crea **Active Watch** 72-168h
4. Genera tickers candidatos predictivos
5. Vigila DexScreener cada ciclo por matches
6. Cuando aparece coin validada → 💎 alerta inmediata

### 🎯 Modo 2 — Coin existente + catalizador
1. Cada N ciclos escanea DexScreener (low/mid cap 10-500k MC)
2. LLM evalúa: *"¿hay catalizador futuro para esta coin?"*
3. Si R/R ≥ 6.5 y catalizador <60d → 🎯 alerta event-linked

## Filtros duros (Mode 1)

- ✅ **DexScreener listada** (no Pump.fun crudo)
- ✅ MC 10k–500k (preferente <80k)
- ✅ Liquidez ≥ $5k
- ✅ Volumen 24h ≥ $5k
- ✅ Holders ≥ 50
- ✅ Edad ≥ 10 min
- ✅ RugCheck score ≥ 50

## Fuentes monitorizadas

- **Reddit** — r/all, r/news, r/PublicFreakout, r/UFOs, r/politics, r/conspiracy, +20 subs
- **Google News** — 14 feeds bilingües, queries específicos
- **Breaking news RSS** — Reuters, AP, BBC, Al Jazeera, Bloomberg, Politico, TMZ
- **Wikipedia Recent Changes** — spike detection de páginas high-value
- **Polymarket** — cambios de probabilidad >10% (alpha pre-mainstream)
- **X/Twitter (Nitter)** — timelines de Elon, Trump, periodistas + búsquedas
- **Bluesky** — búsquedas
- **4chan /biz/** — ticker mentions
- **Google Trends** — picos US/ES/UK
- **Pump.fun / DexScreener / Solana Tracker / GMGN** — para coin discovery

## Tipos de alerta

- 🚨 **NARRATIVA POTENCIAL** — algo memetable detectado, sin coin aún
- 💎 **COIN MATCHED** — coin recién listada matching un watch activo
- 🎯 **EVENT-LINKED OPPORTUNITY** — coin existente low-cap + catalizador futuro
- ⚡ **ESCALATION** — narrativa watched está creciendo

## Setup

→ Lee [SETUP_PARA_TI.md](SETUP_PARA_TI.md).

## Arquitectura

```
src/
  main.py                          # orquestador V3
  daily_digest.py                  # digest 9am Madrid
  bot_commands.py                  # /status, /watches, /help
  health.py                        # health check
  collectors/                      # 11 fuentes
    reddit · google_news · breaking_news · wikipedia · polymarket
    nitter · bluesky · fourchan_biz · google_trends
    pump_fun · dexscreener · solana_tracker · gmgn
  intelligence/
    clustering.py                  # signal grouping
    momentum.py                    # cross-source boost
    narrative_potential.py         # NEW scorer (principios memetéticos)
    active_watch.py                # NEW sistema de watches persistentes
  crypto/
    dex_matcher.py                 # NEW DexScreener-only matcher (filtros duros)
    event_radar.py                 # NEW LLM infiere catalizadores futuros
    rugcheck.py                    # safety score
  alerts/
    formatter.py                   # 4 alert types nuevos
    telegram.py
  memory/store.py
config/
  events.yaml                      # VACÍO (sin calendario hardcoded)
  memetic_principles.yaml          # principios memetéticos para LLM
  sources.yaml                     # fuentes
  settings.yaml                    # umbrales, módulos
dashboard/index.html               # dashboard con tabs
.github/workflows/
  run.yml                          # main cycle (cron PAUSADO durante rebuild)
  daily_digest.yml                 # daily 7:00 UTC (cron PAUSADO)
```
