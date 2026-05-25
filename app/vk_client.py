import os
from typing import Sequence
from vk_api import VkApi
from vk_api.upload import VkUpload

# Предпочитаем пользовательский токен (vk1…)
VK_USER_TOKEN = os.getenv("VK_USER_TOKEN")
# Фоллбэк — старый токен сообщества (если вдруг захочешь использовать его)
VK_GROUP_TOKEN = os.getenv("VK_TOKEN")

VK_GROUP_ID = int(os.getenv("VK_GROUP_ID", "0"))

if VK_USER_TOKEN:
    _session = VkApi(token=VK_USER_TOKEN)  # user access_token с правами wall,photos,groups,offline
else:
    _session = VkApi(token=VK_GROUP_TOKEN) # fallback: group token

_vk = _session.get_api()
_upload = VkUpload(_session)


def post(message: str, image_paths: Sequence[str] | None = None) -> dict:
    """
    Загружает фото на стену сообщества и публикует пост.
    Работает и с user-token, и с group-token.
    Для user-token ставим from_group=1, чтобы пост шёл от имени сообщества.
    """
    attachments = None
    if image_paths:
        photos = _upload.photo_wall(list(map(str, image_paths)), group_id=VK_GROUP_ID)
        attachments = ",".join(f"photo{p['owner_id']}_{p['id']}" for p in photos)

    return _vk.wall.post(
        owner_id=-VK_GROUP_ID,
        from_group=1,                 # c user-token позволяет постить от лица сообщества
        message=message,
        attachments=attachments
    )
