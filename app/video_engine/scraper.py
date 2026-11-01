# app/video_engine/scraper.py
"""
Модуль автоматического парсинга актуальных лотов и картин
из публичного Telegram-канала аукциона: https://t.me/s/marinakhakimova_auction
"""

import os
import re
import html
import logging
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

CHANNEL_DEFAULT_URL = "https://t.me/s/marinakhakimova_auction"


def clean_artist_name(name: str) -> str:
    if not name:
        return "Неизвестный автор"
    name = name.strip()
    parts = name.split()
    # Если формат "Романова Татьяна" -> "Татьяна Романова"
    if len(parts) == 2 and parts[0].endswith("а") and parts[1].endswith("а"):
        return f"{parts[1]} {parts[0]}"
    return name


def clean_title(title: str) -> str:
    if not title:
        return "Без названия"
    title = html.unescape(title).strip()
    title = re.sub(r"^[,\s\"'«»]+", "", title)
    title = re.sub(r"[,\s\"'«»]+$", "", title)
    if " по мотивам" in title:
        title = title.split(" по мотивам")[0].strip()
    return title


def download_photo(url: str, dest_path: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            dest_path.write_bytes(resp.read())
            return True
    except Exception as e:
        logger.error("Failed to download image from %s: %s", url, e)
        return False


def fetch_channel_lots(
    channel_url: str = CHANNEL_DEFAULT_URL,
    max_count: int = 5,
    download_dir: Optional[Path] = None,
    only_active: bool = False,
) -> List[Dict[str, Any]]:
    """
    Выгружает посты из публичного веб-интерфейса канала Telegram,
    парсит метаданные лотов и скачивает их фото.
    """
    logger.info("Fetching public posts from %s...", channel_url)
    req = urllib.request.Request(channel_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html_content = resp.read().decode("utf-8")
    except Exception as e:
        logger.error("Failed to fetch Telegram channel HTML: %s", e)
        return []

    message_blocks = re.findall(
        r'<div class="tgme_widget_message [^"]*" data-post="([^"]+)"(.*?)<div class="tgme_widget_message_footer',
        html_content,
        re.DOTALL
    )

    lots = []
    for post_id, block in message_blocks:
        photo_m = re.search(r"background-image:url\(['\"]?(https://cdn\d*\.telesco\.pe/file/[^'\"]+)['\"]?\)", block)
        if not photo_m:
            continue
        photo_url = photo_m.group(1)

        text_m = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
        if not text_m:
            continue

        raw_text = text_m.group(1)
        clean_text = re.sub(r'<br\s*/?>', '\n', raw_text)
        clean_text = re.sub(r'<.*?>', '', clean_text)
        clean_text = html.unescape(clean_text).strip()

        lot_num_m = re.search(r"(?:аукцион|лот)[^\d]*№?\s*(\d+)", clean_text, re.IGNORECASE)
        if not lot_num_m:
            continue
        lot_num = int(lot_num_m.group(1))

        # Title
        title_m = re.search(r"(?:название работы|название):?\s*([^\n]+)", clean_text, re.IGNORECASE)
        title = clean_title(title_m.group(1)) if title_m else "Без названия"

        # Artist
        artist_m = re.search(r"(?:автор|художник):?\s*([^\n]+)", clean_text, re.IGNORECASE)
        artist = clean_artist_name(artist_m.group(1)) if artist_m else "Художник аукциона"

        # Price
        price_m = re.search(r"(?:текущая ставка|старт|цена|ставка)\s*:?\s*(\d[\d\s]*\d|\d+)\s*(?:₽|руб|р\.?)?", clean_text, re.IGNORECASE)
        if price_m:
            price = f"{re.sub(r'\s+', ' ', price_m.group(1).strip())} ₽"
        else:
            price = "10 000 ₽"

        is_sold = bool(re.search(r"(?:завершен|продан|лот завершен)", clean_text, re.IGNORECASE))

        if only_active and is_sold:
            continue

        lots.append({
            "post_id": post_id,
            "lot_num": lot_num,
            "title": title,
            "artist": artist,
            "price": price,
            "is_sold": is_sold,
            "photo_url": photo_url,
        })

    # Выбираем нужное количество последних лотов
    if only_active:
        selected = [l for l in lots if not l["is_sold"]][-max_count:]
    else:
        # Сначала пробуем активные
        actives = [l for l in lots if not l["is_sold"]]
        if len(actives) >= max_count:
            selected = actives[-max_count:]
        else:
            selected = lots[-max_count:]

    # Если передан download_dir — скачиваем фото
    if download_dir:
        download_dir.mkdir(parents=True, exist_ok=True)
        for l in selected:
            dest = download_dir / f"lot_{l['lot_num']}.jpg"
            if not dest.exists() or dest.stat().st_size < 1000:
                download_photo(l["photo_url"], dest)
            l["image_path"] = str(dest)

    return selected
