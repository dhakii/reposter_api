from __future__ import annotations

import os
import time
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any

from .base import BasePublisher, PublishMetadata, PublishResult

logger = logging.getLogger("publisher.instagram")

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class InstagramReelsPublisher(BasePublisher):
    """
    Полноценный модуль публикации в Instagram Reels через официальный Meta Graph API.
    
    Алгоритм Meta Graph API для Reels:
      1. Регистрация контейнера (POST /{ig_user_id}/media с media_type=REELS)
      2. Опрос статуса обработки видео серверами Meta (GET /{container_id} -> FINISHED)
      3. Публикация контейнера в ленту и Reels (POST /{ig_user_id}/media_publish)
      4. Получение прямой ссылки (permalink) на опубликованный Reels
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
        public_url = os.getenv("PUBLIC_APP_URL")
        return bool(token and account_id and public_url)

    def get_auth_instructions(self) -> str:
        return (
            "Для подключения Instagram Reels (Meta Graph API):\n"
            "  1. Переведите профиль Instagram в 'Профессиональный' (Бизнес или Автор)\n"
            "  2. Свяжите его со страницей Facebook в Meta Business Suite\n"
            "  3. В developers.facebook.com создайте приложение (Тип: Бизнес) и добавьте 'Instagram Graph API'\n"
            "  4. Получите Long-Lived Token с правами: instagram_basic, instagram_content_publish\n"
            "  5. В .env укажите:\n"
            "     INSTAGRAM_ACCESS_TOKEN=ваш_токен_meta\n"
            "     INSTAGRAM_ACCOUNT_ID=ваш_числовой_id_instagram_аккаунта\n"
            "     PUBLIC_APP_URL=http://ip_вашего_vps:8000  # (Meta скачивает видео по публичному URL)"
        )

    def publish(self, video_path: Path, metadata: PublishMetadata) -> PublishResult:
        if not self.is_configured():
            missing = []
            if not os.getenv("INSTAGRAM_ACCESS_TOKEN"):
                missing.append("INSTAGRAM_ACCESS_TOKEN")
            if not os.getenv("INSTAGRAM_ACCOUNT_ID"):
                missing.append("INSTAGRAM_ACCOUNT_ID")
            if not os.getenv("PUBLIC_APP_URL"):
                missing.append("PUBLIC_APP_URL")
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error=f"Instagram не настроен (отсутствуют: {', '.join(missing)} в .env). " + self.get_auth_instructions(),
            )

        token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        public_base_url = os.getenv("PUBLIC_APP_URL", "").rstrip("/")

        # Формируем публичную ссылку на скачивание видео
        video_filename = video_path.name
        video_download_url = f"{public_base_url}/video/download/{video_filename}"

        caption = metadata.full_caption("instagram")
        logger.info("Публикация в Instagram Reels: account_id=%s, video_url=%s", account_id, video_download_url)

        session = requests.Session()
        session.headers.update({"User-Agent": "AuctionReposter/2.0"})

        try:
            # --- ШАГ 1: Создание медиа-контейнера Reels ---
            create_url = f"{GRAPH_API_BASE}/{account_id}/media"
            create_payload = {
                "media_type": "REELS",
                "video_url": video_download_url,
                "caption": caption,
                "share_to_feed": "true",
                "thumb_offset": "0",
                "access_token": token,
            }

            logger.info("Шаг 1: отправка запроса на создание контейнера Reels...")
            resp = session.post(create_url, data=create_payload, timeout=30)
            data = resp.json()

            if "error" in data:
                err_msg = data["error"].get("message", str(data["error"]))
                logger.error("Meta Graph API error (создание контейнера): %s", err_msg)
                return PublishResult(
                    success=False,
                    platform=self.platform_id,
                    error=f"Ошибка создания контейнера Instagram: {err_msg}",
                    details=data,
                )

            container_id = data.get("id")
            if not container_id:
                return PublishResult(
                    success=False,
                    platform=self.platform_id,
                    error="Не получен container_id от Meta Graph API",
                    details=data,
                )

            logger.info("Контейнер создан: container_id=%s. Ожидание обработки видео Meta...", container_id)

            # --- ШАГ 2: Опрос готовности контейнера (Status Polling) ---
            status_url = f"{GRAPH_API_BASE}/{container_id}"
            max_wait_seconds = 180  # 3 минуты максимум
            start_time = time.time()
            status_finished = False

            while time.time() - start_time < max_wait_seconds:
                time.sleep(5)
                st_resp = session.get(status_url, params={"fields": "status_code,status", "access_token": token}, timeout=15)
                st_data = st_resp.json()
                status_code = st_data.get("status_code")

                logger.debug("Статус обработки видео Meta: %s", status_code)

                if status_code == "FINISHED":
                    status_finished = True
                    logger.info("Видео успешно обработано серверами Instagram.")
                    break
                elif status_code == "ERROR":
                    err_details = st_data.get("status", "Unknown processing error")
                    return PublishResult(
                        success=False,
                        platform=self.platform_id,
                        error=f"Ошибка обработки видео в Instagram: {err_details}",
                        details=st_data,
                    )
                elif status_code == "EXPIRED":
                    return PublishResult(
                        success=False,
                        platform=self.platform_id,
                        error="Контейнер видео Instagram истек до публикации.",
                        details=st_data,
                    )

            if not status_finished:
                return PublishResult(
                    success=False,
                    platform=self.platform_id,
                    error="Таймаут ожидания обработки видео в Instagram (более 180 сек).",
                )

            # --- ШАГ 3: Публикация контейнера ---
            publish_url = f"{GRAPH_API_BASE}/{account_id}/media_publish"
            publish_payload = {
                "creation_id": container_id,
                "access_token": token,
            }

            logger.info("Шаг 3: публикация готового контейнера Reels...")
            pub_resp = session.post(publish_url, data=publish_payload, timeout=30)
            pub_data = pub_resp.json()

            if "error" in pub_data:
                err_msg = pub_data["error"].get("message", str(pub_data["error"]))
                logger.error("Meta Graph API error (публикация): %s", err_msg)
                return PublishResult(
                    success=False,
                    platform=self.platform_id,
                    error=f"Ошибка публикации Reels: {err_msg}",
                    details=pub_data,
                )

            media_id = pub_data.get("id")
            logger.info("Reels успешно опубликован! media_id=%s", media_id)

            # --- ШАГ 4: Запрос permalink (прямой ссылки) ---
            permalink = None
            try:
                media_info_url = f"{GRAPH_API_BASE}/{media_id}"
                m_resp = session.get(media_info_url, params={"fields": "permalink", "access_token": token}, timeout=15)
                m_data = m_resp.json()
                permalink = m_data.get("permalink")
            except Exception:
                pass

            final_url = permalink or f"https://www.instagram.com/reel/{media_id}/"

            return PublishResult(
                success=True,
                platform=self.platform_id,
                post_id=media_id,
                url=final_url,
                details={"container_id": container_id, "media_id": media_id, "permalink": permalink},
            )

        except Exception as e:
            logger.error("Непредвиденная ошибка при публикации в Instagram: %s", e, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error=f"Сетевая ошибка или сбой Instagram Graph API: {str(e)}",
            )
