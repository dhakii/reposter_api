# app/video_engine/overlays.py
"""
Мобильный оверлей-генератор:
- Премиум-каталог (Варианты 4A, 4B, 4C): полупрозрачный блюр-фон из картины, симметричный текст, выделение цены
- Адаптивный умный блюр (Вариант 2): глубокий темный блюр-фон
- Финал на фирменном светлом фоне логотипа (#EFEDEE)
"""

import os
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H = 1080, 1920

BRAND_LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "brand" / "logo.png"


def _load_font(candidates, size):
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


FONTS = {
    # Крупные шрифты для мобильных экранов
    "hook_kicker": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 28),
    "artist_top": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 52),
    "title_bottom": _load_font([r"C:\Windows\Fonts\georgiaz.ttf", "georgiaz.ttf"], 44),
    "price_bottom": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 56),
    "channel_bottom": _load_font([r"C:\Windows\Fonts\segoeui.ttf", "segoeui.ttf"], 30),
    "channel_bold": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 30),

    # Для стилей Премиум-каталога (4A, 4B, 4C)
    "edit_kicker": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 26),
    "edit_artist": _load_font([r"C:\Windows\Fonts\georgiab.ttf", "georgiab.ttf", r"C:\Windows\Fonts\segoeuib.ttf"], 52),
    "edit_title": _load_font([r"C:\Windows\Fonts\georgiaz.ttf", "georgiaz.ttf"], 44),
    "edit_badge": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 36),
    "edit_price_large": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 58),
    "edit_label": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 24),
    "edit_channel": _load_font([r"C:\Windows\Fonts\segoeui.ttf", "segoeui.ttf"], 28),

    # Финальный бренд-слайд
    "brand_tag": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 28),
    "brand_handle": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 46),
    "brand_hint": _load_font([r"C:\Windows\Fonts\segoeui.ttf", "segoeui.ttf"], 28),
}


def make_semi_transparent_blurred_background(
    art_img: Image.Image,
    art_opacity: float = 0.25,
    base_rgb: Tuple[int, int, int] = (246, 245, 241),
) -> Image.Image:
    """
    Создает светлый пастельный фон с полупрозрачной размытой картиной:
    - Размываем картину мягким блюром через даунскейл
    - Смешиваем с теплым галерейным офф-вайтом (base_rgb) с заданной прозрачностью art_opacity (20-30%)
    - Результат: мягкий акварельный оттенок красок полотна на светлой бумаге
    """
    bw, bh = art_img.size
    scale = max(W / bw, H / bh)
    scaled_w, scaled_h = int(bw * scale), int(bh * scale)
    bg_scaled = art_img.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)

    crop_x = (scaled_w - W) // 2
    crop_y = (scaled_h - H) // 2
    bg_cropped = bg_scaled.crop((crop_x, crop_y, crop_x + W, crop_y + H))

    # Быстрый мягкий блюр через 4x downscale
    bg_small = bg_cropped.resize((W // 4, H // 4), Image.Resampling.BILINEAR)
    bg_blur_small = bg_small.filter(ImageFilter.GaussianBlur(18))
    bg_blur = bg_blur_small.resize((W, H), Image.Resampling.BICUBIC).convert("RGBA")

    base_bg = Image.new("RGBA", (W, H), (*base_rgb, 255))
    return Image.blend(base_bg, bg_blur, art_opacity)


def create_adaptive_ambient_background(
    art_img: Image.Image,
    width: int = W,
    height: int = H,
    brightness: float = 0.38,
    blur_radius: int = 75,
) -> Image.Image:
    """
    Создает адаптивный глубокий темный фон из колорита самой картины (Вариант 2).
    """
    bw, bh = art_img.size
    scale = max(width / bw, height / bh)
    scaled_w, scaled_h = int(bw * scale), int(bh * scale)
    bg_scaled = art_img.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)

    crop_x = (scaled_w - width) // 2
    crop_y = (scaled_h - height) // 2
    bg_cropped = bg_scaled.crop((crop_x, crop_y, crop_x + width, crop_y + height))

    small_w, small_h = width // 4, height // 4
    bg_small = bg_cropped.resize((small_w, small_h), Image.Resampling.BILINEAR)
    bg_blurred_small = bg_small.filter(ImageFilter.GaussianBlur(blur_radius // 4))
    bg_blurred = bg_blurred_small.resize((width, height), Image.Resampling.BICUBIC)

    enhancer = ImageEnhance.Brightness(bg_blurred)
    bg_dark = enhancer.enhance(brightness)
    canvas = bg_dark.convert("RGBA")

    vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for y in range(350):
        alpha = int(180 * (1.0 - y / 350.0))
        vdraw.line([(0, y), (width, y)], fill=(8, 10, 14, alpha))
    for y in range(1380, height):
        alpha = int(210 * ((y - 1380) / (height - 1380)))
        vdraw.line([(0, y), (width, y)], fill=(8, 10, 14, alpha))

    return Image.alpha_composite(canvas, vignette)


def make_editorial_typography_overlay(
    lot_num: int,
    artist: str,
    title: str,
    price: str,
    variant: str = "hybrid",
    is_first_slide: bool = False,
    is_sold: bool = False,
    channel_link: str = "@marinakhakimova_auction",
) -> Image.Image:
    """
    Создает симметричный статический оверлей для стилей Премиум-каталога:
    - «hybrid»: Верх (автор из 4A + ЛОТ в красной плашке из 4B) + Низ из 4C (цена Sotheby's с лучами)
    - «4a»: Красный бейдж со стартовой ценой
    - «4b»: Белая плашка с рамкой
    - «4c»: Типографика Sotheby's
    """
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    v = variant.lower()
    quoted_title = f"«{title}»" if not title.startswith("«") else title

    # =========================================================================
    # ГИБРИДНЫЙ ВАРИАНТ (ВЫБОР ПОЛЬЗОВАТЕЛЯ):
    # Верх: Автор из 4A + ЛОТ в красной плашке из 4B + разделитель
    # Низ: Sotheby's из 4C (СТАРТОВАЯ ЦЕНА + Крупная цифра с линиями + Telegram)
    # =========================================================================
    if v in ["hybrid", "4_hybrid"]:
        badge_str = f"АУКЦИОН  •  ЛОТ №{lot_num}"
        tb = draw.textbbox((0, 0), badge_str, font=FONTS["edit_label"])
        btw = tb[2] - tb[0]
        bbw = btw + 44
        bbh = 42
        bbx = (W - bbw) // 2
        bby = 150
        draw.rounded_rectangle([bbx, bby, bbx + bbw, bby + bbh], radius=21, fill=(229, 45, 39, 240))
        draw.text((W // 2, bby + bbh // 2), badge_str, fill=(255, 255, 255, 255), font=FONTS["edit_label"], anchor="mm")

        draw.text((W // 2, 230), artist, fill=(20, 22, 26, 255), font=FONTS["edit_artist"], anchor="mm")
        draw.line([(W // 2 - 35, 275), (W // 2 + 35, 275)], fill=(229, 45, 39, 180), width=2)

        # НИЖНИЙ БЛОК: Сдвинут вниз в безопасную зону с гарантированным зазором от картины (>100px)
        draw.text((W // 2, 1465), quoted_title, fill=(45, 48, 55, 255), font=FONTS["edit_title"], anchor="mm")

        status_label = "ПРОДАНО" if is_sold else "СТАРТОВАЯ ЦЕНА"
        lbl_color = (40, 167, 69, 255) if is_sold else (229, 45, 39, 255)
        draw.text((W // 2, 1525), status_label, fill=lbl_color, font=FONTS["edit_label"], anchor="mm")
        draw.text((W // 2, 1580), price, fill=(18, 20, 24, 255), font=FONTS["edit_price_large"], anchor="mm")

        pb = draw.textbbox((W // 2, 1580), price, font=FONTS["edit_price_large"], anchor="mm")
        draw.line([(pb[0] - 50, 1580), (pb[0] - 15, 1580)], fill=(*lbl_color[:3], 200), width=3)
        draw.line([(pb[2] + 15, 1580), (pb[2] + 50, 1580)], fill=(*lbl_color[:3], 200), width=3)

        draw.text((W // 2, 1660), f"Торги в Telegram: {channel_link}", fill=(85, 90, 102, 255), font=FONTS["edit_channel"], anchor="mm")
        return overlay

    # 1. ВЕРХНИЙ СИММЕТРИЧНЫЙ БЛОК (Центрирован строго по X=540)
    kicker = f"АУКЦИОН  •  ЛОТ №{lot_num}"

    if v == "4b":
        # Вариант 4B: капсула лота сверху
        lot_tag = f"АУКЦИОН  •  ЛОТ №{lot_num}"
        draw.rounded_rectangle([W // 2 - 140, 155, W // 2 + 140, 197], radius=21, fill=(229, 45, 39, 230))
        draw.text((W // 2, 176), lot_tag, fill=(255, 255, 255, 255), font=FONTS["edit_label"], anchor="mm")
        draw.text((W // 2, 238), artist, fill=(20, 22, 28, 255), font=FONTS["edit_artist"], anchor="mm")
        draw.text((W // 2, 285), "ТВОЯ КОЛЛЕКЦИЯ  •  АУКЦИОН КАРТИН", fill=(130, 135, 145, 255), font=_load_font([r"C:\Windows\Fonts\segoeui.ttf", "segoeui.ttf"], 22), anchor="mm")
    else:
        # Варианты 4A и 4C: чистый центрированный заголовок с тонкой разделительной линией
        draw.text((W // 2, 175), kicker, fill=(229, 45, 39, 255), font=FONTS["edit_kicker"], anchor="mm")
        draw.text((W // 2, 230), artist, fill=(20, 22, 26, 255), font=FONTS["edit_artist"], anchor="mm")
        line_w = 60 if v == "4a" else 360
        line_color = (229, 45, 39, 180) if v == "4a" else (210, 205, 195, 255)
        draw.line([(W // 2 - line_w // 2, 275), (W // 2 + line_w // 2, 275)], fill=line_color, width=2)

    # 2. НИЖНИЙ СИММЕТРИЧНЫЙ БЛОК
    quoted_title = f"«{title}»" if not title.startswith("«") else title

    if v == "4a":
        # Вариант 4A: Сочный красный бейдж со скруглением
        draw.text((W // 2, 1435), quoted_title, fill=(45, 48, 55, 255), font=FONTS["edit_title"], anchor="mm")

        badge_text = f"ПРОДАНО: {price}" if is_sold else f"СТАРТ: {price}"
        badge_bg = (40, 167, 69, 255) if is_sold else (229, 45, 39, 255)

        bb = draw.textbbox((0, 0), badge_text, font=FONTS["edit_badge"])
        tw = bb[2] - bb[0]
        bw = tw + 70
        bh = 64
        bx = (W - bw) // 2
        by = 1485

        # Тень под бейджем
        bsh = Image.new("RGBA", (bw + 20, bh + 20), (0, 0, 0, 0))
        bdraw = ImageDraw.Draw(bsh)
        bdraw.rounded_rectangle([10, 12, 10 + bw, 12 + bh], radius=24, fill=(*badge_bg[:3], 70))
        bsh = bsh.filter(ImageFilter.GaussianBlur(8))
        overlay.paste(bsh, (bx - 10, by - 10), bsh)

        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=24, fill=badge_bg)
        draw.text((W // 2, by + bh // 2), badge_text, fill=(255, 255, 255, 255), font=FONTS["edit_badge"], anchor="mm")

        # Канал
        draw.text((W // 2, 1595), f"Торги в Telegram: {channel_link}", fill=(75, 80, 92, 255), font=FONTS["edit_channel"], anchor="mm")

    elif v == "4b":
        # Вариант 4B: Белая карточка с окантовкой и акцентной точкой
        draw.text((W // 2, 1435), quoted_title, fill=(45, 48, 55, 255), font=FONTS["edit_title"], anchor="mm")

        badge_text = f"Продано:  {price}" if is_sold else f"Старт:  {price}"
        dot_color = (40, 167, 69, 255) if is_sold else (229, 45, 39, 255)

        bb = draw.textbbox((0, 0), badge_text, font=FONTS["edit_badge"])
        tw = bb[2] - bb[0]
        bw = tw + 70
        bh = 66
        bx = (W - bw) // 2
        by = 1485

        bsh = Image.new("RGBA", (bw + 20, bh + 20), (0, 0, 0, 0))
        bdraw = ImageDraw.Draw(bsh)
        bdraw.rounded_rectangle([10, 12, 10 + bw, 12 + bh], radius=22, fill=(0, 0, 0, 35))
        bsh = bsh.filter(ImageFilter.GaussianBlur(10))
        overlay.paste(bsh, (bx - 10, by - 10), bsh)

        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=22, fill=(255, 255, 255, 245), outline=(*dot_color[:3], 160), width=2)
        draw.ellipse([bx + 26, by + bh // 2 - 5, bx + 36, by + bh // 2 + 5], fill=dot_color)
        draw.text((W // 2 + 10, by + bh // 2), badge_text, fill=(20, 22, 28, 255), font=FONTS["edit_badge"], anchor="mm")

        draw.text((W // 2, 1595), f"Торги в Telegram: {channel_link}", fill=(80, 85, 96, 255), font=FONTS["edit_channel"], anchor="mm")

    else:
        # Вариант 4C: Крупная центрированная цена Sotheby's с графичными лучами
        draw.text((W // 2, 1430), quoted_title, fill=(45, 48, 55, 255), font=FONTS["edit_title"], anchor="mm")

        status_label = "ПРОДАНО" if is_sold else "СТАРТОВАЯ ЦЕНА"
        lbl_color = (40, 167, 69, 255) if is_sold else (229, 45, 39, 255)
        draw.text((W // 2, 1485), status_label, fill=lbl_color, font=FONTS["edit_label"], anchor="mm")
        draw.text((W // 2, 1535), price, fill=(18, 20, 24, 255), font=FONTS["edit_price_large"], anchor="mm")

        pb = draw.textbbox((W // 2, 1535), price, font=FONTS["edit_price_large"], anchor="mm")
        draw.line([(pb[0] - 50, 1535), (pb[0] - 15, 1535)], fill=(*lbl_color[:3], 200), width=3)
        draw.line([(pb[2] + 15, 1535), (pb[2] + 50, 1535)], fill=(*lbl_color[:3], 200), width=3)

        draw.text((W // 2, 1610), f"Торги в Telegram: {channel_link}", fill=(85, 90, 102, 255), font=FONTS["edit_channel"], anchor="mm")

    return overlay


def make_static_typography_overlay(
    lot_num: int,
    artist: str,
    title: str,
    price: str,
    is_first_slide: bool = False,
    is_sold: bool = False,
    channel_link: str = "@marinakhakimova_auction",
) -> Image.Image:
    """
    Классический левосторонний оверлей для темного фона (Вариант 2).
    """
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if is_first_slide:
        kicker_text = "НОВАЯ ПОДБОРКА  •  ТВОЯ КОЛЛЕКЦИЯ"
    else:
        kicker_text = f"ЛОТ №{lot_num}  •  ТВОЯ КОЛЛЕКЦИЯ"

    draw.text((70, 175), kicker_text, fill=(245, 60, 50, 255), font=FONTS["hook_kicker"])
    draw.text((70, 220), artist, fill=(255, 255, 255, 255), font=FONTS["artist_top"])

    quoted_title = f"«{title}»" if not title.startswith("«") else title
    draw.text((70, 1430), quoted_title, fill=(220, 230, 245, 255), font=FONTS["title_bottom"])

    if is_sold:
        price_text = f"Продано: {price}" if not price.startswith("Продано") else price
        price_color = (76, 217, 100, 255)
    else:
        price_text = f"Старт: {price}" if not (price.startswith("Старт") or price.startswith("от")) else price
        price_color = (255, 255, 255, 255)

    draw.text((70, 1495), price_text, fill=price_color, font=FONTS["price_bottom"])

    prefix = "Торги в Telegram: "
    draw.text((70, 1575), prefix, fill=(180, 190, 205, 230), font=FONTS["channel_bottom"])
    bbox = draw.textbbox((70, 1575), prefix, font=FONTS["channel_bottom"])
    draw.text((bbox[2], 1575), channel_link, fill=(255, 255, 255, 255), font=FONTS["channel_bold"])

    return overlay


def render_brand_white_outro(
    channel_link: str = "@marinakhakimova_auction",
) -> Image.Image:
    """
    Финальный слайд на фирменном светлом фоне логотипа (#EFEDEE).
    """
    bg_color = (239, 237, 238, 255)
    canvas = Image.new("RGBA", (W, H), bg_color)

    if BRAND_LOGO_PATH.exists():
        raw_logo = Image.open(BRAND_LOGO_PATH).convert("RGBA")
        logo_d = 380
        logo_resized = raw_logo.resize((logo_d, logo_d), Image.Resampling.LANCZOS)

        mask = Image.new("L", (logo_d, logo_d), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.ellipse((0, 0, logo_d - 1, logo_d - 1), fill=255)
        logo_resized.putalpha(mask)

        logo_y = 660
        canvas.paste(logo_resized, ((W - logo_d) // 2, logo_y), logo_resized)

    draw = ImageDraw.Draw(canvas)

    tag_y = 1100
    draw.text((W // 2, tag_y), "АУКЦИОН КАРТИН В TELEGRAM", fill=(229, 45, 39, 255), font=FONTS["brand_tag"], anchor="mm")
    draw.text((W // 2, tag_y + 70), channel_link, fill=(20, 22, 26, 255), font=FONTS["brand_handle"], anchor="mm")
    draw.text((W // 2, tag_y + 140), "Ставки и полный каталог в описании профиля", fill=(110, 115, 125, 255), font=FONTS["brand_hint"], anchor="mm")

    return canvas
