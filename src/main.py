"""Entry point V3 — Punto Cero.

Filosofía: radar cultural inteligente. Detecta narrativas frescas con potencial memético
y trackea coins existentes con catalizadores futuros. Sin calendario hardcoded.

Pipeline por ciclo:
1. Bot commands (/status, /help)
2. RECOLECCIÓN amplia (Reddit, breaking news, Wikipedia, Polymarket, X via Nitter,
                       Bluesky, 4chan, Google News/Trends)
3. CLUSTERING — agrupa señales en narrativas candidatas
4. MOMENTUM PRE-LLM — cross-source bonus
5. NARRATIVE POTENTIAL SCORER (LLM) — evalúa con principios memetéticos
6. Si score >= umbral → crea ACTIVE WATCH (con tickers candidatos + key_terms)
7. PROCESS ACTIVE WATCHES — cada watch activo busca coin matching en DexScreener
   (filtros duros: MC 10-500k, liq 5k+, vol 5k+, holders 50+, age 10min+)
8. EVENT-LINKED RADAR (cada 4 ciclos) — escanea low-cap Solana y pregunta al LLM
   si hay catalizador futuro conocido
9. ANTICIPACIÓN EVENTOS (legacy, deshabilitado por default)
10. HEALTH CHECK
"""
import os
import sys
import yaml
import json
import traceback
from datetime import date, datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.collectors import (
    reddit, google_news, google_trends, bluesky, nitter,
    fourchan_biz, solana_tracker, gmgn,
    wikipedia, breaking_news, polymarket,
)
from src.intelligence.clustering import cluster_signals
from src.intelligence.momentum import (
    load_history, save_history, compute_momentum_boost, update_history,
)
from src.intelligence.narrative_potential import (
    score_narrative, load_principles,
)
from src.intelligence import active_watch
from src.crypto import dex_matcher, event_radar
from src.alerts import telegram, formatter
from src.memory import store
from src import health, bot_commands


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, path)


def collect_all(sources_cfg: dict, polymarket_state_path: str) -> tuple[list, dict]:
    """Recolecta de TODAS las fuentes habilitadas."""
    signals: list = []
    status: dict = {}

    def _run(name, fn):
        try:
            sigs = fn()
            status[name] = len(sigs)
            print(f"[{name}] {len(sigs)} signals")
            return sigs
        except Exception as e:
            print(f"[{name}] failed: {e}")
            status[name] = 0
            return []

    if sources_cfg.get("reddit", {}).get("enabled"):
        rc = sources_cfg["reddit"]
        signals += _run("reddit", lambda: reddit.collect(
            rc.get("subreddits", []),
            hot_limit=rc.get("hot_limit", 30),
            min_score=rc.get("min_score", 80),
            also_rising=rc.get("also_fetch_rising", True),
        ))

    if sources_cfg.get("google_news", {}).get("enabled"):
        signals += _run("google_news", lambda: google_news.collect(
            sources_cfg["google_news"].get("feeds", [])
        ))

    if sources_cfg.get("breaking_news_feeds", {}).get("enabled"):
        signals += _run("breaking_news", lambda: breaking_news.collect(
            sources_cfg["breaking_news_feeds"].get("feeds", [])
        ))

    if sources_cfg.get("wikipedia", {}).get("enabled"):
        wc = sources_cfg["wikipedia"]
        signals += _run("wikipedia", lambda: wikipedia.collect(
            wc.get("watched_pages", []),
            edit_spike_threshold=wc.get("edit_spike_threshold", 5),
            check_global=wc.get("check_recent_changes_global", True),
        ))

    if sources_cfg.get("polymarket", {}).get("enabled"):
        pm_cfg = sources_cfg["polymarket"]
        def _pm():
            prev_state = _load_json(polymarket_state_path)
            sigs, new_state = polymarket.collect(
                min_change_pct=pm_cfg.get("min_probability_change_pct", 10),
                max_markets=pm_cfg.get("max_markets_per_cycle", 50),
                state=prev_state,
            )
            _save_json(polymarket_state_path, new_state)
            return sigs
        signals += _run("polymarket", _pm)

    if sources_cfg.get("nitter", {}).get("enabled"):
        nc = sources_cfg["nitter"]
        signals += _run("nitter", lambda: nitter.collect(
            instances=nc.get("instances", []),
            queries=nc.get("search_queries", []),
            accounts=nc.get("accounts_to_watch", []),
        ))

    if sources_cfg.get("bluesky", {}).get("enabled"):
        signals += _run("bluesky", lambda: bluesky.collect(
            sources_cfg["bluesky"].get("search_queries", [])
        ))

    if sources_cfg.get("fourchan_biz", {}).get("enabled"):
        fc = sources_cfg["fourchan_biz"]
        signals += _run("4chan_biz", lambda: fourchan_biz.collect(
            fc.get("catalog_url", "https://a.4cdn.org/biz/catalog.json"),
            max_threads=fc.get("max_threads_to_scan", 60),
            min_ticker_mentions=fc.get("min_ticker_mentions", 3),
            ignored_tickers=fc.get("ignored_tickers", []),
        ))

    if sources_cfg.get("google_trends", {}).get("enabled"):
        signals += _run("google_trends", lambda: google_trends.collect(
            sources_cfg["google_trends"].get("geo_targets", ["US"])
        ))

    return signals, status


def main():
    load_dotenv(BASE_DIR / ".env")

    sources_cfg = _load_yaml(BASE_DIR / "config" / "sources.yaml")
    settings = _load_yaml(BASE_DIR / "config" / "settings.yaml")
    principles = load_principles(str(BASE_DIR / "config" / "memetic_principles.yaml"))

    paths = settings.get("paths", {})
    alerts_path = str(BASE_DIR / paths.get("alerts_log", "data/alerts_log.json"))
    sent_keys_path = str(BASE_DIR / paths.get("sent_keys_file", "data/sent_keys.json"))
    history_path = str(BASE_DIR / paths.get("signals_history_file", "data/signals_history.json"))
    health_path = str(BASE_DIR / paths.get("health_state_file", "data/health.json"))
    active_watches_path = str(BASE_DIR / paths.get("active_watches_file", "data/active_watches.json"))
    matched_coins_path = str(BASE_DIR / paths.get("matched_coins_file", "data/matched_coins.json"))
    event_radar_path = str(BASE_DIR / paths.get("event_radar_state_file", "data/event_radar.json"))
    narrative_log_path = str(BASE_DIR / paths.get("narrative_log_file", "data/narratives.json"))
    polymarket_state_path = str(BASE_DIR / "data" / "polymarket_state.json")

    scoring = settings.get("scoring", {})
    momentum_cfg = settings.get("momentum_boost", {})
    aw_cfg = settings.get("active_watch", {})
    dex_cfg = settings.get("dex_matcher", {})
    dedup = settings.get("deduplication", {})
    health_cfg = settings.get("health_check", {})

    min_alert_score = scoring.get("min_alert_score", 70)
    shadow_log_score = scoring.get("shadow_log_score", 50)
    narrative_cooldown_h = dedup.get("narrative_cooldown_hours", 24)

    # === BOT COMMANDS ===
    try:
        # Load events placeholder (vacío en V3 pero el bot_commands lo necesita)
        events = []
        n_cmds = bot_commands.process_pending(BASE_DIR, settings, events)
        if n_cmds:
            print(f"[bot] respondidos {n_cmds} comandos")
    except Exception as e:
        print(f"[bot] error: {e}")

    # === FASE 1: RECOLECCIÓN ===
    print("\n=== FASE 1: RECOLECCIÓN ===")
    signals, sources_status = collect_all(sources_cfg, polymarket_state_path)
    total_signals = len(signals)
    print(f"Total signals: {total_signals}")

    # Health check
    if health_cfg.get("enabled", True):
        state = health.record_cycle(health_path, total_signals, sources_status)
        if health.should_alert(state, threshold=health_cfg.get("zero_signals_runs_before_alert", 4)):
            telegram.send(formatter.format_health_alert(state))

    # === FASE 2: CLUSTERING + MOMENTUM ===
    if signals:
        clusters = cluster_signals(signals)
        print(f"\n=== FASE 2: CLUSTERING ===\nClusters: {len(clusters)}")
    else:
        clusters = []

    history = load_history(history_path)
    boosted = []
    for c in clusters:
        if momentum_cfg.get("enabled", True):
            m = compute_momentum_boost(
                c, history,
                multi_source_threshold=momentum_cfg.get("multi_source_threshold", 2),
                multi_source_bonus=momentum_cfg.get("multi_source_bonus", 6),
                velocity_window_hours=momentum_cfg.get("velocity_window_hours", 2),
                velocity_x2_bonus=momentum_cfg.get("velocity_x2_bonus", 4),
            )
        else:
            m = {"total_bonus": 0, "reasons": []}
        c["_momentum"] = m
        boosted.append(c)

    boosted.sort(
        key=lambda x: (x["_momentum"]["total_bonus"], x.get("n_distinct_families", 0),
                       x.get("engagement_total", 0)),
        reverse=True,
    )
    top_clusters = boosted[:12]

    # === FASE 3: NARRATIVE POTENTIAL SCORING + ACTIVE WATCH CREATION ===
    print(f"\n=== FASE 3: SCORING NARRATIVAS (top {len(top_clusters)}) ===")
    watches_state = active_watch.load_state(active_watches_path)
    # Expira viejos
    n_expired = active_watch.expire_old(watches_state)
    if n_expired:
        print(f"Watches expirados: {n_expired}")

    sent_count = 0
    shadow_count = 0
    new_watches_created = 0

    for cluster in top_clusters:
        narrative = score_narrative(
            cluster, principles,
            model=scoring.get("llm_model_primary"),
            fallback_model=scoring.get("llm_model_fallback"),
            temperature=scoring.get("llm_temperature", 0.4),
            pre_bonuses=cluster.get("_momentum", {}),
        )
        if narrative.get("error"):
            print(f"  ERROR: {narrative['error']}")
            continue

        score = int(narrative.get("score", 0))
        rec = narrative.get("recommendation", "IGNORE")
        cat = narrative.get("category", "")
        title_short = cluster.get("top_title", "")[:65]
        print(f"  score={score} | {rec} | {cat} | {title_short}")

        # Categoría bloqueada?
        blocked = settings.get("filters", {}).get("blocked_categories", []) or []
        if cat in blocked:
            print(f"    [skip blocked category]")
            continue

        # Shadow log
        if score < min_alert_score:
            if score >= shadow_log_score:
                store.log_alert(alerts_path, "shadow", {
                    "score": score, "category": cat,
                    "title": cluster.get("top_title", "")[:200],
                    "candidate_tickers": narrative.get("candidate_tickers", []),
                })
                shadow_count += 1
            continue
        if rec == "IGNORE":
            continue

        # Dedup
        fp = active_watch.watch_fingerprint(narrative)
        if active_watch.has_recent_watch(watches_state, fp, cooldown_hours=narrative_cooldown_h):
            print(f"    [skip cooldown — watch reciente con misma firma]")
            continue

        # Crear watch
        cluster_meta = {
            "top_title": cluster.get("top_title"),
            "source_families": cluster.get("source_families", []),
        }
        watch = active_watch.create_watch(
            watches_state, narrative, cluster_meta,
            default_duration_hours=aw_cfg.get("default_duration_hours", 72),
            strong_duration_hours=aw_cfg.get("strong_duration_hours", 168),
        )
        new_watches_created += 1

        # Alerta POTENTIAL NARRATIVE
        msg = formatter.format_potential_narrative(narrative, cluster, watch)
        ok = telegram.send(msg)
        if ok:
            sent_count += 1
        store.log_alert(alerts_path, "potential_narrative", {
            "watch_id": watch["id"],
            "score": score,
            "category": cat,
            "title": cluster.get("top_title", "")[:200],
            "candidate_tickers": watch.get("candidate_tickers", []),
        })

    print(f"\nNarrativas detectadas: {new_watches_created}, alertas STRONG enviadas: {sent_count}, shadow: {shadow_count}")
    active_watch.save_state(active_watches_path, watches_state)

    # === FASE 4: PROCESS ACTIVE WATCHES (DEX MATCHER) ===
    print("\n=== FASE 4: ACTIVE WATCHES → DEX MATCHER ===")
    active_list = active_watch.get_active(watches_state)
    print(f"Watches activos a procesar: {len(active_list)}")

    matched_coins = _load_json(matched_coins_path)
    matched_coins.setdefault("matched", [])
    coin_alerts_sent = 0

    for watch in active_list[: int(aw_cfg.get("max_active_watches", 50))]:
        active_watch.increment_scan_attempts(watches_state, watch["id"])
        try:
            coin = dex_matcher.find_matching_coin(
                watch, dex_cfg,
                use_rugcheck=sources_cfg.get("crypto_sources", {}).get("rugcheck", {}).get("enabled", True),
                min_safety_score=sources_cfg.get("crypto_sources", {}).get("rugcheck", {}).get("min_safety_score", 50),
                fuzzy_threshold=dex_cfg.get("fuzzy_match_threshold", 0.70),
            )
        except Exception as e:
            print(f"  [matcher error] {e}")
            coin = None

        if coin:
            mint = coin.get("mint", "")
            print(f"  ✓ MATCH: {watch['id']} → ${coin.get('ticker')} ({mint[:10]}...)")
            # Dedup match
            already_sent = any(m.get("watch_id") == watch["id"] and m.get("mint") == mint
                               for m in matched_coins["matched"])
            if already_sent:
                continue
            msg = formatter.format_coin_matched(coin, watch)
            ok = telegram.send(msg)
            if ok:
                coin_alerts_sent += 1
                active_watch.mark_watch_matched(watches_state, watch["id"], coin)
                matched_coins["matched"].append({
                    "watch_id": watch["id"],
                    "mint": mint,
                    "ticker": coin.get("ticker"),
                    "matched_at": datetime.now(timezone.utc).isoformat(),
                })
                store.log_alert(alerts_path, "coin_matched", {
                    "watch_id": watch["id"],
                    "ticker": coin.get("ticker"),
                    "mint": mint,
                    "mc": coin.get("market_cap_usd"),
                })
    print(f"Coin matches: {coin_alerts_sent}")

    _save_json(matched_coins_path, matched_coins)
    active_watch.save_state(active_watches_path, watches_state)

    # === FASE 5: EVENT-LINKED RADAR (cada N ciclos) ===
    er_cfg = settings.get("event_radar", {})
    if er_cfg.get("enabled", True):
        # Decide si toca correrlo (cada N ciclos)
        radar_state = _load_json(event_radar_path)
        cycles_since = int(radar_state.get("_cycles_since_last_radar", 999))
        scan_every = int(er_cfg.get("scan_every_n_cycles", 4))
        if cycles_since >= scan_every:
            print("\n=== FASE 5: EVENT-LINKED RADAR ===")
            try:
                candidates = event_radar.run(settings, event_radar_path)
                print(f"Event-linked candidates: {len(candidates)}")
                er_sent = 0
                sent_keys = _load_json(sent_keys_path)
                for c in candidates[:3]:
                    coin = c["coin"]
                    ev = c["evaluation"]
                    key = f"event_linked::{coin.get('mint', '')}"
                    if key in sent_keys:
                        continue
                    msg = formatter.format_event_linked(coin, ev)
                    if telegram.send(msg):
                        er_sent += 1
                        sent_keys[key] = {"ts": datetime.now(timezone.utc).isoformat()}
                        store.log_alert(alerts_path, "event_linked", {
                            "ticker": coin.get("ticker"),
                            "mint": coin.get("mint"),
                            "catalyst": ev.get("catalyst_description", "")[:200],
                            "rr": ev.get("rr_score"),
                        })
                _save_json(sent_keys_path, sent_keys)
                print(f"Event-linked alerts: {er_sent}")
            except Exception as e:
                print(f"[event_radar] error: {e}")
            # Reset cycles
            radar_state["_cycles_since_last_radar"] = 0
            _save_json(event_radar_path, radar_state)
        else:
            radar_state["_cycles_since_last_radar"] = cycles_since + 1
            _save_json(event_radar_path, radar_state)

    # === FASE 6: ACTUALIZAR HISTORIAL ===
    history = update_history(history, clusters)
    save_history(history_path, history)
    print("\n✓ Ciclo completo")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
