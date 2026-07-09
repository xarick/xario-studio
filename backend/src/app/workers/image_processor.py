"""
Image processing pipeline.

Dispatches an image job to the handler for its operation (registry mirrors
video_processor._SPECIAL_MODES). To add an operation: write a _run_X handler and
register it in _OPERATIONS — no new branch needed.
"""
import json
import logging
import os

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import ImageStatus, ImageOperation, NotificationType
from app.db.models.notification import Notification
from app.db.session import SessionLocal
from app.modules.images.repository import ImageRepository
from app.modules.notifications.repository import NotificationRepository
from app.workers import imaging

logger = logging.getLogger(__name__)


def _notify(db, image, *, completed: bool) -> None:
    try:
        repo = NotificationRepository(db)
        repo.create(Notification(
            user_id=image.user_id,
            type=NotificationType.job_completed if completed else NotificationType.job_failed,
            title=(image.original_filename or "Image")[:200],
            shorts_count=0,
        ))
        repo.delete_old(image.user_id, keep=50)
    except Exception as exc:
        logger.warning("Could not create image notification: %s", exc)


def _run_bg_remove(image, output_dir: str) -> str:
    out = os.path.join(output_dir, "no_bg.png")
    return imaging.remove_background(image.file_path, out)


def _run_image_to_shorts(image, output_dir: str) -> str:
    import json

    from app.workers.slideshow import build_slideshow

    paths = json.loads(image.input_paths) if image.input_paths else []
    out = os.path.join(output_dir, "short.mp4")
    return build_slideshow(paths, out)


# Geometry / colour tools keep the source format — re-encoding a JPEG photo as
# PNG multiplies its size. Only `convert` (whose whole job is the format) and
# `bg_remove` (which needs alpha) pick their own.
def _run_crop(image, output_dir: str) -> str:
    params = json.loads(image.params_json or "{}")
    out = imaging.keep_format_path(image.file_path, output_dir, "cropped")
    return imaging.crop_to_aspect(image.file_path, out, params.get("aspect", "1:1"))


def _run_resize(image, output_dir: str) -> str:
    params = json.loads(image.params_json or "{}")
    out = imaging.keep_format_path(image.file_path, output_dir, "resized")
    return imaging.resize_image(image.file_path, out, int(params.get("width", 1080)))


def _run_convert(image, output_dir: str) -> str:
    params = json.loads(image.params_json or "{}")
    fmt = params.get("fmt", "png")
    out = os.path.join(output_dir, f"converted.{imaging.output_ext_for_format(fmt)}")
    return imaging.convert_image(image.file_path, out, fmt)


def _run_upscale(image, output_dir: str) -> str:
    params = json.loads(image.params_json or "{}")
    out = imaging.keep_format_path(image.file_path, output_dir, "upscaled")
    return imaging.upscale_image(image.file_path, out, int(params.get("factor", 2)))


def _run_enhance(image, output_dir: str) -> str:
    params = json.loads(image.params_json or "{}")
    out = imaging.keep_format_path(image.file_path, output_dir, "enhanced")
    return imaging.enhance_image(
        image.file_path, out,
        sharpness=float(params.get("sharpness", 1.5)),
        contrast=float(params.get("contrast", 1.1)),
        color=float(params.get("color", 1.1)),
    )


_OPERATIONS = {
    ImageOperation.bg_remove: _run_bg_remove,
    ImageOperation.image_to_shorts: _run_image_to_shorts,
    ImageOperation.crop: _run_crop,
    ImageOperation.resize: _run_resize,
    ImageOperation.convert: _run_convert,
    ImageOperation.enhance: _run_enhance,
    ImageOperation.upscale: _run_upscale,
}


class JobCancelled(RuntimeError):
    """The row was marked terminal by a cancel request while the job ran."""


def _raise_if_cancelled(repo: ImageRepository, image_id: str) -> None:
    """Cooperative cancellation checkpoint — see video_processor for the why."""
    status = repo.current_status(image_id)
    if status is None or status is ImageStatus.failed:
        raise JobCancelled(image_id)


def process_image(image_id: str) -> None:
    db: Session = SessionLocal()
    try:
        repo = ImageRepository(db)
        image = repo.get_by_id(image_id)
        if not image:
            logger.error("Image %s not found — skipping", image_id)
            return

        handler = _OPERATIONS.get(image.operation)
        if handler is None:
            repo.update_status(image_id, ImageStatus.failed,
                               error_message=f"Unsupported operation: {image.operation}")
            return

        output_dir = os.path.join(settings.OUTPUT_DIR, "images", image_id)
        os.makedirs(output_dir, exist_ok=True)
        repo.update_status(image_id, ImageStatus.processing, progress=40)

        try:
            _raise_if_cancelled(repo, image_id)
            output_path = handler(image, output_dir)
            # The job may have been cancelled while the handler ran; marking it
            # completed here would resurrect it and hand back a stale result.
            _raise_if_cancelled(repo, image_id)
            repo.set_output(image_id, output_path)
            repo.update_status(image_id, ImageStatus.completed, progress=100)
            logger.info("Image %s (%s) done", image_id, image.operation.value)
            if image.user_id:
                _notify(db, image, completed=True)
        except JobCancelled:
            logger.info("Image %s cancelled — discarding the result", image_id)
        except Exception as exc:
            logger.exception("Image %s (%s) failed", image_id, image.operation.value)
            repo.update_status(image_id, ImageStatus.failed, error_message=str(exc))
            if image.user_id:
                _notify(db, image, completed=False)
    finally:
        db.close()
