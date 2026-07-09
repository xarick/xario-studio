"""Startup reconciliation for orphaned jobs.

A job in an *active* state (a worker was mid-pipeline) cannot survive a process
restart: its in-memory progress is gone and, with acks_late disabled, the task
is not redelivered. Such rows would otherwise sit at "processing" forever.

On startup we mark every actively-running job as failed with a clear message so
the user can simply resubmit. Jobs still in `pending` are left untouched — they
are queued in Redis and a worker will pick them up.

Jobs a *live* worker is currently running are excluded: with more than one worker
(`docker compose up -d --scale worker=2`) a booting worker would otherwise fail
the job its sibling is halfway through.
"""
import logging

from sqlalchemy import update

from app.db.enums import ImageStatus, VideoStatus
from app.db.models.image import Image
from app.db.models.video import Video
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_MESSAGE = "Interrupted by a server restart — please resubmit."
_INSPECT_TIMEOUT = 2.0

# Active (non-terminal, in-flight) states that cannot survive a restart.
_VIDEO_STUCK = (VideoStatus.downloading, VideoStatus.processing)
_IMAGE_STUCK = (ImageStatus.processing,)


def active_job_ids() -> set[str]:
    """Job ids currently being executed by any live worker.

    Returns an empty set when the broker cannot be inspected — a single worker
    healing itself after a crash matters more than the rare multi-worker race,
    and the failure is logged.
    """
    from app.core.celery_app import celery_app

    try:
        active = celery_app.control.inspect(timeout=_INSPECT_TIMEOUT).active() or {}
    except Exception as exc:  # noqa: BLE001 — broker down, no workers, …
        logger.warning("Could not inspect active tasks (%s) — reconciling everything", exc)
        return set()

    ids: set[str] = set()
    for tasks in active.values():
        for task in tasks or []:
            args = task.get("args") or []
            if args:
                ids.add(str(args[0]))
    if ids:
        logger.info("Skipping %d job(s) still running on a live worker", len(ids))
    return ids


def reconcile_stuck_jobs(exclude_ids: set[str] | None = None) -> int:
    """Fail any video/image job left mid-flight by a previous run. Returns the
    number of rows reset. Never raises — reconciliation must not block startup."""
    skip = exclude_ids if exclude_ids is not None else active_job_ids()
    db = SessionLocal()
    try:
        total = 0
        total += _reset(db, Video, _VIDEO_STUCK, VideoStatus.failed, skip)
        total += _reset(db, Image, _IMAGE_STUCK, ImageStatus.failed, skip)
        if total:
            logger.warning("Reconciled %d stuck job(s) from a previous run", total)
        return total
    except Exception:
        logger.exception("Stuck-job reconciliation failed (continuing startup)")
        db.rollback()
        return 0
    finally:
        db.close()


def _reset(db, model, stuck_states, failed_state, skip: set[str]) -> int:
    stmt = update(model).where(model.status.in_(stuck_states))
    if skip:
        stmt = stmt.where(model.id.notin_(skip))
    result = db.execute(stmt.values(status=failed_state, error_message=_MESSAGE))
    db.commit()
    return result.rowcount or 0
