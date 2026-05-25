"""Entry point — ciclo completo con TODOS los motores integrados.

FOCO: narrativas FRESCAS + coins early stage (MC <100k) + dormant event coins.
NO surfacing coins consolidadas.

Pipeline por ciclo:
1. Bot commands (/status, /events, /help)
2. RECOLECCIÓN — Reddit + Google News + Trends + Bluesky + Nitter + 4chan /biz/
                  + Solana Tracker (early only) + GMGN (early only)
3. CLUSTERING — agrupa señales en narrativas candidatas
4. MOMENTUM PRE-LLM — cross-source bonus + velocity bonus
5. TICKER VELOCITY — detecta spikes x5 mentions ticker en 1h
6. SCORING LLM — top clusters con casos históricos pre-filtrados
7. Si STRONG → hunt coins early + add a active_watch 48h
8. EVENT COIN WATCHER — coins event-linked con R/R alto
9. PUMP.FUN MONITOR — nuevas coins matching eventos / active watch
10. SMART MONEY — confluence + dormant wake-up
11. ANTICIPACIÓN EVENTOS — calendar
12. HEALTH-CHECK
13. Persistencia + dedup
"""
import os
import sys
import yaml
import json
import hashlib
import traceback
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.collectors import reddit, google_news, google_trends, bluesky, nitter
from src.collectors import fourchan_biz, solana_tracker, gmgn
from src.intelligence.clustering import cluster_signals
from src.intelligence.event_matcher import load_events, upcoming_events, match_cluster_to_event
from src.intelligence.scorer import load_historical_cases, score_cluster
from src.intelligence.momentum import (
    load_history, save_history, compute_momentum_boost,
    update_history,
)
from src.intelligence import ticker_velocity, smart_money
from src.crypto.hunter import hunt
from src.crypto import event_watcher, pump_monitor
from src.alerts import telegram, formatter
from src.memory import store
from src import health, bot_commands


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def collect_all(sources_cfg: dict) -> tuple[list, dict]:
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
            min_score=rc.get("min_score", 100),
            also_rising=rc.get("also_fetch_rising", True),
        ))

    if sources_cfg.get("google_news", {}).get("enabled"):
        signals += _run("google_news", lambda: google_news.collect(
            sources_cfg["google_news"].get("feeds", [])
        ))

    if sources_cfg.get("google_trends", {}).get("enabled"):
        signals += _run("google_trends", lambda: google_trends.collect(
            sources_cfg["google_trends"].get("geo_targets", ["US"])
        ))

    if sources_cfg.get("bluesky", {}).get("enabled"):
        signals += _run("bluesky", lambda: bluesky.collect(
            sources_cfg["bluesky"].get("search_queries", [])
        ))

    if sources_cfg.get("nitter", {}).get("enabled"):
        nc = sources_cfg["nitter"]
        signals += _run("nitter", lambda: nitter.collect(
            nc.get("instances", []), nc.get("search_queries", [])
        ))

    if sources_cfg.get("fourchan_biz", {}).get("enabled"):
        fc = sources_cfg["fourchan_biz"]
        signals += _run("4chan_biz", lambda: fourchan_biz.collect(
            fc.get("catalog_url", "https://a.4cdn.org/biz/catalog.json"),
            max_threads=fc.get("max_threads_to_scan", 60),
            min_ticker_mentions=fc.get("min_ticker_mentions", 3),
            ignored_tickers=fc.get("ignored_tickers", []),
        ))

    if sources_cfg.get("solana_tracker", {}).get("enabled"):
        st = sources_cfg["solana_tracker"]
        signals += _run("solana_tracker", lambda: solana_tracker.collect_as_signals(
            timeframe=st.get("trending_timeframe", "1h"),
            limit=st.get("trending_limit", 30),
            max_mc_usd=500000,
        ))

    if sources_cfg.get("gmgn", {}).get("enabled"):
        gm = sources_cfg["gmgn"]
        signals += _run("gmgn", lambda: gmgn.collect_as_signals(
            limit=gm.get("max_tokens", 20),
            max_mc_usd=500000,
        ))

    return signals, status


def _stable_fingerprint(cluster: dict, narrative: dict | None = None) -> str:
    parts = []
    if narrative:
        parts.append(narrative.get("category", ""))
        parts.append(narrative.get("matched_event", "") or "")
    parts.extend(sorted(cluster.get("key_terms", []))[:4])
    s = "::".join(p for p in parts if p)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


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
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main():
    load_dotenv(BASE_DIR / ".env")

    sources_cfg = _load_yaml(BASE_DIR / "config" / "sources.yaml")
    settings = _load_yaml(BASE_DIR / "config" / "settings.yaml")
    events = load_events(str(BASE_DIR / "config" / "events.yaml"))
    historical = load_historical_cases(str(BASE_DIR / "config" / "historical_cases.yaml"))

    paths = settings.get("paths", {})
    narratives_path = str(BASE_DIR / paths.get("narratives_file", "data/narratives.json"))
    coins_path = str(BASE_DIR / paths.get("coins_file", "data/coins_tracked.json"))
    alerts_path = str(BASE_DIR / paths.get("alerts_log", "data/alerts_log.json"))
    sent_keys_path = str(BASE_DIR / paths.get("sent_keys_file", "data/sent_keys.json"))
    history_path = str(BASE_DIR / paths.get("signals_history_file", "data/signals_history.json"))
    health_path = str(BASE_DIR / paths.get("health_state_file", "data/health.json"))
    event_coins_path = str(BASE_DIR / paths.get("event_coins_file", "data/event_coins.json"))
    smart_money_path = str(BASE_DIR / paths.get("smart_money_state_file", "data/smart_money.json"))
    ticker_velocity_path = str(BASE_DIR / paths.get("ticker_velocity_file", "data/ticker_velocity.json"))
    active_watch_path = str(BASE_DIR / paths.get("active_watch_file", "data/active_watch.json"))
    pump_monitor_seen_path = str(BASE_DIR / "data/pump_monitor_seen.json")
    smart_wallets_path = str(BASE_DIR / "config" / "smart_wallets.yaml")

    scoring = settings.get("scoring", {})
    momentum_cfg = settings.get("momentum_boost", {})
    dedup = settings.get("deduplication", {})
    hunter_cfg = settings.get("crypto_hunter", {})
    windows = settings.get("anticipation_windows", {})
    health_cfg = settings.get("health_check", {})

    min_alert_score = scoring.get("min_alert_score", 83)
    shadow_log_score = scoring.get("shadow_log_score", 60)
    cooldown_hours = dedup.get("narrative_cooldown_hours", 24)

    # === BOT COMMANDS ===
    try:
        n_cmds = bot_commands.process_pending(BASE_DIR, settings, events)
        if n_cmds:
            print(f"[bot] respondidos {n_cmds} comandos")
    except Exception as e:
        print(f"[bot] error: {e}")

    # === FASE 1: RECOLECCIÓN ===
    print("\n=== FASE 1: RECOLECCIÓN ===")
    signals, sources_status = collect_all(sources_cfg)
    total_signals = len(signals)
    print(f"Total signals: {total_signals}")

    if health_cfg.get("enabled", True):
        state = health.record_cycle(health_path, total_signals, sources_status)
        if health.should_alert(state, threshold=health_cfg.get("zero_signals_runs_before_alert", 3)):
            telegram.send(health.build_health_message(state))

    # === FASE 2: TICKER VELOCITY ===
    print("\n=== FASE 2: TICKER VELOCITY ===")
    try:
        spikes = ticker_velocity.run(signals, ticker_velocity_path, settings)
        print(f"Velocity spikes: {len(spikes)}")
        sent_keys = _load_json(sent_keys_path)
        for sp in spikes[:5]:
            key = f"velocity::{sp['ticker']}::{int(sp['spike_ratio'])}"
            if key in sent_keys:
                continue
            msg = formatter.format_velocity_spike(sp)
            if telegram.send(msg):
                sent_keys[key] = sp
                store.log_alert(alerts_path, "ticker_velocity", sp)
        _save_json(sent_keys_path, sent_keys)
    except Exception as e:
        print(f"[velocity] error: {e}")

    # === FASE 3: CLUSTERING ===
    if signals:
        print("\n=== FASE 3: CLUSTERING ===")
        clusters = cluster_signals(signals)
        print(f"Clusters: {len(clusters)}")
    else:
        clusters = []

    # === FASE 4: MOMENTUM PRE-LLM ===
    print("\n=== FASE 4: MOMENTUM ===")
    history = load_history(history_path)
    boosted_clusters = []
    for c in clusters:
        if momentum_cfg.get("enabled", True):
            m = compute_momentum_boost(
                c, history,
                multi_source_threshold=momentum_cfg.get("multi_source_threshold", 3),
                multi_source_bonus=momentum_cfg.get("multi_source_bonus", 8),
                velocity_window_hours=momentum_cfg.get("velocity_window_hours", 2),
                velocity_x2_bonus=momentum_cfg.get("velocity_x2_bonus", 5),
            )
        else:
            m = {"total_bonus": 0, "reasons": []}
        c["_momentum"] = m
        boosted_clusters.append(c)

    boosted_clusters.sort(
        key=lambda x: (x["_momentum"]["total_bonus"], x.get("n_distinct_families", 0),
                       x.get("engagement_total", 0)),
        reverse=True,
    )
    top_clusters = boosted_clusters[:12]
    if top_clusters:
        print(f"Top {len(top_clusters)} a LLM:")
        for i, c in enumerate(top_clusters[:5]):
            m = c["_momentum"]
            print(f"  [{i+1}] +bonus={m['total_bonus']} fams={c.get('n_distinct_families',0)} | {c['top_title'][:60]}")

    # === FASE 5: SCORING LLM + alertas + active_watch ===
    print("\n=== FASE 5: SCORING ===")
    sent_count = 0
    shadow_count = 0
    for cluster in top_clusters:
        narrative = score_cluster(
            cluster, historical,
            model=scoring.get("llm_model_primary"),
            fallback_model=scoring.get("llm_model_fallback"),
            temperature=scoring.get("llm_temperature", 0.3),
            pre_bonuses=cluster["_momentum"],
        )
        if narrative.get("error"):
            print(f"  ERROR: {narrative['error']}")
            continue
        score = int(narrative.get("score", 0))
        rec = narrative.get("recommendation", "IGNORE")
        cat = narrative.get("category", "")
        title_short = cluster["top_title"][:60]
        print(f"  score={score} | {rec} | {cat} | {title_short}")

        matched_event = match_cluster_to_event(cluster, events)
        if matched_event:
            narrative["matched_event"] = matched_event.get("name")
        fp = _stable_fingerprint(cluster, narrative)

        if store.was_recently_alerted(narratives_path, fp, cooldown_hours):
            continue

        if score < min_alert_score:
            if score >= shadow_log_score:
                store.log_alert(alerts_path, "shadow", {
                    "fp": fp, "score": score, "category": cat,
                    "title": cluster["top_title"][:160],
                })
                shadow_count += 1
            continue
        if rec == "IGNORE":
            continue

        # Hunt coins early-stage
        try:
            coins = hunt(
                narrative, cluster,
                fuzzy_threshold=hunter_cfg.get("fuzzy_match_threshold", 0.65),
                max_coins=hunter_cfg.get("max_coins_per_alert", 5),
                min_liquidity=hunter_cfg.get("min_liquidity_usd", 500),
                min_age_minutes=hunter_cfg.get("min_token_age_minutes", 5),
                max_age_hours=hunter_cfg.get("max_token_age_hours", 168),
                use_rugcheck=sources_cfg.get("crypto_sources", {}).get("rugcheck", {}).get("enabled", True),
                min_safety_score=sources_cfg.get("crypto_sources", {}).get("rugcheck", {}).get("min_safety_score", 50),
            ) if hunter_cfg.get("enabled", True) else []
        except Exception as e:
            print(f"    hunter error: {e}")
            coins = []

        msg = formatter.format_narrative_alert(narrative, cluster, coins)
        ok = telegram.send(msg)
        if ok:
            sent_count += 1

        # ACTIVE WATCH 48h con keywords del cluster + tickers sugeridos
        try:
            active_terms = (cluster.get("key_terms") or [])[:6] + \
                           (narrative.get("suggested_tickers") or [])
            pump_monitor.add_active_watch(active_watch_path, active_terms, hours=48)
        except Exception:
            pass

        cluster_meta = {
            "top_title": cluster.get("top_title"),
            "key_terms": cluster.get("key_terms"),
            "sources": cluster.get("sources"),
            "source_families": cluster.get("source_families"),
            "engagement_total": cluster.get("engagement_total"),
            "signal_count": cluster.get("signal_count"),
            "n_distinct_families": cluster.get("n_distinct_families"),
        }
        store.remember_narrative(narratives_path, fp, narrative, cluster_meta)
        store.increment_alert_count(narratives_path, fp)
        store.remember_coins(coins_path, coins, fp)
        store.log_alert(alerts_path, "narrative", {
            "fp": fp, "score": score, "title": cluster["top_title"][:200],
            "coins_n": len(coins), "category": cat,
        })

    print(f"Alertas STRONG: {sent_count}, Shadow: {shadow_count}")

    # === FASE 6: EVENT COIN WATCHER (dormant pumpers) ===
    print("\n=== FASE 6: EVENT COIN WATCHER ===")
    try:
        ev_state, candidates = event_watcher.run(events, event_coins_path, settings)
        print(f"Event-linked candidates con R/R alto: {len(candidates)}")
        sent_keys = _load_json(sent_keys_path)
        ev_cooldown = dedup.get("event_coin_alert_cooldown_hours", 48)
        # cooldown handled via sent_keys ts
        ev_sent = 0
        for c in candidates[:5]:
            key = f"event_linked::{c.get('event_id')}::{c.get('mint')}"
            if key in sent_keys:
                continue
            msg = formatter.format_event_linked_opportunity(c)
            if telegram.send(msg):
                sent_keys[key] = {"ts": store.now_utc_iso(), "score": c.get("rr", {}).get("rr_score")}
                ev_sent += 1
                store.log_alert(alerts_path, "event_linked", {
                    "event_id": c.get("event_id"),
                    "ticker": c.get("ticker"),
                    "rr": c.get("rr", {}).get("rr_score"),
                })
        _save_json(sent_keys_path, sent_keys)
        print(f"Event-linked enviados: {ev_sent}")
    except Exception as e:
        print(f"[event_watcher] error: {e}")

    # === FASE 7: PUMP.FUN MONITOR ===
    print("\n=== FASE 7: PUMP.FUN MONITOR ===")
    try:
        matches = pump_monitor.scan(events, settings, pump_monitor_seen_path, active_watch_path)
        print(f"Pump.fun matches: {len(matches)}")
        pm_sent = 0
        for m in matches[:5]:
            coin = m["coin"]
            event_name = m["matched_event_names"][0] if m["matched_event_names"] else "active_watch"
            msg = formatter.format_new_launch_for_event(coin, event_name, m["matched_terms"])
            if telegram.send(msg):
                pm_sent += 1
                store.log_alert(alerts_path, "new_launch_for_event", {
                    "ticker": coin.get("ticker"),
                    "mint": coin.get("mint"),
                    "event": event_name,
                })
        print(f"Pump.fun alerts: {pm_sent}")
    except Exception as e:
        print(f"[pump_monitor] error: {e}")

    # === FASE 8: SMART MONEY ===
    print("\n=== FASE 8: SMART MONEY ===")
    try:
        sm_result = smart_money.run(smart_wallets_path, smart_money_path, settings, sources_cfg)
        polled = sm_result.get("polled", 0)
        print(f"Wallets polled: {polled}, confluence: {len(sm_result.get('confluence', []))}, wake_ups: {len(sm_result.get('wake_ups', []))}")
        sent_keys = _load_json(sent_keys_path)
        sm_sent = 0
        for conf in sm_result.get("confluence", [])[:3]:
            key = f"confluence::{conf['mint']}::{conf['buyer_count']}"
            if key in sent_keys:
                continue
            msg = formatter.format_confluence(conf)
            if telegram.send(msg):
                sm_sent += 1
                sent_keys[key] = True
                store.log_alert(alerts_path, "confluence", conf)
        for wake in sm_result.get("wake_ups", [])[:3]:
            key = f"wakeup::{wake['wallet'][:16]}::{wake.get('mint','')[:16]}"
            if key in sent_keys:
                continue
            msg = formatter.format_wake_up(wake)
            if telegram.send(msg):
                sm_sent += 1
                sent_keys[key] = True
                store.log_alert(alerts_path, "wakeup", wake)
        _save_json(sent_keys_path, sent_keys)
        print(f"Smart money alerts: {sm_sent}")
    except Exception as e:
        print(f"[smart_money] error: {e}")

    # === FASE 9: ANTICIPACIÓN EVENTOS ===
    _check_upcoming_events(events, windows, sent_keys_path, alerts_path)

    # === FASE 10: ACTUALIZAR HISTORIAL ===
    history = update_history(history, clusters)
    save_history(history_path, history)
    print("\n✓ Ciclo completo")


def _check_upcoming_events(events, windows, sent_keys_path, alerts_path):
    print("\n=== FASE 9: ANTICIPACIÓN EVENTOS ===")
    upcoming = upcoming_events(
        events, today=date.today(),
        major_days=windows.get("major_event_days", 30),
        medium_days=windows.get("medium_event_days", 14),
        small_days=windows.get("small_event_days", 7),
        imminent_days=windows.get("imminent_event_days", 3),
    )
    sent_keys = _load_json(sent_keys_path)
    sent_event = 0
    for e in upcoming:
        key = f"event::{e['id']}::{e['window_type']}"
        if key in sent_keys:
            continue
        msg = formatter.format_event_anticipation(e)
        if telegram.send(msg):
            sent_event += 1
            sent_keys[key] = e.get("days_to_event", 0)
            store.log_alert(alerts_path, "event_anticipation", {
                "key": key, "event_id": e["id"], "window": e["window_type"],
            })
    _save_json(sent_keys_path, sent_keys)
    print(f"Alertas evento: {sent_event}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
