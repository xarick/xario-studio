from sqlalchemy import update, desc, func, case, select
from sqlalchemy.orm import Session
from app.db.models.video import Video
from app.db.models.short import Short
from app.db.enums import VideoStatus, ShortStatus, GenerationMode
from app.modules.base_repository import BaseRepository


class VideoRepository(BaseRepository[Video]):
    model = Video

    def list_paginated(
        self,
        page: int,
        limit: int,
        search: str | None = None,
        status: VideoStatus | None = None,
        modes: list[GenerationMode] | None = None,
        owner_id: str | None = None,
    ) -> tuple[list[Video], int]:
        query = self.db.query(Video)
        if owner_id is not None:
            query = query.filter(Video.user_id == owner_id)
        if search:
            like = f"%{search}%"
            query = query.filter(
                Video.original_filename.ilike(like) | Video.source_url.ilike(like)
            )
        if status is not None:
            query = query.filter(Video.status == status)
        if modes:
            query = query.filter(Video.generation_mode.in_(modes))
        query = query.order_by(desc(Video.created_at))
        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        return items, total

    def get_stats(self, owner_id: str | None = None) -> dict:
        status_q = self.db.query(Video.status, func.count(Video.id))
        if owner_id is not None:
            status_q = status_q.filter(Video.user_id == owner_id)
        status_counts = status_q.group_by(Video.status).all()
        counts = {s.value: c for s, c in status_counts}

        shorts_q = (
            self.db.query(func.count(Short.id))
            .filter(Short.status == ShortStatus.completed)
        )
        if owner_id is not None:
            shorts_q = shorts_q.join(Video, Short.video_id == Video.id).filter(Video.user_id == owner_id)
        total_shorts = shorts_q.scalar() or 0

        processing_statuses = {VideoStatus.processing.value, VideoStatus.downloading.value, VideoStatus.pending.value}

        return {
            "total_videos": sum(counts.values()),
            "total_shorts": total_shorts,
            "completed": counts.get(VideoStatus.completed.value, 0),
            "processing": sum(counts.get(s, 0) for s in processing_statuses),
            "failed": counts.get(VideoStatus.failed.value, 0),
        }

    def update_status(
        self,
        video_id: str,
        status: VideoStatus,
        progress: int | None = None,
        error_message: str | None = None,
    ) -> None:
        values: dict = {"status": status}
        if progress is not None:
            values["progress_percent"] = progress
        if error_message is not None:
            values["error_message"] = error_message
        self.db.execute(update(Video).where(Video.id == video_id).values(**values))
        self.db.commit()

    # A job that has already reached a terminal state must never be dragged back
    # into `processing` by a progress tick from an encode that is still winding
    # down — that would silently undo a cancel.
    _LIVE_STATES = (VideoStatus.pending, VideoStatus.downloading, VideoStatus.processing)

    def update_progress(self, video_id: str, progress: int) -> None:
        self.db.execute(
            update(Video)
            .where(Video.id == video_id, Video.status.in_(self._LIVE_STATES))
            .values(status=VideoStatus.processing, progress_percent=progress)
        )
        self.db.commit()

    def current_status(self, video_id: str) -> VideoStatus | None:
        """Re-read the status from the database, bypassing the identity map, so a
        long-running worker can notice a cancel that another process wrote."""
        return self.db.execute(
            select(Video.status).where(Video.id == video_id)
        ).scalar_one_or_none()

    def update_file_info(self, video_id: str, file_path: str, duration_seconds: float) -> None:
        self.db.execute(
            update(Video)
            .where(Video.id == video_id)
            .values(file_path=file_path, duration_seconds=duration_seconds)
        )
        self.db.commit()

    def save_transcript(self, video_id: str, text: str, segments_json: str) -> None:
        self.db.execute(
            update(Video)
            .where(Video.id == video_id)
            .values(transcript_text=text, transcript_segments=segments_json)
        )
        self.db.commit()
