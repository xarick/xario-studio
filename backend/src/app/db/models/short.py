from datetime import datetime
from sqlalchemy import String, Float, Integer, ForeignKey, Enum as SAEnum, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin
from app.db.enums import ShortStatus


class Short(UUIDMixin, Base):
    __tablename__ = "shorts"

    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    index_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    clips_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[ShortStatus] = mapped_column(
        SAEnum(ShortStatus), nullable=False, default=ShortStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    video: Mapped["Video"] = relationship("Video", back_populates="shorts")
