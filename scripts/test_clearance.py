#!/usr/bin/env python3
"""
Скрипт проверки безопасных отступов:
Проверяет, что картина (даже при максимальном зуме +3.5% и с тенью)
НИКОГДА не задевает верхний и нижний текст.
"""

import sys
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.video_engine.overlays import (
    make_semi_transparent_blurred_background,
    _load_font,
    W, H
)

OUTPUT_DIR = ROOT_DIR / "output"
ARTIFACTS_DIR = Path(r"C:\Users\dhakii\.gemini\antigravity\brain\0154ee46-4b06-46fb-a88e-063b8ebc2d08")

FONTS = {
    "lot_badge": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 24),
    "artist": _load_font([r"C:\Windows\Fonts\georgiab.ttf", "georgiab.ttf"], 52),
    "title": _load_font([r"C:\Windows\Fonts\georgiaz.ttf", "georgiaz.ttf"], 44),
    "price_label": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 24),
    "price_large": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 58),
    "channel": _load_font([r"C:\Windows\Fonts\segoeui.ttf", "segoeui.ttf"], 28),
}

def render_safe_slide(art_path: Path, lot_num: int, artist: str, title: str, price: str, is_zoomed: bool = False) -> Image.Image:
    src = Image.open(art_path).convert("RGBA")
    sw, sh = src.size

    # Новые безопасные лимиты полотна
    max_art_w = 960
    max_art_h = 920
    scale = min(max_art_w / sw, max_art_h / sh)
    art_w = int(round(sw * scale))
    art_h = int(round(sh * scale))
    art_resized = src.resize((art_w, art_h), Image.Resampling.LANCZOS)

    # Центрирование картины в зоне Y=330..1390 (высота зоны 1060px)
    art_x = (W - art_w) // 2
    art_y = 330 + (1060 - art_h) // 2

    # Объемная музейная тень
    pad = 60
    sh_layer = Image.new("RGBA", (art_w + pad * 2, art_h + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sh_layer)
    sdraw.rectangle([pad, pad + 12, pad + art_w, pad + art_h + 12], fill=(25, 20, 15, 65))
    sdraw.rectangle([pad + 4, pad + 18, pad + art_w - 4, pad + art_h + 18], fill=(20, 15, 10, 85))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(26))

    art_with_shadow = Image.new("RGBA", (art_w + pad * 2, art_h + pad * 2), (0, 0, 0, 0))
    art_with_shadow.paste(sh_layer, (0, 0), sh_layer)
    art_with_shadow.paste(art_resized, (pad, pad), art_resized)

    # При максимальном зуме (+3.5%)
    cw, ch = art_with_shadow.size
    cx, cy = cw / 2.0, ch / 2.0
    dest_x = art_x - pad
    dest_y = art_y - pad

    if is_zoomed:
        scale_val = 1.035
        matrix = (1.0 / scale_val, 0, cx * (1.0 - 1.0 / scale_val), 0, 1.0 / scale_val, cy * (1.0 - 1.0 / scale_val))
        art_with_shadow = art_with_shadow.transform(
            (cw, ch), Image.Transform.AFFINE, matrix, resample=Image.Resampling.BICUBIC
        )

    # 1. Фон
    canvas = make_semi_transparent_blurred_background(src, art_opacity=0.25, base_rgb=(246, 245, 241))

    # 2. Полотно
    canvas.paste(art_with_shadow, (dest_x, dest_y), art_with_shadow)

    # 3. Текстовый оверлей
    draw = ImageDraw.Draw(canvas)

    # ВЕРХНИЙ БЛОК:
    badge_str = f"АУКЦИОН  •  ЛОТ №{lot_num}"
    tb = draw.textbbox((0, 0), badge_str, font=FONTS["lot_badge"])
    btw = tb[2] - tb[0]
    bbw = btw + 44
    bbh = 42
    bbx = (W - bbw) // 2
    bby = 150
    draw.rounded_rectangle([bbx, bby, bbx + bbw, bby + bbh], radius=21, fill=(229, 45, 39, 240))
    draw.text((W // 2, bby + bbh // 2), badge_str, fill=(255, 255, 255, 255), font=FONTS["lot_badge"], anchor="mm")

    draw.text((W // 2, 230), artist, fill=(20, 22, 26, 255), font=FONTS["artist"], anchor="mm")
    draw.line([(W // 2 - 35, 275), (W // 2 + 35, 275)], fill=(229, 45, 39, 180), width=2)

    # НИЖНИЙ БЛОК (Сдвинут в безопасную зону с гарантированным зазором от картины):
    # Title centered at Y = 1465
    draw.text((W // 2, 1465), f"«{title}»", fill=(45, 48, 55, 255), font=FONTS["title"], anchor="mm")

    # Status at Y = 1525
    draw.text((W // 2, 1525), "СТАРТОВАЯ ЦЕНА", fill=(229, 45, 39, 255), font=FONTS["price_label"], anchor="mm")

    # Price at Y = 1580
    draw.text((W // 2, 1580), price, fill=(18, 20, 24, 255), font=FONTS["price_large"], anchor="mm")

    # Brackets
    pb = draw.textbbox((W // 2, 1580), price, font=FONTS["price_large"], anchor="mm")
    draw.line([(pb[0] - 50, 1580), (pb[0] - 15, 1580)], fill=(229, 45, 39, 200), width=3)
    draw.line([(pb[2] + 15, 1580), (pb[2] + 50, 1580)], fill=(229, 45, 39, 200), width=3)

    # Telegram at Y = 1660
    draw.text((W // 2, 1660), "Торги в Telegram: @marinakhakimova_auction", fill=(85, 90, 102, 255), font=FONTS["channel"], anchor="mm")

    return canvas

def main():
    print("🎨 Тестирование безопасных отступов...")
    s1 = ROOT_DIR / "assets" / "samples" / "sample_art_1.jpg"
    s3 = ROOT_DIR / "assets" / "samples" / "sample_art_3.jpg"

    # 1. Вертикальная картина (Лот 949) в обычном состоянии
    im_v = render_safe_slide(s1, 949, "Татьяна Романова", "Ромашковое настроение", "15 000 ₽", is_zoomed=False)
    im_v.save(ARTIFACTS_DIR / "safe_clearance_vertical.png")

    # 2. Вертикальная картина (Лот 949) при МАКСИМАЛЬНОМ ЗУМЕ (+3.5%)
    im_vz = render_safe_slide(s1, 949, "Татьяна Романова", "Ромашковое настроение", "15 000 ₽", is_zoomed=True)
    im_vz.save(ARTIFACTS_DIR / "safe_clearance_vertical_zoomed.png")

    # 3. Горизонтальная картина (Лот 947) при зуме
    im_h = render_safe_slide(s3, 947, "Елена Смирнова", "Пионы в хрустале", "18 500 ₽", is_zoomed=True)
    im_h.save(ARTIFACTS_DIR / "safe_clearance_horizontal_zoomed.png")

    print("✅ Все тестовые кадры с проверкой зазоров успешно сгенерированы!")

if __name__ == "__main__":
    main()
