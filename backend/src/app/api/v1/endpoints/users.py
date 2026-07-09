from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.v1.deps import require_superadmin
from app.core.exceptions import NotFoundError, AppError
from app.db.models.user import User
from app.db.enums import UserRole
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import (
    CreateUserRequest, AdminUpdateUserRequest,
    UserResponse, UserListResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


def _get_target(user_id: str, db: Session, current_user: User) -> User:
    svc = AuthService(db)
    target = svc.get_user_by_id(user_id)
    if not target:
        raise NotFoundError(f"Foydalanuvchi topilmadi")
    if target.role is UserRole.superadmin:
        raise AppError("Super admin boshqarilmaydi", status_code=403)
    return target


@router.get("", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    return AuthService(db).list_users(page, limit)


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    payload: CreateUserRequest,
    current_user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    return AuthService(db).create_user(payload)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: AdminUpdateUserRequest,
    current_user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    target = _get_target(user_id, db, current_user)
    return AuthService(db).admin_update_user(target, payload)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    current_user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    target = _get_target(user_id, db, current_user)
    AuthService(db).delete_user(target)
