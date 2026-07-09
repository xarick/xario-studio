"""Which queue a job belongs on.

Both video and image jobs enter Celery through the same two tasks, so the task
*name* says nothing about cost: a 5-second GIF and a one-hour dub are both
`process_video_task`. With a single queue the dub blocks the GIF for an hour.

Cost is decided by the generation mode, so the queue is chosen when the job is
enqueued. Run one worker per queue to keep the cheap lane moving:

    celery -A app.core.celery_app:celery_app worker -Q media   # ffmpeg, seconds
    celery -A app.core.celery_app:celery_app worker -Q heavy   # ML, minutes

A worker started with `-Q media,heavy` (what `make worker` does) drains both, so
single-process development is unchanged.
"""
from app.core.config import settings
from app.db.enums import GenerationMode

# Modes that load an ML model — whisper, XTTS or Demucs — costing gigabytes of
# RAM/VRAM and minutes of runtime. The rest are plain ffmpeg transforms.
HEAVY_MODES = frozenset({
    GenerationMode.smart,       # whisper, for speech-density scoring
    GenerationMode.pro,         # whisper + per-frame reframing analysis
    GenerationMode.subtitle,    # whisper, for forced alignment
    GenerationMode.transcribe,
    GenerationMode.separate,
    GenerationMode.tts,
    GenerationMode.dub,
})


def queue_for(mode: GenerationMode | None, subtitles_enabled: bool = False) -> str:
    """The queue a video job belongs on.

    Burning subtitles onto a `simple` cut still runs whisper, so that job is as
    heavy as a smart one despite its mode.
    """
    if mode in HEAVY_MODES or subtitles_enabled:
        return settings.CELERY_QUEUE_HEAVY
    return settings.CELERY_QUEUE_MEDIA


def enqueue_video(video) -> None:
    """Send a freshly-created video job to the queue that matches its cost.

    The row id doubles as the Celery task id, so a job can be revoked later
    without storing a separate task id alongside it.
    """
    from app.workers.tasks import process_video_task

    queue = queue_for(video.generation_mode, bool(video.subtitles_enabled))
    process_video_task.apply_async(args=[video.id], task_id=video.id, queue=queue)


def enqueue_image(image) -> None:
    """Image ops are all short — they share the cheap lane."""
    from app.workers.tasks import process_image_task

    process_image_task.apply_async(args=[image.id], task_id=image.id,
                                   queue=settings.CELERY_QUEUE_MEDIA)


def revoke(job_id: str) -> None:
    """Stop a queued job from ever starting. Never raises — a broker that is
    down must not block the caller from marking the row terminal."""
    from app.core.celery_app import celery_app

    try:
        celery_app.control.revoke(job_id)
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("Could not revoke job %s: %s", job_id, exc)
