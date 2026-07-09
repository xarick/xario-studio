from sqlalchemy import update
from sqlalchemy.orm import Session
from app.db.models.short import Short
from app.db.enums import ShortStatus
from app.modules.base_repository import BaseRepository


class ShortRepository(BaseRepository[Short]):
    model = Short

    def bulk_create(self, shorts: list[Short]) -> list[Short]:
        self.db.add_all(shorts)
        self.db.commit()
        # UUIDs are generated in Python, so we can fetch all in one query
        ids = [s.id for s in shorts]
        return (
            self.db.query(Short)
            .filter(Short.id.in_(ids))
            .order_by(Short.index_number)
            .all()
        )

    def get_by_video_id(self, video_id: str) -> list[Short]:
        return (
            self.db.query(Short)
            .filter(Short.video_id == video_id)
            .order_by(Short.index_number)
            .all()
        )

    def update_status(
        self,
        short_id: str,
        status: ShortStatus,
        file_path: str | None = None,
    ) -> None:
        values: dict = {"status": status}
        if file_path is not None:
            values["file_path"] = file_path
        self.db.execute(update(Short).where(Short.id == short_id).values(**values))
        self.db.commit()
