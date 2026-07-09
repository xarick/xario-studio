"""Storage hygiene — reclaim disk from finished/orphaned jobs.

Two safe rules, so we never touch anything still in use:

  * UPLOAD_DIR: a source upload is only needed *while* its job runs. We delete
    upload files older than the retention window that are NOT referenced by any
    still-active (pending/processing) video or image job. Completed/failed jobs
    no longer need their source, so it ages out.

  * OUTPUT_DIR: results are named by their owning id (``<video_id>/`` and
    ``images/<image_id>/``). We delete only directories whose id no longer
    exists in the database — i.e. truly orphaned leftovers — and only once they
    are older than the window. A completed job's output is always kept.

Best-effort and never raises: cleanup must not break startup or a job.
"""
import json
import logging
import os
import shutil
import time

from app.core.config import settings
from app.db.enums import ImageStatus, VideoStatus
from app.db.models.image import Image
from app.db.models.video import Video
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Jobs in these states still need their source upload on disk.
_ACTIVE_VIDEO = (VideoStatus.pending, VideoStatus.downloading, VideoStatus.processing)
_ACTIVE_IMAGE = (ImageStatus.pending, ImageStatus.processing)


def _active_upload_paths(db) -> set[str]:
    """Every upload path referenced by a job that is still running."""
    paths: set[str] = set()

    for (file_path, params_json) in db.query(Video.file_path, Video.params_json).filter(
        Video.status.in_(_ACTIVE_VIDEO)
    ):
        if file_path:
            paths.add(file_path)
        # Merge/tool jobs keep extra inputs (paths[], music_path, logo_path) in JSON.
        if params_json:
            try:
                p = json.loads(params_json)
            except (ValueError, TypeError):
                p = {}
            for extra in p.get("paths") or []:
                if extra:
                    paths.add(extra)
            for key in ("music_path", "logo_path"):
                if p.get(key):
                    paths.add(p[key])

    for (file_path, input_paths) in db.query(Image.file_path, Image.input_paths).filter(
        Image.status.in_(_ACTIVE_IMAGE)
    ):
        if file_path:
            paths.add(file_path)
        if input_paths:
            try:
                for extra in json.loads(input_paths) or []:
                    if extra:
                        paths.add(extra)
            except (ValueError, TypeError):
                pass

    # Normalise so comparisons are robust to relative/absolute spelling.
    return {os.path.abspath(p) for p in paths}


def sweep_orphans(retention_days: int | None = None) -> dict:
    """Remove aged, unreferenced uploads and orphaned output dirs.

    Returns a small summary dict; never raises."""
    days = settings.FILE_RETENTION_DAYS if retention_days is None else retention_days
    cutoff = time.time() - days * 86400
    removed_uploads = removed_outputs = 0
    db = SessionLocal()
    try:
        active = _active_upload_paths(db)
        video_ids = {row[0] for row in db.query(Video.id)}
        image_ids = {row[0] for row in db.query(Image.id)}

        removed_uploads = _sweep_uploads(settings.UPLOAD_DIR, cutoff, active)
        removed_outputs = _sweep_output_dirs(settings.OUTPUT_DIR, cutoff, video_ids)
        removed_outputs += _sweep_output_dirs(
            os.path.join(settings.OUTPUT_DIR, "images"), cutoff, image_ids
        )

        if removed_uploads or removed_outputs:
            logger.info(
                "Cleanup: removed %d upload(s) + %d orphan output dir(s)",
                removed_uploads, removed_outputs,
            )
    except Exception:  # noqa: BLE001 — hygiene must never crash the caller
        logger.exception("Storage cleanup failed (continuing)")
    finally:
        db.close()
    return {"uploads": removed_uploads, "outputs": removed_outputs}


def _sweep_uploads(upload_dir: str, cutoff: float, active: set[str]) -> int:
    if not os.path.isdir(upload_dir):
        return 0
    removed = 0
    for entry in os.scandir(upload_dir):
        try:
            if not entry.is_file() or entry.stat().st_mtime >= cutoff:
                continue
            if os.path.abspath(entry.path) in active:
                continue
            os.remove(entry.path)
            removed += 1
        except OSError as exc:
            logger.warning("Could not remove upload %s: %s", entry.path, exc)
    return removed


def _sweep_output_dirs(base: str, cutoff: float, known_ids: set[str]) -> int:
    if not os.path.isdir(base):
        return 0
    removed = 0
    for entry in os.scandir(base):
        try:
            # The video OUTPUT_DIR also holds the nested "images" tree — skip it.
            if not entry.is_dir() or entry.name == "images":
                continue
            if entry.name in known_ids or entry.stat().st_mtime >= cutoff:
                continue
            shutil.rmtree(entry.path, ignore_errors=True)
            removed += 1
        except OSError as exc:
            logger.warning("Could not remove output dir %s: %s", entry.path, exc)
    return removed
