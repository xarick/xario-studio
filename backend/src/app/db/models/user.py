from sqlalchemy import String, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDMixin, TimestampMixin
from app.db.enums import UserRole


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.user)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
