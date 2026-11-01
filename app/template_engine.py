from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("template_engine")

TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "templates" / "social_templates.json"


class SocialTemplateEngine:
    """
    Шаблонизатор текстов и тегов для публикации в соцсети.
    Загружает шаблоны из templates/social_templates.json,
    где пользователь может легко менять тексты и подборки тегов под каждую платформу.
    """

    def __init__(self, template_path: Optional[Path] = None):
        self.template_path = Path(template_path or TEMPLATES_PATH)
        self._templates = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.template_path.exists():
            try:
                return json.loads(self.template_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error("Ошибка чтения файла шаблонов %s: %s", self.template_path, e)
        return {}

    def reload(self):
        """Перечитывает шаблоны с диска без перезапуска приложения."""
        self._templates = self._load()

    def get_template(self, platform: str) -> Dict[str, Any]:
        return self._templates.get(platform.lower(), {})

    def render(
        self,
        platform: str,
        lots: List[Dict[str, Any]],
        channel_handle: str = "@marinakhakimova_auction",
        channel_url: str = "https://t.me/marinakhakimova_auction",
    ) -> Tuple[str, str, List[str]]:
        """
        Формирует (заголовок, полное_описание_с_тегами, список_тегов) для заданной платформы.
        """
        tmpl = self.get_template(platform)
        if not tmpl:
            # Дефолтный fallback, если шаблон не найден
            tmpl = {
                "title": "Аукцион «Твоя Коллекция» — лоты {lot_range}",
                "description": "Подборка картин аукциона. Торги в Telegram: {channel_handle}",
                "tags": ["твояколлекция", "аукцион", "живопись", "картины", "клипы"],
            }

        # 1. Формируем переменные для подстановки
        lot_nums = [l.get("lot_num") for l in lots if l.get("lot_num")]
        if lot_nums:
            if len(lot_nums) > 1:
                lot_range = f"№{min(lot_nums)}..№{max(lot_nums)}"
            else:
                lot_range = f"№{lot_nums[0]}"
        else:
            lot_range = "актуальные лоты"

        parsed_prices = []
        for l in lots:
            try:
                val = int(l.get("price", 0))
                if val > 0:
                    parsed_prices.append(val)
            except (ValueError, TypeError):
                pass
        min_price_str = f"{min(parsed_prices):,}".replace(",", " ") if parsed_prices else "5 000"

        # Человечный список лотов
        lot_lines = []
        for l in lots:
            num = l.get("lot_num")
            artist = l.get("artist") or "Художник"
            title = l.get("title") or "Работа без названия"
            price = l.get("price")
            try:
                p_num = int(price)
                price_str = f" — от {p_num:,} ₽".replace(",", " ")
            except (ValueError, TypeError):
                price_str = f" — от {price} ₽" if price else ""
            num_str = f"№{num} " if num else ""
            lot_lines.append(f"• Лот {num_str}«{title}» ({artist}{price_str})")
        lot_list_str = "\n".join(lot_lines)

        context = {
            "lot_range": lot_range,
            "lot_list": lot_list_str,
            "min_price": min_price_str,
            "channel_handle": channel_handle,
            "channel_url": channel_url,
        }

        # 2. Подставляем в заголовок и описание
        raw_title = tmpl.get("title", "Аукцион «Твоя Коллекция»")
        raw_desc = tmpl.get("description", "")
        tags = tmpl.get("tags", [])

        try:
            rendered_title = raw_title.format(**context)
        except Exception:
            rendered_title = raw_title

        try:
            rendered_desc = raw_desc.format(**context)
        except Exception:
            rendered_desc = raw_desc

        # 3. Формируем хэштеги с учетом правил площадки
        clean_tags = [t.lstrip("#").strip() for t in tags if t.strip()]
        tag_line = " ".join(f"#{t}" for t in clean_tags)

        # Полный текст для соцсети: описание + ссылка + хэштеги
        full_caption = f"{rendered_desc}\n\n{tag_line}".strip()

        return rendered_title, full_caption, clean_tags
