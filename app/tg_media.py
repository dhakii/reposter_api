# app/tg_media.py
import os
import logging
import tempfile
from pathlib import Path
import requests
from typing import List

logger = logging.getLogger(__name__)

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
    """
    paths: List[Path] = []
    if not file_ids:
        return paths

    if not TG_BOT_TOKEN or not API or not FILE_API:
        logger.warning("TG_BOT_TOKEN is missing, skipping Telegram photo download")
        return paths

    tmpdir = Path(tempfile.mkdtemp(prefix="reposter_"))
    logger.info("Downloading %d photo(s) from Telegram...", len(file_ids))

    for i, fid in enumerate(file_ids, 1):
        if not fid:
            continue
        try:
            logger.info("[%d/%d] Fetching file info from Telegram for fid=%s...", i, len(file_ids), fid[:16])
            res = requests.get(f"{API}/getFile", params={"file_id": fid}, timeout=10)
            if res.status_code != 200:
                logger.error("[%d/%d] getFile failed (status=%s): %s", i, len(file_ids), res.status_code, res.text)
                continue
            data = res.json()
            if not data.get("ok"):
                logger.error("[%d/%d] getFile response not ok: %s", i, len(file_ids), data)
                continue

            file_path = data["result"]["file_path"]

            logger.info("[%d/%d] Downloading photo content from %s...", i, len(file_ids), file_path)
            res_file = requests.get(f"{FILE_API}/{file_path}", timeout=15)
            if res_file.status_code != 200:
                logger.error("[%d/%d] Photo download failed (status=%s)", i, len(file_ids), res_file.status_code)
                continue

            ext = Path(file_path).suffix or ".jpg"
            target = tmpdir / f"{fid}{ext}"
            target.write_bytes(res_file.content)
            logger.info("[%d/%d] Photo saved to %s (%d bytes)", i, len(file_ids), target.name, len(res_file.content))
            paths.append(target)
        except Exception as e:
            logger.exception("[%d/%d] Failed to download photo fid=%s: %s", i, len(file_ids), fid[:16], e)
            continue

    logger.info("Finished downloading %d/%d photos", len(paths), len(file_ids))
    return paths
