#!/usr/bin/env python3
"""
Скрипт проверки готовности всех модулей публикации и шаблонизатора (VK, YouTube, Instagram):
1. Проверяет наличие ключей в .env
2. Тестирует генерацию текстов и индивидуальных тегов под каждую сеть
3. Показывает точный статус готовности
"""

import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.publishers.manager import PublisherManager
from app.template_engine import SocialTemplateEngine


def main():
    print("=" * 70)
    print("  ПРОВЕРКА ГОТОВНОСТИ ПЛАТФОРМ ПУБЛИКАЦИИ И ШАБЛОНОВ")
    print("=" * 70)

    # 1. Проверяем шаблонизатор
    engine = SocialTemplateEngine()
    dummy_lots = [
        {"lot_num": 956, "artist": "Иван Иванов", "title": "Утренний туман", "price": 14000},
        {"lot_num": 957, "artist": "Анна Смирнова", "title": "Цветы у окна", "price": 22000},
    ]

    print("\n--- ТЕСТ ГЕНЕРАЦИИ ТЕКСТОВ И ТЕГОВ ---")
    for platform in ["vk", "youtube", "instagram"]:
        title, caption, tags = engine.render(
            platform=platform,
            lots=dummy_lots,
            channel_handle="@marinakhakimova_auction",
            channel_url="https://t.me/marinakhakimova_auction",
        )
        print(f"\n[{platform.upper()}] Заголовок: {title}")
        print(f"[{platform.upper()}] Теги ({len(tags)} шт.): {' '.join('#' + t for t in tags[:6])}...")
        print(f"[{platform.upper()}] Описание (первые 120 симв.):\n{caption[:120]}...\n" + "-" * 50)

    # 2. Проверяем статус модулей
    manager = PublisherManager()
    print("\n--- СТАТУС ПОДКЛЮЧЕНИЯ ПЛОЩАДОК В .ENV ---")
    status = manager.status()
    for pid, p in status.items():
        state_icon = "[OK] ГОТОВ" if p["configured"] else "[X] НЕ НАСТРОЕН"
        print(f"\n{state_icon} -> {p['name']} (ID: {pid})")
        if not p["configured"]:
            print("  Инструкция по настройке:")
            for line in p["auth_instructions"].split("\n"):
                print(f"    {line}")

    print("\n" + "=" * 70)
    print("Файл шаблонов для ручного редактирования текстов и тегов:")
    print(f"  {ROOT_DIR / 'templates' / 'social_templates.json'}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
