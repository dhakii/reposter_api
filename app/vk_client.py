import os
import logging
from typing import Sequence, Optional
import requests
from vk_api import VkApi
from vk_api.upload import VkUpload

logger = logging.getLogger(__name__)


class VkRuSession(requests.Session):
    """
    Сессия с автоматической переадресацией api.vk.com -> api.vk.ru
    и защитным таймаутом, предотвращающим зависание на российских серверах.
    """
    def request(self, method, url, *args, **kwargs):
        if "api.vk.com" in url:
            url = url.replace("api.vk.com", "api.vk.ru")
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30
        return super().request(method, url, *args, **kwargs)


_cached_token = None
_vk = None
_upload = None


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
        _cached_token = token

    return _vk, _upload


def get_target_album_id(group_id: int, custom_album_id: Optional[int] = None) -> Optional[int]:
    """
    Определяет или создает альбом в сообществе для сохранения лотов аукциона.
    """
    if custom_album_id:
        return custom_album_id

    env_album = os.getenv("VK_ALBUM_ID")
    if env_album and env_album.strip():
        try:
            return int(env_album.strip())
        except ValueError:
            pass

    vk, _ = _get_vk_and_upload()
    try:
        albums_resp = vk.photos.getAlbums(owner_id=-group_id)
        items = albums_resp.get("items", [])

        # 1. Поиск альбома по ключевым словам
        for a in items:
            title_lower = (a.get("title") or "").lower()
            if any(k in title_lower for k in ("лот", "аукцион", "коллекци")):
                return a["id"]

        # 2. Поиск "Основной альбом"
        for a in items:
            title_lower = (a.get("title") or "").lower()
            if "основной" in title_lower:
                return a["id"]

        # 3. Первый доступный альбом
        if items:
            return items[0]["id"]

        # 4. Если альбомов нет, создаем новый
        new_album = vk.photos.createAlbum(
            title="Лоты аукциона «Твоя Коллекция»",
            group_id=group_id,
            description="Каталог лотов Telegram-аукциона @marinakhakimova_auction",
            upload_by_admins_only=1,
            comments_disabled=0,
        )
        return new_album.get("id")
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
        return []

    vk, upload = _get_vk_and_upload()
    try:
        uploaded = upload.photo(
            photos=list(map(str, image_paths)),
            album_id=album_id,
            group_id=group_id,
            caption=caption,
        )
        logger.info("Saved %d photo(s) to VK group album %s", len(uploaded), album_id)
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
    При включенном save_to_album также сохраняет работы в альбом группы.
    """
    group_id = int(os.getenv("VK_GROUP_ID", "0"))
    if not group_id:
        raise ValueError("VK_GROUP_ID is not configured")

    vk, upload = _get_vk_and_upload()

    # 1. Автоматическое сохранение в альбом группы (каталог)
    album_saved_photos = []
    if image_paths and save_to_album:
        album_saved_photos = save_photos_to_album(
            image_paths=image_paths,
            group_id=group_id,
            caption=album_caption,
            custom_album_id=custom_album_id,
        )

    # 2. Загрузка фото для публикации на стене
    attachments = None
    if image_paths:
        wall_photos = upload.photo_wall(list(map(str, image_paths)), group_id=group_id)
        attachments = ",".join(f"photo{p['owner_id']}_{p['id']}" for p in wall_photos)

    # 3. Публикация поста на стене сообщества
    post_res = vk.wall.post(
        owner_id=-group_id,
        from_group=1,
        message=message,
        attachments=attachments,
    )
    post_res["album_saved_count"] = len(album_saved_photos)
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
        # ВКонтакте поддерживает до 10 вложений к посту
        limited_paths = list(map(str, image_paths))[:10]
        photos = upload.photo_wall(limited_paths, group_id=group_id)
        attachments = ",".join(f"photo{p['owner_id']}_{p['id']}" for p in photos)

    return vk.wall.post(
        owner_id=-group_id,
        from_group=1,
        message=message,
        attachments=attachments,
    )
