from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional

class RepostRequest(BaseModel):
    auction_id: int = Field(..., ge=1)
    status: str = Field(default="Активен", min_length=1)
    body: str = Field(..., min_length=1)
    lot_url: Optional[HttpUrl] = None
    photo_file_ids: List[str] = []
    header: Optional[str] = None
    template: Optional[str] = "random"     # "random", "gallery", "auction", "story", "compact"
    save_to_album: Optional[bool] = True   # автоматически сохранять фото в альбом группы
    album_id: Optional[int] = None         # опциональный ID конкретного альбома

class RepostResponse(BaseModel):
    vk_post_id: int
    vk_owner_id: int
    message: str
    album_saved_count: Optional[int] = 0

class DigestItem(BaseModel):
    auction_id: int
    title: str
    price: Optional[str] = None
    lot_url: Optional[HttpUrl] = None
    photo_file_id: Optional[str] = None

class DigestRequest(BaseModel):
    title: Optional[str] = "🎨 Подборка недели | Аукцион «Твоя Коллекция»"
    intro: Optional[str] = None
    items: List[DigestItem] = []
    outro: Optional[str] = None
