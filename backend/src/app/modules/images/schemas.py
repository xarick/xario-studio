from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.db.enums import ImageStatus, ImageOperation


class ImageResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    original_filename: Optional[str] = None
    operation: ImageOperation
    status: ImageStatus
    progress_percent: int
    prompt: Optional[str] = None
    aspect_ratio: Optional[str] = None
    error_message: Optional[str] = None
    # Extension of the result file ("jpg", "png", "mp4"…). The geometry tools
    # keep the source format, so the client cannot infer it from `operation`.
    output_ext: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImageListResponse(BaseModel):
    items: list[ImageResponse]
    total: int
    page: int
    limit: int
    pages: int
