# app/video_engine/builder.py
"""
Движок сборки вертикального видео Reels/Shorts (1080x1920) из подборки картин.
Реализует спецификацию DESIGN_SYSTEM.md:
- Раздел 6: Dynamic Layout Engine (математика вертикального стека)
- Раздел 7.1: Хронометраж ролика (Интро 2.5с, 5 лотов по 4.0с, Аутро 2.5с = 25.0с)
- Раздел 7.2: Субпиксельный Ken Burns s(p) = 1.0 + 0.045 * (1 - cos(pi*p)) / 2
- Раздел 7.3: Плавное всплывание E(p) = 1 - (1 - p)^3 (pill dY=-22, card dY=+38)
- Сегментный рендеринг через in-memory пайпинг в FFmpeg (libx264 yuv420p)
- Нормализация звука EBU R128 (-14 LUFS) с fade-out 2.0с
"""

import os
import math
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from PIL import Image

from .overlays import (
    make_background_layer,
    render_upper_pill_component,
    render_bottom_card_component,
    render_intro_slide,
    render_outro_slide,
)
from .liquid_glass import render_floating_artwork
from .music_manager import MusicManager

W, H = 1080, 1920


class VideoBatchBuilder:
    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="reels_design_sys_"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.music_manager = MusicManager()

    def _render_artwork_segment_animated(
        self,
        art: Dict[str, Any],
        output_mp4: str,
        duration: float = 4.0,
        fps: int = 30,
        channel_link: str = "@marinakhakimova_auction",
    ) -> str:
        """
        Рендерит анимированный 4-секундный сегмент лота строго по разделам 6 и 7 DESIGN_SYSTEM.md:
        1. Dynamic Layout Engine:
           - H_pill = 52, G_top = 38, G_bottom = 40, H_card = 216
           - H_total = H_art + 346 px
           - Y_start = round((1920 - H_total) / 2) - 10
           - Y_pill = Y_start
           - Y_art = Y_start + 90 px
           - Y_card = Y_art + H_art + 40 px
        2. Ken Burns:
           s(p) = 1.0 + 0.045 * (1 - cos(pi * p)) / 2 (субпиксельный bicubic)
        3. Всплывание (0..0.55s):
           E(p) = 1 - (1 - p)^3
           pill: dY = -22 * (1 - E(p)), opacity = E(p)
           card: dY = +38 * (1 - E(p)), opacity = E(p)
        """
        src_path = art["image_path"]
        bg = make_background_layer(src_path)
        raw_art = Image.open(src_path)

        # 1. Парящее полотно с двойной тенью (max 940x1180, скругление 14px)
        art_canvas, (art_w, art_h), (pad_x, pad_y) = render_floating_artwork(
            raw_art, max_w=940, max_h=1180, corner_radius=14
        )

        # 2. Dynamic Layout Engine (Раздел 6)
        h_pill = 52
        g_top = 38
        g_bottom = 40
        h_card = 216
        h_total = art_h + 346

        y_start = int(round((H - h_total) / 2.0)) - 10
        y_pill = y_start
        y_art = y_start + 90
        y_card = y_art + art_h + 40

        # 3. Пре-рендеринг Liquid Glass компонентов
        pill_cropped, (px, py) = render_upper_pill_component(
            bg=bg,
            pill_y=y_pill,
            lot_num=art.get("lot_num", 1),
        )

        card_cropped, (cx, cy) = render_bottom_card_component(
            bg=bg,
            card_y=y_card,
            artist=art.get("artist", "Неизвестный автор"),
            title=art.get("title", "Без названия"),
            price=art.get("price", "По запросу"),
            channel_link=channel_link,
        )

        # 4. Потоковый рендеринг кадров в FFmpeg
        total_frames = int(fps * duration)
        anim_frames = int(fps * 0.55)  # 16 кадров на появление

        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgba",
            "-s", f"{W}x{H}",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "faster",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            output_mp4
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        cw, ch = art_canvas.size
        cx_pt, cy_pt = cw / 2.0, ch / 2.0
        art_base_x = int(round((W - art_w) / 2.0)) - pad_x
        art_base_y = y_art - pad_y

        for i in range(total_frames):
            # А. Синусоидальный Ken Burns (Раздел 7.2)
            p = i / float(total_frames - 1)
            scale = 1.0 + 0.045 * (1.0 - math.cos(math.pi * p)) / 2.0
            matrix = (1.0 / scale, 0, cx_pt * (1.0 - 1.0 / scale), 0, 1.0 / scale, cy_pt * (1.0 - 1.0 / scale))
            zoomed_art = art_canvas.transform(
                (cw, ch), Image.Transform.AFFINE, matrix, resample=Image.Resampling.BICUBIC
            )

            # Б. Сборка кадра
            frame = bg.copy()
            frame.paste(zoomed_art, (art_base_x, art_base_y), zoomed_art)

            # В. Анимация появления плашек (Раздел 7.3)
            if i < anim_frames:
                t_in = i / float(anim_frames)
                # E(p) = 1 - (1 - p)^3
                ease = 1.0 - (1.0 - t_in) ** 3.0

                # TopLotPill: dY = -22 * (1 - E(p))
                dy_pill = int(round(-22.0 * (1.0 - ease)))
                p_anim = pill_cropped.copy()
                if ease < 0.99:
                    pr, pg, pb, pa = p_anim.split()
                    pa = pa.point(lambda val: int(val * ease))
                    p_anim.putalpha(pa)
                frame.paste(p_anim, (px, py + dy_pill), p_anim)

                # LotInfoCard: dY = +38 * (1 - E(p))
                dy_card = int(round(38.0 * (1.0 - ease)))
                c_anim = card_cropped.copy()
                if ease < 0.99:
                    cr, cg, cb, ca = c_anim.split()
                    ca = ca.point(lambda val: int(val * ease))
                    c_anim.putalpha(ca)
                frame.paste(c_anim, (cx, cy + dy_card), c_anim)
            else:
                frame.paste(pill_cropped, (px, py), pill_cropped)
                frame.paste(card_cropped, (cx, cy), card_cropped)

            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        proc.wait()
        return output_mp4

    def _render_card_segment_animated(
        self,
        slide_image: Image.Image,
        output_mp4: str,
        duration: float = 2.5,
        fps: int = 30,
        fade_duration: float = 0.35,
    ) -> str:
        """
        Рендерит сегмент HeroModalCard (Интро или Аутро, 2.5с):
        - Плавный кинематографичный наезд фона (+2.5%)
        - Мягкий фейд на входе и выходе (0.35с)
        """
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
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            output_mp4
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        cx_pt, cy_pt = W / 2.0, H / 2.0
        fade_frames = int(fps * fade_duration)

        for i in range(total_frames):
            p = i / float(total_frames - 1)
            scale = 1.0 + 0.025 * (1.0 - math.cos(math.pi * p)) / 2.0
            matrix = (1.0 / scale, 0, cx_pt * (1.0 - 1.0 / scale), 0, 1.0 / scale, cy_pt * (1.0 - 1.0 / scale))
            zoomed = slide_image.transform(
                (W, H), Image.Transform.AFFINE, matrix, resample=Image.Resampling.BICUBIC
            )

            # Crossfade
            if i < fade_frames:
                alpha = i / float(fade_frames)
                zoomed = Image.blend(Image.new("RGBA", (W, H), (8, 10, 14, 255)), zoomed, alpha)
            elif i >= total_frames - fade_frames:
                alpha = (total_frames - 1 - i) / float(fade_frames)
                zoomed = Image.blend(Image.new("RGBA", (W, H), (8, 10, 14, 255)), zoomed, alpha)

            proc.stdin.write(zoomed.tobytes())

        proc.stdin.close()
        proc.wait()
        return output_mp4

    def build_batch_reels(
        self,
        artworks: List[Dict[str, Any]],
        output_file: str,
        batch_title: str = "5 картин на аукционе сейчас",
        channel_link: str = "@marinakhakimova_auction",
        slide_duration: float = 4.0,
        intro_duration: float = 2.5,
        outro_duration: float = 2.5,
        audio_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Собирает полный 25-секундный ролик строго по таймлайну раздела 7.1:
        0.0s – 2.5s: 01_intro
        2.5s – 6.5s: 02_lot_949
        6.5s – 10.5s: 03_lot_948
        10.5s – 14.5s: 04_lot_947
        14.5s – 18.5s: 05_lot_946
        18.5s – 22.5s: 06_lot_945
        22.5s – 25.0s: 07_outro
        Итого: ровно 25.0 секунд!
        """
        start_time = time.time()
        segments = []

        if not artworks:
            raise ValueError("Список картин artworks пуст")

        # 1. СЛАЙД 01_intro (2.5 сек)
        first_img = artworks[0]["image_path"]
        intro_slide = render_intro_slide(
            source_image_path=first_img,
            title=batch_title,
            subtitle="Твоя Коллекция  •  Ставки в Telegram",
        )
        intro_mp4 = self.work_dir / "seg_00_intro.mp4"
        self._render_card_segment_animated(
            slide_image=intro_slide,
            output_mp4=str(intro_mp4),
            duration=intro_duration,
            fade_duration=0.35,
        )
        segments.append(intro_mp4)

        # 2. СЛАЙДЫ ЛОТОВ 02..06 (по 4.0 сек)
        for i, art in enumerate(artworks, 1):
            seg_mp4 = self.work_dir / f"seg_{i:02d}_art.mp4"
            self._render_artwork_segment_animated(
                art=art,
                output_mp4=str(seg_mp4),
                duration=slide_duration,
                channel_link=channel_link,
            )
            segments.append(seg_mp4)

        # 3. СЛАЙД 07_outro (2.5 сек)
        last_img = artworks[-1]["image_path"]
        outro_slide = render_outro_slide(
            source_image_path=last_img,
            cta_title="Понравилась картина?",
            cta_subtitle="Участвуйте в торгах в Telegram",
            channel_link=channel_link,
        )
        outro_mp4 = self.work_dir / "seg_99_outro.mp4"
        self._render_card_segment_animated(
            slide_image=outro_slide,
            output_mp4=str(outro_mp4),
            duration=outro_duration,
            fade_duration=0.35,
        )
        segments.append(outro_mp4)

        # 4. СПИСОК СЕГМЕНТОВ ДЛЯ СКЛЕЙКИ
        concat_txt = self.work_dir / "concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for seg in segments:
                safe_path = str(seg).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        # 5. ПОДГОТОВКА ЗВУКОВОЙ ДОРОЖКИ (FreeToUse Royalty-Free MP3)
        total_duration = intro_duration + (len(artworks) * slide_duration) + outro_duration
        if not audio_file or not os.path.exists(audio_file):
            selected_track = self.music_manager.get_track()
            final_audio = str(selected_track)
        else:
            final_audio = str(audio_file)

        # 6. ФИНАЛЬНАЯ СКЛЕЙКА + НАЛОЖЕНИЕ ЗВУКА (-14 LUFS, fade-out 2.0c)
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

        # 7. Генерация обложки (на 3.8 секунде — центр показа первого лота)
        thumb_path = out_path.with_suffix(".jpg")
        thumb_cmd = [
            "ffmpeg", "-y",
            "-ss", f"{intro_duration + 1.2:.2f}",
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
            "soundtrack": Path(final_audio).name,
            "file_size_mb": round(out_path.stat().st_size / (1024 * 1024), 2),
        }
