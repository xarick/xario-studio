from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.v1.deps import get_current_user, require_admin
from app.core.config import settings
from app.core.ratelimit import RateLimiter, client_ip
from app.db.models.user import User
from app.modules.auth.service import AuthService
from app.modules.auth.schemas import (
    LoginRequest, TokenResponse, UserResponse,
    UpdateUserRequest, ChangePasswordRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Per-IP brute-force throttle, shared across requests in this process.
_login_limiter = RateLimiter(
    settings.LOGIN_RATE_MAX_ATTEMPTS, settings.LOGIN_RATE_WINDOW_SEC
)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    _login_limiter.hit(client_ip(request))
    return AuthService(db).login(payload)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(
    payload: UpdateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return AuthService(db).update_user(current_user, payload)


@router.put("/password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    AuthService(db).change_password(current_user, payload)
