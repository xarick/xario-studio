import json
import logging
import os
import shutil

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.uploads import save_upload
from app.db.enums import ImageOperation, ImageStatus
from app.db.models.image import Image
from app.modules.images.repository import ImageRepository
from app.modules.images.schemas import ImageListResponse, ImageResponse

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_ASPECT_RATIOS = {"1:1", "9:16", "16:9", "3:4", "4:3"}


class ImageService:
    def __init__(self, db: Session) -> None:
        self.repo = ImageRepository(db)

    async def submit_bg_remove(self, file: UploadFile, user_id: str) -> Image:
        file_path = await save_upload(file, _IMAGE_EXTENSIONS)
        image = Image(
            user_id=user_id,
            original_filename=file.filename,
            file_path=file_path,
            operation=ImageOperation.bg_remove,
            status=ImageStatus.pending,
        )
        return self.repo.create(image)

    async def submit_image_to_shorts(self, files: list[UploadFile], user_id: str) -> Image:
        files = [f for f in files if f and f.filename]
        if not files:
            raise ValidationError("At least one image is required.")
        if len(files) > settings.SLIDESHOW_MAX_IMAGES:
            raise ValidationError(f"Too many images (max {settings.SLIDESHOW_MAX_IMAGES}).")
        paths = [await save_upload(f, _IMAGE_EXTENSIONS) for f in files]
        image = Image(
            user_id=user_id,
            original_filename=files[0].filename,
            input_paths=json.dumps(paths),
            operation=ImageOperation.image_to_shorts,
            status=ImageStatus.pending,
        )
        return self.repo.create(image)

    _TOOL_OPS = {
        "crop": ImageOperation.crop,
        "resize": ImageOperation.resize,
        "convert": ImageOperation.convert,
        "enhance": ImageOperation.enhance,
        "upscale": ImageOperation.upscale,
    }

    async def submit_image_tool(self, file: UploadFile, op: str, params: dict, user_id: str) -> Image:
        operation = self._TOOL_OPS.get(op)
        if operation is None:
            raise ValidationError(f"Unknown image tool: {op}")
        if op == "crop" and params.get("aspect") not in _ASPECT_RATIOS:
            params["aspect"] = "1:1"

        file_path = await save_upload(file, _IMAGE_EXTENSIONS)
        image = Image(
            user_id=user_id,
            original_filename=file.filename,
            file_path=file_path,
            operation=operation,
            params_json=json.dumps(params or {}),
            status=ImageStatus.pending,
        )
        return self.repo.create(image)

    def get_image(self, image_id: str, owner_id: str | None = None) -> Image:
        image = self.repo.get_by_id(image_id)
        # Hide other users' rows behind a 404 rather than leaking their existence.
        if not image or (owner_id is not None and image.user_id != owner_id):
            raise NotFoundError(f"Image {image_id} not found")
        return image

    def list_images(
        self, page: int = 1, limit: int = 20, status: str | None = None,
        owner_id: str | None = None,
    ) -> ImageListResponse:
        limit = min(limit, 100)
        status_enum = ImageStatus(status) if status else None
        items, total = self.repo.list_paginated(page, limit, status_enum, owner_id)
        pages = (total + limit - 1) // limit if total else 0
        return ImageListResponse(
            items=[ImageResponse.model_validate(i) for i in items],
            total=total, page=page, limit=limit, pages=pages,
        )

    # Mirrors VideoService: a cancelled job is a `failed` row with this reason,
    # so no status enum value (and no migration) is needed to tell them apart.
    CANCEL_MESSAGE = "Cancelled by the user."
    _ACTIVE_STATES = (ImageStatus.pending, ImageStatus.processing)

    def cancel_image(self, image_id: str, owner_id: str | None = None) -> Image:
        """Stop a queued or running image job.

        A queued task is revoked and never starts. A running one is marked
        terminal; the worker notices before it writes its result.
        """
        from app.workers.queues import revoke

        image = self.get_image(image_id, owner_id)
        if image.status not in self._ACTIVE_STATES:
            raise ValidationError("This job has already finished.")

        revoke(image.id)
        self.repo.update_status(image.id, ImageStatus.failed, error_message=self.CANCEL_MESSAGE)
        return self.get_image(image_id, owner_id)

    def delete_image(self, image_id: str, owner_id: str | None = None) -> None:
        image = self.get_image(image_id, owner_id)

        # Deleting the output directory and the source uploads under a running
        # worker leaves it encoding into nothing — and, if the worker is later
        # killed, an orphaned ffmpeg spinning forever. Stop the job first.
        if image.status in self._ACTIVE_STATES:
            logger.info("Cancelling active image job %s before deleting it", image_id)
            self.cancel_image(image_id, owner_id)

        output_dir = os.path.join(settings.OUTPUT_DIR, "images", image_id)
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
        # Source uploads: the single bg_remove file, plus any image_to_shorts inputs.
        sources = []
        if image.file_path:
            sources.append(image.file_path)
        if image.input_paths:
            try:
                sources.extend(json.loads(image.input_paths))
            except (ValueError, TypeError):
                pass
        for path in sources:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as exc:
                    logger.warning("Could not delete image upload %s: %s", path, exc)
        self.repo.delete(image)
