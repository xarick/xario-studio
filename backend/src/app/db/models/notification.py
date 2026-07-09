from datetime import datetime
from sqlalchemy import String, Boolean, Integer, ForeignKey, Enum as SAEnum, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDMixin
from app.db.enums import NotificationType


class Notification(UUIDMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    shorts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    video_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
