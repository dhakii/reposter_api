# app/video_engine/builder.py
"""
Движок сборки вертикального видео Reels/Shorts (1080x1920).
Поддерживает стили:
- «4a»: Премиум-каталог (красный бейдж со стартовой ценой, симметрия, полупрозрачный блюр)
- «4b»: Премиум-каталог (белая плашка с тонкой рамкой, симметрия, полупрозрачный блюр)
- «4c»: Премиум-каталог (крупная центрированная цена Sotheby's, полупрозрачный блюр)
- «2»: Атмосферный темный блюр-фон

Общие черты:
1. Мгновенный хук: старт сразу с 1-й картины (0-я секунда)
2. Текст СТАТИЧЕН (не зумируется и не дрожит, идеальная читаемость)
3. Полотно плавно оживает по центру (Ken Burns +3.5%) с глубокой музейной тенью
4. Финал: переход на фирменный светлый фон логотипа (#EFEDEE)
5. Роялти-фри саундтрек (-14 LUFS) с плавным затуханием
"""

import os
import math
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFilter

from .overlays import (
    make_semi_transparent_blurred_background,
    create_adaptive_ambient_background,
    make_editorial_typography_overlay,
    make_static_typography_overlay,
    render_brand_white_outro,
)
from .music_manager import MusicManager

W, H = 1080, 1920


class VideoBatchBuilder:
    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="reels_editorial_"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.music_manager = MusicManager()

    def _render_artwork_segment(
        self,
        art: Dict[str, Any],
        output_mp4: str,
        duration: float = 4.0,
        fps: int = 30,
        is_first_slide: bool = False,
        channel_link: str = "@marinakhakimova_auction",
        style_variant: str = "hybrid",
    ) -> str:
        """
        Рендерит сегмент произведения в заданном стиле (4a, 4b, 4c, 2).
        """
        src = Image.open(art["image_path"]).convert("RGBA")
        sw, sh = src.size

        # 1. Полноразмерное полотно с гармоничными пропорциями
        max_art_w = 960
        max_art_h = 1040
        scale = min(max_art_w / sw, max_art_h / sh)
        art_w = int(round(sw * scale))
        art_h = int(round(sh * scale))
        art_resized = src.resize((art_w, art_h), Image.Resampling.LANCZOS)

        # Центрирование картины в зоне Y=295..1435 (высота зоны 1140px)
        art_x = (W - art_w) // 2
        art_y = 295 + (1140 - art_h) // 2

        v = style_variant.lower()

        if v in ["hybrid", "4_hybrid", "4a", "4b", "4c"]:
            # Премиум-каталог: полупрозрачный блюр на светлом фоне
            opacity = 0.25 if v in ["hybrid", "4_hybrid", "4a"] else (0.30 if v == "4b" else 0.20)
            base_rgb = (246, 245, 241) if v in ["hybrid", "4_hybrid"] else ((245, 244, 240) if v == "4a" else ((248, 246, 242) if v == "4b" else (246, 244, 238)))
            base_bg = make_semi_transparent_blurred_background(src, art_opacity=opacity, base_rgb=base_rgb)

            # Музейная многослойная тень для светлой подложки
            pad = 60
            sh_canvas = Image.new("RGBA", (art_w + pad * 2, art_h + pad * 2), (0, 0, 0, 0))
            sdraw = ImageDraw.Draw(sh_canvas)
            sdraw.rectangle([pad, pad + 12, pad + art_w, pad + art_h + 12], fill=(25, 20, 15, 65))
            sdraw.rectangle([pad + 4, pad + 18, pad + art_w - 4, pad + art_h + 18], fill=(20, 15, 10, 85))
            sh_canvas = sh_canvas.filter(ImageFilter.GaussianBlur(28))

            art_with_shadow = Image.new("RGBA", (art_w + pad * 2, art_h + pad * 2), (0, 0, 0, 0))
            art_with_shadow.paste(sh_canvas, (0, 0), sh_canvas)
            art_with_shadow.paste(art_resized, (pad, pad), art_resized)

            typography_overlay = make_editorial_typography_overlay(
                lot_num=art.get("lot_num", 1),
                artist=art.get("artist", "Неизвестный автор"),
                title=art.get("title", "Без названия"),
                price=art.get("price", "По запросу"),
                variant=v,
                is_first_slide=is_first_slide,
                is_sold=art.get("is_sold", False),
                channel_link=channel_link,
            )
        else:
            # Вариант 2: Темный адаптивный блюр
            base_bg = create_adaptive_ambient_background(src, width=W, height=H)

            pad = 60
            sh_canvas = Image.new("RGBA", (art_w + pad * 2, art_h + pad * 2), (0, 0, 0, 0))
            sdraw = ImageDraw.Draw(sh_canvas)
            sdraw.rectangle([pad, pad + 10, pad + art_w - 1, pad + art_h + 10], fill=(0, 0, 0, 200))
            sh_canvas = sh_canvas.filter(ImageFilter.GaussianBlur(35))

            art_with_shadow = Image.new("RGBA", (art_w + pad * 2, art_h + pad * 2), (0, 0, 0, 0))
            art_with_shadow.paste(sh_canvas, (0, 0), sh_canvas)
            art_with_shadow.paste(art_resized, (pad, pad), art_resized)

            typography_overlay = make_static_typography_overlay(
                lot_num=art.get("lot_num", 1),
                artist=art.get("artist", "Неизвестный автор"),
                title=art.get("title", "Без названия"),
                price=art.get("price", "По запросу"),
                is_first_slide=is_first_slide,
                is_sold=art.get("is_sold", False),
                channel_link=channel_link,
            )

        total_frames = int(fps * duration)

        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgba",
            "-s", f"{W}x{H}",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "faster",
            "-crf", "19",
            "-pix_fmt", "yuv420p",
            output_mp4
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        cw, ch = art_with_shadow.size
        cx, cy = cw / 2.0, ch / 2.0
        dest_x = art_x - pad
        dest_y = art_y - pad

        last_frame = None
        for i in range(total_frames):
            p = i / float(total_frames - 1)
            # Плавный наезд Ken Burns (+3.5%)
            scale_val = 1.0 + 0.035 * (1.0 - math.cos(math.pi * p)) / 2.0
            matrix = (1.0 / scale_val, 0, cx * (1.0 - 1.0 / scale_val), 0, 1.0 / scale_val, cy * (1.0 - 1.0 / scale_val))
            zoomed_art = art_with_shadow.transform(
                (cw, ch), Image.Transform.AFFINE, matrix, resample=Image.Resampling.BICUBIC
            )

            frame = base_bg.copy()
            frame.paste(zoomed_art, (dest_x, dest_y), zoomed_art)
            frame.alpha_composite(typography_overlay)

            proc.stdin.write(frame.tobytes())
            if i == total_frames - 1:
                last_frame = frame.copy()

        proc.stdin.close()
        proc.wait()
        return output_mp4, last_frame

    def _render_outro_segment(
        self,
        output_mp4: str,
        duration: float = 3.0,
        fps: int = 30,
        channel_link: str = "@marinakhakimova_auction",
        prev_frame: Optional[Image.Image] = None,
        fade_out_duration: float = 0.40,
        pause_duration: float = 0.10,
        fade_in_duration: float = 0.50,
    ) -> str:
        """
        Рендерит финальный слайд с двухфазным переходом «Dip-to-White»:
        1. Картина мягко угасает в чистый светлый фон (#EFEDEE) без наложения текстов.
        2. Чистый белый экран (короткая пауза для чистоты восприятия).
        3. Из светлого фона плавно проявляется фирменный логотип и контакты аукциона.
        """
        outro_img = render_brand_white_outro(channel_link=channel_link)
        pure_white = Image.new("RGBA", (W, H), (239, 237, 238, 255))

        total_frames = int(fps * duration)
        fade_out_frames = int(fps * fade_out_duration)
        pause_frames = int(fps * pause_duration)
        fade_in_frames = int(fps * fade_in_duration)

        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgba",
            "-s", f"{W}x{H}",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "faster",
            "-crf", "19",
            "-pix_fmt", "yuv420p",
            output_mp4
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        cx, cy = W / 2.0, H / 2.0

        for i in range(total_frames):
            p = i / float(total_frames - 1)
            # Микро-зум логотипа 1.5%
            scale_val = 1.0 + 0.015 * (1.0 - math.cos(math.pi * p)) / 2.0
            matrix = (1.0 / scale_val, 0, cx * (1.0 - 1.0 / scale_val), 0, 1.0 / scale_val, cy * (1.0 - 1.0 / scale_val))
            zoomed = outro_img.transform(
                (W, H), Image.Transform.AFFINE, matrix, resample=Image.Resampling.BICUBIC
            )

            # Двухфазная анимация «Dip-to-White»:
            if prev_frame is not None and i < fade_out_frames:
                # Фаза 1: угасание предыдущей картины в чистый белый
                alpha = i / float(fade_out_frames)
                t = (1.0 - math.cos(alpha * math.pi)) / 2.0
                frame = Image.blend(prev_frame, pure_white, t)
            elif prev_frame is not None and i < (fade_out_frames + pause_frames):
                # Фаза 2: чистый белый экран (момент тишины и чистоты)
                frame = pure_white
            elif i < (fade_out_frames + pause_frames + fade_in_frames):
                # Фаза 3: плавное проявление логотипа и надписей из белого
                start_i = fade_out_frames + pause_frames if prev_frame is not None else 0
                idx = i - start_i
                alpha = min(max(idx / float(fade_in_frames), 0.0), 1.0)
                t = (1.0 - math.cos(alpha * math.pi)) / 2.0
                frame = Image.blend(pure_white, zoomed, t)
            else:
                # Фаза 4: стабильный показ аутро с легким живым дрейфом
                frame = zoomed

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        proc.wait()
        return output_mp4

    def build_batch_reels(
        self,
        artworks: List[Dict[str, Any]],
        output_file: str,
        channel_link: str = "@marinakhakimova_auction",
        slide_duration: float = 4.0,
        outro_duration: float = 3.0,
        audio_file: Optional[str] = None,
        style_variant: str = "hybrid",
    ) -> Dict[str, Any]:
        """
        Собирает видеоролик в заданном стиле:
        - Мгновенный хук (0.0с)
        - Слайды лотов по 4.0с
        - Финал на светлом фоне (#EFEDEE) 3.0с с двухфазным переходом (исчезновение в белый -> появление лого)
        """
        start_time = time.time()
        segments = []

        if not artworks:
            raise ValueError("Список картин artworks пуст")

        # 1. Сегменты картин (с 0.0 секунды)
        last_artwork_frame = None
        for i, art in enumerate(artworks, 1):
            seg_mp4 = self.work_dir / f"seg_{i:02d}_art.mp4"
            _, last_frame = self._render_artwork_segment(
                art=art,
                output_mp4=str(seg_mp4),
                duration=slide_duration,
                is_first_slide=(i == 1),
                channel_link=channel_link,
                style_variant=style_variant,
            )
            if i == len(artworks):
                last_artwork_frame = last_frame
            segments.append(seg_mp4)

        # 2. Финал на светлом фоне с мягким двухфазным переходом (Dip-to-White -> Fade-in Logo)
        outro_mp4 = self.work_dir / "seg_99_outro.mp4"
        self._render_outro_segment(
            output_mp4=str(outro_mp4),
            duration=outro_duration,
            channel_link=channel_link,
            prev_frame=last_artwork_frame,
            fade_out_duration=0.40,
            pause_duration=0.10,
            fade_in_duration=0.50,
        )
        segments.append(outro_mp4)

        # 3. Список сегментов для склейки
        concat_txt = self.work_dir / "concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for seg in segments:
                safe_path = str(seg).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        # 4. Музыка
        total_duration = (len(artworks) * slide_duration) + outro_duration
        if not audio_file or not os.path.exists(audio_file):
            selected_track = self.music_manager.get_track()
            final_audio = str(selected_track)
        else:
            final_audio = str(audio_file)

        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        audio_fade_start = max(0.0, total_duration - 2.0)
        af_filters = f"afade=t=in:st=0:d=0.5,afade=t=out:st={audio_fade_start}:d=2.0,loudnorm=I=-14:LRA=7:TP=-1.5"

        final_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-i", final_audio,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-af", af_filters,
            "-t", f"{total_duration:.2f}",
            str(out_path)
        ]

        final_res = subprocess.run(final_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if final_res.returncode != 0:
            raise RuntimeError(f"FFmpeg concat error: {final_res.stderr[-500:]}")

        thumb_path = out_path.with_suffix(".jpg")
        thumb_cmd = [
            "ffmpeg", "-y",
            "-ss", "00:00:02.00",
            "-i", str(out_path),
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_path)
        ]
        subprocess.run(thumb_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        render_time = round(time.time() - start_time, 2)
        return {
            "status": "success",
            "video_path": str(out_path),
            "thumbnail_path": str(thumb_path) if thumb_path.exists() else None,
            "duration": total_duration,
            "render_time_sec": render_time,
            "artworks_count": len(artworks),
            "style_variant": style_variant,
            "soundtrack": Path(final_audio).name,
            "file_size_mb": round(out_path.stat().st_size / (1024 * 1024), 2),
        }
