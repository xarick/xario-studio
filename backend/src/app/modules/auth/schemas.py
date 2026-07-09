from pydantic import BaseModel, field_validator
from typing import Literal
import re

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    limit: int
    pages: int


class UpdateUserRequest(BaseModel):
    """Self-update: own username."""
    username: str | None = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str | None) -> str | None:
        if v is not None and not _USERNAME_RE.match(v):
            raise ValueError("Username 3-32 belgi: harflar, raqamlar, _ bo'lishi kerak")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Yangi parol kamida 8 belgi bo'lishi kerak")
        return v


class CreateUserRequest(BaseModel):
    """Superadmin creates a new admin or user account."""
    username: str
    password: str
    role: Literal["admin", "user"] = "admin"

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError("Username 3-32 belgi: harflar, raqamlar, _ bo'lishi kerak")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Parol kamida 8 belgi bo'lishi kerak")
        return v


class AdminUpdateUserRequest(BaseModel):
    """Superadmin updates another user."""
    username: str | None = None
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str | None) -> str | None:
        if v is not None and not _USERNAME_RE.match(v):
            raise ValueError("Username 3-32 belgi: harflar, raqamlar, _ bo'lishi kerak")
        return v
