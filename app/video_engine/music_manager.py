# app/video_engine/music_manager.py
"""
Менеджер фоновой роялти-фри музыки для видеороликов.
Поддерживает локальный кэш треков в assets/audio, а также загрузку через FreeToUse Music API.
Все треки лицензированы для коммерческого и некоммерческого использования в соцсетях без копирайт-страйков.
"""

import os
import random
import urllib.request
import json
from pathlib import Path
from typing import Optional, List

AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "audio"

# Рекомендуемые проверенные категории в FreeToUse API
MOOD_CATEGORIES = {
    "calm": "78b17c21-bfb1-90ae-5240-e59d82c5ef3a",
    "classical": "e8eb326e-cb23-408f-e6cf-e7a5ab10e197",
    "ambient": "b5bc7541-bdc2-d42a-3986-572fddd29753",
    "chill": "91ca6cf0-08d4-0e57-e024-2fd0e1413327",
}


class MusicManager:
    """Управление аудиотреками для Reels/Shorts."""

    def __init__(self, audio_dir: Optional[Path] = None):
        self.audio_dir = Path(audio_dir) if audio_dir else AUDIO_DIR
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def list_local_tracks(self) -> List[Path]:
        """Возвращает список всех локально сохраненных MP3/WAV треков."""
        tracks = list(self.audio_dir.glob("*.mp3")) + list(self.audio_dir.glob("*.wav"))
        return [t for t in tracks if t.stat().st_size > 50000]

    def get_track(self, preferred_filename: Optional[str] = None) -> Path:
        """
        Возвращает путь к аудиофайлу.
        Если указан preferred_filename и он существует, возвращает его.
        Иначе выбирает случайный из локальной библиотеки.
        """
        if preferred_filename:
            target = self.audio_dir / preferred_filename
            if target.exists() and target.stat().st_size > 50000:
                return target

        local_tracks = self.list_local_tracks()
        if local_tracks:
            return random.choice(local_tracks)

        # Если локальных треков нет, скачиваем базовый трек из API
        downloaded = self.download_featured_track(category="calm")
        if downloaded:
            return downloaded

        raise FileNotFoundError(f"Нет доступных аудиофайлов в {self.audio_dir}")

    def download_featured_track(self, category: str = "calm") -> Optional[Path]:
        """Скачивает один трек из указанной категории FreeToUse API."""
        cat_id = MOOD_CATEGORIES.get(category, MOOD_CATEGORIES["calm"])
        api_url = f"https://api.freetouse.com/v3/music/categories/{cat_id}/tracks"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AuctionBot/1.0"}

        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            tracks_data = data.get("data", [])
            if not tracks_data:
                return None

            # Выбираем случайный трек
            track_info = random.choice(tracks_data[:10])
            mp3_url = track_info.get("files", {}).get("mp3")
            if not mp3_url:
                return None

            clean_title = "".join(c if c.isalnum() else "_" for c in track_info.get("title", "track")).lower()
            out_file = self.audio_dir / f"{category}_{clean_title}.mp3"

            req_mp3 = urllib.request.Request(mp3_url, headers=headers)
            with urllib.request.urlopen(req_mp3, timeout=20) as resp_mp3, open(out_file, "wb") as f:
                f.write(resp_mp3.read())

            return out_file
        except Exception as e:
            print(f"⚠️ Ошибка загрузки музыки из API: {e}")
            return None
