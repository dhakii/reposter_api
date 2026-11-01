import re
import sys
import html
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

with open('temp_channel.html', encoding='utf-8') as f:
    html_content = f.read()

# Pattern for message blocks
message_blocks = re.findall(r'<div class="tgme_widget_message [^"]*" data-post="([^"]+)"(.*?)<div class="tgme_widget_message_footer', html_content, re.DOTALL)
print(f"Found {len(message_blocks)} message blocks")

parsed_lots = []
for post_id, block in message_blocks:
    # Photo url
    photo_match = re.search(r"background-image:url\(['\"]?(https://cdn\d*\.telesco\.pe/file/[^'\"]+)['\"]?\)", block)
    if not photo_match:
        continue
    photo_url = photo_match.group(1)

    # Text
    text_match = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
    if not text_match:
        continue
    raw_text = text_match.group(1)
    clean_text = re.sub(r'<br\s*/?>', '\n', raw_text)
    clean_text = re.sub(r'<.*?>', '', clean_text)
    clean_text = html.unescape(clean_text).strip()

    # Extract fields
    lot_num_m = re.search(r"(?:аукцион|лот)[^\d]*№?\s*(\d+)", clean_text, re.IGNORECASE)
    lot_num = int(lot_num_m.group(1)) if lot_num_m else None

    # Title
    title_m = re.search(r"(?:название работы|название):?\s*([^\n]+)", clean_text, re.IGNORECASE)
    title = title_m.group(1).strip() if title_m else None

    # Artist
    artist_m = re.search(r"(?:автор|художник):?\s*([^\n]+)", clean_text, re.IGNORECASE)
    artist = artist_m.group(1).strip() if artist_m else None

    # Price / start / current
    price_m = re.search(r"(?:старт|цена|текущая ставка|ставка|старт:)\s*:?\s*(\d[\d\s]*\d|\d+)\s*(?:₽|руб|р\.?)?", clean_text, re.IGNORECASE)
    if price_m:
        price = f"{re.sub(r'\s+', ' ', price_m.group(1).strip())} ₽"
    else:
        price = "По запросу"

    is_sold = bool(re.search(r"(?:завершен|продан|лот завершен)", clean_text, re.IGNORECASE))

    parsed_lots.append({
        "post_id": post_id,
        "lot_num": lot_num,
        "title": title,
        "artist": artist,
        "price": price,
        "is_sold": is_sold,
        "photo_url": photo_url,
        "raw_text": clean_text
    })

print(f"\nExtracted {len(parsed_lots)} real artwork lots:")
for idx, p in enumerate(parsed_lots, 1):
    print(f"{idx}. Post: {p['post_id']} | Лот: {p['lot_num']} | Автор: {p['artist']} | Название: {p['title']} | Цена: {p['price']} | Завершен: {p['is_sold']}")
