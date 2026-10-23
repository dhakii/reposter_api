import os
import logging
import threading
from typing import Sequence, Optional
import requests
from vk_api import VkApi
from vk_api.upload import VkUpload

logger = logging.getLogger(__name__)


class VkRuSession(requests.Session):
    """
    Сессия с автоматической переадресацией api.vk.com / pu.vk.com -> api.vk.ru / pu.vk.ru
    и защитным таймаутом 20с, предотвращающим зависание на российских серверах.
    """
    def request(self, method, url, *args, **kwargs):
        if "api.vk.com" in url:
            url = url.replace("api.vk.com", "api.vk.ru")
        if "pu.vk.com" in url:
            url = url.replace("pu.vk.com", "pu.vk.ru")
        if "timeout" not in kwargs:
            kwargs["timeout"] = 20
        clean_url = url.split("?")[0]
        logger.info("VK HTTP %s %s (timeout=%s)", method, clean_url, kwargs.get("timeout"))
        return super().request(method, url, *args, **kwargs)


_cached_token = None
_vk = None
_upload = None
_cached_target_album_id = None


def _get_vk_and_upload():
    global _cached_token, _vk, _upload
    token = os.getenv("VK_USER_TOKEN") or os.getenv("VK_TOKEN")
    if not token:
        raise ValueError("Neither VK_USER_TOKEN nor VK_TOKEN is set in environment")

    if token != _cached_token or _vk is None or _upload is None:
        session = VkApi(token=token)
        session.http = VkRuSession()
        _vk = session.get_api()
        _upload = VkUpload(session)
        _upload.http = VkRuSession()
        _cached_token = token

    return _vk, _upload


def get_target_album_id(group_id: int, custom_album_id: Optional[int] = None) -> Optional[int]:
    """
    Определяет или создает альбом в сообществе для сохранения лотов аукциона.
    Кэширует ID альбома в памяти, чтобы не делать тяжелых запросов при каждом посте.
    """
    global _cached_target_album_id
    if custom_album_id:
        return custom_album_id

    if _cached_target_album_id:
        return _cached_target_album_id

    env_album = os.getenv("VK_ALBUM_ID")
    if env_album and env_album.strip():
        try:
            _cached_target_album_id = int(env_album.strip())
            return _cached_target_album_id
        except ValueError:
            pass

    # Дефолтный ID альбома для сообщества 232528016 ("Основной альбом")
    if group_id == 232528016:
        _cached_target_album_id = 309969339
        return _cached_target_album_id

    vk, _ = _get_vk_and_upload()
    try:
        logger.info("Checking VK albums for group -%d...", group_id)
        albums_resp = vk.photos.getAlbums(owner_id=-group_id)
        items = albums_resp.get("items", [])

        # 1. Поиск альбома по ключевым словам
        for a in items:
            title_lower = (a.get("title") or "").lower()
            if any(k in title_lower for k in ("лот", "аукцион", "коллекци")):
                _cached_target_album_id = a["id"]
                return _cached_target_album_id

        # 2. Поиск "Основной альбом"
        for a in items:
            title_lower = (a.get("title") or "").lower()
            if "основной" in title_lower:
                _cached_target_album_id = a["id"]
                return _cached_target_album_id

        # 3. Первый доступный альбом
        if items:
            _cached_target_album_id = items[0]["id"]
            return _cached_target_album_id

        # 4. Если альбомов нет, создаем новый
        new_album = vk.photos.createAlbum(
            title="Лоты аукциона «Твоя Коллекция»",
            group_id=group_id,
            description="Каталог лотов Telegram-аукциона @marinakhakimova_auction",
            upload_by_admins_only=1,
            comments_disabled=0,
        )
        _cached_target_album_id = new_album.get("id")
        return _cached_target_album_id
    except Exception as e:
        logger.warning("Could not determine or create VK album: %s", e)
        return None


def save_photos_to_album(
    image_paths: Sequence[str],
    group_id: int,
    caption: str = "",
    custom_album_id: Optional[int] = None,
) -> list[dict]:
    """
    Сохраняет фотографии в альбом сообщества с подписью.
    """
    if not image_paths:
        return []

    album_id = get_target_album_id(group_id, custom_album_id)
    if not album_id:
        logger.warning("No target album available, skipping album save")
        return []

    vk, upload = _get_vk_and_upload()
    try:
        logger.info("Uploading %d photo(s) to VK group album %s...", len(image_paths), album_id)
        uploaded = upload.photo(
            photos=list(map(str, image_paths)),
            album_id=album_id,
            group_id=group_id,
            caption=caption,
        )
        logger.info("Successfully saved %d photo(s) to VK group album %s", len(uploaded), album_id)
        return uploaded
    except Exception as e:
        logger.warning("Failed to save photos to VK album %s: %s", album_id, e)
        return []


def post(
    message: str,
    image_paths: Sequence[str] | None = None,
    save_to_album: bool = True,
    album_caption: str = "",
    custom_album_id: Optional[int] = None,
) -> dict:
    """
    Загружает фото на стену сообщества и публикует пост от имени группы.
    В первую очередь быстро публикует пост на стене, а сохранение фото в альбом
    выполняет в фоновом потоке, чтобы исключить таймауты Telegram-бота.
    """
    group_id = int(os.getenv("VK_GROUP_ID", "0"))
    if not group_id:
        raise ValueError("VK_GROUP_ID is not configured")

    vk, upload = _get_vk_and_upload()

    # 1. Загрузка фото для публикации на стене (быстро, 1-2 секунды)
    attachments = None
    if image_paths:
        logger.info("Uploading %d photo(s) to VK group wall...", len(image_paths))
        wall_photos = upload.photo_wall(list(map(str, image_paths)), group_id=group_id)
        attachments = ",".join(f"photo{p['owner_id']}_{p['id']}" for p in wall_photos)
        logger.info("Wall photos uploaded: attachments=%s", attachments)

    # 2. Публикация поста на стене сообщества
    logger.info("Publishing wall post from group_id=%d...", group_id)
    post_res = vk.wall.post(
        owner_id=-group_id,
        from_group=1,
        message=message,
        attachments=attachments,
    )
    logger.info("Wall post published successfully: post_id=%s", post_res.get("post_id"))

    # 3. Сохранение фото в альбом сообщества запускаем в фоне, не блокируя ответ боту
    if image_paths and save_to_album:
        def _bg_album_save():
            try:
                save_photos_to_album(
                    image_paths=image_paths,
                    group_id=group_id,
                    caption=album_caption,
                    custom_album_id=custom_album_id,
                )
            except Exception as exc:
                logger.warning("Background album save error: %s", exc)

        threading.Thread(target=_bg_album_save, daemon=True, name="vk-album-save").start()

    post_res["album_saved_count"] = len(image_paths) if (image_paths and save_to_album) else 0
    return post_res


def post_digest(message: str, image_paths: Sequence[str] | None = None) -> dict:
    """
    Публикует дайджест / подборку недели на стене сообщества.
    """
    group_id = int(os.getenv("VK_GROUP_ID", "0"))
    if not group_id:
        raise ValueError("VK_GROUP_ID is not configured")

    vk, upload = _get_vk_and_upload()

    attachments = None
    if image_paths:
        limited_paths = list(map(str, image_paths))[:10]
        logger.info("Uploading %d photo(s) for digest to VK group wall...", len(limited_paths))
        photos = upload.photo_wall(limited_paths, group_id=group_id)
        attachments = ",".join(f"photo{p['owner_id']}_{p['id']}" for p in photos)

    logger.info("Publishing digest wall post from group_id=%d...", group_id)
    return vk.wall.post(
        owner_id=-group_id,
        from_group=1,
        message=message,
        attachments=attachments,
    )
