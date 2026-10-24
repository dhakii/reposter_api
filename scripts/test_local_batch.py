#!/usr/bin/env python3
"""
Скрипт локального тестирования генерации пакетного Reels-видео.
Полное соответствие эталонной спецификации DESIGN_SYSTEM.md.
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
        "image_path": str(SAMPLES_DIR / "sample_art_1.jpg"),
    },
    {
        "lot_num": 948,
        "artist": "Алексей Васильев",
        "title": "Утренний туман на Волге",
        "price": "22 000 ₽",
        "image_path": str(SAMPLES_DIR / "sample_art_2.jpg"),
    },
    {
        "lot_num": 947,
        "artist": "Елена Смирнова",
        "title": "Пионы в хрустале",
        "price": "18 500 ₽",
        "image_path": str(SAMPLES_DIR / "sample_art_3.jpg"),
    },
    {
        "lot_num": 946,
        "artist": "Дмитрий Морозов",
        "title": "Старый переулок",
        "price": "14 000 ₽",
        "image_path": str(SAMPLES_DIR / "sample_art_4.jpg"),
    },
    {
        "lot_num": 945,
        "artist": "Анна Кузнецова",
        "title": "Золотой октябрь",
        "price": "20 000 ₽",
        "image_path": str(SAMPLES_DIR / "sample_art_5.jpg"),
    },
]


def main():
    print("\n" + "=" * 65)
    print("💎 [DESIGN_SYSTEM.md] Эталонная сборка вертикальных Reels (25.0s)")
    print("=" * 65 + "\n")

    for art in SAMPLE_ARTWORKS:
        if not os.path.exists(art["image_path"]):
            print(f"❌ Файл изображения не найден: {art['image_path']}")
            return 1

    output_mp4 = ROOT_DIR / "output" / "batch_reels_design_system.mp4"
    builder = VideoBatchBuilder()

    print(f"📦 Сборка подборки из {len(SAMPLE_ARTWORKS)} лотов...")
    print("🎬 Токены и параметры:")
    print("   - Спецификация: DESIGN_SYSTEM.md")
    print("   - Разрешение: 1080x1920 (9:16)")
    print("   - Хронометраж: 01_intro (2.5с) + 5 лотов (по 4.0с) + 07_outro (2.5с) = 25.0 сек")
    print("   - Динамический стек: Y_start = round((1920 - H_total) / 2) - 10")
    print("   - Ken Burns: синусоидальный наезд s(p) = 1.0 + 0.045 * (1 - cos(pi*p)) / 2")
    print("   - Liquid Glass: 135° стеклянный градиент, 1.5px фаска, Backdrop Blur r=30, Saturation 1.3x")
    print("   - Outro: бейдж @marinakhakimova_auction + кнопка «Перейти в аукцион →»")
    print("   - Звук: FreeToUse EBU R128 (-14 LUFS) с затуханием 2.0с\n")

    result = builder.build_batch_reels(
        artworks=SAMPLE_ARTWORKS,
        output_file=str(output_mp4),
        batch_title="5 картин на аукционе сейчас",
        channel_link="@marinakhakimova_auction",
        slide_duration=4.0,
        intro_duration=2.5,
        outro_duration=2.5,
    )

    print("✨ Рендеринг завершен успешно!")
    print(f"   - Видео: {result['video_path']}")
    print(f"   - Обложка: {result['thumbnail_path']}")
    print(f"   - Длительность: {result['duration']} сек")
    print(f"   - Время рендера: {result['render_time_sec']} сек")
    print(f"   - Саундтрек: {result['soundtrack']}")
    print(f"   - Размер файла: {result['file_size_mb']} MB")
    print("\n" + "=" * 65 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
