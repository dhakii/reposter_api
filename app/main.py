# app/main.py
import os
import random
import logging
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .models import RepostRequest, RepostResponse, DigestRequest
from .tg_media import download_photos
from .vk_client import post as vk_post, post_digest as vk_post_digest
from .utils import add_utm

SHARED = os.getenv("SHARED_SECRET", "")
VK_TOKEN = os.getenv("VK_USER_TOKEN") or os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

app = FastAPI(title="VK Reposter API", version="1.1.1")


TEMPLATES = {
    "classic": (
        "{header}\n\n"
        "{body}\n\n"
        "Ссылка на лот: {lot_url}\n"
        "#твояколлекция #аукцион #искусство #арт #art #купитькартину #красота #вдохновение #живопись"
    ),
    "gallery": (
        "🏛 Новое поступление в коллекцию | Аукцион №{auction_id}\n\n"
        "{body}\n\n"
        "✨ Участвовать в торгах и следить за лотом:\n"
        "👉 {lot_url}\n\n"
        "#твояколлекция #аукцион #живопись #арт #картина #искусство #коллекция"
    ),
    "auction": (
        "🔨 Открыты торги по лоту №{auction_id} ({status})!\n\n"
        "{body}\n\n"
        "📌 Подробности, правила и текущая ставка доступны в Telegram:\n"
        "🔗 {lot_url}\n\n"
        "Успейте сделать ставку до завершения раунда!\n"
        "#аукцион #арт #картины #твояколлекция #купитькартину #art #живопись"
    ),
    "story": (
        "🎨 Прекрасная работа ищет свой новый дом.\n\n"
        "Аукцион №{auction_id} — {status}\n\n"
        "{body}\n\n"
        "Взгляните на детали и примите участие в торгах:\n"
        "✨ {lot_url}\n\n"
        "#твояколлекция #авторскаяживопись #искусствовдом #аукцион #картинамаслом"
    ),
    "compact": (
        "Лот №{auction_id} — {status}\n\n"
        "{body}\n\n"
        "Участие в торгах: {lot_url}\n\n"
        "#твояколлекция #аукцион"
    ),
}


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


def _format_post_message(req: RepostRequest, lot_url: str | None) -> str:
    url_str = str(lot_url) if lot_url else "-"
    header = req.header or f"Аукцион №{req.auction_id} — {req.status}"
    template_key = (req.template or "classic").lower().strip()

    if template_key in ("classic", "default", ""):
        return (
            f"{header}\n\n"
            f"{req.body}\n\n"
            f"Ссылка на лот: {url_str}\n"
            f"#твояколлекция #аукцион #искусство #арт #art #купитькартину #красота #вдохновение #живопись"
        )

    if template_key == "random":
        template_key = random.choice(["gallery", "auction", "story", "compact"])

    if template_key in TEMPLATES:
        return TEMPLATES[template_key].format(
            auction_id=req.auction_id,
            status=req.status,
            body=req.body,
            header=header,
            lot_url=url_str,
        )

    return (
        f"{header}\n\n"
        f"{req.body}\n\n"
        f"Ссылка на лот: {url_str}\n"
        f"#твояколлекция #аукцион #искусство #арт #art #купитькартину #красота #вдохновение #живопись"
    )


@app.post("/repost", response_model=RepostResponse)
def repost(req: RepostRequest, x_reposter_secret: str | None = Header(default=None)):
    logger.info(
        ">>> [START /repost] auction_id=%d, status='%s', photos=%d, template='%s', save_album=%s",
        req.auction_id,
        req.status,
        len(req.photo_file_ids),
        req.template,
        req.save_to_album,
    )
    _auth(x_reposter_secret)
    _require_env()

    lot_url_str = str(req.lot_url) if req.lot_url else None
    lot_url = add_utm(lot_url_str) if lot_url_str else None
    msg = _format_post_message(req, lot_url)

    photos = download_photos(req.photo_file_ids) if req.photo_file_ids else []

    album_caption = f"Лот №{req.auction_id} ({req.status})\n{lot_url or ''}".strip()
    save_album = True if req.save_to_album is None else bool(req.save_to_album)

    logger.info("Executing vk_post: message_len=%d, photos_count=%d, save_to_album=%s", len(msg), len(photos), save_album)
    vk_resp = vk_post(
        message=msg,
        image_paths=photos,
        save_to_album=save_album,
        album_caption=album_caption,
        custom_album_id=req.album_id,
    )
    logger.info(
        ">>> [FINISH /repost] auction_id=%d: vk_post_id=%s, album_saved=%s",
        req.auction_id,
        vk_resp.get("post_id"),
        vk_resp.get("album_saved_count"),
    )

    return JSONResponse(
        content=RepostResponse(
            vk_post_id=vk_resp.get("post_id"),
            vk_owner_id=-int(os.getenv("VK_GROUP_ID", "0")),
            message="ok",
            album_saved_count=vk_resp.get("album_saved_count", 0),
        ).dict()
    )


@app.post("/digest")
def create_digest(req: DigestRequest, x_reposter_secret: str | None = Header(default=None)):
    logger.info(">>> [START /digest] items=%d, title='%s'", len(req.items), req.title)
    _auth(x_reposter_secret)
    _require_env()

    intro = req.intro or (
        f"{req.title}\n\n"
        f"Друзья, представляем актуальные лоты нашего аукциона! "
        f"Каждая работа уникальна и доступна для участия в торгах в Telegram:\n"
    )

    items_text = []
    photo_file_ids = []
    for i, item in enumerate(req.items, 1):
        line = f"{i}️⃣ Лот №{item.auction_id}: {item.title}"
        if item.price:
            line += f" ({item.price})"
        if item.lot_url:
            line += f"\n👉 {item.lot_url}"
        items_text.append(line)
        if item.photo_file_id:
            photo_file_ids.append(item.photo_file_id)

    outro = req.outro or (
        "\nПрисоединяйтесь к торгах в нашем боте: https://t.me/marinakhakimova_auction\n"
        "#твояколлекция #аукцион #подборканедели #искусство #живопись #коллекция"
    )

    full_message = f"{intro}\n\n" + "\n\n".join(items_text) + f"\n\n{outro}"

    photos = download_photos(photo_file_ids) if photo_file_ids else []
    vk_resp = vk_post_digest(message=full_message, image_paths=photos)
    logger.info(">>> [FINISH /digest] vk_post_id=%s", vk_resp.get("post_id"))

    return JSONResponse(
        content={
            "vk_post_id": vk_resp.get("post_id"),
            "vk_owner_id": -int(os.getenv("VK_GROUP_ID", "0")),
            "message": "ok",
            "items_count": len(req.items),
        }
    )
