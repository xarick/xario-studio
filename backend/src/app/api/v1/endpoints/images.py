import os
import mimetypes

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.v1.deps import require_admin, owner_scope
from app.db.models.user import User
from app.db.enums import UserRole
from app.modules.images.service import ImageService
from app.modules.images.schemas import ImageResponse, ImageListResponse
from app.modules.auth.repository import UserRepository
from app.core.exceptions import NotFoundError
from app.core.security import decode_access_token
from app.workers.queues import enqueue_image

router = APIRouter(prefix="/images", tags=["images"])

_PANEL_ROLES = {UserRole.admin, UserRole.superadmin}


def _resolve_output(image_id: str, db: Session, owner_id: str | None = None):
    image = ImageService(db).get_image(image_id, owner_id)
    if not image.output_path or not os.path.exists(image.output_path):
        raise NotFoundError("Image is not ready yet")
    return image


@router.post("/bg-remove", response_model=ImageResponse, status_code=202, summary="Remove an image's background")
async def remove_background(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    image = await ImageService(db).submit_bg_remove(file, user_id=current_user.id)
    enqueue_image(image)
    return image


@router.post("/to-shorts", response_model=ImageResponse, status_code=202, summary="Turn images into a 9:16 short")
async def images_to_shorts(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    image = await ImageService(db).submit_image_to_shorts(files, user_id=current_user.id)
    enqueue_image(image)
    return image


@router.post("/tool", response_model=ImageResponse, status_code=202, summary="Run an image tool (crop/resize/convert)")
async def image_tool(
    file: UploadFile = File(...),
    op: str = Form(...),
    params: str = Form("{}"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    import json
    try:
        parsed = json.loads(params or "{}")
        if not isinstance(parsed, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=422, detail="params must be a JSON object")
    image = await ImageService(db).submit_image_tool(file, op, parsed, user_id=current_user.id)
    enqueue_image(image)
    return image


@router.get("", response_model=ImageListResponse, summary="List image jobs")
def list_images(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(pending|processing|completed|failed)$"),
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    return ImageService(db).list_images(page, limit, status or None, scope)


@router.get("/{image_id}", response_model=ImageResponse, summary="Get image job status")
def get_image(
    image_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    return ImageService(db).get_image(image_id, scope)


@router.post("/{image_id}/cancel", response_model=ImageResponse, summary="Cancel a queued or running image job")
def cancel_image(
    image_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    return ImageService(db).cancel_image(image_id, scope)


@router.delete("/{image_id}", status_code=204, summary="Delete an image job and its files")
def delete_image(
    image_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    ImageService(db).delete_image(image_id, scope)


@router.get("/{image_id}/download", summary="Download the processed image")
def download_image(
    image_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    image = _resolve_output(image_id, db, scope)
    ext = os.path.splitext(image.output_path)[1].lower() or ".png"
    media_type = mimetypes.types_map.get(ext, "application/octet-stream")
    return FileResponse(image.output_path, media_type=media_type, filename=f"{image.operation.value}{ext}")


@router.get("/{image_id}/stream", summary="Stream the processed image via query-param token (for <img>)")
def stream_image(
    image_id: str,
    token: str = Query(..., description="JWT access token"),
    db: Session = Depends(get_db),
):
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active or user.role not in _PANEL_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    scope = None if user.role is UserRole.superadmin else user.id
    image = _resolve_output(image_id, db, scope)
    ext = os.path.splitext(image.output_path)[1].lower() or ".png"
    return FileResponse(image.output_path, media_type=mimetypes.types_map.get(ext, "image/png"))
