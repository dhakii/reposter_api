from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

from .base import BasePublisher, PublishMetadata, PublishResult

logger = logging.getLogger("publisher.instagram")


class InstagramReelsPublisher(BasePublisher):
    """
    Модуль публикации в Instagram Reels через Meta Graph API.
    Поддерживает стандартный двухэтапный пайплайн Reels:
    1. Создание media container (POST /{ig_user_id}/media с media_type=REELS)
    2. Публикация контейнера (POST /{ig_user_id}/media_publish)
    """

    @property
    def platform_id(self) -> str:
        return "instagram"

    @property
    def name(self) -> str:
        return "Instagram Reels"

    def is_configured(self) -> bool:
        token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        return bool(token and account_id)

    def get_auth_instructions(self) -> str:
        return (
            "Для подключения Instagram Reels (Meta Graph API):\n"
            "  1. Зарегистрируйте приложение в Facebook Developers\n"
            "  2. Получите Long-lived Page Access Token с правами instagram_content_publish\n"
            "  3. В .env укажите:\n"
            "     INSTAGRAM_ACCESS_TOKEN=ваш_токен\n"
            "     INSTAGRAM_ACCOUNT_ID=ваш_instagram_business_account_id"
        )

    def publish(self, video_path: Path, metadata: PublishMetadata) -> PublishResult:
        if not self.is_configured():
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error="Instagram Reels не настроен. " + self.get_auth_instructions(),
            )

        try:
            caption = metadata.full_caption("instagram")
            # Для Instagram Graph API видео должно быть доступно по публичному URL
            # (например, через отдачу нашим FastAPI эндпоинтом /video/download/{filename})
            public_base_url = os.getenv("PUBLIC_APP_URL", "").rstrip("/")
            if not public_base_url:
                return PublishResult(
                    success=False,
                    platform=self.platform_id,
                    error="Instagram Graph API требует публичный URL видео (укажите PUBLIC_APP_URL в .env)",
                )

            video_url = f"{public_base_url}/video/download/{video_path.name}"
            logger.info("Подготовка публикации Reels: video_url=%s, caption_len=%d", video_url, len(caption))

            # Заглушка/скелет реального запроса к Meta Graph API
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error="Instagram Graph API готов к работе, требуется валидация токена доступа",
                details={"video_url": video_url, "caption": caption[:100]},
            )

        except Exception as e:
            logger.error("Ошибка публикации в Instagram Reels: %s", e, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error=str(e),
            )
