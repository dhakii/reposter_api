#!/usr/bin/env python3
"""
Скрипт первичной авторизации YouTube Data API на локальном компьютере:
1. Запрашивает путь к client_secret.json (или читает его из корня проекта)
2. Открывает браузер для входа в Google/YouTube аккаунт
3. Получает вечный Refresh Token
4. Выводит готовые строки для вставки в .env на VPS:
     YOUTUBE_CLIENT_ID=...
     YOUTUBE_CLIENT_SECRET=...
     YOUTUBE_REFRESH_TOKEN=...
"""

import os
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    print("=" * 70)
    print("  МАСТЕР АВТОРИЗАЦИИ YOUTUBE SHORTS (Google OAuth 2.0)")
    print("=" * 70)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("\nОШИБКА: Не установлены библиотеки Google OAuth.")
        print("Выполните: pip install google-auth-oauthlib google-api-python-client")
        return 1

    # Ищем client_secret.json
    secret_file = None
    possible_names = ["client_secret.json", "client_secrets.json"]
    for name in possible_names:
        p = ROOT_DIR / name
        if p.exists():
            secret_file = p
            break

    if not secret_file:
        user_input = input("\nВведите путь к скачанному client_secret.json (или перетащите файл в консоль): ").strip(' "\'')
        if user_input and Path(user_input).exists():
            secret_file = Path(user_input)
        else:
            print("\nФайл не найден. Скачайте client_secret.json из Google Cloud Console:")
            print("1. Зайдите в https://console.cloud.google.com/apis/credentials")
            print("2. Создайте OAuth 2.0 Client ID (тип: Desktop App / Приложение для ПК)")
            print("3. Скачайте JSON и положите в папку проекта под именем client_secret.json")
            return 1

    print(f"\n[+] Найден файл ключей: {secret_file.name}")
    print("[*] Запуск локального веб-сервера для подтверждения в браузере...")

    try:
        with open(secret_file, "r", encoding="utf-8") as f:
            secret_data = json.load(f)
        
        info = secret_data.get("installed") or secret_data.get("web") or {}
        client_id = info.get("client_id", "")
        client_secret = info.get("client_secret", "")

        flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

        refresh_token = creds.refresh_token
        if not refresh_token:
            print("\nВНИМАНИЕ: Google не вернул refresh_token (возможно, аккаунт уже был авторизован ранее).")
            print("Чтобы принудительно получить refresh_token, удалите доступ приложения в https://myaccount.google.com/permissions и запустите скрипт заново.")
            return 1

        # Сохраняем локальный токен-файл
        token_out = ROOT_DIR / "youtube_token.json"
        token_out.write_text(creds.to_json(), encoding="utf-8")

        print("\n" + "=" * 70)
        print("  УСПЕХ! АВТОРИЗАЦИЯ YOUTUBE ЗАВЕРШЕНА")
        print("=" * 70)
        print("\nСкопируйте следующие 3 строки в ваш файл .env (на сервере VPS):")
        print("-" * 70)
        print(f"YOUTUBE_CLIENT_ID={client_id}")
        print(f"YOUTUBE_CLIENT_SECRET={client_secret}")
        print(f"YOUTUBE_REFRESH_TOKEN={refresh_token}")
        print("-" * 70)
        print("\nГотово! Модуль YouTube Shorts настроен.")
        return 0

    except Exception as e:
        print(f"\nОшибка при авторизации: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
