from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

from .base import BasePublisher, PublishMetadata, PublishResult

logger = logging.getLogger("publisher.vk")


class VKPublisher(BasePublisher):
    """
    Модуль публикации в VK Клипы и сообщество ВКонтакте.
    """

    @property
    def platform_id(self) -> str:
        return "vk"

    @property
    def name(self) -> str:
        return "VK Клипы / ВКонтакте"

    def is_configured(self) -> bool:
        token = os.getenv("VK_USER_TOKEN") or os.getenv("VK_TOKEN") or os.getenv("VK_ACCESS_TOKEN")
        group_id = os.getenv("VK_GROUP_ID")
        return bool(token and group_id)

    def get_auth_instructions(self) -> str:
        return (
            "Для подключения VK укажите в .env:\n"
            "  VK_USER_TOKEN=ваш_токен_пользователя_с_правами_wall_video\n"
            "  VK_GROUP_ID=числовой_id_группы (без минуса)\n"
            "  VK_PROXY_URL=опционально_cloudflare_worker"
        )

    def publish(self, video_path: Path, metadata: PublishMetadata) -> PublishResult:
        if not self.is_configured():
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error="VK не настроен (отсутствуют VK_USER_TOKEN или VK_GROUP_ID в .env)",
            )

        try:
            from app.vk_client import upload_video_to_vk

            group_id = int(os.getenv("VK_GROUP_ID", "0"))
            caption = metadata.full_caption("vk")

            res = upload_video_to_vk(
                video_path=video_path,
                title=metadata.title,
                description=caption,
                post_to_wall=True,
                group_id=group_id,
            )

            video_id = res.get("video_id")
            owner_id = res.get("owner_id")
            post_id = res.get("post_id")
            direct_link = res.get("direct_link") or (f"https://vk.ru/wall{owner_id}_{post_id}" if post_id else None)

            return PublishResult(
                success=True,
                platform=self.platform_id,
                post_id=str(post_id or video_id),
                url=direct_link,
                details=res,
            )
        except Exception as e:
            logger.error("Ошибка публикации в VK: %s", e, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform_id,
                error=str(e),
            )
