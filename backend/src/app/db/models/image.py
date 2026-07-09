import os

from sqlalchemy import Text, String, ForeignKey, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDMixin, TimestampMixin
from app.db.enums import ImageStatus, ImageOperation


class Image(UUIDMixin, TimestampMixin, Base):
    """A single image-processing job (upload → operation → output file)."""
    __tablename__ = "images"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)     # uploaded source
    input_paths: Mapped[str | None] = mapped_column(Text, nullable=True)           # image_to_shorts: JSON list of source images
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)                # text_to_image: the generation prompt
    aspect_ratio: Mapped[str | None] = mapped_column(String(8), nullable=True)     # text_to_image: "1:1" | "9:16" | …
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)           # crop/resize/convert: JSON of tool params
    output_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)   # processed result
    operation: Mapped[ImageOperation] = mapped_column(
        SAEnum(ImageOperation, native_enum=False, length=16), nullable=False
    )
    status: Mapped[ImageStatus] = mapped_column(
        SAEnum(ImageStatus, native_enum=False, length=16),
        nullable=False, default=ImageStatus.pending,
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def output_ext(self) -> str | None:
        """Extension of the produced file, without the dot.

        The geometry tools keep the source format, so the client cannot guess it
        from the operation — a cropped JPEG comes back as a JPEG.
        """
        if not self.output_path:
            return None
        return os.path.splitext(self.output_path)[1].lstrip(".").lower() or None
