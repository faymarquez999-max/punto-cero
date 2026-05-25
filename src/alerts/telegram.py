"""Envío Telegram vía Bot API HTTP — chunking inteligente + retry."""
import os
import time
import requests
from typing import Optional, List

API_BASE = "https://api.telegram.org"
MAX_CHUNK = 3800   # margen bajo el límite 4096


def _split_smart(text: str, max_len: int = MAX_CHUNK) -> List[str]:
    """Parte en \\n\\n cercanos, sin partir tags HTML."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    rest = text
    while len(rest) > max_len:
        cut = rest.rfind("\n\n", 0, max_len)
        if cut < max_len // 2:
            cut = rest.rfind("\n", 0, max_len)
        if cut < max_len // 2:
            cut = max_len
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip()
    if rest:
        chunks.append(rest)
    return chunks


def send(message: str, bot_token: Optional[str] = None,
         chat_id: Optional[str] = None,
         disable_web_preview: bool = True,
         parse_mode: str = "HTML",
         max_retries: int = 2) -> bool:
    bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("[telegram] falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID — skip")
        return False

    url = f"{API_BASE}/bot{bot_token}/sendMessage"
    chunks = _split_smart(message)
    ok = True
    for chunk in chunks:
        for attempt in range(max_retries + 1):
            try:
                r = requests.post(url, data={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": "true" if disable_web_preview else "false",
                }, timeout=15)
                if r.status_code == 200:
                    break
                if r.status_code == 429:
                    j = {}
                    try:
                        j = r.json()
                    except Exception:
                        pass
                    wait = int(j.get("parameters", {}).get("retry_after", 3))
                    time.sleep(wait + 1)
                    continue
                print(f"[telegram] {r.status_code}: {r.text[:200]}")
                ok = False
                break
            except Exception as e:
                print(f"[telegram] exception: {e}")
                if attempt >= max_retries:
                    ok = False
                else:
                    time.sleep(1.5)
    return ok


def get_updates(offset: Optional[int] = None,
                bot_token: Optional[str] = None,
                timeout: int = 0) -> list:
    """getUpdates polling — para comandos /status."""
    bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return []
    url = f"{API_BASE}/bot{bot_token}/getUpdates"
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return (r.json() or {}).get("result", []) or []
    except Exception as e:
        print(f"[telegram] getUpdates exception: {e}")
    return []
