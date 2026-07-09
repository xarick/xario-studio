from sqlalchemy import Boolean, Text, Integer, Float, String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin, TimestampMixin
from app.db.enums import VideoSourceType, VideoStatus, GenerationMode


class Video(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "videos"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_type: Mapped[VideoSourceType] = mapped_column(SAEnum(VideoSourceType), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    shorts_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    subtitles_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    subtitle_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # subtitle mode: user-supplied text to align
    transcript_segments: Mapped[str | None] = mapped_column(Text, nullable=True)  # transcribe mode: JSON [{start,end,text}]
    tts_voice: Mapped[str | None] = mapped_column(String(64), nullable=True)  # tts/dub: built-in XTTS speaker ("" = clone original)
    dub_target_language: Mapped[str | None] = mapped_column(String(8), nullable=True)  # dub mode: language to translate into
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # edit/tool modes: JSON of operation params
    generation_mode: Mapped[GenerationMode] = mapped_column(
        SAEnum(GenerationMode, native_enum=False, length=16),
        nullable=False,
        default=GenerationMode.smart,
    )
    status: Mapped[VideoStatus] = mapped_column(
        SAEnum(VideoStatus), nullable=False, default=VideoStatus.pending
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    shorts: Mapped[list["Short"]] = relationship(
        "Short", back_populates="video", cascade="all, delete-orphan"
    )
