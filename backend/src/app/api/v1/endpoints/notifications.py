from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.user import User
from app.api.v1.deps import require_admin
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    repo = NotificationRepository(db)
    items = repo.list_for_user(current_user.id, limit=limit, unread_only=unread_only)
    unread = repo.unread_count(current_user.id)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        unread_count=unread,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    count = NotificationRepository(db).unread_count(current_user.id)
    return UnreadCountResponse(count=count)


@router.post("/{notif_id}/read", response_model=NotificationResponse)
def mark_read(
    notif_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    notif = NotificationRepository(db).mark_read(notif_id, current_user.id)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationResponse.model_validate(notif)


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    count = NotificationRepository(db).mark_all_read(current_user.id)
    return {"marked": count}
