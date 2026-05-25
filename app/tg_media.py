# app/tg_media.py
import os
import tempfile
from pathlib import Path
import requests
from typing import List
from dotenv import load_dotenv

load_dotenv()  # чтобы TG_BOT_TOKEN подтянулся из .env при локальном запуске

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
    session = requests.Session()

    for fid in file_ids:
        try:
            r = session.get(f"{API}/getFile", params={"file_id": fid}, timeout=15)
            if r.status_code != 200:
                continue  # пропускаем проблемный file_id
            file_path = r.json().get("result", {}).get("file_path")
            if not file_path:
                continue

            url = f"{FILE_API}/{file_path}"
            resp = session.get(url, timeout=30)
            if resp.status_code != 200 or not resp.content:
                continue

            out = tmpdir / Path(file_path).name
            out.write_bytes(resp.content)
            paths.append(out)
        except requests.RequestException:
            # сетевые проблемы — пропускаем конкретное фото
            continue

    return paths
