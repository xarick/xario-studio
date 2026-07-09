"""Shared test fixtures.

Environment is configured BEFORE any app module is imported so the settings
singleton picks up the SQLite test database and an eager (in-process) queue.
"""
import os
import tempfile

# ── Test environment — must be set before importing app.* ────────────────────
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db", prefix="xario_test_")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DEBUG"] = "True"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"
os.environ["AI_API_KEY"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine, SessionLocal  # noqa: E402
# Import every model so its table is registered on Base.metadata.
import app.db.models  # noqa: E402,F401
import app.db.models.notification  # noqa: E402,F401
from app.db.enums import UserRole  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.core.security import hash_password, create_access_token  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    """A clean schema for every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def enqueued(monkeypatch):
    """Capture Celery submissions instead of running the pipeline inline.

    CELERY_TASK_ALWAYS_EAGER makes an un-patched submit execute the whole media
    pipeline against the test's fake bytes, which hangs. Autouse so no test can
    do that by accident; request the fixture to assert on what was enqueued.
    """
    from app.workers import tasks

    calls: list[dict] = []

    def _capture(kind):
        def apply_async(args=None, queue=None, **_kw):
            calls.append({"kind": kind, "id": (args or [None])[0], "queue": queue})
        return apply_async

    monkeypatch.setattr(tasks.process_video_task, "apply_async", _capture("video"))
    monkeypatch.setattr(tasks.process_image_task, "apply_async", _capture("image"))
    return calls


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin(db) -> User:
    user = User(
        username="admin",
        hashed_password=hash_password("Admin123!"),
        role=UserRole.superadmin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(admin) -> dict:
    token = create_access_token(admin.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def teardown_module():  # pragma: no cover
    try:
        os.remove(_DB_PATH)
    except OSError:
        pass
