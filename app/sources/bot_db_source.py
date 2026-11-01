from __future__ import annotations

import os
import json
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .base import BaseLotSource

logger = logging.getLogger("source.bot_db")


class AuctionBotDBSource(BaseLotSource):
    """
    Источник лотов напрямую из базы данных SQLite основного аукционного бота (auction-bot).
    Позволяет извлекать тысячи исторических лотов, когда сервис крутится на одном VPS с ботом.
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        env_path = os.getenv("AUCTION_DB_PATH") or os.getenv("DB_PATH")
        self.db_path = Path(db_path or env_path or "/root/auction-bot/auction_bot.db")

    @property
    def name(self) -> str:
        return f"Auction Bot SQLite DB ({self.db_path.name})"

    def is_available(self) -> bool:
        return self.db_path.exists() and self.db_path.is_file()

    def fetch_lots(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.is_available():
            logger.debug("База данных бота по пути %s не найдена.", self.db_path)
            return []

        logger.info("Чтение лотов из базы данных SQLite: %s", self.db_path)
        lots = []
        try:
            with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT auction_id, title, author_name, start_price, current_price,
                           size, material, photos, description, status
                    FROM auctions
                    WHERE (photos IS NOT NULL AND photos != '')
                    ORDER BY auction_id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
                for row in rows:
                    price = row["current_price"] if (row["current_price"] and row["current_price"] > 0) else row["start_price"]
                    # photos может быть JSON-списком или строкой
                    photos_raw = row["photos"] or ""
                    photo_val = None
                    try:
                        p_list = json.loads(photos_raw)
                        if isinstance(p_list, list) and p_list:
                            photo_val = p_list[0]
                        elif isinstance(p_list, str):
                            photo_val = p_list
                    except Exception:
                        photo_val = photos_raw.split(",")[0].strip()

                    lots.append({
                        "lot_num": row["auction_id"],
                        "artist": row["author_name"] or "Неизвестный художник",
                        "title": row["title"] or f"Лот №{row['auction_id']}",
                        "price": price or 0,
                        "size": row["size"] or "",
                        "material": row["material"] or "",
                        "photo_ref": photo_val,
                        "description": row["description"] or "",
                        "source": "auction_db",
                    })
            logger.info("Из базы данных аукциона извлечено %d архивных лотов", len(lots))
            return lots
        except Exception as e:
            logger.error("Ошибка чтения базы данных аукциона: %s", e)
            return []
