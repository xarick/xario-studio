from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from app.core.config import settings
from app.db.enums import VideoStatus, VideoSourceType, GenerationMode


class VideoSubmitURL(BaseModel):
    url: str
    shorts_count: int
    subtitles_enabled: bool = True
    subtitle_language: Optional[str] = None   # "" / None = auto-detect
    generation_mode: GenerationMode = GenerationMode.smart
    transcript_text: Optional[str] = None     # subtitle mode: text to align

    @field_validator("shorts_count")
    @classmethod
    def shorts_count_range(cls, v: int) -> int:
        if not (1 <= v <= settings.MAX_SHORTS_COUNT):
            raise ValueError(f"shorts_count must be between 1 and {settings.MAX_SHORTS_COUNT}")
        return v

    @field_validator("url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url cannot be empty")
        return v


class VideoResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    source_type: VideoSourceType
    source_url: Optional[str] = None
    original_filename: Optional[str] = None
    duration_seconds: Optional[float] = None
    shorts_requested: int
    subtitles_enabled: bool = True
    subtitle_language: Optional[str] = None
    generation_mode: GenerationMode = GenerationMode.smart
    status: VideoStatus
    progress_percent: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    items: list[VideoResponse]
    total: int
    page: int
    limit: int
    pages: int


class VideoStatsResponse(BaseModel):
    total_videos: int
    total_shorts: int
    completed: int
    processing: int
    failed: int


class VideoAnalyzeRequest(BaseModel):
    url: str


class VideoAnalyzeResponse(BaseModel):
    suggested_count: int
    reason: str
    duration: float | None = None


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptResponse(BaseModel):
    video_id: str
    status: VideoStatus
    filename: Optional[str] = None
    text: str = ""
    segments: list[TranscriptSegment] = []
