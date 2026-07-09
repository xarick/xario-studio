from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundError
from app.db.models.short import Short
from app.modules.shorts.repository import ShortRepository
from app.modules.videos.repository import VideoRepository


class ShortService:
    def __init__(self, db: Session) -> None:
        self.repo = ShortRepository(db)
        self.video_repo = VideoRepository(db)

    def list_by_video(self, video_id: str, owner_id: str | None = None) -> list[Short]:
        video = self.video_repo.get_by_id(video_id)
        if not video or (owner_id is not None and video.user_id != owner_id):
            raise NotFoundError(f"Video {video_id} not found")
        return self.repo.get_by_video_id(video_id)

    def get_short(self, short_id: str, owner_id: str | None = None) -> Short:
        short = self.repo.get_by_id(short_id)
        if not short:
            raise NotFoundError(f"Short {short_id} not found")
        # A short is owned by whoever owns its parent video.
        if owner_id is not None:
            video = self.video_repo.get_by_id(short.video_id)
            if not video or video.user_id != owner_id:
                raise NotFoundError(f"Short {short_id} not found")
        return short
