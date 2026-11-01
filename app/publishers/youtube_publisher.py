from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from .base import BasePublisher, PublishMetadata, PublishResult

logger = logging.getLogger("publisher.youtube")


class YouTubeShortsPublisher(BasePublisher):
    """
    Полноценный модуль публикации в YouTube Shorts через официальный YouTube Data API v3.
    Поддерживает:
      1. Headless-авторизацию через YOUTUBE_REFRESH_TOKEN в .env (не требует браузера на VPS)
      2. Либо локальный youtube_token.json / client_secret.json
      3. Возобновляемую загрузку (Resumable Upload) для стабильности
      4. Автоматическое форматирование под формат Shorts (#Shorts в названии, вертикальный формат)
    """

    @property
    def platform_id(self) -> str:
        return "youtube"

    @property
    def name(self) -> str:
        return "YouTube Shorts"

    def is_configured(self) -> bool:
        # Проверяем наличие либо прямых токенов в .env, либо файла токенов
        has_env_tokens = bool(
            os.getenv("YOUTUBE_CLIENT_ID")
            and os.getenv("YOUTUBE_CLIENT_SECRET")
            and os.getenv("YOUTUBE_REFRESH_TOKEN")
        )
        token_file = Path(os.getenv("YOUTUBE_TOKEN_FILE", "youtube_token.json"))
        return has_env_tokens or token_file.exists()

    def get_auth_instructions(self) -> str:
        return (
            "Для подключения YouTube Shorts:\n"
            "  1. Создайте проект в Google Cloud Console и включите YouTube Data API v3\n"
            "  2. Создайте OAuth 2.0 Client ID (тип: Desktop App) и скачайте client_secret.json\n"
            "  3. Запустите на своем компьютере скрипт авторизации: python scripts/setup_youtube_auth.py\n"
            "  4. Скрипт выдаст три строки для .env на сервере:\n"
            "     YOUTUBE_CLIENT_ID=...\n"
            "     YOUTUBE_CLIENT_SECRET=...\n"
            "     YOUTUBE_REFRESH_TOKEN=..."
        )

    def _get_credentials(self):
        from google.oauth2.credentials import Credentials

        # 1. Проверяем переменные в .env
        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

        if client_id and client_secret and refresh_token:
            return Credentials(
                None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=["https://www.googleapis.com/auth/youtube.upload"],
            )

        # 2. Проверяем локальный файл youtube_token.json
        token_file = Path(os.getenv("YOUTUBE_TOKEN_FILE", "youtube_token.json"))
        if token_file.exists():
            return Credentials.from_authorized_user_file(
                str(token_file),
                scopes=["https://www.googleapis.com/auth/youtube.upload"],
            )

        raise ValueError("YouTube credentials не найдены. Укажите YOUTUBE_REFRESH_TOKEN в .env")

    def publish(self, video_path: Path, metadata: PublishMetadata) -> PublishResult:
        if not self.is_configured():
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error="YouTube Shorts не настроен. " + self.get_auth_instructions(),
            )

        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from googleapiclient.errors import HttpError
        except ImportError:
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error="Не установлена библиотека google-api-python-client. Выполните: pip install google-api-python-client google-auth-oauthlib",
            )

        try:
            creds = self._get_credentials()
            youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

            # Название видео для Shorts (должно быть до 100 символов, обязательно с тегом #Shorts)
            title = metadata.title.strip()
            if "#Shorts" not in title and "#shorts" not in title:
                title = f"{title} #Shorts"
            if len(title) > 100:
                title = title[:92].strip() + " #Shorts"

            description = metadata.full_caption("youtube")
            tags = [t.lstrip("#") for t in metadata.tags][:20]

            privacy_status = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")

            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": "22",  # People & Blogs
                    "defaultLanguage": "ru",
                },
                "status": {
                    "privacyStatus": privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            logger.info("Загрузка видео в YouTube Shorts: '%s' (файл: %s)...", title, video_path.name)
            media = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                chunksize=-1,
                resumable=True,
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            # Выполняем возобновляемую загрузку
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info("Прогресс загрузки на YouTube: %d%%", int(status.progress() * 100))

            video_id = response.get("id")
            shorts_url = f"https://youtube.com/shorts/{video_id}"
            logger.info("Видео успешно опубликовано в YouTube Shorts! URL: %s", shorts_url)

            return PublishResult(
                success=True,
                platform=self.platform_id,
                post_id=video_id,
                url=shorts_url,
                details=response,
            )

        except Exception as e:
            logger.error("Ошибка при публикации в YouTube Shorts: %s", e, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error=f"Ошибка YouTube API: {str(e)}",
            )
