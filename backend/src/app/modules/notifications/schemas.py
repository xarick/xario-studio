from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.db.enums import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: NotificationType
    title: str
    shorts_count: int
    video_id: str | None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class UnreadCountResponse(BaseModel):
    count: int
