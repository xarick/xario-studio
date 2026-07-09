"""Job routing: ML work must not share a lane with plain ffmpeg transforms."""
from app.core.config import settings
from app.db.enums import GenerationMode
from app.workers.queues import HEAVY_MODES, queue_for


def test_ml_modes_go_to_the_heavy_lane():
    for mode in (GenerationMode.dub, GenerationMode.tts, GenerationMode.separate,
                 GenerationMode.transcribe, GenerationMode.smart, GenerationMode.pro,
                 GenerationMode.subtitle):
        assert queue_for(mode) == settings.CELERY_QUEUE_HEAVY, mode


def test_plain_ffmpeg_modes_stay_on_the_cheap_lane():
    for mode in (GenerationMode.tool, GenerationMode.edit,
                 GenerationMode.cleanup, GenerationMode.simple):
        assert queue_for(mode) == settings.CELERY_QUEUE_MEDIA, mode


def test_subtitles_make_a_simple_cut_heavy():
    """Burning subtitles runs whisper, whatever the mode says."""
    assert queue_for(GenerationMode.simple) == settings.CELERY_QUEUE_MEDIA
    assert queue_for(GenerationMode.simple, subtitles_enabled=True) == settings.CELERY_QUEUE_HEAVY


def test_every_mode_is_classified():
    """A new mode must be triaged deliberately, not silently land on `media`."""
    light = set(GenerationMode) - set(HEAVY_MODES)
    assert light == {
        GenerationMode.simple, GenerationMode.cleanup,
        GenerationMode.edit, GenerationMode.tool,
    }


def test_enqueue_uses_the_queue_for_the_mode(monkeypatch):
    from app.workers import queues, tasks

    sent: list[dict] = []
    monkeypatch.setattr(tasks.process_video_task, "apply_async",
                        lambda **kw: sent.append(kw))

    class _Video:
        id = "v1"
        generation_mode = GenerationMode.dub
        subtitles_enabled = False

    queues.enqueue_video(_Video())
    # The row id doubles as the Celery task id so the job can be revoked later.
    assert sent == [{"args": ["v1"], "task_id": "v1", "queue": settings.CELERY_QUEUE_HEAVY}]


def test_enqueue_image_is_revocable_by_its_row_id(monkeypatch):
    from app.workers import queues, tasks

    sent: list[dict] = []
    monkeypatch.setattr(tasks.process_image_task, "apply_async",
                        lambda **kw: sent.append(kw))

    class _Image:
        id = "i1"

    queues.enqueue_image(_Image())
    assert sent == [{"args": ["i1"], "task_id": "i1", "queue": settings.CELERY_QUEUE_MEDIA}]
