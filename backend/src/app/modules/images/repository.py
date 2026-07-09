from sqlalchemy import update, desc, select
from app.db.models.image import Image
from app.db.enums import ImageStatus
from app.modules.base_repository import BaseRepository


class ImageRepository(BaseRepository[Image]):
    model = Image

    def current_status(self, image_id: str) -> ImageStatus | None:
        """Re-read the status from the database, bypassing the identity map, so a
        running worker can notice a cancel written by another process."""
        return self.db.execute(
            select(Image.status).where(Image.id == image_id)
        ).scalar_one_or_none()

    def list_paginated(
        self, page: int, limit: int, status: ImageStatus | None = None,
        owner_id: str | None = None,
    ) -> tuple[list[Image], int]:
        query = self.db.query(Image)
        if owner_id is not None:
            query = query.filter(Image.user_id == owner_id)
        if status is not None:
            query = query.filter(Image.status == status)
        query = query.order_by(desc(Image.created_at))
        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        return items, total

    def update_status(
        self,
        image_id: str,
        status: ImageStatus,
        progress: int | None = None,
        error_message: str | None = None,
    ) -> None:
        values: dict = {"status": status}
        if progress is not None:
            values["progress_percent"] = progress
        if error_message is not None:
            values["error_message"] = error_message
        self.db.execute(update(Image).where(Image.id == image_id).values(**values))
        self.db.commit()

    def set_output(self, image_id: str, output_path: str) -> None:
        self.db.execute(update(Image).where(Image.id == image_id).values(output_path=output_path))
        self.db.commit()
