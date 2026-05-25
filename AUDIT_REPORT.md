# Auditoría Profunda — Narrative Alpha Hunter 1
**Fecha:** 2026-05-25
**Tipo:** Revisión microscópica post-MVP, identificación de bugs y gaps críticos antes de deploy.

---

## Resumen ejecutivo

El MVP es sólido como esqueleto pero tenía **1 bug bloqueante** (consumo de GitHub Actions free tier), **8 bugs medios** (umbrales mal calibrados, datos desactualizados, endpoints frágiles) y **~15 gaps importantes** (features que diferencian un sistema "bueno" de uno "fuera de lo normal").

He clasificado todos los hallazgos en 3 tiers de impacto y los implemento por orden.

---

## TIER 1 — BUGS CRÍTICOS (bloquean o degradan el sistema)

### 1. BLOCKER: Consumo de GitHub Actions excede free tier
- **Hallazgo:** cron cada 10 min en repo privado = 4320 runs/mes × ~2 min ≈ 8640 min/mes. El free tier de GitHub Actions es **2000 min/mes para repos privados**.
- **Impacto:** El sistema deja de funcionar a los 4-5 días del despliegue.
- **Fix:** 3 opciones — cambio a 30 min cron, repo público (minutos ilimitados pero datos visibles), o VPS Oracle Cloud Always Free.
- **Decisión:** cron **15 min** + recomiendo repo público para máxima frecuencia. El usuario decide.

### 2. Fecha GTA VI incorrecta
- **Hallazgo:** `events.yaml` decía `2026-09-17` — la fecha confirmada por Rockstar es **19 noviembre 2026**.
- **Fix:** Actualizar fecha.

### 3. Topuria — opponent y location faltantes
- **Hallazgo:** Pelea Topuria 14-jun-2026 es contra **Justin Gaethje en la CASA BLANCA** (evento histórico, Dana White + Trump). La narrativa "UFC en la Casa Blanca" es la más grande del año.
- **Fix:** Corregir descripción y añadir keywords específicas.

### 4. Pump.fun API endpoint frágil
- **Hallazgo:** Uso `frontend-api.pump.fun` — los endpoints están segmentados ahora: `frontend-api-v3`, `frontend-api-v2`, `advanced-api-v2` y algunos requieren JWT.
- **Fix:** Implementar cadena de fallback entre endpoints + retry.

### 5. Reddit min_score=500 demasiado alto
- **Hallazgo:** En la primera hora un post viral puede tener 50-200 upvotes. Filtrar a 500 pierde detección temprana.
- **Fix:** Bajar a 100 + meta de "rising" en lugar de solo hot.

### 6. Google News engagement=0 → señales filtradas downstream
- **Hallazgo:** Google News no expone métrica de engagement. Asigno 0. Cualquier filtro futuro por engagement las descarta.
- **Fix:** Asignar score base por novelty (timestamp reciente) y nº de feeds donde aparece.

### 7. Clustering threshold demasiado bajo
- **Hallazgo:** `min_overlap=2` agrupa narrativas distintas que comparten 2 palabras genéricas ("ufc", "fight").
- **Fix:** Subir a 3 + raise title_similarity 70→80.

### 8. _already_sent O(N) scan + memoria que trunca a 2000
- **Hallazgo:** Búsqueda lineal sobre log que se trunca a 2000 — eventos antiguos pueden re-disparar.
- **Fix:** Usar un set persistente `sent_keys.json` separado del log.

### 9. Config muerta sin enganchar al código
- **Hallazgo:** `settings.yaml` define `enabled_categories` y `rate_limits` pero el código NUNCA los lee.
- **Fix:** O conectarlos o eliminarlos. Conecto categorías (filtro post-LLM) y elimino rate_limits muerto.

### 10. Dependencia inútil
- **Hallazgo:** `python-telegram-bot` en requirements pero envío con `requests` directo.
- **Fix:** Eliminar dep para acelerar CI.

### 11. Telegram chunking puede partir tags HTML
- **Hallazgo:** Split naïve a 3900 chars puede romper `<a href=...>`.
- **Fix:** Split en `\n\n` cercano.

---

## TIER 2 — GAPS DE INTELIGENCIA (lo que diferencia "normal" de "fuera de lo normal")

### A. Falta cross-source momentum
- **Por qué importa:** Que una narrativa aparezca en Reddit + Google News + Bluesky simultáneamente es la señal MÁS fuerte de viralidad real. Hoy solo cuento engagement.
- **Fix:** Boost score si signal_count ≥ 3 fuentes distintas. Penaliza si solo 1.

### B. Falta detección de momentum temporal (velocity)
- **Por qué importa:** "Narrativa que va de 0 → 10 menciones en 1h" es alpha. Hoy solo veo el estado actual.
- **Fix:** Cada run compara con runs anteriores (memoria) y calcula delta — boost si crecimiento súbito.

### C. Casos históricos incompletos
- **Por qué importa:** Faltan los más recientes y representativos (TRUMP coin, WIF, MOG, MELANIA, LIBRA scandal, MOTHER). La IA decide por analogía — sin estos, calibra mal.
- **Fix:** Añadir 6 casos más.

### D. Calendario de eventos demasiado pequeño
- **Por qué importa:** Solo 6 eventos. Faltan UFC eventos mensuales, NBA Finals, Champions League, lanzamientos tech, eventos políticos Trump.
- **Fix:** Añadir ≥10 eventos verificados + sub-eventos del Mundial.

### E. No hay digest diario
- **Por qué importa:** Si no hay alertas STRONG, te quedas sin info. Un resumen matinal de "top narrativas últimas 24h" da contexto incluso en días tranquilos.
- **Fix:** Cron extra a las 9:00 Madrid (07:00 UTC) que manda recap del día.

### F. No hay health-check
- **Por qué importa:** Si las APIs caen en cascada y 0 signals durante 6h, no te enteras hasta que falte algo importante.
- **Fix:** Si total_signals=0 durante N runs consecutivos → alerta de salud.

### G. Pump.fun coins sin filtro de calidad
- **Por qué importa:** El 95% de coins lanzadas en pump.fun son basura. Recomendarlas todas es ruido.
- **Fix:** Filtro mínimo — debe tener twitter, telegram O website + descripción no vacía + creator no haya hecho rug previo.

### H. No hay subreddits/feeds en español
- **Por qué importa:** Topuria, GTA VI (versión ES), Mundial → muchas narrativas españolas se filtran solo en inglés.
- **Fix:** Añadir r/spain, r/uruguay, r/argentina, r/futbol + feeds Google News ES con queries específicas.

### I. Score umbral 83 sin calibración
- **Por qué importa:** Puede ser muy restrictivo (0 alertas) o muy permisivo. Sin métricas no sabes.
- **Fix:** Modo "shadow" durante 48h donde TODO score ≥ 60 se loguea pero solo ≥ 83 alerta. Permite calibrar.

### J. El LLM ve TODOS los casos históricos cada vez
- **Por qué importa:** Prompt enorme = más lento + más consumo. El LLM lee 12 casos para evaluar 1 narrativa.
- **Fix:** Pre-filtrar casos por categoría/keyword antes de pasarlos.

### K. Crypto hunter no chequea seguridad
- **Por qué importa:** Si recomiendo una coin y es rug → daño reputacional + pérdida real.
- **Fix:** Validar contra RugCheck.xyz (free API) o al menos chequear edad del token y holders.

### L. No hay /status command en el bot
- **Por qué importa:** Quieres saber "está vivo?". Hoy solo recibes alertas.
- **Fix:** Polling getUpdates cada run para responder `/status` con "último ciclo: X min ago, signals procesados: Y".

### M. Sin Telegram channels (Telethon)
- **Por qué importa:** Los canales alpha de Telegram son donde se incuban las narrativas crypto 6-12h antes que el resto.
- **Fix:** Telethon con session string (la guías en setup).

### N. Sin dashboard
- **Por qué importa:** Querrás revisar histórico, ver patrones, calibrar.
- **Fix:** HTML estático + JSON que se hospeda gratis en GitHub Pages.

### O. Anti-spam frágil
- **Por qué importa:** El cluster fingerprint depende de key_terms que cambian entre runs → la misma narrativa puede generar 5 alertas.
- **Fix:** Fingerprint normalizado por categoría + matched_event si existe.

---

## TIER 3 — POLISH (nice-to-have, no urgentes)

- Image OCR para detectar memes virales en imágenes
- Whale wallet tracking (Helius API free)
- Backtest mode para validar contra eventos pasados
- Reddit OAuth con credenciales para mayor rate-limit
- Sentiment analysis nativo (sin LLM) como pre-filtro barato
- Alertas por gravedad (silenciar las de score 83-90 en horario de sueño)

---

## Plan de implementación (orden de ejecución)

### Bloque 1 — Bugs críticos (Tier 1 completo)
1. Fix workflow + recomendación repo público
2. Update fechas/datos events.yaml (GTA, Topuria-Gaethje-WhiteHouse)
3. Pump.fun multi-endpoint fallback
4. Reddit thresholds + min_score
5. Google News engagement scoring
6. Clustering thresholds
7. Sent keys persistentes (Tier 1.8)
8. Remover dead deps
9. Telegram chunking smart

### Bloque 2 — Inteligencia (Tier 2 alto impacto)
10. Cross-source momentum scoring
11. Velocity tracking (delta vs run anterior)
12. Casos históricos +6 (TRUMP, WIF, MOG, LIBRA, MELANIA, MOTHER)
13. Eventos +10 (UFC, NBA, sports, política)
14. Spanish-specific sources
15. Pump.fun quality filters
16. Daily digest workflow
17. Health-check alert
18. /status bot command
19. Calibration log mode (shadow alerts)
20. LLM prompt slimming (sólo casos relevantes)
21. RugCheck integration

### Bloque 3 — Final
22. Dashboard HTML estático
23. SETUP_PARA_TI.md actualizado con hosting trade-offs
24. README final
