import os
from typing import Sequence
from vk_api import VkApi
from vk_api.upload import VkUpload

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
        _vk = session.get_api()
        _upload = VkUpload(session)
        _cached_token = token

    return _vk, _upload


def post(message: str, image_paths: Sequence[str] | None = None) -> dict:
    """
    Загружает фото на стену сообщества и публикует пост от имени группы.
    Требует пользовательский токен администратора группы (права wall, photos, groups, offline).
    """
    group_id = int(os.getenv("VK_GROUP_ID", "0"))
    if not group_id:
        raise ValueError("VK_GROUP_ID is not configured")

    vk, upload = _get_vk_and_upload()

    attachments = None
    if image_paths:
        photos = upload.photo_wall(list(map(str, image_paths)), group_id=group_id)
        attachments = ",".join(f"photo{p['owner_id']}_{p['id']}" for p in photos)

    return vk.wall.post(
        owner_id=-group_id,
        from_group=1,
        message=message,
        attachments=attachments
    )
