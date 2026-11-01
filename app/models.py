from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional

class RepostRequest(BaseModel):
    auction_id: int = Field(..., ge=1)
    status: str = Field(default="Активен", min_length=1)
    body: str = Field(..., min_length=1)
    lot_url: Optional[HttpUrl] = None
    photo_file_ids: List[str] = []
    header: Optional[str] = None
    template: Optional[str] = "classic"     # "classic", "random", "gallery", "auction", "story", "compact"
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


class VideoLotItem(BaseModel):
    lot_num: int = Field(..., ge=1)
    artist: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    price: str = Field(default="По запросу")
    is_sold: Optional[bool] = False
    photo_file_id: Optional[str] = None
    photo_url: Optional[str] = None
    image_path: Optional[str] = None


class VideoCreateRequest(BaseModel):
    items: Optional[List[VideoLotItem]] = None
    auto_fetch_channel: Optional[bool] = False
    count: Optional[int] = Field(default=5, ge=1, le=10)
    channel_link: Optional[str] = "@marinakhakimova_auction"
    slide_duration: Optional[float] = Field(default=4.0, ge=2.0, le=10.0)
    outro_duration: Optional[float] = Field(default=3.0, ge=1.5, le=8.0)
    style_variant: Optional[str] = "hybrid"


class VideoCreateResponse(BaseModel):
    status: str
    video_path: str
    thumbnail_path: Optional[str] = None
    duration: float
    render_time_sec: float
    file_size_mb: float
    artworks_count: int
    soundtrack: str
    download_url: Optional[str] = None
    lots: List[dict] = []


class VideoPublishRequest(BaseModel):
    filename: Optional[str] = None
    video_path: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    post_to_wall: Optional[bool] = True


class VideoPublishResponse(BaseModel):
    status: str
    video_id: Optional[int] = None
    owner_id: Optional[int] = None
    post_id: Optional[int] = None
    direct_link: Optional[str] = None
