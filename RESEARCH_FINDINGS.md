# Investigación Profunda — Mayo 2026
**Lo que cambia la arquitectura del bot tras research del ecosistema actual.**

---

## 🎯 La meta-narrativa 2026 (lo que REALMENTE pumpea ahora)

Tras revisar el estado actual del mercado memecoin Solana en mayo 2026:

### Las 4 narrativas dominantes 2026:
1. **AI Agent coins** — PIPPIN, FARTCOIN, GOAT, "sentient memes". Tokens donde un agente IA "gestiona" treasury y social. NARRATIVA #1 del ciclo.
2. **PolitiFi** — TRUMP, MELANIA, coins relacionadas con midterms USA noviembre 2026. La gala TRUMP del 25 abril disparó dormant whale → +60% en horas.
3. **NFT-linked community** — PENGU (Pudgy World), BONK. Coins con ecosystem real.
4. **Classic meme revival** — TROLL (10 mayo 2026: +77% en 24h, $90M MC), Mog Coin (1800% via 4chan).

### Categorías "tier 1" que pumpean en 2026:
Dog, Cat, Frog, AI agent, PolitiFi, NFT-linked, Sports/UFC, Anime, Gaming, Celebrity, Conspiracy, Sentient memes, "Bonk-derivative", Election-cycle, Animal-injustice.

**Acción:** ampliar `historical_cases.yaml` con AI Agent cases (FARTCOIN, GOAT, PIPPIN) + TROLL + Moo Deng + dormant whale TRUMP gala.

---

## 🔑 APIs gratis CRÍTICAS que estamos perdiendo

### 1. **Solana Tracker** — `solanatracker.io` (free tier escala a millones requests)
- 70+ endpoints
- `GET /tokens/trending/{timeframe}` → trending por volumen 1h/6h/24h
- `GET /tokens/search` → búsqueda por texto/ticker
- `GET /wallet/{address}/pnl` → P&L de wallet
- **Free API key con solo signup**
- **Es objetivamente mejor que DexScreener para trending Solana**

### 2. **GMGN.ai** — `gmgn.ai/ai`
- Trending tokens cross-chain (Solana, BSC, Base, ETH)
- Smart money positions, KOL holdings, insider wallets
- Sniper detection, bundled wallet exposure
- **Free API key (upload pubkey)**
- Su web pública (`gmgn.ai/trend?chain=sol`) es scrapeable

### 3. **Nansen Smart Money** — `nansen.ai`
- Free Solana wallet tracking
- Labels: funds, whales, successful traders, KOLs
- Token God Mode (gratis con limit)
- **Sin API en free tier — necesitamos webhook o scrape**

### 4. **LunarCrush** — `lunarcrush.com`
- **Galaxy Score™** = score combinado de precio + social impact + sentiment + correlation
- 4000+ cryptos cubiertas
- **"Ticker Velocity"** = mentions x500% en 5 min → trigger temprano
- Free tier limitado pero usable

### 5. **Helius** — `helius.dev`
- **Webhooks gratis** para wallet activity (smart money real-time)
- Free RPC Solana
- **Game changer**: cuando una whale tracked compra en Pump.fun, te enteras en 1-2 segundos

### 6. **4chan /biz/ JSON API**
- `https://a.4cdn.org/biz/catalog.json` (público, gratis, sin auth)
- "Mayor driver del mercado crypto" según Mechanism Capital
- MOG nació aquí (+1800% en 2024)
- Cualquier ticker que se menciona varias veces en /biz/ con momentum = señal fuerte

---

## 🐋 El patrón "Dormant Whale + Second Wave" (CONFIRMADO)

**Ejemplo real, abril 2026:** Wallet dormido 5 meses → compra 2.2M TRUMP el día del anuncio de la gala 25-abr → +60% precio en horas.

Esto valida exactamente lo que me dijo el usuario sobre **UFC Casablanca**: pump → dump → entrar en valle antes del evento → re-pump.

### Lo que necesitamos detectar:
1. Coin existe + tuvo ATH alto + ahora drawdown ≥80% + evento conocido se acerca = **DORMANT EVENT COIN** (jugada de valor)
2. Wallet etiquetada como "smart money" en sleep → de repente compra una coin tracked = **WHALE WAKE-UP** (señal real-time)
3. Múltiples wallets smart money entrando a la misma coin en mismo periodo = **CONFLUENCE** (señal muy fuerte)

---

## 📊 Métricas que predicen pumps (data-driven)

Según research (LunarCrush, Santiment, Sharpe):

1. **Social velocity** (mentions/hora subiendo exponencial) — predictor más fuerte
2. **Ticker velocity** = +500% mentions en 5 min con volumen bajo → entrada óptima
3. **Holder velocity** (nuevos holders/hora subiendo)
4. **Wallet concentration drop** (top 10 % bajando = distribución sana)
5. **Buy/sell ratio > 1.5** sostenido
6. **Smart money confluence** (≥3 wallets etiquetadas comprando misma coin)
7. **Volume spike > 5x media de 24h sin price spike** (acumulación silenciosa)

---

## 🏛️ Calendar de eventos 2026 (catalysts confirmados/probables)

Investigando eventos verificados que faltan:

- **2026-05-30** — Champions League Final (París, Allianz Arena)
- **2026-06-04** — NBA Finals start
- **2026-06-11** — Mundial 2026 inicio (USA/MX/CA)
- **2026-06-14** — UFC Casa Blanca: Topuria vs Gaethje (CRÍTICO, ya incluido)
- **2026-07-19** — Mundial Final
- **2026-09** — UFC Paris esperado
- **2026-10** — Halloween + altseason peak típico
- **2026-11-03** — US Midterms (PolitiFi catalyst)
- **2026-11-19** — GTA VI launch
- **2026-12-25** — Christmas memes recurrentes
- **2027-02-07** — Super Bowl LXI
- **Moo Deng birthday** (julio) — pumper recurrente
- **Trump events / galas / executive orders** — catalysts no programables

---

## 🧠 Lecciones críticas

### A) El bot tiene que ser PROACTIVO, no reactivo
- Actual: detecta narrativa → busca coins
- Nuevo: **mantiene watchlist permanente de coins event-linked** + escanea Pump.fun por keywords de eventos cada ciclo

### B) Cuando no hay coin del evento, fallback a adjacent
- Sin $TOPURIA → sugerir $UFC, $WHITEHOUSE, $GAETHJE, $MATADOR (con score de proximidad)
- Mostrar lifecycle: pump+dump pasado, MC actual, % desde ATH

### C) Smart money tracking es lo más infravalorado
- Tener una lista de 50-200 wallets etiquetadas como "smart money Solana"
- Webhook Helius cuando compran ANYTHING → analizar narrativa de esa coin
- Confluence de 3+ smart wallets = señal muy fuerte

### D) 4chan /biz/ es la fuente más subestimada
- Ticker mentions en /biz/ subiendo = alpha PRE-mainstream
- Free, JSON API, sin auth

### E) Social velocity > engagement absoluto
- Que una narrativa tenga 1000 menciones es bueno
- Que pase de 10 a 1000 menciones en 2h es ORO

### F) AI Agent meta es el motor 2026
- Necesitamos categorización especial para "AI agent coins"
- Patrón: agente IA controla wallet/twitter → mucho hype + cierto fundamento técnico

---

## 🎬 Próxima arquitectura (resumen)

Voy a montar **3 motores nuevos** integrados al pipeline existente:

### Motor #1 — Event Coin Watcher (proactivo)
- Para cada evento del calendario activo, mantener watchlist de coins relacionadas
- Cada ciclo: scan Dexscreener + Solana Tracker para todas las coins watchlist
- Detectar 4 estados: `FRESH_LAUNCH`, `DORMANT_PUMPER`, `RECOVERING`, `DEAD`
- Score R/R: días al evento + drawdown desde ATH + smart money presente

### Motor #2 — Smart Money Tracker
- Lista curada de 100+ smart wallets Solana (públicas de Nansen/GMGN)
- Pollear actividad (Helius free RPC) cada ciclo
- Si ≥2 wallets compran la misma coin en <2h → alerta CONFLUENCE
- Si una whale dormant (sin actividad >7 días) compra → alerta WAKE-UP

### Motor #3 — Social Velocity Engine
- Trackear ticker velocity: cada ciclo, contar menciones por ticker en TODAS las fuentes
- Calcular delta vs ciclo anterior + delta vs media 24h
- Velocity x5 en 1h = alerta TICKER VELOCITY SPIKE

### Nuevos collectors:
- `4chan_biz.py` — JSON catalog scraper, extracción de tickers
- `solana_tracker.py` — trending 1h, search, P&L
- `gmgn_web.py` — scraper de páginas públicas
- `helius_smart_money.py` — RPC polls de wallets watchlist

### Nuevos alert types:
1. 🎯 **EVENT-LINKED OPPORTUNITY** — coin existente bien posicionada para evento futuro
2. 🐋 **SMART MONEY CONFLUENCE** — ≥3 smart wallets en la misma coin
3. 💤 **DORMANT WHALE WAKE-UP** — wallet smart money que despierta
4. ⚡ **TICKER VELOCITY SPIKE** — mentions explotando
5. 💎 **NEW LAUNCH FOR TRACKED EVENT** — Pump.fun coin recién creada que matchea evento del calendario
6. 🧠 **AI AGENT NARRATIVE EMERGING** — categoría especial 2026

### Smart wallet seed list (público, gratis):
Voy a curar una lista inicial de ~50 wallets Solana etiquetadas como smart money desde:
- GMGN trending traders pages
- Nansen public Solana smart money
- SolanaTracker top traders endpoint
- Listas comunitarias en GitHub

---

## ⚖️ Trade-offs (qué dejo fuera y por qué)

- **X API ($200/mes)**: NO. Confirmado que scraping libre es inviable en 2026. Compensamos con Bluesky + 4chan /biz/ + Telegram channels + LunarCrush social signals.
- **Yellowstone gRPC** (400ms early): NO. Es paid, lo usan profesionales sniper bots. Nuestro foco es narrative anticipation, no first-block sniping.
- **Nansen API**: NO en free. Compensamos con scraping web pública + curación manual de wallets.
- **CoinMarketCal API**: NO. Solo 7 días free. Mantenemos calendario propio.

---

Esta es la base. Ahora construyo todo siguiendo este plan.
