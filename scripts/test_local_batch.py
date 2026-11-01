#!/usr/bin/env python3
"""
Скрипт локального тестирования вертикального видео:
- Сразу начинается с картин (мгновенный хук)
- Разделенный крупный текст (Сверху: ЛОТ + Автор, Снизу: Название + Цена + Telegram)
- Текст СТАТИЧЕН (не зумируется и не дрожит, идеальная читаемость)
- Финал на фирменном светлом фоне логотипа (#EFEDEE)
"""

import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from app.video_engine.builder import VideoBatchBuilder

SAMPLES_DIR = ROOT_DIR / "assets" / "samples"

SAMPLE_ARTWORKS = [
    {
        "lot_num": 949,
        "artist": "Татьяна Романова",
        "title": "Ромашковое настроение",
        "price": "15 000 ₽",
        "is_sold": False,
        "image_path": str(SAMPLES_DIR / "sample_art_1.jpg"),
    },
    {
        "lot_num": 948,
        "artist": "Алексей Васильев",
        "title": "Утренний туман на Волге",
        "price": "22 000 ₽",
        "is_sold": False,
        "image_path": str(SAMPLES_DIR / "sample_art_2.jpg"),
    },
    {
        "lot_num": 947,
        "artist": "Елена Смирнова",
        "title": "Пионы в хрустале",
        "price": "18 500 ₽",
        "is_sold": False,
        "image_path": str(SAMPLES_DIR / "sample_art_3.jpg"),
    },
    {
        "lot_num": 946,
        "artist": "Дмитрий Морозов",
        "title": "Старый переулок",
        "price": "14 000 ₽",
        "is_sold": False,
        "image_path": str(SAMPLES_DIR / "sample_art_4.jpg"),
    },
    {
        "lot_num": 945,
        "artist": "Анна Кузнецова",
        "title": "Золотой октябрь",
        "price": "20 000 ₽",
        "is_sold": False,
        "image_path": str(SAMPLES_DIR / "sample_art_5.jpg"),
    },
]


def main():
    print("\n" + "=" * 65)
    print("🎬 [SPLIT TYPOGRAPHY REELS] Крупный статический текст + Светлый финал")
    print("=" * 65 + "\n")

    for art in SAMPLE_ARTWORKS:
        if not os.path.exists(art["image_path"]):
            print(f"❌ Файл не найден: {art['image_path']}")
            return 1

    output_mp4 = ROOT_DIR / "output" / "reels_hybrid_editorial.mp4"
    builder = VideoBatchBuilder()

    print(f"📦 Сборка {len(SAMPLE_ARTWORKS)} лотов...")
    print("🎬 Параметры:")
    print("   - Стиль: ГИБРИДНЫЙ ПРЕМИУМ-КАТАЛОГ")
    print("   - Верх: ЛОТ в красной плашке + Имя автора крупно (Georgia Bold) + черта")
    print("   - Фон: Полупрозрачный блюр из красок картины на галерейном офф-вайте")
    print("   - Низ: Название + СТАРТОВАЯ ЦЕНА + Крупная цена с лучами + Telegram")
    print("   - Полотно: Плавный Ken Burns (+3.5%) с глубокой музейной тенью")
    print("   - Финал (3.0с): Двухфазный переход Dip-to-White (исчезновение в белый -> появление логотипа)\n")

    result = builder.build_batch_reels(
        artworks=SAMPLE_ARTWORKS,
        output_file=str(output_mp4),
        channel_link="@marinakhakimova_auction",
        slide_duration=4.0,
        outro_duration=3.0,
        style_variant="hybrid",
    )

    print("✨ Рендеринг завершен!")
    print(f"   - Видео: {result['video_path']}")
    print(f"   - Обложка: {result['thumbnail_path']}")
    print(f"   - Длительность: {result['duration']} сек")
    print(f"   - Время рендера: {result['render_time_sec']} сек")
    print(f"   - Саундтрек: {result['soundtrack']}")
    print(f"   - Размер: {result['file_size_mb']} MB")
    print("\n" + "=" * 65 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
