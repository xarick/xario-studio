from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.enums import UserRole
from app.modules.auth.repository import UserRepository

bearer = HTTPBearer(auto_error=False)

_PANEL_ROLES = {UserRole.admin, UserRole.superadmin}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allow admin and superadmin."""
    if current_user.role not in _PANEL_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """Allow superadmin only."""
    if current_user.role is not UserRole.superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return current_user


def owner_scope(current_user: User = Depends(require_admin)) -> str | None:
    """Row-ownership filter for panel resources (videos, shorts, images).

    A regular admin only sees and manages rows they own → returns their user id.
    A superadmin sees everything → returns ``None`` (no filter). Pass the result
    to the service layer, which hides other users' rows behind a 404.
    """
    if current_user.role is UserRole.superadmin:
        return None
    return current_user.id


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        return None
    return UserRepository(db).get_by_id(user_id)
