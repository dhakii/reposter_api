# app/main.py
import os
import random
import logging
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path

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

from .models import (
    RepostRequest,
    RepostResponse,
    DigestRequest,
    VideoCreateRequest,
    VideoCreateResponse,
    VideoPublishRequest,
    VideoPublishResponse,
)
from .tg_media import download_photos
from .vk_client import (
    post as vk_post,
    post_digest as vk_post_digest,
    upload_video_to_vk,
)
from .utils import add_utm
from .video_engine import VideoBatchBuilder, fetch_channel_lots

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

    caption_parts = [f"Лот №{req.auction_id}"]
    if req.body and req.body.strip():
        caption_parts.append(req.body.strip())
    if lot_url:
        caption_parts.append(f"Ссылка на лот: {lot_url}")
    album_caption = "\n\n".join(caption_parts).strip()
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


VIDEO_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/video/create", response_model=VideoCreateResponse)
def create_video(req: VideoCreateRequest, x_reposter_secret: str | None = Header(default=None)):
    """
    Генерирует вертикальный видеоролик (Reels / Shorts / Clips 1080x1920)
    в утвержденном аукционном стиле «Премиум-каталог»:
    - Если req.items передан: берет картины из запроса
    - Если req.items пуст или req.auto_fetch_channel=True: парсит актуальные картины напрямую из канала
    """
    logger.info(
        ">>> [START /video/create] auto_fetch=%s, items_len=%d, count=%d",
        req.auto_fetch_channel,
        len(req.items) if req.items else 0,
        req.count,
    )
    _auth(x_reposter_secret)

    artworks = []
    managed_dir = VIDEO_OUTPUT_DIR / "real_lots"
    managed_dir.mkdir(parents=True, exist_ok=True)

    # 1. Если включен авто-парсинг или список пуст
    if req.auto_fetch_channel or not req.items:
        scraped = fetch_channel_lots(
            channel_url=f"https://t.me/s/{req.channel_link.lstrip('@')}" if req.channel_link else "https://t.me/s/marinakhakimova_auction",
            max_count=req.count or 5,
            download_dir=managed_dir,
        )
        for s in scraped:
            artworks.append({
                "lot_num": s["lot_num"],
                "artist": s["artist"],
                "title": s["title"],
                "price": s["price"],
                "is_sold": s.get("is_sold", False),
                "image_path": s.get("image_path"),
            })
    else:
        # 2. Берем картины из переданного списка
        for item in req.items:
            img_path = item.image_path
            if not img_path or not Path(img_path).exists():
                if item.photo_file_id:
                    downloaded = download_photos([item.photo_file_id])
                    if downloaded:
                        img_path = str(downloaded[0])
                elif item.photo_url:
                    dest = managed_dir / f"lot_{item.lot_num}.jpg"
                    from .video_engine.scraper import download_photo
                    if download_photo(str(item.photo_url), dest):
                        img_path = str(dest)

            if img_path and Path(img_path).exists():
                artworks.append({
                    "lot_num": item.lot_num,
                    "artist": item.artist,
                    "title": item.title,
                    "price": item.price,
                    "is_sold": item.is_sold,
                    "image_path": img_path,
                })

    if not artworks:
        raise HTTPException(
            status_code=400,
            detail="Не удалось получить изображения полотен для генерации видео. Проверьте фото или канал."
        )

    # Уникальное имя выходного файла
    import uuid
    uid = uuid.uuid4().hex[:8]
    out_name = f"reels_digest_{uid}.mp4"
    out_file = VIDEO_OUTPUT_DIR / out_name

    builder = VideoBatchBuilder()
    result = builder.build_batch_reels(
        artworks=artworks,
        output_file=str(out_file),
        channel_link=req.channel_link or "@marinakhakimova_auction",
        slide_duration=req.slide_duration or 4.0,
        outro_duration=req.outro_duration or 3.0,
        style_variant=req.style_variant or "hybrid",
    )

    download_url = f"/video/download/{out_name}"
    logger.info(">>> [FINISH /video/create] file=%s, duration=%.1fs, render_time=%.1fs", out_name, result["duration"], result["render_time_sec"])

    return JSONResponse(
        content={
            "status": "success",
            "video_path": result["video_path"],
            "thumbnail_path": result.get("thumbnail_path"),
            "duration": result["duration"],
            "render_time_sec": result["render_time_sec"],
            "file_size_mb": result["file_size_mb"],
            "artworks_count": len(artworks),
            "soundtrack": result.get("soundtrack", ""),
            "download_url": download_url,
            "lots": [
                {
                    "lot_num": a["lot_num"],
                    "artist": a["artist"],
                    "title": a["title"],
                    "price": a["price"],
                }
                for a in artworks
            ],
        }
    )


@app.get("/video/download/{filename}")
def download_video(filename: str):
    """
    Отдает сгенерированный mp4 файл для скачивания или стриминга.
    """
    safe_filename = Path(filename).name
    file_path = VIDEO_OUTPUT_DIR / safe_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Видеофайл не найден")
    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=safe_filename,
    )


@app.get("/video/latest")
def get_latest_video():
    """
    Возвращает информацию о последнем сгенерированном ролике.
    """
    mp4_files = sorted(VIDEO_OUTPUT_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not mp4_files:
        raise HTTPException(status_code=404, detail="Нет сгенерированных видео")
    latest = mp4_files[0]
    return {
        "filename": latest.name,
        "path": str(latest),
        "size_mb": round(latest.stat().st_size / (1024 * 1024), 2),
        "download_url": f"/video/download/{latest.name}",
    }


@app.post("/video/publish", response_model=VideoPublishResponse)
def publish_video(req: VideoPublishRequest, x_reposter_secret: str | None = Header(default=None)):
    """
    Публикует сгенерированное вертикальное видео в VK Клипы / Видеозаписи группы ВКонтакте
    и (опционально) создает пост на стене сообщества.
    """
    _auth(x_reposter_secret)

    token = os.getenv("VK_USER_TOKEN") or os.getenv("VK_TOKEN")
    group_id = os.getenv("VK_GROUP_ID")
    if not token or not group_id:
        raise HTTPException(
            status_code=500,
            detail="VK_USER_TOKEN или VK_GROUP_ID не настроены в окружении сервера."
        )

    # Определяем файл для загрузки
    target_path = None
    if req.video_path and Path(req.video_path).exists():
        target_path = Path(req.video_path)
    elif req.filename:
        p = VIDEO_OUTPUT_DIR / Path(req.filename).name
        if p.exists():
            target_path = p

    if not target_path:
        # Берем самый свежий ролик
        mp4_files = sorted(VIDEO_OUTPUT_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
        if mp4_files:
            target_path = mp4_files[0]

    if not target_path or not target_path.exists():
        raise HTTPException(status_code=404, detail="Файл видео для публикации не найден.")

    logger.info(">>> [START /video/publish] file=%s, wall=%s", target_path.name, req.post_to_wall)
    try:
        res = upload_video_to_vk(
            video_path=target_path,
            title=req.title,
            description=req.description,
            post_to_wall=True if req.post_to_wall is None else bool(req.post_to_wall),
            group_id=int(group_id),
        )
        logger.info(">>> [FINISH /video/publish] video_id=%s, post_id=%s", res.get("video_id"), res.get("post_id"))
        return JSONResponse(content=res)
    except Exception as exc:
        logger.error("Failed to publish video to VK: %s", exc)
        raise HTTPException(status_code=500, detail=f"Ошибка публикации в VK: {exc}")
