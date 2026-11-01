from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseLotSource(ABC):
    """
    Базовый интерфейс для источников лотов (Telegram-канал, База данных SQLite аукционного бота, Локальный архив).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Название источника."""
        pass

    @abstractmethod
    def fetch_lots(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Возвращает список словарей с лотами:
        [
            {
                "lot_num": 956,
                "artist": "Имя Фамилия",
                "title": "Название работы",
                "price": 15000,
                "size": "50x70 см",
                "material": "холст, масло",
                "image_path": "/path/to/local/image.jpg",
                "image_url": "https://...",
            },
            ...
        ]
        """
        pass
