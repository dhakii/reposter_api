from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger("publisher")


@dataclass
class PublishMetadata:
    """Метаданные для публикации видеоролика в соцсети."""
    title: str
    description: str
    channel_handle: str = "@marinakhakimova_auction"
    lot_nums: List[int] = field(default_factory=list)
    tags: List[str] = field(default_factory=lambda: [
        "твояколлекция", "аукцион", "живопись", "искусство", "картины", "shorts", "reels", "клипы"
    ])
    extra: Dict[str, Any] = field(default_factory=dict)

    def full_caption(self, platform_id: str = "generic") -> str:
        """Формирует готовый текст описания с тегами под формат площадки."""
        tag_str = " ".join(f"#{t.lstrip('#')}" for t in self.tags)
        lots_str = f"Лоты: {', '.join(str(n) for n in self.lot_nums)}" if self.lot_nums else ""
        lines = [self.title]
        if self.description and self.description != self.title:
            lines.append(self.description)
        if lots_str:
            lines.append(lots_str)
        lines.append(f"Участие в торгах в Telegram: {self.channel_handle}")
        lines.append("")
        lines.append(tag_str)
        return "\n".join(lines).strip()


@dataclass
class PublishResult:
    """Результат попытки публикации."""
    success: bool
    platform: str
    post_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.success:
            return f"[{self.platform}] OK: id={self.post_id or 'unknown'} url={self.url or 'n/a'}"
        return f"[{self.platform}] FAILED: {self.error}"


class BasePublisher(ABC):
    """
    Базовый абстрактный класс для модулей публикации видео (VK, YouTube, Instagram, TikTok).
    Каждый модуль реализует единый интерфейс.
    """

    @property
    @abstractmethod
    def platform_id(self) -> str:
        """Уникальный идентификатор платформы (vk, youtube, instagram, tiktok)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Человекочитаемое название платформы."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Проверяет, заданы ли все необходимые токены/ключи в окружении."""
        pass

    @abstractmethod
    def get_auth_instructions(self) -> str:
        """Возвращает краткую инструкцию, какие переменные окружения нужны для подключения."""
        pass

    @abstractmethod
    def publish(self, video_path: Path, metadata: PublishMetadata) -> PublishResult:
        """
        Публикует видеофайл на платформу.
        :param video_path: Путь к MP4-файлу на диске
        :param metadata: Заголовок, описание, теги
        :return: PublishResult
        """
        pass
