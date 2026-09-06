"""
Telegram bildirim katmani.

Ayarlar ortam degiskenlerinden okunur:
    TELEGRAM_BOT_TOKEN   BotFather'dan aldiginiz token
    TELEGRAM_CHAT_ID     Mesajin gidecegi sohbet/kanal id'si

Ayni klasordeki .env dosyasi varsa otomatik yuklenir.
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 3900          # Telegram siniri 4096; pay birakiyoruz


def load_env(path: str | Path = ".env") -> None:
    """Basit .env yukleyici — ek bagimlilik istemiyoruz."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def _credentials() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID tanimli degil. "
            ".env dosyasini olusturun veya ortam degiskeni verin."
        )
    return token, chat


def _post(method: str, fields: dict, retries: int = 3) -> dict:
    token, _ = _credentials()
    url = API.format(token=token, method=method)
    body = urllib.parse.urlencode(fields).encode("utf-8")

    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body)
            with urllib.request.urlopen(req, timeout=30) as r:
                import json
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            last = RuntimeError(f"Telegram HTTP {e.code}: {detail}")
            if e.code == 429:                       # rate limit
                time.sleep(5 * (attempt + 1))
                continue
            break
        except Exception as e:                      # aglayan ag, timeout vb.
            last = e
            time.sleep(2 * (attempt + 1))
    raise last or RuntimeError("Telegram gonderimi basarisiz")


def split_message(text: str, limit: int = MAX_LEN) -> list[str]:
    """Uzun mesaji satir sinirlarindan bolerek parcalar."""
    if len(text) <= limit:
        return [text]
    parts, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > limit:
            parts.append(buf.rstrip())
            buf = ""
        buf += line + "\n"
    if buf.strip():
        parts.append(buf.rstrip())
    return parts


def send(text: str, parse_mode: str = "HTML", silent: bool = False) -> None:
    """Metni gonderir; gerekirse birden fazla mesaja boler."""
    _, chat = _credentials()
    for i, chunk in enumerate(split_message(text)):
        _post("sendMessage", {
            "chat_id": chat,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": "true",
            "disable_notification": "true" if silent else "false",
        })
        if i:
            time.sleep(1)       # ard arda mesajlarda rate limit'e takilmamak icin


def send_document(path: str | Path, caption: str = "") -> None:
    """CSV gibi bir dosyayi ekler. multipart govdeyi elle kuruyoruz."""
    import uuid

    token, chat = _credentials()
    p = Path(path)
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []

    def field(name: str, value: str) -> None:
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8")
        )

    field("chat_id", chat)
    if caption:
        field("caption", caption)
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="document"; '
        f'filename="{p.name}"\r\nContent-Type: text/csv\r\n\r\n'.encode("utf-8")
    )
    parts.append(p.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        API.format(token=token, method="sendDocument"),
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60):
        pass


def test_connection() -> str:
    """Kurulumu dogrulamak icin: bot adini doner."""
    info = _post("getMe", {})
    name = info.get("result", {}).get("username", "?")
    send(f"✅ Baglanti tamam. Bot: <b>@{name}</b>")
    return name


if __name__ == "__main__":
    load_env()
    print("Bot:", test_connection())
