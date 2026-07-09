"""Startup reconciliation fails mid-flight jobs, leaves queued ones alone."""
import pytest

from app.db.enums import (
    GenerationMode,
    ImageOperation,
    ImageStatus,
    VideoSourceType,
    VideoStatus,
)
from app.db.models.image import Image
from app.db.models.video import Video
from app.workers import reconcile
from app.workers.reconcile import active_job_ids, reconcile_stuck_jobs


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    """Never let a test reach the real broker to ask who is busy."""
    monkeypatch.setattr(reconcile, "active_job_ids", lambda: set())


def _video(db, status):
    v = Video(
        source_type=VideoSourceType.upload,
        shorts_requested=1,
        generation_mode=GenerationMode.smart,
        status=status,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _image(db, status):
    i = Image(operation=ImageOperation.bg_remove, status=status)
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


def test_reconcile_fails_active_jobs(db):
    downloading = _video(db, VideoStatus.downloading)
    processing = _video(db, VideoStatus.processing)
    img = _image(db, ImageStatus.processing)

    reset = reconcile_stuck_jobs()
    assert reset == 3

    for obj in (downloading, processing, img):
        db.refresh(obj)
    assert downloading.status == VideoStatus.failed
    assert processing.status == VideoStatus.failed
    assert img.status == ImageStatus.failed
    assert downloading.error_message


def test_reconcile_leaves_pending_and_terminal(db):
    pending = _video(db, VideoStatus.pending)
    completed = _video(db, VideoStatus.completed)
    failed = _video(db, VideoStatus.failed)
    img_pending = _image(db, ImageStatus.pending)

    reset = reconcile_stuck_jobs()
    assert reset == 0

    for obj in (pending, completed, failed, img_pending):
        db.refresh(obj)
    assert pending.status == VideoStatus.pending
    assert completed.status == VideoStatus.completed
    assert failed.status == VideoStatus.failed
    assert img_pending.status == ImageStatus.pending


def test_a_job_running_on_a_live_worker_is_left_alone(db):
    """A second worker booting must not fail the job its sibling is running."""
    mine = _video(db, VideoStatus.processing)
    theirs = _video(db, VideoStatus.processing)

    reset = reconcile_stuck_jobs(exclude_ids={theirs.id})
    assert reset == 1

    db.refresh(mine)
    db.refresh(theirs)
    assert mine.status == VideoStatus.failed
    assert theirs.status == VideoStatus.processing


def test_active_job_ids_reads_the_first_arg_of_every_running_task(monkeypatch):
    class _Inspect:
        def active(self):
            return {
                "worker@a": [{"name": "process_video_task", "args": ["vid-1"]}],
                "worker@b": [{"name": "process_image_task", "args": ["img-9"]}],
                "worker@c": None,
            }

    from app.core import celery_app as celery_mod
    monkeypatch.setattr(celery_mod.celery_app.control, "inspect", lambda **_kw: _Inspect())
    assert active_job_ids() == {"vid-1", "img-9"}


def test_active_job_ids_is_empty_when_the_broker_cannot_be_reached(monkeypatch):
    from app.core import celery_app as celery_mod

    def boom(**_kw):
        raise OSError("broker down")

    monkeypatch.setattr(celery_mod.celery_app.control, "inspect", boom)
    assert active_job_ids() == set()
