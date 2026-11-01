#!/usr/bin/env python3
"""
Скрипт рендеринга всех 3 вариантов «Премиум-каталога»:
1. 4A: Красный бейдж (Red Pill Badge)
2. 4B: Плашка с рамкой (Framed Card Badge)
3. 4C: Типографика Sotheby's (Large Centered Price)
"""

import os
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.video_engine.builder import VideoBatchBuilder

SAMPLES_DIR = ROOT_DIR / "assets" / "samples"
OUTPUT_DIR = ROOT_DIR / "output"
ARTIFACTS_DIR = Path(r"C:\Users\dhakii\.gemini\antigravity\brain\0154ee46-4b06-46fb-a88e-063b8ebc2d08")

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

VARIANTS = [
    ("4a", "reels_editorial_4a_red_pill.mp4", "Премиум-каталог: Красный бейдж цены"),
    ("4b", "reels_editorial_4b_framed_badge.mp4", "Премиум-каталог: Плашка с рамкой"),
    ("4c", "reels_editorial_4c_sothebys.mp4", "Премиум-каталог: Sotheby's Типографика"),
]


def main():
    print("\n" + "=" * 70)
    print("🎬 РЕНДЕРИНГ ВСЕХ 3 ВАРИАНТОВ «ПРЕМИУМ-КАТАЛОГА»")
    print("=" * 70 + "\n")

    results = []

    for var_code, out_name, desc in VARIANTS:
        print(f"\n▶️ Сборка варианта [{var_code.upper()}]: {desc}...")
        builder = VideoBatchBuilder()
        out_mp4 = OUTPUT_DIR / out_name

        res = builder.build_batch_reels(
            artworks=SAMPLE_ARTWORKS,
            output_file=str(out_mp4),
            channel_link="@marinakhakimova_auction",
            slide_duration=4.0,
            outro_duration=2.5,
            style_variant=var_code,
        )

        # Копируем превью обложки в артефакты
        if res.get("thumbnail_path") and os.path.exists(res["thumbnail_path"]):
            thumb_src = Path(res["thumbnail_path"])
            thumb_dest = ARTIFACTS_DIR / f"thumb_{var_code}.jpg"
            thumb_dest.write_bytes(thumb_src.read_bytes())
            res["artifact_thumb"] = str(thumb_dest)

        results.append(res)
        print(f"✅ Готово: {out_name} ({res['duration']}s, {res['render_time_sec']}s render, {res['file_size_mb']}MB)")

    print("\n" + "=" * 70)
    print("🎉 ВСЕ 3 РОЛИКА УСПЕШНО СОБРАНЫ!")
    for r in results:
        print(f" - [{r['style_variant'].upper()}] {r['video_path']}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
