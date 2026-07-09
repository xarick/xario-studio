"""Pipeline outcome tests for the shorts-cutting loop.

These cover what the pure-function tests can't: what the job row and the owner's
notification look like when some — or all — of the shorts fail to render.
"""
import subprocess

import pytest

from app.core.config import settings
from app.db.enums import (
    GenerationMode, NotificationType, ShortStatus, VideoSourceType, VideoStatus,
)
from app.db.models.notification import Notification
from app.db.models.short import Short
from app.db.models.user import User
from app.db.models.video import Video
from app.workers import ffmpeg, video_processor
from app.workers.ffmpeg import VideoMeta


@pytest.fixture
def video(db, admin: User, tmp_path, monkeypatch) -> Video:
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setattr(ffmpeg, "probe", lambda _p: VideoMeta(duration=300.0, width=1920, height=1080))

    row = Video(
        user_id=admin.id,
        source_type=VideoSourceType.upload,
        original_filename="clip.mp4",
        file_path=str(tmp_path / "clip.mp4"),
        shorts_requested=2,
        subtitles_enabled=False,
        generation_mode=GenerationMode.simple,
        status=VideoStatus.pending,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _shorts(db, video_id: str) -> list[Short]:
    return db.query(Short).filter(Short.video_id == video_id).order_by(Short.index_number).all()


def _notifications(db, video_id: str) -> list[Notification]:
    return db.query(Notification).filter(Notification.video_id == video_id).all()


def test_all_shorts_failing_fails_the_video(db, video, monkeypatch):
    """Every short failed → nothing is downloadable, so the job is not a success."""
    def boom(*_a, **_kw):
        raise ffmpeg.MediaError("encoder exploded")

    monkeypatch.setattr(video_processor.ffmpeg, "concat_clips_as_short", boom)

    video_processor.process_video(video.id)

    db.expire_all()
    row = db.get(Video, video.id)
    assert row.status is VideoStatus.failed
    assert "encoder exploded" in (row.error_message or "")
    assert [s.status for s in _shorts(db, video.id)] == [ShortStatus.failed] * 2

    notes = _notifications(db, video.id)
    assert [n.type for n in notes] == [NotificationType.job_failed]


def test_encode_timeout_fails_the_video_and_notifies(db, video, monkeypatch):
    """A watchdog timeout is a MediaError now, not an uncaught SubprocessError."""
    def timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=600)

    monkeypatch.setattr(video_processor.ffmpeg, "concat_clips_as_short", timeout)

    video_processor.process_video(video.id)

    db.expire_all()
    assert db.get(Video, video.id).status is VideoStatus.failed
    assert [n.type for n in _notifications(db, video.id)] == [NotificationType.job_failed]


def test_partial_failure_completes_with_the_real_count(db, video, monkeypatch):
    """One short rendered → the job succeeds, but reports 1 short, not 2."""
    calls: list[dict] = []

    def half(_src, out_file, clips, subtitle_path=None, on_progress=None):
        calls.append({"clips": clips, "on_progress": on_progress})
        if len(calls) == 1:
            open(out_file, "w").close()
            return
        raise ffmpeg.MediaError("second short failed")

    monkeypatch.setattr(video_processor.ffmpeg, "concat_clips_as_short", half)

    video_processor.process_video(video.id)

    db.expire_all()
    assert db.get(Video, video.id).status is VideoStatus.completed
    assert [s.status for s in _shorts(db, video.id)] == [
        ShortStatus.completed, ShortStatus.failed,
    ]

    notes = _notifications(db, video.id)
    assert [n.type for n in notes] == [NotificationType.job_completed]
    assert notes[0].shorts_count == 1

    # Each short reports live encode progress inside its own band.
    assert all(callable(c["on_progress"]) for c in calls)


def test_progress_reporter_stays_inside_its_band(db, video):
    report = video_processor._progress_reporter(
        video_processor.VideoRepository(db), video.id, lo=40, hi=69,
    )
    report(0.0)
    db.expire_all()
    assert db.get(Video, video.id).progress_percent == 40

    report(1.0)
    db.expire_all()
    assert db.get(Video, video.id).progress_percent == 69

    report(2.0)  # out-of-range fractions are clamped, never written past `hi`
    db.expire_all()
    assert db.get(Video, video.id).progress_percent == 69
