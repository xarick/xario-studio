from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.db.models.user import User
from app.db.enums import UserRole
from app.modules.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username).first()

    def list_paginated(self, page: int, limit: int) -> tuple[list[User], int]:
        q = self.db.query(User).filter(User.role != UserRole.superadmin)
        total = q.count()
        items = q.order_by(desc(User.created_at)).offset((page - 1) * limit).limit(limit).all()
        return items, total
