#!/usr/bin/env python3
"""
Тест гибридного дизайна:
- Верх: Автор из 4A (крупная антиква) + надпись ЛОТ в красной плашке/рамочке из 4B
- Центр: Парящий холст с музейной тенью на полупрозрачном размытом фоне полотна
- Низ: Аукционная типографика из 4C (Название + СТАРТОВАЯ ЦЕНА + Крупная цена с линиями-лучами + Telegram)
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

W, H = 1080, 1920

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output"
ARTIFACTS_DIR = Path(r"C:\Users\dhakii\.gemini\antigravity\brain\0154ee46-4b06-46fb-a88e-063b8ebc2d08")

def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    paths = [
        Path(r"C:\Windows\Fonts") / name,
        Path(name),
    ]
    for p in paths:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()

FONTS = {
    "lot_badge": load_font("segoeuib.ttf", 22),
    "brand_sub": load_font("segoeui.ttf", 20),
    "artist": load_font("georgiab.ttf", 52),
    "title": load_font("georgiaz.ttf", 44),
    "price_label": load_font("segoeuib.ttf", 24),
    "price_large": load_font("segoeuib.ttf", 58),
    "channel": load_font("segoeui.ttf", 28),
}

def fit_artwork(img: Image.Image, max_w: int = 980, max_h: int = 1060) -> Image.Image:
    sw, sh = img.size
    scale = min(max_w / sw, max_h / sh)
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)

def make_semi_transparent_blurred_background(art_img: Image.Image, art_opacity: float = 0.25, base_rgb=(246, 245, 241)) -> Image.Image:
    bw, bh = art_img.size
    scale = max(W / bw, H / bh)
    scaled_w, scaled_h = int(bw * scale), int(bh * scale)
    bg_scaled = art_img.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)

    crop_x = (scaled_w - W) // 2
    crop_y = (scaled_h - H) // 2
    bg_cropped = bg_scaled.crop((crop_x, crop_y, crop_x + W, crop_y + H))

    bg_small = bg_cropped.resize((W // 4, H // 4), Image.Resampling.BILINEAR)
    bg_blur_small = bg_small.filter(ImageFilter.GaussianBlur(18))
    bg_blur = bg_blur_small.resize((W, H), Image.Resampling.BICUBIC).convert("RGBA")

    base_bg = Image.new("RGBA", (W, H), (*base_rgb, 255))
    return Image.blend(base_bg, bg_blur, art_opacity)

def render_hybrid_editorial_slide(
    art_img: Image.Image,
    lot_num: int,
    artist: str,
    title: str,
    price: str,
    is_first_slide: bool = False,
    is_sold: bool = False,
    channel_link: str = "@marinakhakimova_auction",
) -> Image.Image:
    # 1. Полупрозрачный фон из красок картины
    canvas = make_semi_transparent_blurred_background(art_img, art_opacity=0.25, base_rgb=(246, 245, 241))

    # 2. Полотно картины
    art_resized = fit_artwork(art_img, max_w=980, max_h=1060)
    aw, ah = art_resized.size
    ax = (W - aw) // 2
    ay = 340 + (1060 - ah) // 2

    # Музейная тень картины
    pad = 60
    sh_layer = Image.new("RGBA", (aw + pad * 2, ah + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sh_layer)
    sdraw.rectangle([pad, pad + 12, pad + aw, pad + ah + 12], fill=(25, 20, 15, 65))
    sdraw.rectangle([pad + 4, pad + 18, pad + aw - 4, pad + ah + 18], fill=(20, 15, 10, 85))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(28))

    canvas.paste(sh_layer, (ax - pad, ay - pad), sh_layer)
    canvas.paste(art_resized, (ax, ay), art_resized)

    draw = ImageDraw.Draw(canvas)

    # 3. ВЕРХНИЙ БЛОК:
    # «АУКЦИОН  •  ЛОТ №... в красной капсуле + Автор крупно + черта»
    badge_str = f"АУКЦИОН  •  ЛОТ №{lot_num}"
    tb = draw.textbbox((0, 0), badge_str, font=FONTS["lot_badge"])
    btw = tb[2] - tb[0]
    bbw = btw + 44
    bbh = 42
    bbx = (W - bbw) // 2
    bby = 155

    # Красная капсула лота
    draw.rounded_rectangle([bbx, bby, bbx + bbw, bby + bbh], radius=21, fill=(229, 45, 39, 240))
    draw.text((W // 2, bby + bbh // 2), badge_str, fill=(255, 255, 255, 255), font=FONTS["lot_badge"], anchor="mm")

    # Имя автора (крупно, элегантная антиква из 4A)
    draw.text((W // 2, 238), artist, fill=(20, 22, 26, 255), font=FONTS["artist"], anchor="mm")

    # Тонкая разделительная черточка под автором из 4A
    line_w = 70
    draw.line([(W // 2 - line_w // 2, 285), (W // 2 + line_w // 2, 285)], fill=(229, 45, 39, 180), width=2)

    # 4. НИЖНИЙ БЛОК:
    # «Низ мне нравится на последнем варианте (4C)»
    quoted_title = f"«{title}»" if not title.startswith("«") else title
    draw.text((W // 2, 1430), quoted_title, fill=(45, 48, 55, 255), font=FONTS["title"], anchor="mm")

    status_label = "ПРОДАНО" if is_sold else "СТАРТОВАЯ ЦЕНА"
    lbl_color = (40, 167, 69, 255) if is_sold else (229, 45, 39, 255)
    draw.text((W // 2, 1485), status_label, fill=lbl_color, font=FONTS["price_label"], anchor="mm")

    # Крупная цена по центру
    draw.text((W // 2, 1535), price, fill=(18, 20, 24, 255), font=FONTS["price_large"], anchor="mm")

    # Тонкие графичные лучи по бокам от цены
    pb = draw.textbbox((W // 2, 1535), price, font=FONTS["price_large"], anchor="mm")
    draw.line([(pb[0] - 50, 1535), (pb[0] - 15, 1535)], fill=(*lbl_color[:3], 200), width=3)
    draw.line([(pb[2] + 15, 1535), (pb[2] + 50, 1535)], fill=(*lbl_color[:3], 200), width=3)

    # Канал
    draw.text((W // 2, 1610), f"Торги в Telegram: {channel_link}", fill=(85, 90, 102, 255), font=FONTS["channel"], anchor="mm")

    return canvas

def main():
    print("🎨 Генерация слайдов в гибридном стиле...")
    art1 = Image.open(ROOT_DIR / "assets" / "samples" / "sample_art_1.jpg").convert("RGBA")
    art3 = Image.open(ROOT_DIR / "assets" / "samples" / "sample_art_3.jpg").convert("RGBA")

    # Вертикальная
    img_v = render_hybrid_editorial_slide(
        art_img=art1,
        lot_num=949,
        artist="Татьяна Романова",
        title="Ромашковое настроение",
        price="15 000 ₽",
        is_first_slide=True,
    )
    img_v.save(OUTPUT_DIR / "hybrid_editorial_vertical.png")
    img_v.save(ARTIFACTS_DIR / "hybrid_editorial_vertical.png")

    # Горизонтальная
    img_h = render_hybrid_editorial_slide(
        art_img=art3,
        lot_num=947,
        artist="Елена Смирнова",
        title="Пионы в хрустале",
        price="18 500 ₽",
        is_first_slide=False,
    )
    img_h.save(OUTPUT_DIR / "hybrid_editorial_horizontal.png")
    img_h.save(ARTIFACTS_DIR / "hybrid_editorial_horizontal.png")

    print("✅ Слайды гибридного дизайна успешно созданы!")

if __name__ == "__main__":
    main()
