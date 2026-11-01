#!/usr/bin/env python3
"""
Скрипт полной автоматической сборки видеоролика на РЕАЛЬНЫХ картинах
из Telegram-канала @marinakhakimova_auction:
1. Выгрузка постов прямо из канала
2. Скачивание фотографий картин в assets/real_lots/
3. Очистка и нормализация названий, авторов и цен
4. Сборка видеоролика в утвержденном стиле (Премиум-каталог, Dip-to-White, безопасные отступы)
5. Экспорт раскадровки для просмотра
"""

import os
import sys
import re
import html
import time
import urllib.request
from pathlib import Path
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.video_engine.builder import VideoBatchBuilder

REAL_ASSETS_DIR = ROOT_DIR / "assets" / "real_lots"
REAL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR = Path(r"C:\Users\dhakii\.gemini\antigravity\brain\0154ee46-4b06-46fb-a88e-063b8ebc2d08")

CHANNEL_URL = "https://t.me/s/marinakhakimova_auction"


def download_file(url: str, dest_path: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            dest_path.write_bytes(data)
            return True
    except Exception as e:
        print(f"❌ Ошибка скачивания {url}: {e}")
        return False


def clean_artist_name(name: str) -> str:
    if not name:
        return "Неизвестный автор"
    name = name.strip()
    # If "Фамилия Имя" -> "Имя Фамилия"
    parts = name.split()
    if len(parts) == 2 and parts[0].endswith("а") and parts[1].endswith("а"):
        # e.g. Романова Татьяна -> Татьяна Романова, Колесникова Ирина -> Ирина Колесникова
        return f"{parts[1]} {parts[0]}"
    return name


def clean_title(title: str) -> str:
    if not title:
        return "Без названия"
    # Remove leading/trailing quotes, commas, html entities
    title = html.unescape(title).strip()
    title = re.sub(r"^[,\s\"'«»]+", "", title)
    title = re.sub(r"[,\s\"'«»]+$", "", title)
    # Remove excessive suffixes like "по мотивам..." if too long
    if " по мотивам" in title:
        title = title.split(" по мотивам")[0].strip()
    return title


def get_real_channel_lots():
    print(f"📡 Загрузка данных из Telegram-канала {CHANNEL_URL}...")
    req = urllib.request.Request(CHANNEL_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html_content = resp.read().decode("utf-8")

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
        # Look for "Текущая ставка: X ₽" or "Старт: X ₽"
        price_m = re.search(r"(?:текущая ставка|старт|цена|ставка)\s*:?\s*(\d[\d\s]*\d|\d+)\s*(?:₽|руб|р\.?)?", clean_text, re.IGNORECASE)
        if price_m:
            price = f"{re.sub(r'\s+', ' ', price_m.group(1).strip())} ₽"
        else:
            price = "10 000 ₽"

        is_sold = bool(re.search(r"(?:завершен|продан|лот завершен)", clean_text, re.IGNORECASE))

        lots.append({
            "post_id": post_id,
            "lot_num": lot_num,
            "title": title,
            "artist": artist,
            "price": price,
            "is_sold": is_sold,
            "photo_url": photo_url,
        })

    return lots


def main():
    print("\n" + "=" * 70)
    print("🎨 ВЫГРУЗКА РЕАЛЬНЫХ КАРТИН ИЗ TELEGRAM И ГЕНЕРАЦИЯ ВИДЕО")
    print("=" * 70 + "\n")

    lots = get_real_channel_lots()
    print(f"📦 Всего распознано лотов с картинами: {len(lots)}")

    # Prefer active lots or the latest 5 lots
    active_lots = [l for l in lots if not l["is_sold"]]
    if len(active_lots) >= 4:
        selected_lots = active_lots[-5:]
    else:
        selected_lots = lots[-5:]

    print(f"\nВыбрано {len(selected_lots)} актуальных лотов для сборки видео:")
    artworks_for_builder = []

    for idx, lot in enumerate(selected_lots, 1):
        lot_img_path = REAL_ASSETS_DIR / f"real_lot_{lot['lot_num']}.jpg"
        print(f"  {idx}. [Лот №{lot['lot_num']}] {lot['artist']} — «{lot['title']}» ({lot['price']})")

        if not lot_img_path.exists() or lot_img_path.stat().st_size < 1000:
            print(f"     ⬇️ Скачивание фото: {lot['photo_url'][:60]}...")
            download_file(lot["photo_url"], lot_img_path)

        artworks_for_builder.append({
            "lot_num": lot["lot_num"],
            "artist": lot["artist"],
            "title": lot["title"],
            "price": lot["price"],
            "is_sold": lot["is_sold"],
            "image_path": str(lot_img_path),
        })

    # Render video
    output_mp4 = OUTPUT_DIR / "real_channel_auction_reels.mp4"
    builder = VideoBatchBuilder()

    print("\n🎬 Запуск рендеринга видео в утвержденном стиле «Премиум-каталог»...")
    print("   - Мгновенный хук с 0.0 секунды")
    print("   - Полупрозрачный адаптивный блюр-фон из красок каждого полотна")
    print("   - Верхняя плашка: [ АУКЦИОН • ЛОТ №... ] + Автор + Черта")
    print("   - Нижний блок: Название + СТАРТОВАЯ ЦЕНА с лучами + Telegram")
    print("   - Безопасные отступы (>100px) без наплыва на текст")
    print("   - Двухфазный переход Dip-to-White в брендовый светлый финал с логотипом")

    res = builder.build_batch_reels(
        artworks=artworks_for_builder,
        output_file=str(output_mp4),
        channel_link="@marinakhakimova_auction",
        slide_duration=4.0,
        outro_duration=3.0,
        style_variant="hybrid",
    )

    print("\n🎉 ВИДЕОРОЛИК НА РЕАЛЬНЫХ КАРТИНАХ УСПЕШНО СОБРАН!")
    print(f"   - Видео: {res['video_path']}")
    print(f"   - Длительность: {res['duration']} сек")
    print(f"   - Время рендера: {res['render_time_sec']} сек")
    print(f"   - Размер файла: {res['file_size_mb']} MB")

    # Generate keyframe screenshots for user review
    print("\n📸 Создание раскадровки для демонстрации...")
    import subprocess
    art_dir = ARTIFACTS_DIR
    frames = []
    for i, lot in enumerate(artworks_for_builder, 1):
        t = (i - 1) * 4.0 + 2.0
        fn = f"real_frame_{i:02d}_lot_{lot['lot_num']}.png"
        out_f = art_dir / fn
        cmd = ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(output_mp4), "-vframes", "1", "-q:v", "2", str(out_f)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        frames.append((fn, f"Лот {lot['lot_num']}: {lot['artist']}"))

    # Outro frame
    outro_fn = "real_frame_99_outro.png"
    cmd = ["ffmpeg", "-y", "-ss", f"{res['duration'] - 1.0:.2f}", "-i", str(output_mp4), "-vframes", "1", "-q:v", "2", str(art_dir / outro_fn)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    frames.append((outro_fn, "Финал @marinakhakimova_auction"))

    # Make storyboard 3x2
    cols, rows = 3, 2
    card_w, card_h = 360, 640
    pad_x, pad_y = 20, 20
    total_w = cols * card_w + (cols + 1) * pad_x
    total_h = rows * card_h + (rows + 1) * pad_y + 80

    canvas = Image.new("RGB", (total_w, total_h), (24, 26, 32))
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(canvas)
    font_title = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 26)
    font_lbl = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 16)

    draw.text((pad_x, 22), "РЕАЛЬНЫЕ КАРТИНЫ ИЗ КАНАЛА @marinakhakimova_auction (1080x1920)", fill=(255, 255, 255), font=font_title)

    for idx, (fn, lbl) in enumerate(frames):
        c = idx % cols
        r = idx // cols
        x = pad_x + c * (card_w + pad_x)
        y = 70 + pad_y + r * (card_h + pad_y)

        im = Image.open(art_dir / fn).convert("RGB")
        im_thumb = im.resize((card_w, card_h), Image.Resampling.LANCZOS)
        canvas.paste(im_thumb, (x, y))
        draw.text((x + 10, y + card_h - 32), lbl, fill=(255, 255, 255), font=font_lbl)

    storyboard_path = art_dir / "real_channel_video_storyboard.jpg"
    canvas.save(storyboard_path, quality=93)
    print(f"✨ Раскадровка сохранена: {storyboard_path}")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
