# Guía de Setup — Narrative Alpha Hunter 1

Esta guía es para que la sigas **sin saber programar**. **Tiempo total: 25-40 min**, una sola vez.
Después corre solo 24/7.

---

## ¿Qué hace este sistema?

- Monitoriza Reddit, Google News, Trends, Bluesky, Pump.fun, Dexscreener cada 15 min
- Clusteriza señales y detecta narrativas virales tempranas
- La IA (Groq Llama 3.3 70B, gratis) puntúa cada narrativa comparándola con 18 casos históricos
- Boost extra si la narrativa aparece en múltiples fuentes O crece rápido (momentum)
- Si score ≥ 83 → busca coins relacionadas en Solana, comprueba seguridad (RugCheck), y avisa por Telegram
- Eventos del calendario (Topuria-Gaethje Casa Blanca, GTA VI nov 19, Mundial...) → alertas automáticas según se acercan
- Daily digest cada mañana a las 9:00 Madrid con resumen
- Health alert si las APIs caen
- Comandos: `/status`, `/events`, `/help`

---

## Paso 1 — Bot de Telegram (5 min)

1. En Telegram busca **@BotFather**, mándale `/newbot`.
2. Te pide nombre y username. Te dará un **TOKEN** tipo `7458291038:AAEx...`. **Guárdalo**.
3. Para conseguir tu `chat_id`:
   - Busca **@userinfobot** → `/start` → te dice tu chat_id (número como `123456789`).
   - Si quieres recibir alertas en un grupo: añade tu bot como admin, escribe un mensaje, luego abre en navegador `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` y copia el `"id":-100xxxx` del grupo.
4. **Importante:** mándale `/start` a tu bot desde el chat donde quieres recibir alertas. Sin esto Telegram bloquea bots → users.

---

## Paso 2 — Groq API key (3 min, IA gratis)

1. Ve a https://console.groq.com/keys
2. Cuenta gratis (Google/GitHub login). Click **Create API Key** → cópiala (empieza por `gsk_...`).

---

## Paso 3 — Decisión: ¿repo público o privado?

GitHub Actions tiene dos modos. **Lee esto antes de elegir:**

| | PÚBLICO (recomendado) | PRIVADO |
|---|---|---|
| Minutos Actions | **Ilimitados** | 2000/mes |
| Frecuencia que puedes permitir | Cada 5 min (más alpha) | Cada 15-30 min |
| Tus alertas y memoria | Visibles en el repo | Solo tú las ves |
| Dashboard GitHub Pages | ✅ funciona | Solo con cuenta Pro |

**Recomendación:** Empieza **público**. Las alertas las recibes tú primero por Telegram — el archivo `data/*.json` del repo es histórico, no operativo. Tus claves van en Secrets que **nunca son visibles** aunque el código sea público.

Si insistes en privado: cambia `cron: "*/15 * * * *"` por `cron: "*/30 * * * *"` en `.github/workflows/run.yml` para no quemar minutos.

---

## Paso 4 — Crear repo y subir archivos (10 min)

### 4.1 Cuenta GitHub
- Si no tienes: https://github.com (gratis)

### 4.2 Crear repo
- Click **+** arriba derecha → **New repository**
- Nombre: `narrative-alpha-hunter` (o el que quieras)
- **Visibility:** PUBLIC o PRIVATE según el paso 3
- **NO** marques "Add README"
- Click **Create repository**

### 4.3 Subir archivos — la forma más fácil (sin programar)

**Opción A — Drag & drop desde el navegador:**

1. En el repo: click **uploading an existing file**.
2. Abre el Explorador en `C:\Users\fayma\Projects\NarrativeAlphaHunter1`.
3. **Habilita ver archivos ocultos** (Explorador → Ver → Mostrar → Elementos ocultos) — necesario para que se vea la carpeta `.github`.
4. Selecciona TODO con Ctrl+A. Arrastra a GitHub.
5. ⚠️ Si la carpeta `.github` no se sube: súbela aparte usando "Add file → Create new file" → escribe `.github/workflows/run.yml` (GitHub te crea las carpetas) → pega el contenido. Repite con `daily_digest.yml`.
6. Click **Commit changes**.

**Opción B — GitHub Desktop (mejor si vas a editar):**

1. Descarga https://desktop.github.com.
2. File → Clone repository → tu repo.
3. Copia todos los archivos a la carpeta clonada.
4. En Desktop verás los cambios → Commit → Push.

---

## Paso 5 — Configurar Secrets (5 min)

1. En tu repo → **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret** y añade UNO a UNO:

| Nombre | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del paso 1 |
| `TELEGRAM_CHAT_ID` | Tu chat_id del paso 1 |
| `GROQ_API_KEY` | Key del paso 2 |

El resto (`REDDIT_*`, `BIRDEYE_*`, `TELEGRAM_API_*`) son opcionales. Déjalos vacíos.

---

## Paso 6 — Activar Actions y primer run (5 min)

1. Repo → **Actions** (pestaña arriba).
2. Si aparece "I understand my workflows, go ahead and enable them" → click.
3. Verás 2 workflows:
   - **Narrative Alpha Hunter — Main Cycle** (cada 15 min)
   - **Narrative Alpha Hunter — Daily Digest** (1 vez al día 9am Madrid)
4. Entra en el primero → **Run workflow** → **Run workflow** (botón verde) — primera ejecución manual.
5. Espera 2-3 min. Verde = OK. Rojo = error (click para ver logs).
6. Cuando vaya verde y configuraste bien Telegram → **deberías recibir mensajes**.

A partir de aquí corre solo cada 15 min. Mientras tanto puedes usar los comandos `/status`, `/events`, `/help` en Telegram.

---

## Paso 7 — Dashboard (opcional, 3 min, solo repos públicos)

Para ver alertas históricas en una web bonita:

1. Repo → **Settings** → **Pages**.
2. Source: **Deploy from a branch** → Branch: **main**, carpeta: **/(root)**.
3. Click **Save**.
4. Al cabo de ~1 min, GitHub te da una URL tipo `https://tuusuario.github.io/narrative-alpha-hunter/dashboard/`.
5. Ábrela. Verás stats, alertas STRONG, shadow log, coins en seguimiento.

---

## Errores comunes

| Error | Causa | Solución |
|---|---|---|
| `falta TELEGRAM_BOT_TOKEN` | Secret mal puesto | Repite paso 5 |
| `no_groq_key_or_lib` | GROQ_API_KEY mal | Verifica que la pegaste sin espacios |
| `groq_failure: rate_limit` | Demasiadas requests Groq | Baja `top_n_to_score` en `src/main.py` |
| Bot no manda nada pero workflow verde | Telegram bloquea bot→user | Manda `/start` al bot |
| Run falla en `Commit memory` | Permission denied | Settings → Actions → General → Workflow permissions → **Read and write** |
| Cero alertas en horas | Score umbral alto (83) | Cambia `min_alert_score: 75` en `config/settings.yaml` para más alertas |

---

## Personalización

Todos los parámetros en `config/`:

- **`events.yaml`** — añade peleas, lanzamientos, eventos políticos que sepas vienen
- **`historical_cases.yaml`** — añade casos virales nuevos para que la IA aprenda
- **`sources.yaml`** — activa/desactiva fuentes, añade subreddits
- **`settings.yaml`** — `min_alert_score`, ventanas de anticipación, momentum bonuses

Edita en GitHub web → Commit → se aplica en el próximo run.

---

## Comandos del bot Telegram

- **`/status`** — último ciclo, salud, estado de cada fuente
- **`/events`** — próximos eventos vigilados
- **`/help`** — esta lista
- **`/start`** — sirve para registrarte (necesario primera vez)

---

## Coste real

**0 €/mes** si usas:
- GitHub Actions (público: ilimitado; privado: 2000 min)
- Groq tier gratis (rate limit muy generoso)
- Reddit/Google News/Bluesky/Pump.fun/Dexscreener/RugCheck — APIs públicas gratis

Único riesgo: que Groq cambie su free tier. Aún así son centavos al mes si se pasara a pago.

---

## APIs gratis OPCIONALES (más alpha)

Estas no son obligatorias pero potencian el bot:

### Solana Tracker (gratis con signup, recomendado)
1. Registrate en https://www.solanatracker.io
2. Settings → API → Create Key
3. En GitHub repo → Settings → Secrets → añade `SOLANATRACKER_API_KEY` con la key
4. Activa búsquedas más rápidas + trending mejor

### Helius RPC (CRÍTICO para smart money real-time)
1. Cuenta gratis en https://www.helius.dev (100k req/día free)
2. Dashboard → Endpoints → copia tu RPC URL completa con tu API key
3. Añade secret `HELIUS_RPC_URL` con esa URL completa
4. Activa polling rápido de wallets smart money

### Smart wallets curados (manual, 15 min)
1. Ve a https://gmgn.ai/?chain=sol → ranking traders 7d
2. Copia ~30-50 addresses con buen P&L (>$100k 30d, win rate >60%)
3. Pégalas en `config/smart_wallets.yaml` siguiendo el formato del archivo
4. El bot ahora detecta confluence (≥2 wallets en misma coin) y wake-ups (wallet dormida que despierta)

---

## Próximos niveles (cuando quieras aún más)

1. **Telegram channels via Telethon** — activar en `sources.yaml` y añadir secrets `TELEGRAM_API_ID/HASH/SESSION`.
2. **X API ($200/mes Basic)** — detección aún más temprana en X/Twitter.
3. **VPS Oracle Cloud Always Free** — 24/7 sin GitHub Actions.

Pídeme cuando estés listo — todo modular.
