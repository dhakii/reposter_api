from __future__ import annotations

import os
import sys
import time
import logging
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.sources.telegram_source import TelegramChannelSource
from app.sources.pool import LotPool
from app.publishers.manager import PublisherManager
from app.publishers.base import PublishMetadata, PublishResult
from app.video_engine.builder import VideoBatchBuilder

logger = logging.getLogger("orchestrator")


class VideoDigestOrchestrator:
    """
    Модульный оркестратор пайплайна видео-дайджестов:
    1. Источники: скачивает свежие лоты из канала и сохраняет в постоянный архив.
    2. Выборка: берет свежие лоты, а если их не хватает — плавно добирает из архива старых картин.
    3. Рендеринг: собирает вертикальный ролик в стиле Hybrid Editorial с Dip-to-White и фоновой музыкой.
    4. Публикация: отправляет через PublisherManager во все настроенные соцсети (VK Клипы, YouTube Shorts, Instagram Reels, TikTok).
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        archive_path: Optional[Path] = None,
    ):
        root_dir = Path(__file__).resolve().parent.parent
        self.output_dir = Path(output_dir or root_dir / "output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.pool = LotPool(archive_path=archive_path)
        self.publishers = PublisherManager()
        self.builder = VideoBatchBuilder()
        self.channel_source = TelegramChannelSource(
            download_dir=self.output_dir / "real_lots"
        )

    def sync_sources(self, limit: int = 15) -> int:
        """Синхронизирует свежие посты из Telegram-канала и пополняет пул/архив лотов."""
        logger.info("Синхронизация свежих лотов из канала...")
        fresh_lots = self.channel_source.fetch_lots(limit=limit)
        new_count = self.pool.register_lots(fresh_lots)
        return new_count

    def run(
        self,
        count: int = 5,
        publish: bool = True,
        force: bool = False,
        allow_fallback: bool = True,
        target_platforms: Optional[List[str]] = None,
        channel_handle: str = "@marinakhakimova_auction",
        style_variant: str = "hybrid",
    ) -> Dict[str, Any]:
        """
        Запускает полный цикл сборки и публикации.
        """
        logger.info("=== Запуск модульного пайплайна видео-дайджеста ===")

        # 1. Синхронизируем последние лоты из канала
        try:
            self.sync_sources(limit=max(15, count * 2))
        except Exception as e:
            logger.warning("Синхронизация с Telegram завершилась с ошибкой: %s (продолжаем с архивными лотами)", e)

        # 2. Выбираем лоты (свежие + умный fallback на архивные)
        lots, strategy = self.pool.get_lots_for_digest(
            count=count,
            allow_archive_fallback=allow_fallback,
        )

        if not lots:
            logger.error("Нет доступных лотов для создания видеоролика.")
            return {"status": "error", "message": "No lots available"}

        lot_nums = [l.get("lot_num") for l in lots]
        logger.info("Выбраны лоты: %s (стратегия: %s)", lot_nums, strategy)

        # 3. Генерируем видеоролик
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        video_filename = f"digest_{timestamp}.mp4"
        video_path = self.output_dir / video_filename

        logger.info("Рендеринг видео: %s", video_path)
        build_res = self.builder.build_batch_reels(
            artworks=lots,
            output_file=str(video_path),
            channel_link=channel_handle,
            slide_duration=4.0,
            outro_duration=3.0,
            style_variant=style_variant,
        )

        logger.info(
            "Видео успешно собрано: %s (длительность: %.1f с, размер: %.2f МБ)",
            video_filename,
            build_res.get("duration", 0),
            build_res.get("file_size_mb", 0),
        )

        # Помечаем лоты в пуле как показанные
        self.pool.mark_featured([l.get("lot_num") for l in lots if l.get("lot_num")])

        # 4. Формируем метаданные публикации
        lot_range = f"№{lot_nums[0]}..№{lot_nums[-1]}" if len(lot_nums) > 1 else f"№{lot_nums[0]}"
        metadata = PublishMetadata(
            title=f"Аукцион «Твоя Коллекция» — лоты {lot_range}",
            description="Подборка картин аукциона живописи «Твоя Коллекция». Участвуйте в торгах в Telegram!",
            channel_handle=channel_handle,
            lot_nums=[n for n in lot_nums if isinstance(n, int)],
            tags=["твояколлекция", "аукцион", "живопись", "картины", "клипы", "shorts", "reels"],
        )

        # 5. Публикация
        publish_results = {}
        if publish:
            logger.info("Запуск публикации через модульные publisher-ы...")
            publish_results = self.publishers.publish_all(
                video_path=video_path,
                metadata=metadata,
                target_platforms=target_platforms,
                skip_unconfigured=True,
            )

        summary = {
            "status": "success",
            "video_path": str(video_path),
            "video_filename": video_filename,
            "duration": build_res.get("duration"),
            "file_size_mb": build_res.get("file_size_mb"),
            "strategy": strategy,
            "lot_nums": lot_nums,
            "publish_results": {pid: str(r) for pid, r in publish_results.items()},
        }
        logger.info("=== Пайплайн завершен: %s ===", summary)
        return summary


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Модульный оркестратор видео-дайджестов аукциона")
    parser.add_argument("--count", type=int, default=5, help="Количество лотов для ролика (по умолчанию 5)")
    parser.add_argument("--publish", action="store_true", help="Опубликовать в настроенные соцсети")
    parser.add_argument("--platforms", type=str, default="", help="Список платформ через запятую (например: vk,youtube)")
    parser.add_argument("--no-fallback", action="store_true", help="Запретить fallback на старые лоты из архива")
    parser.add_argument("--force", action="store_true", help="Принудительный запуск")
    parser.add_argument("--status", action="store_true", help="Показать статус модулей и статистику архива")
    args = parser.parse_args()

    orchestrator = VideoDigestOrchestrator()

    if args.status:
        print("\n--- СТАТУС ПЛАТФОРМ ПУБЛИКАЦИИ ---")
        for pid, pdata in orchestrator.publishers.status().items():
            status_text = "READY" if pdata["configured"] else "NOT CONFIGURED"
            print(f"  [{pdata['platform_id'].upper()}] {pdata['name']}: {status_text}")
        print("\n--- СТАТИСТИКА АРХИВА ЛОТОВ ---")
        for k, v in orchestrator.pool.stats().items():
            print(f"  {k}: {v}")
        print()
        return 0

    target_platforms = [p.strip() for p in args.platforms.split(",") if p.strip()] if args.platforms else None

    res = orchestrator.run(
        count=args.count,
        publish=args.publish,
        force=args.force,
        allow_fallback=not args.no_fallback,
        target_platforms=target_platforms,
    )

    return 0 if res.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
