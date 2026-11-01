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
from app.cascade import CascadeCampaignManager
from app.template_engine import SocialTemplateEngine

logger = logging.getLogger("orchestrator")


class VideoDigestOrchestrator:
    """
    Модульный оркестратор пайплайна видео-дайджестов:
    1. Источники: скачивает свежие лоты из канала и сохраняет в постоянный архив.
    2. Выборка: берет свежие лоты, а если их не хватает — плавно добирает из архива старых картин.
    3. Рендеринг: собирает вертикальный ролик в стиле Hybrid Editorial с Dip-to-White и фоновой музыкой.
    4. Шаблоны: форматирует индивидуальные заголовки, описания и теги под каждую платформу (VK, IG, YT).
    5. Каскадная публикация (1 ролик на 3 дня):
       - День 1 (18:00): Сборка ролика -> Публикация в VK Клипы
       - День 2 (18:00): Тот же ролик -> Публикация в Instagram Reels
       - День 3 (18:00): Тот же ролик -> Публикация в YouTube Shorts
       - День 4 (18:00): Новый цикл (новый ролик -> VK)
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
        self.cascade = CascadeCampaignManager()
        self.template_engine = SocialTemplateEngine()
        self.channel_source = TelegramChannelSource(
            download_dir=self.output_dir / "real_lots"
        )

    def sync_sources(self, limit: int = 15) -> int:
        """Синхронизирует свежие посты из Telegram-канала и пополняет пул/архив лотов."""
        logger.info("Синхронизация свежих лотов из канала...")
        fresh_lots = self.channel_source.fetch_lots(limit=limit)
        new_count = self.pool.register_lots(fresh_lots)
        return new_count

    def generate_video(
        self,
        count: int = 5,
        allow_fallback: bool = True,
        channel_handle: str = "@marinakhakimova_auction",
        style_variant: str = "hybrid",
    ) -> Dict[str, Any]:
        """Синхронизирует лоты, выбирает картины и рендерит видеоролик."""
        try:
            self.sync_sources(limit=max(15, count * 2))
        except Exception as e:
            logger.warning("Синхронизация с Telegram завершилась с ошибкой: %s (продолжаем с архивными лотами)", e)

        lots, strategy = self.pool.get_lots_for_digest(
            count=count,
            allow_archive_fallback=allow_fallback,
        )

        if not lots:
            raise RuntimeError("В пуле и архиве нет доступных лотов для генерации видео.")

        lot_nums = [l.get("lot_num") for l in lots]
        logger.info("Отобраны лоты: %s (стратегия: %s)", lot_nums, strategy)

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

        # Помечаем лоты в пуле как использованные
        self.pool.mark_featured([l.get("lot_num") for l in lots if l.get("lot_num")])

        return {
            "video_path": video_path,
            "video_filename": video_filename,
            "duration": build_res.get("duration"),
            "file_size_mb": build_res.get("file_size_mb"),
            "lot_nums": lot_nums,
            "lots": lots,
            "strategy": strategy,
        }

    def run_cascade_tick(
        self,
        count: int = 5,
        force_new: bool = False,
        channel_handle: Optional[str] = None,
        channel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ежедневный вызов по таймеру в 18:00:
        1. Если идет активная 3-дневная кампания — берет текущее видео и отправляет
           на площадку сегодняшнего дня (День 2: Инста, День 3: YouTube) с шаблоном под эту соцсеть.
        2. Если кампания завершена (День 4+) или force_new=True — рендерит НОВЫЙ ролик
           и публикует его в День 1 (VK).
        """
        logger.info("=== Ежедневный каскадный шаг публикации (18:00) ===")

        handle = channel_handle or os.getenv("TELEGRAM_CHANNEL_HANDLE", "@marinakhakimova_auction")
        url = channel_url or os.getenv("TELEGRAM_CHANNEL_URL", "https://t.me/marinakhakimova_auction")

        pending_action = None if force_new else self.cascade.get_pending_action()

        if pending_action:
            # --- Продолжение текущей кампании (День 2 или День 3) ---
            day = pending_action["day"]
            platform = pending_action["platform"]
            video_path = pending_action["video_path"]
            lot_nums = pending_action["lot_nums"]
            lots = pending_action.get("lots", [])

            logger.info("Кампания продолжается: День %d -> Публикация на платформу '%s'", day, platform)

            # Формируем индивидуальные заголовок, описание и теги через шаблонизатор
            title, caption, tags = self.template_engine.render(
                platform=platform,
                lots=lots,
                channel_handle=handle,
                channel_url=url,
            )

            metadata = PublishMetadata(
                title=title,
                description=title,
                custom_caption=caption,
                channel_handle=handle,
                lot_nums=[n for n in lot_nums if isinstance(n, int)],
                tags=tags,
            )

            pub = self.publishers.get(platform)
            if not pub:
                result = PublishResult(success=False, platform=platform, error=f"Издатель {platform} не найден")
            elif not pub.is_configured():
                result = PublishResult(success=False, platform=platform, error=f"Издатель {platform} не настроен в .env")
            else:
                result = pub.publish(video_path, metadata)

            self.cascade.record_step_result(pending_action["step_index"], result)
            return {
                "status": "success",
                "mode": "cascade_step",
                "campaign_id": pending_action["campaign_id"],
                "day": day,
                "platform": platform,
                "published": result.success,
                "result": str(result),
            }

        # --- Старт нового 3-дневного цикла (День 1) ---
        logger.info("Активной кампании нет или запрошен новый ролик. Запуск Дня 1 нового цикла!")
        video_data = self.generate_video(count=count, channel_handle=handle)
        video_path = video_data["video_path"]
        lot_nums = video_data["lot_nums"]
        lots = video_data["lots"]

        chain = self.cascade.get_configured_chain()
        first_platform = chain[0]
        logger.info("День 1: публикация первого шага в '%s'...", first_platform)

        title, caption, tags = self.template_engine.render(
            platform=first_platform,
            lots=lots,
            channel_handle=handle,
            channel_url=url,
        )

        metadata = PublishMetadata(
            title=title,
            description=title,
            custom_caption=caption,
            channel_handle=handle,
            lot_nums=[n for n in lot_nums if isinstance(n, int)],
            tags=tags,
        )

        pub = self.publishers.get(first_platform)
        if pub and pub.is_configured():
            first_res = pub.publish(video_path, metadata)
        else:
            first_res = PublishResult(
                success=False,
                platform=first_platform,
                error=f"Платформа {first_platform} не настроена в .env",
            )

        campaign = self.cascade.start_new_campaign(
            video_path=video_path,
            video_filename=video_data["video_filename"],
            lot_nums=lot_nums,
            lots=lots,
            first_platform_result=first_res,
        )

        return {
            "status": "success",
            "mode": "new_campaign_started",
            "campaign_id": campaign["campaign_id"],
            "video": video_data["video_filename"],
            "day_1_platform": first_platform,
            "day_1_result": str(first_res),
            "next_step": f"День 2 -> {chain[1]}" if len(chain) > 1 else "Нет следующих шагов",
        }


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

    parser = argparse.ArgumentParser(description="Модульный оркестратор каскадных видео-дайджестов (1 ролик на 3 дня)")
    parser.add_argument("--cascade-tick", action="store_true", help="Ежедневный запуск каскада в 18:00 (рекомендуется для systemd)")
    parser.add_argument("--force-new", action="store_true", help="Принудительно начать новый 3-дневный цикл с новым видео")
    parser.add_argument("--count", type=int, default=5, help="Количество лотов для ролика (по умолчанию 5)")
    parser.add_argument("--status", action="store_true", help="Показать статус модулей, состояние каскада и статистику архива")
    args = parser.parse_args()

    orchestrator = VideoDigestOrchestrator()

    if args.status:
        print("\n--- СОСТОЯНИЕ КАСКАДА (1 РОЛИК НА 3 ДНЯ) ---")
        state = orchestrator.cascade.load_state()
        if state:
            print(f"  Активная кампания: {state.get('campaign_id')} (Статус: {state.get('status')})")
            print(f"  Видео: {state.get('video_filename')}")
            print(f"  Цепочка: {' -> '.join(state.get('chain', []))}")
            for step in state.get("steps", []):
                print(f"    День {step['day']} [{step['platform'].upper()}]: {step['status']} ({step.get('published_at') or 'ожидает'})")
        else:
            print("  Нет активной кампании (при следующем запуске создастся новый ролик).")

        print("\n--- СТАТУС ПЛАТФОРМ ПУБЛИКАЦИИ ---")
        for pid, pdata in orchestrator.publishers.status().items():
            status_text = "READY" if pdata["configured"] else "NOT CONFIGURED"
            print(f"  [{pdata['platform_id'].upper()}] {pdata['name']}: {status_text}")

        print("\n--- СТАТИСТИКА АРХИВА ЛОТОВ ---")
        for k, v in orchestrator.pool.stats().items():
            print(f"  {k}: {v}")
        print()
        return 0

    res = orchestrator.run_cascade_tick(
        count=args.count,
        force_new=args.force_new,
    )

    return 0 if res.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
