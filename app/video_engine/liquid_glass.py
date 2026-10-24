# app/video_engine/liquid_glass.py
"""
Модуль рендеринга Apple Liquid Glass и фотореалистичных теней.
Соответствует спецификации DESIGN_SYSTEM.md:
- Раздел 3.2: Материал Liquid Glass (Backdrop blur 30px + saturation 130% + спекулярная фаска 1.5px)
- Раздел 3.5: Тени (Ambient 65px + Contact 18px + Glass shadow 40px)
- Раздел 5.2: FloatingArtwork (чистый холст без рамок, скругление 14px)
- Раздел 5.5: BrandEmblem (логотип 180x180 с 4x суперсэмплингом и тенью)
- Раздел 8: Эталонная реализация шейдера Liquid Glass
"""

import os
from pathlib import Path
from typing import Tuple, List, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

BRAND_LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "brand" / "logo.png"


def render_liquid_glass_card(
    base_canvas: Image.Image,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int = 28,
    opacity: float = 1.0,
) -> Image.Image:
    """
    Рендерит плашку в стиле Apple Liquid Glass поверх копии base_canvas (RGBA).
    Включает:
    - Внешнюю рассеянную тень (offset_y=+16, blur=40, rgba(0,0,0,0.50))
    - Backdrop Blur (r=30) + Saturation (1.3x) участка фона
    - Поверхностный стеклянный градиент 135°:
        * 0% (верх-лево): rgba(255, 255, 255, 0.16)
        * 45%: rgba(22, 26, 34, 0.60)
        * 100% (низ-право): rgba(10, 12, 18, 0.74)
    - Спекулярную световую фаску 1.5px под 135° (0.48 -> 0.10 -> 0.24)
    """
    canvas = base_canvas.convert("RGBA")

    # 1. Антиалиасинг-маска скругленного прямоугольника (суперсэмплинг 4x)
    ss = 4
    mask_hr = Image.new("L", (w * ss, h * ss), 0)
    draw_mask = ImageDraw.Draw(mask_hr)
    draw_mask.rounded_rectangle(
        (0, 0, w * ss - 1, h * ss - 1),
        radius=radius * ss,
        fill=int(255 * opacity)
    )
    mask = mask_hr.resize((w, h), Image.Resampling.LANCZOS)

    # 2. Внешняя тень карточки (offset_y=+16, blur=40, rgba(0,0,0,0.50))
    pad = 80
    shadow_layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    shadow_fill = Image.new("RGBA", (w, h), (0, 0, 0, int(128 * opacity)))
    shadow_layer.paste(shadow_fill, (pad, pad + 16), mask)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=40))
    canvas.alpha_composite(shadow_layer, (x - pad, y - pad))

    # 3. Backdrop Blur + повышение насыщенности участка под карточкой
    crop_box = (max(0, x), max(0, y), min(canvas.width, x + w), min(canvas.height, y + h))
    backdrop = canvas.crop(crop_box).resize((w, h), Image.Resampling.BILINEAR)
    backdrop = backdrop.filter(ImageFilter.GaussianBlur(radius=30))
    backdrop = ImageEnhance.Color(backdrop).enhance(1.30)

    # 4. Поверхностный стеклянный градиент 135° (верх-лево -> низ-право)
    yy, xx = np.mgrid[0:h, 0:w]
    t = np.clip((xx / max(1, w - 1) + yy / max(1, h - 1)) / 2.0, 0.0, 1.0)

    # Интерполяция между точками (согласно токенам раздела 3.2):
    # t=0.0: rgba(255, 255, 255, 0.16)
    # t=0.45: rgba(22, 26, 34, 0.60)
    # t=1.0: rgba(10, 12, 18, 0.74)
    r = np.interp(t, [0.0, 0.45, 1.0], [255, 22, 10]).astype(np.uint8)
    g = np.interp(t, [0.0, 0.45, 1.0], [255, 26, 12]).astype(np.uint8)
    b = np.interp(t, [0.0, 0.45, 1.0], [255, 34, 18]).astype(np.uint8)
    a = np.interp(t, [0.0, 0.45, 1.0], [41, 153, 189]).astype(np.uint8)

    grad_overlay = Image.fromarray(np.dstack([r, g, b, a]), mode="RGBA")
    glass_body = Image.alpha_composite(backdrop, grad_overlay)

    # 5. Спекулярная фаска 1.5px (Specular Border 135°: 0.48 -> 0.10 -> 0.24)
    border_mask_hr = Image.new("L", (w * ss, h * ss), 0)
    draw_border = ImageDraw.Draw(border_mask_hr)
    draw_border.rounded_rectangle(
        (3, 3, w * ss - 4, h * ss - 4),
        radius=radius * ss,
        outline=255,
        width=int(1.5 * ss)
    )
    border_mask = border_mask_hr.resize((w, h), Image.Resampling.LANCZOS)

    b_alpha = np.interp(t, [0.0, 0.5, 1.0], [122, 26, 61]).astype(np.uint8)
    border_arr = np.dstack([
        np.full((h, w), 255, dtype=np.uint8),
        np.full((h, w), 255, dtype=np.uint8),
        np.full((h, w), 255, dtype=np.uint8),
        (b_alpha.astype(np.float32) * (np.array(border_mask, dtype=np.float32) / 255.0)).astype(np.uint8)
    ])
    border_img = Image.fromarray(border_arr, mode="RGBA")
    glass_body = Image.alpha_composite(glass_body, border_img)

    # 6. Вставка готовой стеклянной карточки по скругленной маске
    card_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    card_layer.paste(glass_body, (0, 0), mask)
    canvas.alpha_composite(card_layer, (x, y))
    return canvas


def make_gradient_135(w: int, h: int, stops: List[Tuple[float, Tuple[int, int, int, int]]]) -> Image.Image:
    """Генерирует RGBA изображение градиента под углом 135°."""
    y, x = np.mgrid[0:h, 0:w]
    proj = np.clip((x.astype(np.float32) / max(1, w - 1) + y.astype(np.float32) / max(1, h - 1)) / 2.0, 0.0, 1.0)

    positions = np.array([s[0] for s in stops], dtype=np.float32)
    colors = np.array([s[1] for s in stops], dtype=np.float32)

    r = np.interp(proj, positions, colors[:, 0])
    g = np.interp(proj, positions, colors[:, 1])
    b = np.interp(proj, positions, colors[:, 2])
    a = np.interp(proj, positions, colors[:, 3])

    rgba = np.stack([r, g, b, a], axis=-1).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def make_gradient_180(w: int, h: int, stops: List[Tuple[float, Tuple[int, int, int, int]]]) -> Image.Image:
    """Генерирует вертикальный градиент 180° сверху вниз."""
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    y_full = np.tile(y, (1, w))

    positions = np.array([s[0] for s in stops], dtype=np.float32)
    colors = np.array([s[1] for s in stops], dtype=np.float32)

    r = np.interp(y_full, positions, colors[:, 0])
    g = np.interp(y_full, positions, colors[:, 1])
    b = np.interp(y_full, positions, colors[:, 2])
    a = np.interp(y_full, positions, colors[:, 3])

    rgba = np.stack([r, g, b, a], axis=-1).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def make_rounded_mask(w: int, h: int, radius: int, supersample: int = 4) -> Image.Image:
    """Создает суперсглаженную маску скругленного прямоугольника."""
    sw, sh = w * supersample, h * supersample
    sr = radius * supersample
    mask = Image.new("L", (sw, sh), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=255)
    return mask.resize((w, h), Image.Resampling.LANCZOS)


def make_specular_border_mask(w: int, h: int, radius: int, border_width: float = 1.5, supersample: int = 4) -> Image.Image:
    """Создает антиалиасную маску рамки толщиной border_width пикселей."""
    sw, sh = int(w * supersample), int(h * supersample)
    sr = int(radius * supersample)
    sbw = int(border_width * supersample)

    outer = Image.new("L", (sw, sh), 0)
    odraw = ImageDraw.Draw(outer)
    odraw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=255)

    inner = Image.new("L", (sw, sh), 0)
    idraw = ImageDraw.Draw(inner)
    idraw.rounded_rectangle([sbw, sbw, sw - 1 - sbw, sh - 1 - sbw], radius=max(0, sr - sbw), fill=255)

    border_arr = np.clip(np.array(outer, dtype=np.int16) - np.array(inner, dtype=np.int16), 0, 255).astype(np.uint8)
    return Image.fromarray(border_arr, "L").resize((w, h), Image.Resampling.LANCZOS)


def render_floating_artwork(
    source_img: Image.Image,
    max_w: int = 940,
    max_h: int = 1180,
    corner_radius: int = 14,
) -> Tuple[Image.Image, Tuple[int, int], Tuple[int, int]]:
    """
    Рендерит парящую картину (Floating Artwork) согласно разделу 5.2:
    - Масштабирование contain внутри 940x1180 px
    - Скругление углов 14px (антиалиасинг)
    - Двойная тень (раздел 3.5):
      * ARTWORK_SHADOW_AMBIENT: offset_y=+30px, blur=65px, rgba(0,0,0,0.70)
      * ARTWORK_SHADOW_CONTACT: offset_y=+10px, blur=18px, rgba(0,0,0,0.48)
    Возвращает:
      (canvas_with_shadow, (art_w, art_h), (pad_x, pad_y))
    """
    sw, sh = source_img.size
    scale = min(max_w / sw, max_h / sh)
    art_w = int(round(sw * scale))
    art_h = int(round(sh * scale))

    art_resized = source_img.convert("RGBA").resize((art_w, art_h), Image.Resampling.LANCZOS)

    mask = make_rounded_mask(art_w, art_h, corner_radius)
    art_rounded = Image.new("RGBA", (art_w, art_h), (0, 0, 0, 0))
    art_rounded.paste(art_resized, (0, 0), mask)

    pad_x = 130
    pad_y = 130
    canvas_w = art_w + pad_x * 2
    canvas_h = art_h + pad_y * 2

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Слой 1: Ambient Shadow (y=+30, blur=65, opacity=0.70)
    amb_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    adraw = ImageDraw.Draw(amb_layer)
    ax = pad_x
    ay = pad_y + 30
    adraw.rounded_rectangle([ax, ay, ax + art_w - 1, ay + art_h - 1], radius=corner_radius, fill=(0, 0, 0, int(255 * 0.70)))
    amb_blur = amb_layer.filter(ImageFilter.GaussianBlur(65))

    # Слой 2: Contact Shadow (y=+10, blur=18, opacity=0.48)
    cnt_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(cnt_layer)
    cx = pad_x
    cy = pad_y + 10
    cdraw.rounded_rectangle([cx, cy, cx + art_w - 1, cy + art_h - 1], radius=corner_radius, fill=(0, 0, 0, int(255 * 0.48)))
    cnt_blur = cnt_layer.filter(ImageFilter.GaussianBlur(18))

    canvas.paste(amb_blur, (0, 0), amb_blur)
    canvas.paste(cnt_blur, (0, 0), cnt_blur)
    canvas.paste(art_rounded, (pad_x, pad_y), art_rounded)

    return canvas, (art_w, art_h), (pad_x, pad_y)


def get_supersampled_logo(target_diameter: int = 180) -> Optional[Image.Image]:
    """
    Рендерит круглый логотип бренда согласно разделу 5.5:
    1. Исходник приводится к квадрату 720x720 (4x суперсэмплинг)
    2. Круглая маска с мягким краем
    3. Спекулярное белое кольцо толщиной 1.5px (6px в масштабе 4x)
    4. Сжатие до target_diameter через LANCZOS
    5. Тень: offset_y=+12px, blur=28px, rgba(0,0,0,0.45)
    """
    if not BRAND_LOGO_PATH.exists():
        return None

    try:
        raw_logo = Image.open(BRAND_LOGO_PATH).convert("RGBA")
        supersample = 4
        large_d = target_diameter * supersample

        large_logo = raw_logo.resize((large_d, large_d), Image.Resampling.LANCZOS)

        mask_large = Image.new("L", (large_d, large_d), 0)
        draw_large = ImageDraw.Draw(mask_large)
        draw_large.ellipse((2, 2, large_d - 3, large_d - 3), fill=255)

        # Тонкое кольцо 6px (1.5px в финале)
        ring_large = Image.new("RGBA", (large_d, large_d), (0, 0, 0, 0))
        rdraw = ImageDraw.Draw(ring_large)
        rdraw.ellipse((2, 2, large_d - 3, large_d - 3), outline=(255, 255, 255, int(255 * 0.65)), width=6)

        large_logo.putalpha(mask_large)
        large_logo = Image.alpha_composite(large_logo, ring_large)
        smooth_logo = large_logo.resize((target_diameter, target_diameter), Image.Resampling.LANCZOS)

        pad = 50
        canvas_d = target_diameter + pad * 2
        logo_canvas = Image.new("RGBA", (canvas_d, canvas_d), (0, 0, 0, 0))

        # Тень: offset_y=+12, blur=28, rgba(0,0,0,0.45)
        shadow_layer = Image.new("RGBA", (canvas_d, canvas_d), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow_layer)
        sx = pad
        sy = pad + 12
        sdraw.ellipse((sx, sy, sx + target_diameter - 1, sy + target_diameter - 1), fill=(0, 0, 0, int(255 * 0.45)))
        shadow_blur = shadow_layer.filter(ImageFilter.GaussianBlur(28))

        logo_canvas.paste(shadow_blur, (0, 0), shadow_blur)
        logo_canvas.paste(smooth_logo, (pad, pad), smooth_logo)

        return logo_canvas
    except Exception as e:
        print(f"⚠️ Ошибка загрузки логотипа: {e}")
        return None
