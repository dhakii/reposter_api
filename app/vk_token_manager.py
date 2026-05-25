# app/vk_token_manager.py
import os
import json
import time
import threading
from pathlib import Path
import requests

VK_CLIENT_ID   = os.getenv("VK_CLIENT_ID")
VK_DEVICE_ID   = os.getenv("VK_DEVICE_ID")
VK_REFRESH     = os.getenv("VK_REFRESH_TOKEN")
CACHE_PATH     = Path(os.getenv("VK_TOKEN_CACHE", "/tmp/vk_token.json"))

_REFRESH_URL = "https://id.vk.ru/oauth2/auth"

class VKTokenManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._access_token = None
        self._refresh_token = VK_REFRESH
        self._expires_at = 0
        self._load_cache()

    def _load_cache(self):
        try:
            if CACHE_PATH.exists():
                data = json.loads(CACHE_PATH.read_text())
                self._access_token = data.get("access_token") or None
                self._refresh_token = data.get("refresh_token") or self._refresh_token
                self._expires_at = data.get("expires_at") or 0
        except Exception:
            pass

    def _save_cache(self):
        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(json.dumps({
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "expires_at": self._expires_at,
            }, ensure_ascii=False, indent=2))
            try:
                os.chmod(CACHE_PATH, 0o600)
            except Exception:
                pass
        except Exception:
            pass

    def _refresh(self):
        if not (VK_CLIENT_ID and VK_DEVICE_ID and self._refresh_token):
            raise RuntimeError("VK token refresh: missing VK_CLIENT_ID / VK_DEVICE_ID / VK_REFRESH_TOKEN")

        resp = requests.post(_REFRESH_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": VK_CLIENT_ID,
            "device_id": VK_DEVICE_ID,
        }, timeout=20)
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"VK token refresh failed: {data}")

        self._access_token = data["access_token"]
        # VK часто выдаёт новый refresh_token — берём его, иначе оставляем старый
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        expires_in = int(data.get("expires_in", 3600) or 3600)
        # небольшой буфер, чтобы не ловить 5 ошибку прямо на границе
        self._expires_at = int(time.time()) + max(60, expires_in - 60)
        self._save_cache()

    def get_access_token(self) -> str:
        with self._lock:
            now = time.time()
            if not self._access_token or now >= self._expires_at:
                self._refresh()
            return self._access_token

    def force_refresh(self) -> str:
        with self._lock:
            self._refresh()
            return self._access_token

# Глобальный менеджер
manager = VKTokenManager()
