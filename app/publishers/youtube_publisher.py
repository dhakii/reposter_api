from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

from .base import BasePublisher, PublishMetadata, PublishResult

logger = logging.getLogger("publisher.youtube")


class YouTubeShortsPublisher(BasePublisher):
    """
    Модуль публикации в YouTube Shorts через YouTube Data API v3.
    """

    @property
    def platform_id(self) -> str:
        return "youtube"

    @property
    def name(self) -> str:
        return "YouTube Shorts"

    def is_configured(self) -> bool:
        # Для загрузки видео в YouTube требуется OAuth2 refresh token или client_secrets.json
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE")
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
        return bool((client_secret and Path(client_secret).exists()) or refresh_token)

    def get_auth_instructions(self) -> str:
        return (
            "Для подключения YouTube Shorts:\n"
            "  1. В Google Cloud Console включите YouTube Data API v3\n"
            "  2. Скачайте client_secret.json в папку проекта\n"
            "  3. В .env укажите:\n"
            "     YOUTUBE_CLIENT_SECRETS_FILE=./client_secret.json\n"
            "     # или YOUTUBE_REFRESH_TOKEN=...\n"
            "  4. Установите библиотеку: pip install google-api-python-client google-auth-oauthlib"
        )

    def publish(self, video_path: Path, metadata: PublishMetadata) -> PublishResult:
        if not self.is_configured():
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error="YouTube Shorts не настроен. " + self.get_auth_instructions(),
            )

        try:
            # Проверяем наличие библиотеки google-api-python-client
            try:
                from googleapiclient.discovery import build
                from googleapiclient.http import MediaFileUpload
            except ImportError:
                return PublishResult(
                    success=False,
                    platform=self.platform_id,
                    error="Пакет google-api-python-client не установлен. Выполните: pip install google-api-python-client google-auth-oauthlib",
                )

            # Формируем заголовок с обязательным тегом #Shorts
            title = metadata.title
            if "#Shorts" not in title and "#shorts" not in title:
                title = f"{title} #Shorts"
            if len(title) > 100:
                title = title[:92] + " #Shorts"

            description = metadata.full_caption("youtube")

            # Здесь размещается реальный вызов YouTube Data API
            # В данном шаблоне подготовлена вся структура запроса:
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": metadata.tags + ["Shorts", "YouTubeShorts"],
                    "categoryId": "22",  # People & Blogs
                },
                "status": {
                    "privacyStatus": os.getenv("YOUTUBE_PRIVACY_STATUS", "public"),
                    "selfDeclaredMadeForKids": False,
                },
            }

            logger.info("Подготовка к отправке Shorts на YouTube: %s", title)
            # В продакшене авторизация и upload.execute()
            # Пока выводим структурированный статус готовности модуля
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error="YouTube API credentials обнаружены, но требуется первичная генерация OAuth token (run scripts/auth_youtube.py)",
                details={"body": body},
            )

        except Exception as e:
            logger.error("Ошибка публикации в YouTube Shorts: %s", e, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error=str(e),
            )
