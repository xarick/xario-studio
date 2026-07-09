from sqlalchemy.orm import Session
from app.core.exceptions import ValidationError, AppError
from app.core.security import hash_password, verify_password, create_access_token
from app.db.models.user import User
from app.db.enums import UserRole
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import (
    LoginRequest, TokenResponse,
    UpdateUserRequest, ChangePasswordRequest,
    CreateUserRequest, AdminUpdateUserRequest, UserListResponse, UserResponse,
)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.repo = UserRepository(db)

    def login(self, payload: LoginRequest) -> TokenResponse:
        user = self.repo.get_by_username(payload.username)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise AppError("Username yoki parol noto'g'ri", status_code=401)
        if not user.is_active:
            raise AppError("Hisob faolsizlantirilgan", status_code=403)
        return TokenResponse(access_token=create_access_token(user.id))

    # ── Self-management (admin + superadmin) ───────────────────────────────

    def update_user(self, user: User, payload: UpdateUserRequest) -> User:
        if payload.username and payload.username != user.username:
            if self.repo.get_by_username(payload.username):
                raise ValidationError("Bu username band")
            user.username = payload.username
        return self.repo.save(user)

    def change_password(self, user: User, payload: ChangePasswordRequest) -> None:
        if not verify_password(payload.current_password, user.hashed_password):
            raise AppError("Joriy parol noto'g'ri", status_code=400)
        user.hashed_password = hash_password(payload.new_password)
        self.repo.save(user)

    # ── Superadmin: user management ────────────────────────────────────────

    def list_users(self, page: int = 1, limit: int = 20) -> UserListResponse:
        limit = min(limit, 100)
        items, total = self.repo.list_paginated(page, limit)
        pages = (total + limit - 1) // limit if total else 0
        return UserListResponse(
            items=[UserResponse.model_validate(u) for u in items],
            total=total, page=page, limit=limit, pages=pages,
        )

    def create_user(self, payload: CreateUserRequest) -> User:
        if self.repo.get_by_username(payload.username):
            raise ValidationError("Bu username band")
        user = User(
            username=payload.username,
            hashed_password=hash_password(payload.password),
            role=UserRole(payload.role),
        )
        return self.repo.create(user)

    def admin_update_user(self, target: User, payload: AdminUpdateUserRequest) -> User:
        if payload.username and payload.username != target.username:
            if self.repo.get_by_username(payload.username):
                raise ValidationError("Bu username band")
            target.username = payload.username
        if payload.role is not None:
            target.role = UserRole(payload.role)
        if payload.is_active is not None:
            target.is_active = payload.is_active
        return self.repo.save(target)

    def delete_user(self, target: User) -> None:
        self.repo.delete(target)

    def get_user_by_id(self, user_id: str) -> User | None:
        return self.repo.get_by_id(user_id)
