from __future__ import annotations

import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger("source.pool")

DEFAULT_ARCHIVE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "lot_archive.json"


class LotPool:
    """
    Менеджер пула лотов и долгосрочного архива.
    Решает ключевую задачу:
    - Если в Telegram есть свежие лоты — собирает ролик из них.
    - Если свежих лотов недостаточно или новых постов нет — плавно добирает
      недостающие картины из богатого архива старых проверенных лотов по принципу
      ротации (выбирает те, что крутились реже всего и дольше всего назад).
    """

    def __init__(self, archive_path: Optional[Path] = None):
        self.archive_path = Path(archive_path or DEFAULT_ARCHIVE_FILE)
        self.archive_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.archive_path.exists():
            try:
                return json.loads(self.archive_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Не удалось прочитать архив лотов %s: %s", self.archive_path, e)
        return {"lots": {}}

    def _save(self):
        try:
            self.archive_path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error("Ошибка сохранения архива лотов: %s", e)

    def register_lots(self, lots: List[Dict[str, Any]]) -> int:
        """
        Добавляет новые лоты в архив или обновляет существующие,
        сохраняя историю показов (featured_count).
        Возвращает количество добавленных абсолютно новых лотов.
        """
        store = self._data.setdefault("lots", {})
        new_count = 0
        now_ts = time.strftime("%Y-%m-%d %H:%M:%S")

        for lot in lots:
            key = str(lot.get("lot_num") or lot.get("id") or lot.get("title"))
            if not key or key == "None":
                continue

            # Проверяем, существует ли локальный файл картинки
            img_p = lot.get("image_path")
            has_valid_img = bool(img_p and Path(img_p).exists() and Path(img_p).stat().st_size > 1000)

            if key not in store:
                store[key] = {
                    "lot_num": lot.get("lot_num"),
                    "artist": lot.get("artist") or "Художник аукциона",
                    "title": lot.get("title") or f"Лот №{key}",
                    "price": lot.get("price") or 0,
                    "size": lot.get("size") or "",
                    "material": lot.get("material") or "",
                    "image_path": str(img_p) if img_p else None,
                    "image_url": lot.get("image_url"),
                    "first_seen": now_ts,
                    "featured_count": 0,
                    "last_featured": None,
                }
                new_count += 1
            else:
                # Обновляем метаданные и путь к картинке, если появился качественный файл
                if has_valid_img:
                    store[key]["image_path"] = str(img_p)
                new_price = lot.get("price")
                if new_price not in (None, "", 0):
                    store[key]["price"] = new_price
                if lot.get("artist"):
                    store[key]["artist"] = lot.get("artist")
                if lot.get("title"):
                    store[key]["title"] = lot.get("title")

        if new_count > 0 or lots:
            self._save()

        logger.info("Архив обновлен: всего в базе %d лотов (новых добавлено: %d)", len(store), new_count)
        return new_count

    def get_lots_for_digest(
        self,
        count: int = 5,
        allow_archive_fallback: bool = True,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Выбирает 'count' лучших лотов для очередного видеоролика:
        1. Сначала отбирает свежие лоты (featured_count == 0).
        2. Если их не хватает и разрешен fallback — добирает из архива
           по алгоритму наименее используемых (LRU: featured_count ASC, last_featured ASC).
        """
        store = self._data.get("lots", {})
        candidates = []

        # Фильтруем лоты, у которых есть существующий локальный файл картинки
        for key, item in store.items():
            img_path = item.get("image_path")
            if img_path and Path(img_path).exists():
                candidates.append(item)

        if not candidates:
            logger.warning("В архиве нет доступных лотов с загруженными изображениями.")
            return [], "empty"

        # 1. Ищем совершенно свежие лоты
        fresh = [c for c in candidates if c.get("featured_count", 0) == 0]
        # Сортируем свежие по номеру лота от старшего к младшему (самые последние публикации)
        def _safe_lot_num(x):
            try:
                return int(x.get("lot_num") or 0)
            except (ValueError, TypeError):
                return 0

        fresh.sort(key=_safe_lot_num, reverse=True)

        selected: List[Dict[str, Any]] = []
        strategy = "fresh"

        if len(fresh) >= count:
            selected = fresh[:count]
            strategy = "fresh"
        else:
            selected.extend(fresh)
            if allow_archive_fallback:
                needed = count - len(selected)
                # Берем архивные лоты, исключая уже выбранные
                selected_keys = {str(s.get("lot_num")) for s in selected}
                archive_pool = [c for c in candidates if str(c.get("lot_num")) not in selected_keys]

                # Сортируем архив по: 1) наименьшему количеству показов, 2) времени последнего показа
                def sort_key(item):
                    f_count = item.get("featured_count", 0)
                    last_f = item.get("last_featured") or "1970-01-01"
                    return (f_count, last_f)

                archive_pool.sort(key=sort_key)
                picked_from_archive = archive_pool[:needed]
                selected.extend(picked_from_archive)

                if fresh:
                    strategy = f"mixed ({len(fresh)} fresh + {len(picked_from_archive)} archive)"
                else:
                    strategy = f"archive_rotation ({len(picked_from_archive)} lots)"

        logger.info(
            "Отобрано %d лотов для видеоролика (стратегия: %s): %s",
            len(selected),
            strategy,
            [s.get("lot_num") for s in selected],
        )
        return selected, strategy

    def mark_featured(self, lot_nums: List[int | str]):
        """Помечает лоты как использованные в видеоролике."""
        store = self._data.get("lots", {})
        now_ts = time.strftime("%Y-%m-%d %H:%M:%S")

        for num in lot_nums:
            k = str(num)
            if k in store:
                store[k]["featured_count"] = store[k].get("featured_count", 0) + 1
                store[k]["last_featured"] = now_ts

        self._save()
        logger.info("Помечено как показанные %d лотов: %s", len(lot_nums), lot_nums)

    def stats(self) -> Dict[str, Any]:
        """Возвращает статистику архива."""
        store = self._data.get("lots", {})
        total = len(store)
        with_images = sum(1 for c in store.values() if c.get("image_path") and Path(c["image_path"]).exists())
        never_featured = sum(1 for c in store.values() if c.get("featured_count", 0) == 0)
        return {
            "total_lots_in_archive": total,
            "lots_with_local_images": with_images,
            "fresh_unfeatured_lots": never_featured,
            "archive_path": str(self.archive_path),
        }
