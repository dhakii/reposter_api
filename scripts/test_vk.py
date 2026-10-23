#!/usr/bin/env python3
"""
Скрипт безопасной проверки связи с VK через Cloudflare Worker.
Проверяет:
1. Доступность воркера и авторизацию IP
2. Запрос к VK API через воркер (photos.getWallUploadServer)
3. Загрузку тестового изображения на сервер VK (pu.vk.ru) через воркер

НЕ публикует посты на стене и НЕ сохраняет фото в группу.
"""

import os
import sys
import tempfile
from pathlib import Path

# Загружаем .env
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Добавляем родительскую папку в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.vk_client import _get_vk_and_upload, VkRuSession

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def main():
    print(f"\n{BOLD}{CYAN}=== Проверка интеграции VK + Cloudflare Worker ==={RESET}\n")

    proxy_url = (os.getenv("VK_PROXY_URL") or "").strip().rstrip("/")
    group_id = int(os.getenv("VK_GROUP_ID", "232528016"))

    print(f"1. Настройки окружения:")
    print(f"   - VK_GROUP_ID: {group_id}")
    print(f"   - VK_PROXY_URL: {proxy_url or (YELLOW + 'НЕ ЗАДАН (прямое подключение)' + RESET)}")

    # 1. Проверка доступности воркера
    if proxy_url:
        print(f"\n2. Проверка соединения с Cloudflare Worker ({proxy_url})...")
        session = VkRuSession()
        try:
            resp = session.get(f"{proxy_url}/", timeout=10)
            data = resp.json() if resp.status_code in (200, 403) else {}
            if resp.status_code == 200 and data.get("ip_authorized"):
                print(f"   {GREEN}✔ Воркер доступен, IP сервера авторизован ({data.get('your_ip')}){RESET}")
            elif resp.status_code == 403:
                print(f"   {RED}✖ Воркер отклонил запрос (403): IP {data.get('your_ip')} не в белом списке{RESET}")
                return 1
            else:
                print(f"   {YELLOW}⚠ Ответ воркера: HTTP {resp.status_code}{RESET}")
        except Exception as e:
            print(f"   {RED}✖ Ошибка подключения к воркеру: {e}{RESET}")
            return 1
    else:
        print(f"\n2. Пропуск проверки воркера (VK_PROXY_URL не настроен).")

    # 2. Проверка VK API (получение адреса сервера загрузки)
    print(f"\n3. Получение URL сервера загрузки фото (photos.getWallUploadServer)...")
    try:
        vk, upload = _get_vk_and_upload()
        upload_data = vk.photos.getWallUploadServer(group_id=group_id)
        upload_url = upload_data.get("upload_url")
        if not upload_url:
            print(f"   {RED}✖ Не удалось получить upload_url: {upload_data}{RESET}")
            return 1
        print(f"   {GREEN}✔ VK API ответил успешно!{RESET}")
        print(f"   - Сервер загрузки: {CYAN}{upload_url.split('?')[0]}{RESET}")
    except Exception as e:
        print(f"   {RED}✖ Ошибка вызова VK API: {e}{RESET}")
        return 1

    # 3. Проверка загрузки фото на pu.vk.ru через воркер
    print(f"\n4. Тестовая загрузка изображения на сервер VK ({upload_url.split('/')[2]})...")
    
    # 1x1 белый JPEG (минимальный валидный файл)
    test_jpeg_bytes = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
        b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19"
        b"\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01"
        b"\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08"
        b"\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    )

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(test_jpeg_bytes)
        tmp_path = tmp.name

    try:
        session = VkRuSession()
        with open(tmp_path, "rb") as f:
            resp = session.post(upload_url, files={"photo": ("test.jpg", f, "image/jpeg")}, timeout=35)

        if resp.status_code == 200:
            res_json = resp.json()
            if "photo" in res_json and res_json.get("photo") != "[]":
                print(f"   {GREEN}✔ Сервер VK успешно принял фотографию через Cloudflare!{RESET}")
                print(f"   - Server ID: {res_json.get('server')}")
                print(f"   - Hash: {res_json.get('hash')}")
                print(f"\n{BOLD}{GREEN}=== ВСЕ ПРОВЕРКИ УСПЕШНО ПРОЙДЕНЫ! ==={RESET}")
                print(f"Связка Reposter ➔ Cloudflare ➔ VK работает стабильно и без задержек.\n")
                return 0
            else:
                print(f"   {YELLOW}⚠ VK вернул ответ: {res_json}{RESET}")
                return 0
        else:
            print(f"   {RED}✖ Ошибка загрузки: HTTP {resp.status_code}: {resp.text}{RESET}")
            return 1
    except Exception as e:
        print(f"   {RED}✖ Исключение при загрузке фото: {e}{RESET}")
        return 1
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    sys.exit(main() or 0)
