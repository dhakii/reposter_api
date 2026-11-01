#!/usr/bin/env python3
"""
Генератор дизайн-вариантов оформления аукционных слайдов:
1. Вариант 1: «Музейный светлый» (Light Gallery) — в тон одобренного светлого финала (#EFEDEE)
2. Вариант 2: «Атмосферный адаптивный блюр» (Adaptive Ambient Glow) — фон из палитры картины
3. Вариант 3: «Студийный спотлайт» (Studio Radial Spotlight) — прожектор в центре, глубокий бархат по краям
4. Вариант 4: «Премиум арт-каталог» (Warm Editorial Off-White) — благородный теплый галерейный тон (#F4F2ED)
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
OUTPUT_DIR = ROOT_DIR / "output" / "design_variants"
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

# Набор шрифтов
FONTS = {
    # Для темных тем
    "dark_kicker": load_font("segoeuib.ttf", 28),
    "dark_artist": load_font("segoeuib.ttf", 52),
    "dark_title": load_font("georgiaz.ttf", 44),
    "dark_price": load_font("segoeuib.ttf", 56),
    "dark_channel": load_font("segoeui.ttf", 30),
    "dark_channel_bold": load_font("segoeuib.ttf", 30),
    
    # Для светлых тем
    "light_kicker": load_font("segoeuib.ttf", 28),
    "light_artist": load_font("segoeuib.ttf", 52),
    "light_title": load_font("georgiaz.ttf", 44),
    "light_price": load_font("segoeuib.ttf", 56),
    "light_channel": load_font("segoeui.ttf", 30),
    "light_channel_bold": load_font("segoeuib.ttf", 30),
    
    # Для editorial
    "edit_kicker": load_font("segoeuib.ttf", 26),
    "edit_artist": load_font("georgiab.ttf", 52),
    "edit_title": load_font("georgiaz.ttf", 42),
    "edit_price": load_font("segoeuib.ttf", 54),
}

def fit_artwork(img: Image.Image, max_w: int = 1000, max_h: int = 1080) -> Image.Image:
    sw, sh = img.size
    scale = min(max_w / sw, max_h / sh)
    nw, nh = int(round(sw * scale)), int(round(sh * scale))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)

def create_radial_gradient(width: int, height: int, center_color: tuple, edge_color: tuple, cx: int, cy: int, radius: int) -> Image.Image:
    """Создает мягкий кинематографичный радиальный спотлайт"""
    # Создаем на половинном разрешении для скорости, затем апскейлим с бикубической фильтрацией
    sw, sh = width // 2, height // 2
    scx, scy, srad = cx // 2, cy // 2, radius // 2
    img = Image.new("RGBA", (sw, sh))
    pixels = img.load()
    
    cr, cg, cb = center_color[:3]
    er, eg, eb = edge_color[:3]
    
    for y in range(sh):
        for x in range(sw):
            dist = math.hypot(x - scx, y - scy)
            t = min(max(dist / srad, 0.0), 1.0)
            # Плавная сигмоида / cosine интерполяция
            t = (1.0 - math.cos(t * math.pi)) / 2.0
            r = int(cr + (er - cr) * t)
            g = int(cg + (eg - cg) * t)
            b = int(cb + (eb - cb) * t)
            pixels[x, y] = (r, g, b, 255)
            
    return img.resize((width, height), Image.Resampling.BICUBIC)


# =========================================================================
# ВАРИАНТ 1: Музейный светлый (Light Gallery — в цвет логотипа #EFEDEE)
# =========================================================================
def render_variant_1_light_gallery(art_img: Image.Image, lot_num: int, artist: str, title: str, price: str, is_first: bool = False) -> Image.Image:
    bg_color = (239, 237, 238, 255) # #EFEDEE — фирменный цвет фона логотипа
    canvas = Image.new("RGBA", (W, H), bg_color)
    
    # 1. Полотно картины
    art_resized = fit_artwork(art_img, max_w=980, max_h=1060)
    aw, ah = art_resized.size
    ax = (W - aw) // 2
    ay = 340 + (1060 - ah) // 2
    
    # Реалистичная музейная тень (глубокая и мягкая)
    pad = 60
    sh_layer = Image.new("RGBA", (aw + pad * 2, ah + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sh_layer)
    # Двухслойная тень
    sdraw.rectangle([pad, pad + 12, pad + aw, pad + ah + 12], fill=(20, 20, 25, 60))
    sdraw.rectangle([pad + 5, pad + 18, pad + aw - 5, pad + ah + 18], fill=(15, 15, 20, 90))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(30))
    
    canvas.paste(sh_layer, (ax - pad, ay - pad), sh_layer)
    canvas.paste(art_resized, (ax, ay), art_resized)
    
    # 2. Типографика (графит + акцентный брендовый красный)
    draw = ImageDraw.Draw(canvas)
    
    # Верхний блок (Y=175..310)
    kicker = "НОВАЯ ПОДБОРКА  •  ТВОЯ КОЛЛЕКЦИЯ" if is_first else f"ЛОТ №{lot_num}  •  ТВОЯ КОЛЛЕКЦИЯ"
    draw.text((70, 175), kicker, fill=(229, 45, 39, 255), font=FONTS["light_kicker"])
    draw.text((70, 220), artist, fill=(24, 26, 32, 255), font=FONTS["light_artist"])
    
    # Нижний блок (Y=1430..1640)
    draw.text((70, 1430), f"«{title}»", fill=(45, 48, 56, 255), font=FONTS["light_title"])
    draw.text((70, 1495), f"Старт: {price}", fill=(18, 20, 24, 255), font=FONTS["light_price"])
    
    prefix = "Торги в Telegram: "
    draw.text((70, 1575), prefix, fill=(105, 112, 124, 255), font=FONTS["light_channel"])
    bbox = draw.textbbox((70, 1575), prefix, font=FONTS["light_channel"])
    draw.text((bbox[2], 1575), "@marinakhakimova_auction", fill=(24, 26, 32, 255), font=FONTS["light_channel_bold"])
    
    return canvas


# =========================================================================
# ВАРИАНТ 2: Атмосферный адаптивный блюр (Adaptive Ambient Glow)
# =========================================================================
def render_variant_2_adaptive_blur(art_img: Image.Image, lot_num: int, artist: str, title: str, price: str, is_first: bool = False) -> Image.Image:
    # 1. Адаптивный живой фон из самой картины
    bg_raw = art_img.copy()
    # Масштабируем с кадрированием по центру под 1080x1920
    bw, bh = bg_raw.size
    scale = max(W / bw, H / bh)
    scaled_w, scaled_h = int(bw * scale), int(bh * scale)
    bg_scaled = bg_raw.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    
    crop_x = (scaled_w - W) // 2
    crop_y = (scaled_h - H) // 2
    bg_cropped = bg_scaled.crop((crop_x, crop_y, crop_x + W, crop_y + H))
    
    # Глубокое художественное размытие
    bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(80))
    # Приглушаем яркость, чтобы фон был благородным и не спорил с картиной
    enhancer = ImageEnhance.Brightness(bg_blurred)
    bg_dark = enhancer.enhance(0.38) # затемняем до 38%
    
    canvas = bg_dark.convert("RGBA")
    
    # Деликатная темная виньетка сверху и снизу для идеальной читаемости текста
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for y in range(350):
        alpha = int(180 * (1.0 - y / 350.0))
        vdraw.line([(0, y), (W, y)], fill=(8, 10, 14, alpha))
    for y in range(1380, H):
        alpha = int(210 * ((y - 1380) / (H - 1380)))
        vdraw.line([(0, y), (W, y)], fill=(8, 10, 14, alpha))
    
    canvas = Image.alpha_composite(canvas, vignette)
    
    # 2. Полотно картины
    art_resized = fit_artwork(art_img, max_w=980, max_h=1060)
    aw, ah = art_resized.size
    ax = (W - aw) // 2
    ay = 340 + (1060 - ah) // 2
    
    # Тень картины
    pad = 60
    sh_layer = Image.new("RGBA", (aw + pad * 2, ah + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sh_layer)
    sdraw.rectangle([pad, pad + 10, pad + aw, pad + ah + 10], fill=(0, 0, 0, 200))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(35))
    
    canvas.paste(sh_layer, (ax - pad, ay - pad), sh_layer)
    canvas.paste(art_resized, (ax, ay), art_resized)
    
    # 3. Типографика (чистая белая с деликатной тенью)
    draw = ImageDraw.Draw(canvas)
    
    kicker = "НОВАЯ ПОДБОРКА  •  ТВОЯ КОЛЛЕКЦИЯ" if is_first else f"ЛОТ №{lot_num}  •  ТВОЯ КОЛЛЕКЦИЯ"
    draw.text((70, 175), kicker, fill=(245, 60, 50, 255), font=FONTS["dark_kicker"])
    draw.text((70, 220), artist, fill=(255, 255, 255, 255), font=FONTS["dark_artist"])
    
    draw.text((70, 1430), f"«{title}»", fill=(220, 230, 245, 255), font=FONTS["dark_title"])
    draw.text((70, 1495), f"Старт: {price}", fill=(255, 255, 255, 255), font=FONTS["dark_price"])
    
    prefix = "Торги в Telegram: "
    draw.text((70, 1575), prefix, fill=(180, 190, 205, 230), font=FONTS["dark_channel"])
    bbox = draw.textbbox((70, 1575), prefix, font=FONTS["dark_channel"])
    draw.text((bbox[2], 1575), "@marinakhakimova_auction", fill=(255, 255, 255, 255), font=FONTS["dark_channel_bold"])
    
    return canvas


# =========================================================================
# ВАРИАНТ 3: Студийный спотлайт (Studio Radial Spotlight)
# =========================================================================
def render_variant_3_studio_spotlight(art_img: Image.Image, lot_num: int, artist: str, title: str, price: str, is_first: bool = False) -> Image.Image:
    # Мягкий графитовый спотлайт в центре (38, 42, 52) -> бархатный черный по краям (10, 11, 14)
    canvas = create_radial_gradient(
        width=W,
        height=H,
        center_color=(36, 40, 50),
        edge_color=(9, 10, 13),
        cx=W // 2,
        cy=870,
        radius=780
    )
    
    # 2. Полотно картины
    art_resized = fit_artwork(art_img, max_w=980, max_h=1060)
    aw, ah = art_resized.size
    ax = (W - aw) // 2
    ay = 340 + (1060 - ah) // 2
    
    # Студийная глубокая тень
    pad = 70
    sh_layer = Image.new("RGBA", (aw + pad * 2, ah + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sh_layer)
    sdraw.rectangle([pad, pad + 15, pad + aw, pad + ah + 15], fill=(0, 0, 0, 220))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(40))
    
    canvas.paste(sh_layer, (ax - pad, ay - pad), sh_layer)
    canvas.paste(art_resized, (ax, ay), art_resized)
    
    # 3. Типографика
    draw = ImageDraw.Draw(canvas)
    
    kicker = "НОВАЯ ПОДБОРКА  •  ТВОЯ КОЛЛЕКЦИЯ" if is_first else f"ЛОТ №{lot_num}  •  ТВОЯ КОЛЛЕКЦИЯ"
    draw.text((70, 175), kicker, fill=(229, 45, 39, 255), font=FONTS["dark_kicker"])
    draw.text((70, 220), artist, fill=(255, 255, 255, 255), font=FONTS["dark_artist"])
    
    draw.text((70, 1430), f"«{title}»", fill=(210, 220, 235, 255), font=FONTS["dark_title"])
    draw.text((70, 1495), f"Старт: {price}", fill=(255, 255, 255, 255), font=FONTS["dark_price"])
    
    prefix = "Торги в Telegram: "
    draw.text((70, 1575), prefix, fill=(160, 170, 185, 230), font=FONTS["dark_channel"])
    bbox = draw.textbbox((70, 1575), prefix, font=FONTS["dark_channel"])
    draw.text((bbox[2], 1575), "@marinakhakimova_auction", fill=(255, 255, 255, 255), font=FONTS["dark_channel_bold"])
    
    return canvas


# =========================================================================
# ВАРИАНТ 4: Премиум арт-каталог (Warm Editorial Off-White #F4F2ED)
# =========================================================================
def render_variant_4_warm_editorial(art_img: Image.Image, lot_num: int, artist: str, title: str, price: str, is_first: bool = False) -> Image.Image:
    bg_color = (244, 242, 237, 255) # Теплый офф-вайт галерейный лен
    canvas = Image.new("RGBA", (W, H), bg_color)
    
    # 1. Полотно картины
    art_resized = fit_artwork(art_img, max_w=980, max_h=1060)
    aw, ah = art_resized.size
    ax = (W - aw) // 2
    ay = 340 + (1060 - ah) // 2
    
    # Мягкая естественная дневная тень
    pad = 50
    sh_layer = Image.new("RGBA", (aw + pad * 2, ah + pad * 2), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sh_layer)
    sdraw.rectangle([pad, pad + 10, pad + aw, pad + ah + 10], fill=(30, 25, 20, 70))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(25))
    
    canvas.paste(sh_layer, (ax - pad, ay - pad), sh_layer)
    canvas.paste(art_resized, (ax, ay), art_resized)
    
    # 2. Типографика (каталог Christie's / Taschen)
    draw = ImageDraw.Draw(canvas)
    
    # Верхний блок
    kicker = "НОВАЯ ПОДБОРКА  •  ТВОЯ КОЛЛЕКЦИЯ" if is_first else f"ЛОТ №{lot_num}  •  ТВОЯ КОЛЛЕКЦИЯ"
    draw.text((70, 175), kicker, fill=(185, 35, 30, 255), font=FONTS["edit_kicker"])
    draw.text((70, 218), artist, fill=(20, 22, 26, 255), font=FONTS["edit_artist"])
    
    # Тонкая графичная линия-акцент над нижним блоком
    draw.line([(70, 1405), (1010, 1405)], fill=(215, 210, 200, 255), width=2)
    
    # Нижний блок
    draw.text((70, 1435), f"«{title}»", fill=(50, 52, 58, 255), font=FONTS["edit_title"])
    draw.text((70, 1495), f"Старт: {price}", fill=(20, 22, 26, 255), font=FONTS["edit_price"])
    
    prefix = "Торги в Telegram: "
    draw.text((70, 1575), prefix, fill=(110, 115, 125, 255), font=FONTS["light_channel"])
    bbox = draw.textbbox((70, 1575), prefix, font=FONTS["light_channel"])
    draw.text((bbox[2], 1575), "@marinakhakimova_auction", fill=(185, 35, 30, 255), font=FONTS["light_channel_bold"])
    
    return canvas


def main():
    print("🎨 Генерация дизайн-вариантов оформления...")
    
    # Лоты для тестирования:
    # 1. Вертикальный лот №949 (Татьяна Романова - Ромашковое настроение)
    art1_path = ROOT_DIR / "assets" / "samples" / "sample_art_1.jpg"
    art1 = Image.open(art1_path).convert("RGBA")
    
    # 2. Горизонтальный лот №947 (Елена Смирнова - Пионы в хрустале)
    art3_path = ROOT_DIR / "assets" / "samples" / "sample_art_3.jpg"
    art3 = Image.open(art3_path).convert("RGBA")
    
    variants = [
        ("variant_1_light_gallery", "Вариант 1: Галерейный светлый (#EFEDEE)", render_variant_1_light_gallery),
        ("variant_2_adaptive_blur", "Вариант 2: Атмосферный умный блюр (Adaptive Blur)", render_variant_2_adaptive_blur),
        ("variant_3_studio_spotlight", "Вариант 3: Студийный спотлайт (Studio Spotlight)", render_variant_3_studio_spotlight),
        ("variant_4_warm_editorial", "Вариант 4: Премиум-каталог (Warm Editorial)", render_variant_4_warm_editorial),
    ]
    
    generated_files = []
    
    for code, title_name, renderer in variants:
        # Вертикальный вариант
        img_vert = renderer(
            art_img=art1,
            lot_num=949,
            artist="Татьяна Романова",
            title="Ромашковое настроение",
            price="15 000 ₽",
            is_first=False
        )
        fn_vert = f"{code}_vertical.png"
        out_vert = OUTPUT_DIR / fn_vert
        img_vert.save(out_vert, format="PNG")
        
        # Копируем в артефакты
        art_vert_path = ARTIFACTS_DIR / fn_vert
        img_vert.save(art_vert_path, format="PNG")
        
        # Горизонтальный вариант
        img_horiz = renderer(
            art_img=art3,
            lot_num=947,
            artist="Елена Смирнова",
            title="Пионы в хрустале",
            price="18 500 ₽",
            is_first=False
        )
        fn_horiz = f"{code}_horizontal.png"
        out_horiz = OUTPUT_DIR / fn_horiz
        img_horiz.save(out_horiz, format="PNG")
        
        # Копируем в артефакты
        art_horiz_path = ARTIFACTS_DIR / fn_horiz
        img_horiz.save(art_horiz_path, format="PNG")
        
        generated_files.append((code, title_name, fn_vert, fn_horiz))
        print(f"✅ Готово: {title_name}")
        
    print(f"\n✨ Все варианты сгенерированы в {OUTPUT_DIR} и скопированы в {ARTIFACTS_DIR}")

if __name__ == "__main__":
    main()
