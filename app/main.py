# app/main.py
import os
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .models import RepostRequest, RepostResponse
from .tg_media import download_photos
from .vk_client import post as vk_post
from .utils import add_utm

# Загружаем .env для локальных запусков
load_dotenv()

SHARED = os.getenv("SHARED_SECRET", "")
VK_TOKEN = os.getenv("VK_USER_TOKEN") or os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

app = FastAPI(title="VK Reposter API", version="1.0.2")


def _auth(secret_header: str | None):
    if not SHARED:
        return True
    if not secret_header or secret_header != SHARED:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


def _require_env():
    token = os.getenv("VK_USER_TOKEN") or os.getenv("VK_TOKEN")
    group_id = os.getenv("VK_GROUP_ID")
    tg_token = os.getenv("TG_BOT_TOKEN")
    missing = []
    if not token:
        missing.append("VK_USER_TOKEN (or VK_TOKEN)")
    if not group_id:
        missing.append("VK_GROUP_ID")
    if not tg_token:
        missing.append("TG_BOT_TOKEN")
    if missing:
        raise HTTPException(status_code=500, detail=f"Missing env: {', '.join(missing)}")


@app.post("/repost", response_model=RepostResponse)
def repost(req: RepostRequest, x_reposter_secret: str | None = Header(default=None)):
    _auth(x_reposter_secret)
    _require_env()

    lot_url = add_utm(req.lot_url) if req.lot_url else None

    # Если header передан – используем его. Иначе дефолт без звёздочек.
    header = req.header or f"Аукцион №{req.auction_id} — {req.status}"

    msg = (
        f"{header}\n\n"
        f"{req.body}\n\n"
        f"Ссылка на лот: {lot_url or '-'}\n"
        f"#твояколлекция #аукцион #искусство #арт #art #купитькартину #красота #вдохновение #живопись"
    )

    photos = download_photos(req.photo_file_ids)
    vk_resp = vk_post(message=msg, image_paths=photos)

    return JSONResponse(
        content=RepostResponse(
            vk_post_id=vk_resp.get("post_id"),
            vk_owner_id=-int(os.getenv("VK_GROUP_ID", "0")),
            message="ok",
        ).dict()
    )
