# app/tg_media.py
import os
import tempfile
from pathlib import Path
import requests
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
API = f"https://api.telegram.org/bot{TG_BOT_TOKEN}" if TG_BOT_TOKEN else None
FILE_API = f"https://api.telegram.org/file/bot{TG_BOT_TOKEN}" if TG_BOT_TOKEN else None


def download_photos(file_ids: List[str]) -> List[Path]:
    """
    Скачивает изображения по file_id во временную папку.
    Если TG_BOT_TOKEN отсутствует или конкретный file_id недоступен —
    пропускаем такие фото и продолжаем (вернём текстовый пост без части медиа).
    """
    paths: List[Path] = []
    if not file_ids:
        return paths

    if not TG_BOT_TOKEN or not API or not FILE_API:
        # Нет токена — возвращаем пустой список, чтобы пост хотя бы с текстом ушёл
        return paths

    tmpdir = Path(tempfile.mkdtemp(prefix="reposter_"))
    for fid in file_ids:
        if not fid:
            continue
        try:
            # 1. getFile -> file_path
            res = requests.get(f"{API}/getFile", params={"file_id": fid}, timeout=20)
            if res.status_code != 200:
                continue
            data = res.json()
            if not data.get("ok"):
                continue

            file_path = data["result"]["file_path"]

            # 2. download content
            res_file = requests.get(f"{FILE_API}/{file_path}", timeout=30)
            if res_file.status_code != 200:
                continue

            # 3. save to local temp file
            ext = Path(file_path).suffix or ".jpg"
            target = tmpdir / f"{fid}{ext}"
            target.write_bytes(res_file.content)
            paths.append(target)
        except Exception:
            # Не валим весь процесс, если одна картинка сбойнула
            continue

    return paths
