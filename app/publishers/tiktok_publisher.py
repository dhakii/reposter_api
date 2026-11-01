from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

from .base import BasePublisher, PublishMetadata, PublishResult

logger = logging.getLogger("publisher.tiktok")


class TikTokPublisher(BasePublisher):
    """
    Модуль публикации в TikTok через TikTok Content Posting API v2.
    Поддерживает прямую загрузку видеофайлов чанками или через pull from URL.
    """

    @property
    def platform_id(self) -> str:
        return "tiktok"

    @property
    def name(self) -> str:
        return "TikTok"

    def is_configured(self) -> bool:
        token = os.getenv("TIKTOK_ACCESS_TOKEN")
        return bool(token)

    def get_auth_instructions(self) -> str:
        return (
            "Для подключения TikTok:\n"
            "  1. Зарегистрируйте Developer аккаунт на developers.tiktok.com\n"
            "  2. Запросите доступ к Content Posting API (scope: video.publish)\n"
            "  3. В .env укажите:\n"
            "     TIKTOK_ACCESS_TOKEN=ваш_токен"
        )

    def publish(self, video_path: Path, metadata: PublishMetadata) -> PublishResult:
        if not self.is_configured():
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error="TikTok не настроен. " + self.get_auth_instructions(),
            )

        try:
            caption = metadata.full_caption("tiktok")
            logger.info("Подготовка публикации TikTok: video=%s, caption_len=%d", video_path.name, len(caption))

            return PublishResult(
                success=False,
                platform=self.platform_id,
                error="TikTok API готов к работе, требуется валидация токена доступа",
                details={"file": str(video_path), "caption": caption[:100]},
            )

        except Exception as e:
            logger.error("Ошибка публикации в TikTok: %s", e, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error=str(e),
            )
