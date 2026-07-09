"""Celery task definitions.

Thin wrappers around the existing pipeline entry points. Each pipeline already
opens and closes its own DB session and reports success/failure into the job
row, so the task only needs to forward the id. Endpoints enqueue work with
e.g. `process_video_task.delay(video_id)`.
"""
import logging

from celery.signals import worker_ready

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@worker_ready.connect
def _reconcile_on_start(**_kwargs) -> None:
    """When the worker boots, fail any job a previous worker left mid-flight.
    Runs here (not on web startup) because the worker is the only thing that
    processes jobs — a restart of the web API must not touch a job a healthy
    worker is still running."""
    from app.workers.reconcile import reconcile_stuck_jobs

    reconcile_stuck_jobs()


@celery_app.task(name="app.workers.tasks.process_video_task")
def process_video_task(video_id: str) -> None:
    # Imported lazily so the heavy worker modules (torch, whisper, …) are only
    # loaded inside the worker, never in the web process that enqueues.
    from app.workers.video_processor import process_video

    logger.info("Picked up video job %s", video_id)
    process_video(video_id)


@celery_app.task(name="app.workers.tasks.process_image_task")
def process_image_task(image_id: str) -> None:
    from app.workers.image_processor import process_image

    logger.info("Picked up image job %s", image_id)
    process_image(image_id)
