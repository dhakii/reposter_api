#!/usr/bin/env python3
"""
Скрипт автоматического запуска дайджеста по расписанию (CLI / Task Scheduler / Cron):
1. Проверяет новые посты в Telegram-канале @marinakhakimova_auction
2. Если есть свежие лоты (или передан флаг --force), собирает видеоролик
3. Сохраняет историю в output/digest_history.json, чтобы не спамить дубликатами
4. При наличии флага --publish и настроенных VK-токенов загружает в VK Клипы / на стену
"""

import os
import sys
import json
import time
import argparse
import logging
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

from app.video_engine.scraper import fetch_channel_lots
from app.video_engine.builder import VideoBatchBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("auto_digest")

OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = OUTPUT_DIR / "digest_history.json"


def load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_history(data: dict):
    HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Автоматический генератор видео-дайджеста аукциона")
    parser.add_argument("--count", type=int, default=5, help="Количество лотов для ролика (по умолчанию 5)")
    parser.add_argument("--channel", type=str, default="https://t.me/s/marinakhakimova_auction", help="URL канала")
    parser.add_argument("--handle", type=str, default="@marinakhakimova_auction", help="Ссылка для текста")
    parser.add_argument("--publish", action="store_true", help="Автоматически опубликовать в VK после сборки")
    parser.add_argument("--force", action="store_true", help="Принудительно собрать видео, даже если лоты не менялись")
    args = parser.parse_args()

    logger.info("=== Запуск проверки авто-дайджеста ===")
    managed_dir = OUTPUT_DIR / "real_lots"
    lots = fetch_channel_lots(
        channel_url=args.channel,
        max_count=args.count,
        download_dir=managed_dir,
    )

    if not lots:
        logger.warning("Не удалось получить лоты из канала.")
        return 1

    lot_nums = [l["lot_num"] for l in lots]
    logger.info("Получено %d лотов: %s", len(lots), lot_nums)

    history = load_history()
    last_lot_nums = history.get("last_lot_nums", [])

    if not args.force and lot_nums == last_lot_nums:
        logger.info("Лоты не изменились с прошлой сборки (%s). Пропуск генерации.", lot_nums)
        return 0

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_mp4 = OUTPUT_DIR / f"auto_digest_{timestamp}.mp4"

    logger.info("Рендеринг нового видеоролика: %s", out_mp4.name)
    builder = VideoBatchBuilder()
    res = builder.build_batch_reels(
        artworks=lots,
        output_file=str(out_mp4),
        channel_link=args.handle,
        slide_duration=4.0,
        outro_duration=3.0,
        style_variant="hybrid",
    )

    logger.info(
        "Ролик готов: %s (%.1f сек, размер %.2f MB)",
        out_mp4.name, res["duration"], res["file_size_mb"]
    )

    # Обновляем историю
    history["last_lot_nums"] = lot_nums
    history["last_video"] = str(out_mp4)
    history["last_timestamp"] = timestamp
    save_history(history)

    # Опциональная публикация в VK
    if args.publish:
        token = os.getenv("VK_USER_TOKEN") or os.getenv("VK_TOKEN")
        group_id = os.getenv("VK_GROUP_ID")
        if token and group_id:
            try:
                from app.vk_client import upload_video_to_vk
                logger.info("Публикация ролика в группу VK -%s...", group_id)
                pub_res = upload_video_to_vk(
                    video_path=out_mp4,
                    title=f"Аукцион «Твоя Коллекция» — лоты {lot_nums[0]}..{lot_nums[-1]}",
                    description=f"Актуальная подборка картин аукциона «Твоя Коллекция».\nУчаствуйте в торгах в Telegram: {args.handle}\n#твояколлекция #аукцион #клипы",
                    post_to_wall=True,
                    group_id=int(group_id),
                )
                logger.info("Успешно опубликовано в VK! video_id=%s, post_id=%s", pub_res.get("video_id"), pub_res.get("post_id"))
            except Exception as e:
                logger.error("Ошибка авто-публикации в VK: %s", e)
        else:
            logger.warning("Флаг --publish указан, но VK_USER_TOKEN или VK_GROUP_ID не заданы в .env")

    logger.info("=== Авто-дайджест успешно завершен ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
