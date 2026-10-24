# app/video_engine/overlays.py
"""
Pillow-генератор графических слоев и слайдов строго по спецификации DESIGN_SYSTEM.md.
Реализует:
- Раздел 3: Все цветовые токены, виньетку 0%..48%..100%, градиенты и шрифты
- Раздел 4: Типографическая шкала (Hero, Artwork, Artist, Price, Kicker, Pill, Captions)
- Раздел 5: Компоненты AmbientBackground, FloatingArtwork, TopLotPill, LotInfoCard, BrandEmblem, HeroModalCard
- Раздел 6: Dynamic Layout Engine (математика стека с адаптивной привязкой)
"""

import os
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .liquid_glass import (
    render_liquid_glass_card,
    render_floating_artwork,
    get_supersampled_logo,
    make_gradient_135,
    make_gradient_180,
    make_rounded_mask,
    make_specular_border_mask,
)

W, H = 1080, 1920

# Загрузка шрифтов по токенам раздела 4 DESIGN_SYSTEM.md
def _load_font(candidates, size):
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()

FONTS = {
    "HERO_TITLE": _load_font([r"C:\Windows\Fonts\georgiab.ttf", "georgiab.ttf"], 50),
    "ARTWORK_TITLE": _load_font([r"C:\Windows\Fonts\georgiaz.ttf", "georgiaz.ttf"], 38),
    "ARTIST_NAME": _load_font([r"C:\Windows\Fonts\seguisb.ttf", "seguisb.ttf"], 25),
    "PRICE_TAG": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 24),
    "CTA_BUTTON_TEXT": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 26),
    "HANDLE_BADGE_TEXT": _load_font([r"C:\Windows\Fonts\seguisb.ttf", "seguisb.ttf"], 26),
    "TOP_PILL_TEXT": _load_font([r"C:\Windows\Fonts\seguisb.ttf", "seguisb.ttf"], 20),
    "SECTION_KICKER": _load_font([r"C:\Windows\Fonts\segoeuib.ttf", "segoeuib.ttf"], 21),
    "BODY_SUBTITLE": _load_font([r"C:\Windows\Fonts\segoeui.ttf", "segoeui.ttf"], 26),
    "CAPTION_META": _load_font([r"C:\Windows\Fonts\segoeui.ttf", "segoeui.ttf"], 21),
    "CAPTION_META_BOLD": _load_font([r"C:\Windows\Fonts\seguisb.ttf", "seguisb.ttf"], 21),
}

# Цветовые токены раздела 3
TEXT_PRIMARY = (255, 255, 255, 255)
TEXT_SECONDARY = (255, 255, 255, int(255 * 0.78))
TEXT_MUTED = (255, 255, 255, int(255 * 0.56))
ACCENT_RED_TEXT = (239, 59, 54, 255)  # #EF3B36


def draw_spaced_text(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    text: str,
    font: ImageFont.ImageFont,
    fill: Any,
    letter_spacing: float = 2.0,
    center: bool = True,
):
    """Отрисовка текста с трекингом (letter-spacing)."""
    widths = []
    for ch in text:
        bbox = draw.textbbox((0, 0), ch, font=font)
        widths.append(bbox[2] - bbox[0])
    total_w = sum(widths) + letter_spacing * (len(text) - 1) if text else 0
    curr_x = x - total_w / 2 if center else x

    for i, ch in enumerate(text):
        draw.text((curr_x, y), ch, font=font, fill=fill)
        curr_x += widths[i] + letter_spacing


def make_background_layer(source_image_path: str) -> Image.Image:
    """
    Компонент AmbientBackground (Раздел 5.1):
    1. Исходник cover 1080x1920
    2. GaussianBlur(radius=65)
    3. Виньетка (Раздел 3.1):
       * 0%: rgba(8, 10, 14, 0.58) -> a=148
       * 48%: rgba(8, 10, 14, 0.34) -> a=87
       * 100%: rgba(8, 10, 14, 0.80) -> a=204
    """
    src = Image.open(source_image_path).convert("RGBA")
    sw, sh = src.size

    scale = max(W / sw, H / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    src_scaled = src.resize((nw, nh), Image.Resampling.LANCZOS)

    cx = (nw - W) // 2
    cy = (nh - H) // 2
    bg_cropped = src_scaled.crop((cx, cy, cx + W, cy + H))
    bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(65))

    # Виньетка 0%..48%..100%
    y_norm = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]
    y_full = np.tile(y_norm, (1, W))

    a_arr = np.where(
        y_full < 0.48,
        148.0 + (87.0 - 148.0) * (y_full / 0.48),
        87.0 + (204.0 - 87.0) * ((y_full - 0.48) / 0.52)
    ).astype(np.uint8)

    r_arr = np.full((H, W), 8, dtype=np.uint8)
    g_arr = np.full((H, W), 10, dtype=np.uint8)
    b_arr = np.full((H, W), 14, dtype=np.uint8)

    vignette = Image.fromarray(np.stack([r_arr, g_arr, b_arr, a_arr], axis=-1), "RGBA")
    return Image.alpha_composite(bg_blurred, vignette)


def render_upper_pill_component(
    bg: Image.Image,
    pill_y: int,
    lot_num: int,
) -> Tuple[Image.Image, Tuple[int, int]]:
    """
    Компонент TopLotPill (Раздел 5.3):
    - Высота: 52px
    - Горизонтальные отступы: 34px слева и справа
    - border_radius: 999px (полная капсула)
    - Текст: TOP_PILL_TEXT (20px, UPPERCASE, трекинг +2.2px)
    """
    text = f"ЛОТ №{lot_num} • ТВОЯ КОЛЛЕКЦИЯ"
    temp_im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(temp_im)

    widths = [tdraw.textbbox((0, 0), ch, font=FONTS["TOP_PILL_TEXT"])[2] - tdraw.textbbox((0, 0), ch, font=FONTS["TOP_PILL_TEXT"])[0] for ch in text]
    text_w = sum(widths) + 2.2 * (len(text) - 1)
    text_h = 22

    pad_x = 34
    pill_w = int(round(text_w + pad_x * 2))
    pill_h = 52
    pill_x = int(round((W - pill_w) / 2))

    card_canvas = render_liquid_glass_card(
        base_canvas=bg,
        x=pill_x,
        y=pill_y,
        w=pill_w,
        h=pill_h,
        radius=999,
    )

    # Отрисовываем текст поверх
    text_local_x = pill_x + pill_w / 2
    text_local_y = pill_y + (pill_h - text_h) / 2 - 2

    content_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(content_layer)
    draw_spaced_text(
        cdraw,
        text_local_x,
        text_local_y,
        text,
        FONTS["TOP_PILL_TEXT"],
        (255, 255, 255, int(255 * 0.92)),
        letter_spacing=2.2,
        center=True,
    )

    card_canvas.alpha_composite(content_layer)
    # Возвращаем слой пилла для анимации смещения
    # Вырежем пилл вместе с тенью для анимации translateY
    crop_pad = 80
    cx1 = max(0, pill_x - crop_pad)
    cy1 = max(0, pill_y - crop_pad)
    cx2 = min(W, pill_x + pill_w + crop_pad)
    cy2 = min(H, pill_y + pill_h + crop_pad)
    cropped_pill = card_canvas.crop((cx1, cy1, cx2, cy2))

    return cropped_pill, (cx1, cy1)


def render_bottom_card_component(
    bg: Image.Image,
    card_y: int,
    artist: str,
    title: str,
    price: str,
    channel_link: str = "@marinakhakimova_auction",
) -> Tuple[Image.Image, Tuple[int, int]]:
    """
    Компонент LotInfoCard (Раздел 5.4):
    - Ширина 940px (X=70), высота 216px, border_radius 28px
    - Строка 1: Имя автора (ARTIST_NAME 25px, X_rel=36, Y_rel=28)
    - Строка 2: Название картины (ARTWORK_TITLE 38px, X_rel=36, Y_rel=64)
    - Разделитель: GLASS_DIVIDER (1px rgba(255,255,255,0.12), X_rel=36, Y_rel=124, ширина 868)
    - Строка 3: Нижний бар (Y_rel=166):
      * Слева: PriceBadge (48px высота, radius 14px, градиент #E52D27->#B31217, 24px Bold)
      * Справа: Торги в канале @marinakhakimova_auction (21px)
    """
    card_w = 940
    card_h = 216
    card_x = 70

    card_canvas = render_liquid_glass_card(
        base_canvas=bg,
        x=card_x,
        y=card_y,
        w=card_w,
        h=card_h,
        radius=28,
    )

    content_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(content_layer)

    # 1. Строка 1: Имя автора
    cdraw.text((card_x + 36, card_y + 28), artist, fill=TEXT_SECONDARY, font=FONTS["ARTIST_NAME"])

    # 2. Строка 2: Название картины
    quoted_title = f"«{title}»" if not title.startswith("«") else title
    cdraw.text((card_x + 36, card_y + 64), quoted_title, fill=TEXT_PRIMARY, font=FONTS["ARTWORK_TITLE"])

    # 3. Разделитель 1px
    div_y = card_y + 124
    cdraw.line([(card_x + 36, div_y), (card_x + 36 + 868, div_y)], fill=(255, 255, 255, int(255 * 0.12)), width=1)

    # 4. Строка 3: Нижний бар
    clean_price = price if price.startswith("Старт:") or price.startswith("от") else f"Старт: {price}"
    p_bbox = cdraw.textbbox((0, 0), clean_price, font=FONTS["PRICE_TAG"])
    ptw = p_bbox[2] - p_bbox[0]

    cap_pad_x = 22
    cap_pad_y = 10
    cap_w = ptw + cap_pad_x * 2
    cap_h = 48
    cap_x = card_x + 36
    cap_y = card_y + 144

    # Заливка капсулы ACCENT_BUTTON_GRADIENT 180° (#E52D27 -> #B31217)
    btn_stops = [
        (0.0, (229, 45, 39, 255)),   # #E52D27
        (1.0, (179, 18, 23, 255)),   # #B31217
    ]
    price_grad = make_gradient_180(cap_w, cap_h, btn_stops)
    price_mask = make_rounded_mask(cap_w, cap_h, radius=14)

    # Обводка 1px rgba(255,255,255,0.30)
    p_border_mask = make_specular_border_mask(cap_w, cap_h, radius=14, border_width=1.0)
    p_border = Image.new("RGBA", (cap_w, cap_h), (255, 255, 255, int(255 * 0.30)))

    content_layer.paste(price_grad, (cap_x, cap_y), price_mask)
    content_layer.paste(p_border, (cap_x, cap_y), p_border_mask)

    # Текст цены
    cdraw.text((cap_x + cap_pad_x, cap_y + cap_pad_y + 1), clean_price, fill=TEXT_PRIMARY, font=FONTS["PRICE_TAG"])

    # Справа: Торги в канале @marinakhakimova_auction
    text_y = cap_y + 13
    prefix = "Торги в канале "
    pref_w = cdraw.textbbox((0, 0), prefix, font=FONTS["CAPTION_META"])[2] - cdraw.textbbox((0, 0), prefix, font=FONTS["CAPTION_META"])[0]

    right_x = cap_x + cap_w + 24
    cdraw.text((right_x, text_y), prefix, fill=TEXT_MUTED, font=FONTS["CAPTION_META"])
    cdraw.text((right_x + pref_w, text_y), channel_link, fill=TEXT_PRIMARY, font=FONTS["CAPTION_META_BOLD"])

    card_canvas.alpha_composite(content_layer)

    crop_pad = 80
    cx1 = max(0, card_x - crop_pad)
    cy1 = max(0, card_y - crop_pad)
    cx2 = min(W, card_x + card_w + crop_pad)
    cy2 = min(H, card_y + card_h + crop_pad)
    cropped_card = card_canvas.crop((cx1, cy1, cx2, cy2))

    return cropped_card, (cx1, cy1)


def render_intro_slide(
    source_image_path: str,
    title: str = "5 картин на аукционе сейчас",
    subtitle: str = "Твоя Коллекция  •  Ставки в Telegram",
) -> Image.Image:
    """
    Компонент HeroModalCard для 01_intro.png (Раздел 5.6 Вариант А):
    - Высота карточки 740px (Y_top = 590px, Y_bottom = 1330px), ширина 920px (X = 80px)
    - Y = 660px: BrandEmblem (180x180)
    - Y = 890px: SECTION_KICKER «НОВАЯ ПОДБОРКА ЛОТОВ» (21px Bold, #EF3B36, трекинг +2.5px)
    - Y = 945px: HERO_TITLE «5 картин на аукционе сейчас» (50px Serif Bold)
    - Y = 1045px: Разделитель 220px, 1px rgba(255,255,255,0.16)
    - Y = 1090px: BODY_SUBTITLE «Твоя Коллекция  •  Ставки в Telegram» (26px)
    - Y = 1185px: «🔊 Включите звук» (21px, rgba(255,255,255,0.55))
    """
    bg = make_background_layer(source_image_path)

    card_w = 920
    card_h = 740
    card_x = 80
    card_y = 590

    glass_canvas = render_liquid_glass_card(
        base_canvas=bg,
        x=card_x,
        y=card_y,
        w=card_w,
        h=card_h,
        radius=36,
    )

    content_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(content_layer)

    # 1. Y = 660 px: BrandEmblem 180x180
    logo = get_supersampled_logo(target_diameter=180)
    if logo:
        lw, lh = logo.size
        # центрируем логотип по горизонтали
        content_layer.paste(logo, ((W - lw) // 2, 660 - 50), logo)

    # 2. Y = 890 px: SECTION_KICKER
    draw_spaced_text(
        cdraw,
        W // 2,
        890,
        "НОВАЯ ПОДБОРКА ЛОТОВ",
        FONTS["SECTION_KICKER"],
        ACCENT_RED_TEXT,
        letter_spacing=2.5,
        center=True,
    )

    # 3. Y = 945 px: HERO_TITLE
    cdraw.text((W // 2, 945), title, fill=TEXT_PRIMARY, font=FONTS["HERO_TITLE"], anchor="mt")

    # 4. Y = 1045 px: Разделитель 220px
    cdraw.line([(W // 2 - 110, 1045), (W // 2 + 110, 1045)], fill=(255, 255, 255, int(255 * 0.16)), width=1)

    # 5. Y = 1090 px: BODY_SUBTITLE
    cdraw.text((W // 2, 1090), subtitle, fill=TEXT_SECONDARY, font=FONTS["BODY_SUBTITLE"], anchor="mt")

    # 6. Y = 1185 px: Включите звук
    cdraw.text((W // 2, 1185), "🔊  Включите звук", fill=TEXT_MUTED, font=FONTS["CAPTION_META"], anchor="mt")

    glass_canvas.alpha_composite(content_layer)
    return glass_canvas


def render_outro_slide(
    source_image_path: str,
    cta_title: str = "Понравилась картина?",
    cta_subtitle: str = "Участвуйте в торгах в Telegram",
    channel_link: str = "@marinakhakimova_auction",
) -> Image.Image:
    """
    Компонент HeroModalCard для 07_outro.png (Раздел 5.6 Вариант Б):
    - Высота карточки 820px (Y_top = 550px, Y_bottom = 1370px), ширина 920px (X = 80px)
    - Y = 615px: BrandEmblem (180x180)
    - Y = 840px: SECTION_KICKER «ТВОЯ КОЛЛЕКЦИЯ • АУКЦИОН» (#EF3B36)
    - Y = 895px: HERO_TITLE «Понравилась картина?» (50px Serif Bold)
    - Y = 980px: BODY_SUBTITLE «Участвуйте в торгах в Telegram» (26px)
    - Y = 1045px: Стеклянный бейдж канала (ширина 560px, высота 58px, radius 16px) -> @marinakhakimova_auction (26px SemiBold)
    - Y = 1135px: Красная CTA-кнопка (ширина 740px, высота 82px, radius 22px) -> «Перейти в аукцион →» (26px Bold)
    - Y = 1265px: CAPTION_META «Ссылка также в описании и шапке профиля» (21px)
    """
    bg = make_background_layer(source_image_path)

    card_w = 920
    card_h = 820
    card_x = 80
    card_y = 550

    glass_canvas = render_liquid_glass_card(
        base_canvas=bg,
        x=card_x,
        y=card_y,
        w=card_w,
        h=card_h,
        radius=36,
    )

    content_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(content_layer)

    # 1. Y = 615 px: BrandEmblem 180x180
    logo = get_supersampled_logo(target_diameter=180)
    if logo:
        lw, lh = logo.size
        content_layer.paste(logo, ((W - lw) // 2, 615 - 50), logo)

    # 2. Y = 840 px: SECTION_KICKER
    draw_spaced_text(
        cdraw,
        W // 2,
        840,
        "ТВОЯ КОЛЛЕКЦИЯ • АУКЦИОН",
        FONTS["SECTION_KICKER"],
        ACCENT_RED_TEXT,
        letter_spacing=2.5,
        center=True,
    )

    # 3. Y = 895 px: HERO_TITLE
    cdraw.text((W // 2, 895), cta_title, fill=TEXT_PRIMARY, font=FONTS["HERO_TITLE"], anchor="mt")

    # 4. Y = 980 px: BODY_SUBTITLE
    cdraw.text((W // 2, 980), cta_subtitle, fill=TEXT_SECONDARY, font=FONTS["BODY_SUBTITLE"], anchor="mt")

    # 5. Y = 1045 px: Стеклянный бейдж канала (560x58)
    badge_w, badge_h = 560, 58
    badge_x = (W - badge_w) // 2
    badge_y = 1045

    b_grad = Image.new("RGBA", (badge_w, badge_h), (255, 255, 255, int(255 * 0.09)))
    b_mask = make_rounded_mask(badge_w, badge_h, radius=16)
    b_border_mask = make_specular_border_mask(badge_w, badge_h, radius=16, border_width=1.0)
    b_border = Image.new("RGBA", (badge_w, badge_h), (255, 255, 255, int(255 * 0.20)))

    content_layer.paste(b_grad, (badge_x, badge_y), b_mask)
    content_layer.paste(b_border, (badge_x, badge_y), b_border_mask)

    cdraw.text(
        (badge_x + badge_w / 2, badge_y + badge_h / 2),
        channel_link,
        fill=TEXT_PRIMARY,
        font=FONTS["HANDLE_BADGE_TEXT"],
        anchor="mm",
    )

    # 6. Y = 1135 px: Красная CTA-кнопка (740x82)
    btn_w, btn_h = 740, 82
    btn_x = (W - btn_w) // 2
    btn_y = 1135

    # Свечение кнопки ACCENT_BUTTON_GLOW: offset_y = +8px, blur = 24px, rgba(229, 45, 39, 0.40)
    glow_pad = 40
    glow_canvas = Image.new("RGBA", (btn_w + glow_pad * 2, btn_h + glow_pad * 2), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow_canvas)
    gdraw.rounded_rectangle(
        [glow_pad, glow_pad + 8, glow_pad + btn_w - 1, glow_pad + btn_h + 7],
        radius=22,
        fill=(229, 45, 39, int(255 * 0.40))
    )
    glow_blurred = glow_canvas.filter(ImageFilter.GaussianBlur(24))
    content_layer.paste(glow_blurred, (btn_x - glow_pad, btn_y - glow_pad), glow_blurred)

    # Тело кнопки: ACCENT_BUTTON_GRADIENT 180° (#E52D27 -> #B31217)
    btn_stops = [
        (0.0, (229, 45, 39, 255)),   # #E52D27
        (1.0, (179, 18, 23, 255)),   # #B31217
    ]
    btn_grad = make_gradient_180(btn_w, btn_h, btn_stops)
    btn_mask = make_rounded_mask(btn_w, btn_h, radius=22)

    # ACCENT_BUTTON_BORDER: 1px solid rgba(255, 255, 255, 0.32)
    btn_border_mask = make_specular_border_mask(btn_w, btn_h, radius=22, border_width=1.0)
    btn_border = Image.new("RGBA", (btn_w, btn_h), (255, 255, 255, int(255 * 0.32)))

    content_layer.paste(btn_grad, (btn_x, btn_y), btn_mask)
    content_layer.paste(btn_border, (btn_x, btn_y), btn_border_mask)

    # Текст внутри кнопки: «Перейти в аукцион →» (26px Bold)
    btn_text = "Перейти в аукцион →"
    cdraw.text(
        (btn_x + btn_w / 2, btn_y + btn_h / 2 - 1),
        btn_text,
        fill=TEXT_PRIMARY,
        font=FONTS["CTA_BUTTON_TEXT"],
        anchor="mm",
    )

    # 7. Y = 1265 px: CAPTION_META
    cdraw.text((W // 2, 1265), "Ссылка также в описании и шапке профиля", fill=TEXT_MUTED, font=FONTS["CAPTION_META"], anchor="mt")

    glass_canvas.alpha_composite(content_layer)
    return glass_canvas
