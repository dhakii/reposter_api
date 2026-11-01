from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .base import BasePublisher, PublishMetadata, PublishResult
from .vk_publisher import VKPublisher
from .youtube_publisher import YouTubeShortsPublisher
from .instagram_publisher import InstagramReelsPublisher
from .tiktok_publisher import TikTokPublisher

logger = logging.getLogger("publisher.manager")


class PublisherManager:
    """
    Диспетчер публикации во все поддерживаемые платформы (VK, YouTube Shorts, Instagram Reels, TikTok).
    Позволяет добавлять новые платформы по единому интерфейсу BasePublisher без изменения основного кода.
    """

    def __init__(self, publishers: Optional[List[BasePublisher]] = None):
        self._publishers: Dict[str, BasePublisher] = {}
        # Регистрируем встроенные издатели
        default_list = publishers or [
            VKPublisher(),
            YouTubeShortsPublisher(),
            InstagramReelsPublisher(),
            TikTokPublisher(),
        ]
        for p in default_list:
            self.register(p)

    def register(self, publisher: BasePublisher):
        """Регистрирует новый модуль публикации."""
        self._publishers[publisher.platform_id.lower()] = publisher
        logger.debug("Зарегистрирован модуль публикации: %s (%s)", publisher.name, publisher.platform_id)

    def get(self, platform_id: str) -> Optional[BasePublisher]:
        return self._publishers.get(platform_id.lower())

    def get_all(self) -> List[BasePublisher]:
        return list(self._publishers.values())

    def get_configured(self) -> List[BasePublisher]:
        return [p for p in self._publishers.values() if p.is_configured()]

    def status(self) -> Dict[str, dict]:
        """Возвращает статус готовности всех зарегистрированных платформ."""
        res = {}
        for pid, p in self._publishers.items():
            res[pid] = {
                "name": p.name,
                "platform_id": p.platform_id,
                "configured": p.is_configured(),
                "auth_instructions": p.get_auth_instructions() if not p.is_configured() else "OK",
            }
        return res

    def publish_all(
        self,
        video_path: Path,
        metadata: PublishMetadata,
        target_platforms: Optional[List[str]] = None,
        skip_unconfigured: bool = True,
    ) -> Dict[str, PublishResult]:
        """
        Публикует видео на целевые платформы.
        :param video_path: Путь к готовому ролику MP4
        :param metadata: Метаданные (название, описание, хэштеги)
        :param target_platforms: Список ID платформ (например ['vk', 'youtube']). Если None, публикует во все сконфигурированные.
        :param skip_unconfigured: Не бросать ошибки на ненастроенные платформы, если целевые не заданы явно.
        :return: Словарь с результатами {platform_id: PublishResult}
        """
        results: Dict[str, PublishResult] = {}
        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(f"Видеофайл для публикации не найден: {video_path}")

        # Определяем список платформ для отправки
        if target_platforms:
            targets = [p.lower() for p in target_platforms]
        else:
            if skip_unconfigured:
                targets = [p.platform_id for p in self.get_configured()]
            else:
                targets = list(self._publishers.keys())

        if not targets:
            logger.warning("Нет доступных или сконфигурированных платформ для публикации.")
            return results

        logger.info("Запуск публикации видео '%s' на платформы: %s", video_path.name, targets)

        for pid in targets:
            pub = self.get(pid)
            if not pub:
                results[pid] = PublishResult(
                    success=False,
                    platform=pid,
                    error=f"Неизвестная платформа '{pid}'. Зарегистрированы: {list(self._publishers.keys())}",
                )
                continue

            if not pub.is_configured() and skip_unconfigured and not target_platforms:
                logger.info("Пропуск платформы %s (не настроена в .env)", pub.name)
                continue

            logger.info("Публикация в %s...", pub.name)
            res = pub.publish(video_path, metadata)
            results[pid] = res
            if res.success:
                logger.info("Успешно опубликовано в %s! ID=%s URL=%s", pub.name, res.post_id, res.url)
            else:
                logger.warning("Не удалось опубликовать в %s: %s", pub.name, res.error)

        return results
