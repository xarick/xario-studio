from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.db.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, notif: Notification) -> Notification:
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)
        return notif

    def list_for_user(
        self,
        user_id: str,
        limit: int = 30,
        unread_only: bool = False,
    ) -> list[Notification]:
        q = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            q = q.where(Notification.is_read.is_(False))
        q = q.order_by(Notification.created_at.desc()).limit(limit)
        return list(self.db.scalars(q).all())

    def unread_count(self, user_id: str) -> int:
        q = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        return self.db.scalar(q) or 0

    def mark_read(self, notif_id: str, user_id: str) -> Notification | None:
        notif = self.db.scalar(
            select(Notification).where(
                Notification.id == notif_id,
                Notification.user_id == user_id,
            )
        )
        if notif:
            notif.is_read = True
            self.db.commit()
            self.db.refresh(notif)
        return notif

    def mark_all_read(self, user_id: str) -> int:
        from sqlalchemy import update
        result = self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        self.db.commit()
        return result.rowcount

    def delete_old(self, user_id: str, keep: int = 50) -> None:
        """Keep only the most recent `keep` notifications per user."""
        subq = (
            select(Notification.id)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(keep)
            .subquery()
        )
        to_del = self.db.scalars(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.id.not_in(select(subq.c.id)),
            )
        ).all()
        for n in to_del:
            self.db.delete(n)
        if to_del:
            self.db.commit()
