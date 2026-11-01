#!/usr/bin/env python3
"""
Генератор вариантов refined «Премиум-каталога»:
- Полупрозрачная размытая картина в фоне (вместо чисто белого/офф-вайта)
- Симметричное центральное расположение текста сверху и снизу
- Различные варианты акцентного выделения цены (плашка, бейдж, типографика)
"""

import os
import sys
import math
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H = 1080, 1920

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output" / "editorial_variants"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
    "kicker": load_font("segoeuib.ttf", 26),
    "artist": load_font("georgiab.ttf", 52),
    "artist_sans": load_font("segoeuib.ttf", 50),
    "title": load_font("georgiaz.ttf", 44),
    "price_badge": load_font("segoeuib.ttf", 36),
    "price_large": load_font("segoeuib.ttf", 58),
    "price_label": load_font("segoeuib.ttf", 24),
    "channel": load_font("segoeui.ttf", 28),
    "channel_bold": load_font("segoeuib.ttf", 28),
}

def fit_artwork(img: Image.Image, max_w: int = 980, max_h: int = 1060) -> Image.Image:
    sw, sh = img.size
    scale = min(max_w / sw, max_h / sh)
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)

def make_semi_transparent_blurred_background(art_img: Image.Image, art_opacity: float = 0.22, base_rgb=(246, 245, 242)) -> Image.Image:
    """
    Создает теплый светлый фон с полупрозрачной размытой картиной:
    - Размываем картину (художественный мягкий блюр)
    - Накладываем её с прозрачностью art_opacity (20-30%) на теплый галерейный офф-вайт
    - Получаем нежный пастельный акварельный оттенок красок полотна
    """
    bw, bh = art_img.size
    scale = max(W / bw, H / bh)
    scaled_w, scaled_h = int(bw * scale), int(bh * scale)
    bg_scaled = art_img.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)

    crop_x = (scaled_w - W) // 2
    crop_y = (scaled_h - H) // 2
    bg_cropped = bg_scaled.crop((crop_x, crop_y, crop_x + W, crop_y + H))

    # Быстрый мягкий блюр через даунскейл
    bg_small = bg_cropped.resize((W // 4, H // 4), Image.Resampling.BILINEAR)
    bg_blur_small = bg_small.filter(ImageFilter.GaussianBlur(18))
    bg_blur = bg_blur_small.resize((W, H), Image.Resampling.BICUBIC).convert("RGBA")

    # Базовая подложка
    base_bg = Image.new("RGBA", (W, H), (*base_rgb, 255))

    # Смешиваем: base_bg + bg_blur с opacity
    # Image.blend: out = image1 * (1 - alpha) + image2 * alpha
    blended = Image.blend(base_bg, bg_blur, art_opacity)
    return blended


# =========================================================================
# ВАРИАНТ 4A: «Премиум-каталог — Красный акцентный бейдж (Red Pill)»
# =========================================================================
def render_variant_4a(art_img: Image.Image, lot_num: int, artist: str, title: str, price: str, is_first: bool = False) -> Image.Image:
    canvas = make_semi_transparent_blurred_background(art_img, art_opacity=0.25, base_rgb=(245, 244, 240))
    
    # 1. Полотно картины
    art_resized = fit_artwork(art_img, max_w=980, max_h=1060)
    aw, ah = art_resized.size
    ax = (W - aw) // 2
    ay = 340 + (1060 - ah) // 2
    
    # Мягкая естественная музейная тень
    pad = 60
    sh_layer = Image.new("RGBA", (aw + pad * 2, ah + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sh_layer)
    sdraw.rectangle([pad, pad + 12, pad + aw, pad + ah + 12], fill=(25, 20, 15, 65))
    sdraw.rectangle([pad + 4, pad + 18, pad + aw - 4, pad + ah + 18], fill=(20, 15, 10, 85))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(28))
    
    canvas.paste(sh_layer, (ax - pad, ay - pad), sh_layer)
    canvas.paste(art_resized, (ax, ay), art_resized)
    
    draw = ImageDraw.Draw(canvas)
    
    # 2. СИММЕТРИЧНЫЙ ВЕРХНИЙ БЛОК (Центрирован строго по X=540)
    kicker = "НОВАЯ ПОДБОРКА  •  ТВОЯ КОЛЛЕКЦИЯ" if is_first else f"ЛОТ №{lot_num}  •  ТВОЯ КОЛЛЕКЦИЯ"
    draw.text((W // 2, 175), kicker, fill=(229, 45, 39, 255), font=FONTS["kicker"], anchor="mm")
    draw.text((W // 2, 230), artist, fill=(20, 22, 26, 255), font=FONTS["artist"], anchor="mm")
    
    # Тонкая элегантная разделительная черточка под автором
    line_w = 60
    draw.line([(W // 2 - line_w // 2, 275), (W // 2 + line_w // 2, 275)], fill=(200, 40, 35, 180), width=2)
    
    # 3. СИММЕТРИЧНЫЙ НИЖНИЙ БЛОК (Центрирован строго по X=540)
    # Название
    draw.text((W // 2, 1435), f"«{title}»", fill=(45, 48, 55, 255), font=FONTS["title"], anchor="mm")
    
    # ВЫДЕЛЕННАЯ ЦЕНА: Яркий красный бейдж со скруглением
    badge_text = f"СТАРТ: {price}"
    bb = draw.textbbox((0, 0), badge_text, font=FONTS["price_badge"])
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    
    bw = tw + 70
    bh = 64
    bx = (W - bw) // 2
    by = 1485
    
    # Тень бейджа
    bsh = Image.new("RGBA", (bw + 20, bh + 20), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bsh)
    bdraw.rounded_rectangle([10, 12, 10 + bw, 12 + bh], radius=24, fill=(229, 45, 39, 70))
    bsh = bsh.filter(ImageFilter.GaussianBlur(8))
    canvas.paste(bsh, (bx - 10, by - 10), bsh)
    
    # Сам красный бейдж
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=24, fill=(229, 45, 39, 255))
    draw.text((W // 2, by + bh // 2), badge_text, fill=(255, 255, 255, 255), font=FONTS["price_badge"], anchor="mm")
    
    # Канал торгов
    prefix = "Торги в Telegram: "
    full_str = prefix + "@marinakhakimova_auction"
    draw.text((W // 2, 1595), full_str, fill=(75, 80, 92, 255), font=FONTS["channel"], anchor="mm")
    
    return canvas


# =========================================================================
# ВАРИАНТ 4B: «Премиум-каталог — Контрастная графитовая рамка (Editorial Badge)»
# =========================================================================
def render_variant_4b(art_img: Image.Image, lot_num: int, artist: str, title: str, price: str, is_first: bool = False) -> Image.Image:
    # Чуть более выразительный пастельный оттенок картины (30%)
    canvas = make_semi_transparent_blurred_background(art_img, art_opacity=0.30, base_rgb=(248, 246, 242))
    
    # 1. Полотно картины
    art_resized = fit_artwork(art_img, max_w=980, max_h=1060)
    aw, ah = art_resized.size
    ax = (W - aw) // 2
    ay = 340 + (1060 - ah) // 2
    
    # Музейная тень
    pad = 60
    sh_layer = Image.new("RGBA", (aw + pad * 2, ah + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sh_layer)
    sdraw.rectangle([pad, pad + 12, pad + aw, pad + ah + 12], fill=(30, 25, 20, 60))
    sdraw.rectangle([pad + 5, pad + 18, pad + aw - 5, pad + ah + 18], fill=(20, 15, 12, 80))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(28))
    
    canvas.paste(sh_layer, (ax - pad, ay - pad), sh_layer)
    canvas.paste(art_resized, (ax, ay), art_resized)
    
    draw = ImageDraw.Draw(canvas)
    
    # 2. СИММЕТРИЧНЫЙ ВЕРХНИЙ БЛОК с капсулой лота
    # Капсула лота по центру
    kicker = f"ЛОТ №{lot_num}" if not is_first else "НОВЫЙ ЛОТ"
    draw.rounded_rectangle([W // 2 - 80, 160, W // 2 + 80, 196], radius=18, fill=(229, 45, 39, 230))
    draw.text((W // 2, 178), kicker, fill=(255, 255, 255, 255), font=FONTS["price_label"], anchor="mm")
    
    draw.text((W // 2, 238), artist, fill=(20, 22, 28, 255), font=FONTS["artist"], anchor="mm")
    draw.text((W // 2, 285), "ТВОЯ КОЛЛЕКЦИЯ  •  АУКЦИОН КАРТИН", fill=(130, 135, 145, 255), font=load_font("segoeui.ttf", 22), anchor="mm")
    
    # 3. СИММЕТРИЧНЫЙ НИЖНИЙ БЛОК
    draw.text((W // 2, 1435), f"«{title}»", fill=(45, 48, 55, 255), font=FONTS["title"], anchor="mm")
    
    # ВЫДЕЛЕННАЯ ЦЕНА: Элегантная белая карточка-плашка с тонкой графитовой/красной окантовкой
    badge_text = f"Старт:  {price}"
    bb = draw.textbbox((0, 0), badge_text, font=FONTS["price_badge"])
    tw = bb[2] - bb[0]
    
    bw = tw + 70
    bh = 66
    bx = (W - bw) // 2
    by = 1485
    
    # Мягкая белая плашка с тенью
    bsh = Image.new("RGBA", (bw + 20, bh + 20), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bsh)
    bdraw.rounded_rectangle([10, 12, 10 + bw, 12 + bh], radius=22, fill=(0, 0, 0, 40))
    bsh = bsh.filter(ImageFilter.GaussianBlur(10))
    canvas.paste(bsh, (bx - 10, by - 10), bsh)
    
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=22, fill=(255, 255, 255, 240), outline=(229, 45, 39, 160), width=2)
    # Красная точка слева от текста
    draw.ellipse([bx + 26, by + bh // 2 - 5, bx + 36, by + bh // 2 + 5], fill=(229, 45, 39, 255))
    draw.text((W // 2 + 10, by + bh // 2), badge_text, fill=(20, 22, 28, 255), font=FONTS["price_badge"], anchor="mm")
    
    # Канал
    draw.text((W // 2, 1595), "Торги в Telegram: @marinakhakimova_auction", fill=(80, 85, 96, 255), font=FONTS["channel"], anchor="mm")
    
    return canvas


# =========================================================================
# ВАРИАНТ 4C: «Премиум-каталог — Sotheby's Typographic (Крупная цена + линии)»
# =========================================================================
def render_variant_4c(art_img: Image.Image, lot_num: int, artist: str, title: str, price: str, is_first: bool = False) -> Image.Image:
    # 20% нежного пастельного размытия на офф-вайте #F5F4EE
    canvas = make_semi_transparent_blurred_background(art_img, art_opacity=0.20, base_rgb=(246, 244, 238))
    
    # 1. Полотно картины
    art_resized = fit_artwork(art_img, max_w=980, max_h=1060)
    aw, ah = art_resized.size
    ax = (W - aw) // 2
    ay = 340 + (1060 - ah) // 2
    
    # Тень
    pad = 60
    sh_layer = Image.new("RGBA", (aw + pad * 2, ah + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sh_layer)
    sdraw.rectangle([pad, pad + 12, pad + aw, pad + ah + 12], fill=(25, 20, 15, 65))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(28))
    
    canvas.paste(sh_layer, (ax - pad, ay - pad), sh_layer)
    canvas.paste(art_resized, (ax, ay), art_resized)
    
    draw = ImageDraw.Draw(canvas)
    
    # 2. СИММЕТРИЧНЫЙ ВЕРХНИЙ БЛОК: Музейный заголовок
    kicker = "НОВАЯ ПОДБОРКА  •  ТВОЯ КОЛЛЕКЦИЯ" if is_first else f"ЛОТ №{lot_num}  •  ТВОЯ КОЛЛЕКЦИЯ"
    draw.text((W // 2, 175), kicker, fill=(229, 45, 39, 255), font=FONTS["kicker"], anchor="mm")
    draw.text((W // 2, 230), artist, fill=(20, 22, 26, 255), font=FONTS["artist"], anchor="mm")
    
    # Тонкая линия шириной 400px
    draw.line([(W // 2 - 180, 275), (W // 2 + 180, 275)], fill=(210, 205, 195, 255), width=2)
    
    # 3. СИММЕТРИЧНЫЙ НИЖНИЙ БЛОК: Название + КРУПНАЯ выразительная цена
    draw.text((W // 2, 1430), f"«{title}»", fill=(45, 48, 55, 255), font=FONTS["title"], anchor="mm")
    
    # ВЫДЕЛЕННАЯ ЦЕНА: Очень крупная цифра в центре с красным кикером
    draw.text((W // 2, 1485), "СТАРТОВАЯ ЦЕНА", fill=(229, 45, 39, 255), font=FONTS["price_label"], anchor="mm")
    draw.text((W // 2, 1535), price, fill=(18, 20, 24, 255), font=FONTS["price_large"], anchor="mm")
    
    # Тонкие графичные лучи по бокам от цены
    pb = draw.textbbox((W // 2, 1535), price, font=FONTS["price_large"], anchor="mm")
    draw.line([(pb[0] - 50, 1535), (pb[0] - 15, 1535)], fill=(229, 45, 39, 200), width=3)
    draw.line([(pb[2] + 15, 1535), (pb[2] + 50, 1535)], fill=(229, 45, 39, 200), width=3)
    
    # Канал
    draw.text((W // 2, 1610), "Торги в Telegram: @marinakhakimova_auction", fill=(85, 90, 102, 255), font=FONTS["channel"], anchor="mm")
    
    return canvas


def main():
    print("🎨 Генерация вариантов Refined Премиум-каталога...")
    
    art1 = Image.open(ROOT_DIR / "assets" / "samples" / "sample_art_1.jpg").convert("RGBA")
    art3 = Image.open(ROOT_DIR / "assets" / "samples" / "sample_art_3.jpg").convert("RGBA")
    
    variants = [
        ("editorial_4a_red_pill", "4A: Премиум-каталог — Сочный красный бейдж цены", render_variant_4a),
        ("editorial_4b_framed_badge", "4B: Премиум-каталог — Элегантная белая плашка с окантовкой", render_variant_4b),
        ("editorial_4c_sothebys_large", "4C: Премиум-каталог — Крупная акцентная цена Sotheby's", render_variant_4c),
    ]
    
    for code, title_name, renderer in variants:
        # Вертикальная
        img_vert = renderer(
            art_img=art1,
            lot_num=949,
            artist="Татьяна Романова",
            title="Ромашковое настроение",
            price="15 000 ₽",
            is_first=False
        )
        fn_vert = f"{code}_vertical.png"
        img_vert.save(OUTPUT_DIR / fn_vert)
        img_vert.save(ARTIFACTS_DIR / fn_vert)
        
        # Горизонтальная
        img_horiz = renderer(
            art_img=art3,
            lot_num=947,
            artist="Елена Смирнова",
            title="Пионы в хрустале",
            price="18 500 ₽",
            is_first=False
        )
        fn_horiz = f"{code}_horizontal.png"
        img_horiz.save(OUTPUT_DIR / fn_horiz)
        img_horiz.save(ARTIFACTS_DIR / fn_horiz)
        
        print(f"✅ Готово: {title_name}")
        
    print("\n✨ Готово! Все варианты успешно сохранены.")

if __name__ == "__main__":
    main()
