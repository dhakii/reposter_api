from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional

class RepostRequest(BaseModel):
    auction_id: int = Field(..., ge=1)
    status: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    lot_url: Optional[HttpUrl] = None
    photo_file_ids: List[str] = []
    header: Optional[str] = None     # ← новое поле

class RepostResponse(BaseModel):
    vk_post_id: int
    vk_owner_id: int
    message: str
