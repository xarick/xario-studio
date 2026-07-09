"""Ownership scoping — a regular admin only sees their own rows; a superadmin
sees everything. Regression guard for the per-user isolation added to the
videos / shorts / images services."""
import io

from app.db.models.user import User
from app.db.enums import UserRole
from app.core.security import hash_password, create_access_token


def _make_admin(db, username, role=UserRole.admin) -> User:
    user = User(
        username=username,
        hashed_password=hash_password("Pw123456!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def _upload_video(client, headers, monkeypatch=None) -> str:
    # Enqueueing is stubbed globally by the autouse `enqueued` fixture.
    r = client.post(
        "/api/v1/videos/upload",
        headers=headers,
        files={"file": ("clip.mp4", io.BytesIO(b"fake-mp4-bytes"), "video/mp4")},
        data={"shorts_count": "2", "generation_mode": "smart"},
    )
    assert r.status_code == 202
    return r.json()["id"]


def test_admin_cannot_access_another_admins_video(client, db, monkeypatch):
    alice = _make_admin(db, "alice")
    bob = _make_admin(db, "bob")
    vid = _upload_video(client, _headers(alice), monkeypatch)

    # Bob may not read, delete, or list Alice's video (hidden behind 404).
    assert client.get(f"/api/v1/videos/{vid}", headers=_headers(bob)).status_code == 404
    assert client.delete(f"/api/v1/videos/{vid}", headers=_headers(bob)).status_code == 404
    assert client.get(f"/api/v1/videos/{vid}/shorts", headers=_headers(bob)).status_code == 404
    assert client.get("/api/v1/videos", headers=_headers(bob)).json()["total"] == 0

    # Alice still owns and sees it.
    assert client.get(f"/api/v1/videos/{vid}", headers=_headers(alice)).status_code == 200
    assert client.get("/api/v1/videos", headers=_headers(alice)).json()["total"] == 1


def test_superadmin_sees_every_video(client, db, admin, monkeypatch):
    alice = _make_admin(db, "alice")
    vid = _upload_video(client, _headers(alice), monkeypatch)
    # The `admin` fixture is a superadmin → no ownership filter.
    su = _headers(admin)
    assert client.get(f"/api/v1/videos/{vid}", headers=su).status_code == 200
    assert client.get("/api/v1/videos", headers=su).json()["total"] == 1


def test_stats_are_scoped_per_owner(client, db, monkeypatch):
    alice = _make_admin(db, "alice")
    bob = _make_admin(db, "bob")
    _upload_video(client, _headers(alice), monkeypatch)
    assert client.get("/api/v1/videos/stats", headers=_headers(alice)).json()["total_videos"] == 1
    assert client.get("/api/v1/videos/stats", headers=_headers(bob)).json()["total_videos"] == 0
