#!/usr/bin/env python3
"""
Скрипт выгрузки реальных картин и описаний лотов из публичного Telegram-канала:
https://t.me/s/marinakhakimova_auction
"""

import os
import sys
import re
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
REAL_ASSETS_DIR = ROOT_DIR / "assets" / "real_lots"
REAL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

CHANNEL_URL = "https://t.me/s/marinakhakimova_auction"

def fetch_channel_html():
    req = urllib.request.Request(
        CHANNEL_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")

def parse_lots(html_content):
    # Split messages by tgme_widget_message_wrap
    raw_messages = re.findall(r'<div class="tgme_widget_message_wrap.*?</div>\s*</div>\s*</div>', html_content, re.DOTALL)
    if not raw_messages:
        raw_messages = html_content.split('class="tgme_widget_message ')

    parsed_lots = []
    for msg in raw_messages:
        # Photo urls
        photo_urls = re.findall(r'background-image:url\([\'"]?(.*?)[\'"]?\)', msg)
        if not photo_urls:
            continue

        # Extract text from tgme_widget_message_text
        text_match = re.search(r'<div class="tgme_widget_message_text[^"]*">(.*?)</div>', msg, re.DOTALL)
        if not text_match:
            continue
        raw_text = text_match.group(1)
        # convert <br> to \n, strip other tags
        clean_text = re.sub(r'<br\s*/?>', '\n', raw_text)
        clean_text = re.sub(r'<.*?>', '', clean_text)
        # unescape html
        import html
        clean_text = html.unescape(clean_text).strip()

        # Parse lot number
        lot_match = re.search(r'(?:лот|аукцион)[^\d]*(\d+)', clean_text, re.IGNORECASE)
        lot_num = int(lot_match.group(1)) if lot_match else None

        # Price
        price_match = re.search(r'(?:старт|цена|ставка)[^\d]*(\d[\d\s]*\d|\d+)\s*(?:₽|руб|р\.?)?', clean_text, re.IGNORECASE)
        if price_match:
            raw_p = price_match.group(1).strip()
            cleaned_p = re.sub(r'\s+', ' ', raw_p)
            price_str = f"{cleaned_p} ₽"
        else:
            alt_price = re.search(r'(\d[\d\s]*\d|\d+)\s*(?:₽|руб)', clean_text)
            if alt_price:
                price_str = f"{re.sub(r'\s+', ' ', alt_price.group(1).strip())} ₽"
            else:
                price_str = "По запросу"

        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]

        artist = None
        title = None

        for line in lines:
            if re.search(r'(?:художник|автор):?\s*(.+)', line, re.IGNORECASE):
                artist = re.search(r'(?:художник|автор):?\s*(.+)', line, re.IGNORECASE).group(1).strip()
            elif re.search(r'(?:название|работа):?\s*(.+)', line, re.IGNORECASE):
                title = re.search(r'(?:название|работа):?\s*(.+)', line, re.IGNORECASE).group(1).strip()

        if not artist and len(lines) > 1:
            for l in lines:
                if '«' in l and '»' in l:
                    title = l
                    break

        parsed_lots.append({
            "lot_num": lot_num,
            "text": clean_text,
            "lines": lines,
            "photo_urls": photo_urls,
            "artist": artist,
            "title": title,
            "price": price_str,
        })

    return parsed_lots

def main():
    print("📡 Подключение к Telegram-каналу @marinakhakimova_auction...")
    html_content = fetch_channel_html()
    lots = parse_lots(html_content)
    print(f"📦 Найдено сообщений с картинами: {len(lots)}")

    for idx, l in enumerate(lots[-8:], 1):
        print(f"\n--- [Пост {idx}] Лот: {l['lot_num']} | Фото: {len(l['photo_urls'])} ---")
        print("Текст первых 3 строк:")
        for line in l['lines'][:3]:
            print(f"  • {line}")
        print(f"Цена: {l['price']}")
        print(f"Фото URL: {l['photo_urls'][0]}")

if __name__ == "__main__":
    main()
