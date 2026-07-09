import os
import mimetypes
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.v1.deps import require_admin, owner_scope
from app.db.models.user import User
from app.db.enums import UserRole
from app.modules.shorts.service import ShortService
from app.modules.shorts.schemas import ShortResponse
from app.modules.auth.repository import UserRepository
from app.core.exceptions import NotFoundError
from app.core.security import decode_access_token

router = APIRouter(prefix="/shorts", tags=["shorts"])

_PANEL_ROLES = {UserRole.admin, UserRole.superadmin}


def _resolve_short_file(short_id: str, db: Session, owner_id: str | None = None):
    short = ShortService(db).get_short(short_id, owner_id)
    if not short.file_path or not os.path.exists(short.file_path):
        raise NotFoundError("Short file is not ready yet")
    return short


@router.get("/{short_id}", response_model=ShortResponse, summary="Get a short")
def get_short(
    short_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    return ShortService(db).get_short(short_id, scope)


@router.get("/{short_id}/download", summary="Download a short as MP4")
def download_short(
    short_id: str,
    scope: str | None = Depends(owner_scope),
    db: Session = Depends(get_db),
):
    short = _resolve_short_file(short_id, db, scope)
    ext = os.path.splitext(short.file_path)[1].lower() or ".mp4"
    media_type = mimetypes.types_map.get(ext, "application/octet-stream")
    return FileResponse(
        short.file_path,
        media_type=media_type,
        filename=f"short_{short.index_number}{ext}",
    )


@router.get("/{short_id}/stream", summary="Stream a short via query-param token (for <video> tags)")
def stream_short(
    short_id: str,
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
    short = _resolve_short_file(short_id, db, scope)
    return FileResponse(short.file_path, media_type="video/mp4")
