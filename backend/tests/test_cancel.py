"""Cancelling a job: the worker must notice, and must not be resurrected."""
import pytest

from app.core.exceptions import ValidationError
from app.db.enums import (
    GenerationMode, ShortStatus, VideoSourceType, VideoStatus,
)
from app.db.models.short import Short
from app.db.models.user import User
from app.db.models.video import Video
from app.modules.videos.repository import VideoRepository
from app.modules.videos.service import VideoService
from app.workers import video_processor
from app.workers.ffmpeg import VideoMeta
from app.workers.video_processor import JobCancelled


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    from app.workers import queues
    monkeypatch.setattr(queues, "revoke", lambda _id: None)


def _video(db, admin: User, status=VideoStatus.processing) -> Video:
    v = Video(
        user_id=admin.id,
        source_type=VideoSourceType.upload,
        original_filename="clip.mp4",
        shorts_requested=2,
        subtitles_enabled=False,
        generation_mode=GenerationMode.simple,
        status=status,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def test_cancel_marks_the_job_terminal_with_a_clear_reason(db, admin):
    video = _video(db, admin, VideoStatus.pending)

    VideoService(db).cancel_video(video.id, admin.id)

    db.expire_all()
    row = db.get(Video, video.id)
    assert row.status is VideoStatus.failed
    assert row.error_message == VideoService.CANCEL_MESSAGE


def test_cancelling_a_finished_job_is_rejected(db, admin):
    video = _video(db, admin, VideoStatus.completed)
    with pytest.raises(ValidationError):
        VideoService(db).cancel_video(video.id, admin.id)


def test_a_progress_tick_cannot_resurrect_a_cancelled_job(db, admin):
    """The encode keeps running for a moment after a cancel; its progress
    callback must not drag the row back into `processing`."""
    video = _video(db, admin)
    repo = VideoRepository(db)

    repo.update_progress(video.id, 50)
    db.expire_all()
    assert db.get(Video, video.id).status is VideoStatus.processing

    VideoService(db).cancel_video(video.id, admin.id)
    repo.update_progress(video.id, 60)          # a late tick from the encoder

    db.expire_all()
    row = db.get(Video, video.id)
    assert row.status is VideoStatus.failed
    assert row.progress_percent == 50           # the late tick was ignored


def test_the_pipeline_stops_at_the_next_short_after_a_cancel(db, admin, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.workers import ffmpeg

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setattr(ffmpeg, "probe", lambda _p: VideoMeta(duration=300.0, width=1920, height=1080))

    video = _video(db, admin, VideoStatus.pending)
    video.file_path = str(tmp_path / "clip.mp4")
    db.commit()

    cut = []

    def cut_one(_src, out_file, clips, subtitle_path=None, on_progress=None):
        cut.append(out_file)
        open(out_file, "w").close()
        # The user cancels while the first short is being encoded.
        VideoService(db).cancel_video(video.id, admin.id)

    monkeypatch.setattr(video_processor.ffmpeg, "concat_clips_as_short", cut_one)

    video_processor.process_video(video.id)

    assert len(cut) == 1, "the second short must never start"
    db.expire_all()
    row = db.get(Video, video.id)
    assert row.status is VideoStatus.failed
    assert row.error_message == VideoService.CANCEL_MESSAGE   # not overwritten
    # The first short did finish; the second was never touched.
    shorts = db.query(Short).filter(Short.video_id == video.id).order_by(Short.index_number).all()
    assert [s.status for s in shorts] == [ShortStatus.completed, ShortStatus.pending]


def test_raise_if_cancelled_fires_when_the_row_disappears(db, admin):
    """A deleted row means the job is gone; the worker must not carry on."""
    video = _video(db, admin)
    repo = VideoRepository(db)
    db.delete(video)
    db.commit()

    with pytest.raises(JobCancelled):
        video_processor._raise_if_cancelled(repo, video.id)


def test_deleting_an_active_job_cancels_it_first(db, admin, tmp_path, monkeypatch):
    """Ripping the output directory out from under a running encode is a race."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))

    video = _video(db, admin, VideoStatus.processing)
    cancelled = []
    real_cancel = VideoService.cancel_video
    monkeypatch.setattr(VideoService, "cancel_video",
                        lambda self, vid, owner=None: (cancelled.append(vid),
                                                       real_cancel(self, vid, owner))[1])

    VideoService(db).delete_video(video.id, admin.id)

    assert cancelled == [video.id]
    assert db.get(Video, video.id) is None


# ── Image jobs ───────────────────────────────────────────────────────────────
def _image(db, admin, status):
    from app.db.enums import ImageOperation, ImageStatus
    from app.db.models.image import Image

    i = Image(user_id=admin.id, operation=ImageOperation.image_to_shorts,
              original_filename="a.png", status=status)
    db.add(i)
    db.commit()
    db.refresh(i)
    return i


def test_deleting_a_running_image_job_cancels_it_first(db, admin, tmp_path, monkeypatch):
    """The real-world failure: deleting a running slideshow ripped its output
    directory away and left an orphaned ffmpeg spinning at 100% CPU."""
    from app.core.config import settings
    from app.db.enums import ImageStatus
    from app.db.models.image import Image
    from app.modules.images.service import ImageService

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    image = _image(db, admin, ImageStatus.processing)
    revoked: list[str] = []
    from app.workers import queues
    monkeypatch.setattr(queues, "revoke", lambda i: revoked.append(i))

    ImageService(db).delete_image(image.id, admin.id)

    assert revoked == [image.id]
    assert db.get(Image, image.id) is None


def test_a_cancelled_image_job_discards_its_result(db, admin, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.db.enums import ImageStatus
    from app.db.models.image import Image
    from app.modules.images.service import ImageService
    from app.workers import image_processor

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    image = _image(db, admin, ImageStatus.pending)

    def slow_handler(_img, output_dir):
        out = str(tmp_path / "short.mp4")
        open(out, "w").close()
        ImageService(db).cancel_image(image.id, admin.id)   # cancelled mid-run
        return out

    monkeypatch.setitem(image_processor._OPERATIONS, image.operation, slow_handler)

    image_processor.process_image(image.id)

    db.expire_all()
    row = db.get(Image, image.id)
    assert row.status is ImageStatus.failed
    assert row.error_message == ImageService.CANCEL_MESSAGE   # not overwritten
    assert row.output_path is None                            # stale result dropped
