"""Celery application — the background job queue.

Heavy media/ML pipelines (video processing, transcription, separation, TTS,
dubbing, image ops) are enqueued here and executed by a separate worker process
(`make worker`), so they never block the FastAPI web process.

Reliability choices:
- prefetch_multiplier=1 + concurrency from settings → one long job at a time per
  worker child, no job is "reserved" behind another that's still running.
- acks_late=False → if a worker crashes mid-job the task is NOT redelivered;
  instead the row is left in a non-terminal state and the startup reconcile
  (app.workers.reconcile) marks it failed so the user can resubmit. This keeps
  behaviour deterministic and avoids half-finished media being reprocessed.
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "xario_studio",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_ignore_result=True,
    # Jobs are routed per-submission by workers.queues.enqueue_* — the task name
    # doesn't reveal cost. Anything enqueued without a queue lands on `media`.
    task_default_queue=settings.CELERY_QUEUE_MEDIA,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.WORKER_CONCURRENCY,
    task_acks_late=False,
    broker_connection_retry_on_startup=True,
    # Dev: execute inline (no broker/worker needed) when enabled.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
)
