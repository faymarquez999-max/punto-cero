"""Smart Money tracker — confluence + dormant wake-up.

Para cada wallet en config/smart_wallets.yaml:
1. Fetch las N transacciones más recientes (Helius RPC o public RPC)
2. Extrae buys/sells de tokens (filtra spam/dust)
3. Trackea última actividad → si >7d inactiva, se marca dormant

Confluence: ≥2 wallets distintas compran la misma coin en <2h
Wake-up: wallet dormant compra cualquier coin
"""
import json
import os
import time
import requests
import yaml
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional


def load_wallets(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        sw = data.get("smart_wallets")
        if not sw or sw == []:
            return []
        return sw
    except Exception:
        return []


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str, indent=2)
    os.replace(tmp, path)


def _rpc_url() -> str:
    helius = os.getenv("HELIUS_RPC_URL", "")
    if helius:
        return helius
    return "https://api.mainnet-beta.solana.com"


def fetch_recent_signatures(wallet: str, limit: int = 10) -> List[Dict]:
    """Helius/public RPC getSignaturesForAddress."""
    try:
        r = requests.post(_rpc_url(), json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getSignaturesForAddress",
            "params": [wallet, {"limit": limit}]
        }, timeout=15)
        if r.status_code != 200:
            return []
        return (r.json() or {}).get("result", []) or []
    except Exception:
        return []


def fetch_transaction(signature: str) -> Optional[Dict]:
    """Detalle de tx con token transfers parsed."""
    try:
        r = requests.post(_rpc_url(), json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getTransaction",
            "params": [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
        }, timeout=15)
        if r.status_code != 200:
            return None
        return (r.json() or {}).get("result")
    except Exception:
        return None


def _extract_token_buys(tx: Dict, wallet: str) -> List[Dict]:
    """Extrae compras de tokens SPL en la tx (delta positivo en token balance del wallet).

    Devuelve lista de {mint, ticker?, amount, ui_amount}. Filtra dust.
    """
    if not tx:
        return []
    meta = tx.get("meta") or {}
    if meta.get("err"):
        return []
    pre = {(x.get("owner"), x.get("mint")): x for x in (meta.get("preTokenBalances") or [])}
    post = {(x.get("owner"), x.get("mint")): x for x in (meta.get("postTokenBalances") or [])}

    buys = []
    for key, post_bal in post.items():
        owner, mint = key
        if owner != wallet:
            continue
        pre_bal = pre.get(key)
        post_amt = float((post_bal.get("uiTokenAmount") or {}).get("uiAmount", 0) or 0)
        pre_amt = float((pre_bal or {}).get("uiTokenAmount", {}).get("uiAmount", 0) or 0) if pre_bal else 0
        delta = post_amt - pre_amt
        if delta <= 0:
            continue
        # Filtra dust (< $0 trivial)
        if delta < 0.000001:
            continue
        buys.append({"mint": mint, "delta_ui": delta})
    return buys


def poll_wallet(wallet_addr: str, tx_limit: int = 10) -> Dict:
    """Devuelve un snapshot del wallet: {last_activity_ts, recent_buys: [...]}"""
    sigs = fetch_recent_signatures(wallet_addr, limit=tx_limit)
    if not sigs:
        return {"last_activity_ts": None, "recent_buys": []}

    last_block_time = max((s.get("blockTime") or 0) for s in sigs)
    recent_buys = []
    for s in sigs[:5]:   # solo top 5 detallados
        tx = fetch_transaction(s["signature"])
        if not tx:
            continue
        buys = _extract_token_buys(tx, wallet_addr)
        for b in buys:
            recent_buys.append({
                **b,
                "block_time": s.get("blockTime"),
                "signature": s["signature"][:16],
            })
        time.sleep(0.3)   # rate limit
    return {
        "last_activity_ts": last_block_time,
        "recent_buys": recent_buys,
    }


def detect_signals(snapshots: Dict[str, Dict], wallets: List[Dict],
                  confluence_window_min: int = 120,
                  confluence_min: int = 2,
                  dormant_days: int = 7) -> Dict:
    """Analiza snapshots y detecta confluence + wake-ups.

    Returns:
        {"confluence": [{mint, wallets, total_amount}], "wake_ups": [{wallet, label, mint}]}
    """
    now_ts = datetime.now(timezone.utc).timestamp()
    window_ts = now_ts - confluence_window_min * 60
    dormant_ts = now_ts - dormant_days * 86400

    # confluence: misma mint comprada por ≥N wallets distintos dentro de ventana
    mint_buyers: Dict[str, List[Dict]] = {}
    wake_ups = []

    wallet_labels = {w.get("address"): w for w in wallets if isinstance(w, dict)}

    for addr, snap in snapshots.items():
        info = wallet_labels.get(addr, {})
        recent = snap.get("recent_buys") or []
        # Wake-up: last_activity_ts antes de dormant_ts pero recent_buys no vacío
        # NOTE: si tiene recent_buys con block_time reciente Y prev_last_activity <dormant_ts
        prev_last = snap.get("prev_last_activity_ts")
        cur_last = snap.get("last_activity_ts")
        if prev_last is not None and cur_last is not None:
            if prev_last < dormant_ts and cur_last >= dormant_ts:
                for b in recent[:3]:
                    wake_ups.append({
                        "wallet": addr,
                        "label": info.get("label", ""),
                        "mint": b.get("mint"),
                        "block_time": b.get("block_time"),
                    })

        # Para confluence
        for b in recent:
            bt = b.get("block_time") or 0
            if bt < window_ts:
                continue
            mint = b.get("mint")
            if not mint:
                continue
            mint_buyers.setdefault(mint, []).append({"wallet": addr, "label": info.get("label", ""), "block_time": bt})

    confluence = []
    for mint, buyers in mint_buyers.items():
        unique = {b["wallet"]: b for b in buyers}.values()
        if len(unique) >= confluence_min:
            confluence.append({
                "mint": mint,
                "buyer_count": len(unique),
                "buyers": list(unique)[:6],
            })

    return {"confluence": confluence, "wake_ups": wake_ups}


def run(wallets_path: str, state_path: str, settings: dict,
        sources_cfg: Dict | None = None) -> Dict:
    """Pipeline completo. Devuelve signals + actualiza state.

    Si la lista de wallets está vacía, hace no-op silencioso.
    sources_cfg: opcional, para leer smart_money_rpc.recent_tx_limit.
    """
    cfg = settings.get("smart_money", {})
    if not cfg.get("enabled", True):
        return {"confluence": [], "wake_ups": [], "polled": 0}
    wallets = load_wallets(wallets_path)
    # Filtra entradas no dict (e.g. el `[]` placeholder)
    wallets = [w for w in wallets if isinstance(w, dict) and w.get("address")]
    if not wallets:
        return {"confluence": [], "wake_ups": [], "polled": 0, "note": "no_wallets_curated"}

    prev_state = _load(state_path)
    max_wallets = int(cfg.get("max_wallets_to_poll", 100))
    snapshots = {}
    # smart_money_rpc config vive en sources.yaml
    rpc_cfg = (sources_cfg or {}).get("smart_money_rpc", {}) if sources_cfg else {}
    tx_limit = int(rpc_cfg.get("recent_tx_limit", 10))

    for w in wallets[:max_wallets]:
        addr = w["address"]
        prev = (prev_state.get("wallets") or {}).get(addr, {})
        snap = poll_wallet(addr, tx_limit=tx_limit)
        snap["prev_last_activity_ts"] = prev.get("last_activity_ts")
        snapshots[addr] = snap
        time.sleep(0.4)   # rate limit between wallets

    signals = detect_signals(
        snapshots, wallets,
        confluence_window_min=int(cfg.get("confluence_window_minutes", 120)),
        confluence_min=int(cfg.get("confluence_min_wallets", 2)),
        dormant_days=int(cfg.get("dormant_threshold_days", 7)),
    )

    # Persist
    new_state = {"wallets": {addr: {"last_activity_ts": s.get("last_activity_ts"),
                                    "recent_buys": s.get("recent_buys", [])[:5]}
                              for addr, s in snapshots.items()},
                 "last_run": datetime.now(timezone.utc).isoformat()}
    _save(state_path, new_state)

    return {**signals, "polled": len(snapshots)}
