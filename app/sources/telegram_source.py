from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .base import BaseLotSource
from app.video_engine.scraper import fetch_channel_lots

logger = logging.getLogger("source.telegram")


class TelegramChannelSource(BaseLotSource):
    """
    Источник лотов из публичного Telegram-канала аукциона.
    Парсит последние опубликованные картины без необходимости API-ключей.
    """

    def __init__(
        self,
        channel_url: str = "https://t.me/s/marinakhakimova_auction",
        download_dir: Optional[Path] = None,
    ):
        self.channel_url = channel_url
        self.download_dir = download_dir or (Path(__file__).resolve().parent.parent.parent / "output" / "real_lots")

    @property
    def name(self) -> str:
        return "Telegram Channel (@marinakhakimova_auction)"

    def fetch_lots(self, limit: int = 10) -> List[Dict[str, Any]]:
        logger.info("Загрузка свежих лотов из канала %s (лимит=%d)...", self.channel_url, limit)
        try:
            lots = fetch_channel_lots(
                channel_url=self.channel_url,
                max_count=limit,
                download_dir=self.download_dir,
            )
            logger.info("Успешно получено %d лотов из Telegram-канала", len(lots))
            return lots
        except Exception as e:
            logger.error("Ошибка при получении лотов из Telegram-канала: %s", e)
            return []
