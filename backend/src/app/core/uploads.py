"""Shared upload helper — validate an upload's extension and stream it to disk
with a size cap. Used by the videos and images services (and any future module
that accepts file uploads)."""
import os
import uuid

import aiofiles
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import ValidationError


async def save_upload(file: UploadFile, allowed: set[str]) -> str:
    """Validate the file extension against `allowed` and stream it into
    UPLOAD_DIR (capped at MAX_UPLOAD_SIZE_MB). Returns the saved path; removes a
    partial file if the size limit is exceeded."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise ValidationError(
            f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(allowed))}"
        )
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4()}{ext}")
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    written = 0
    try:
        async with aiofiles.open(file_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise ValidationError(f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit")
                await out.write(chunk)
    except ValidationError:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    return file_path
