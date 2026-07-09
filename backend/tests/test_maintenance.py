"""Tests for storage cleanup + the login rate limiter."""
import os
import time

import pytest

from app.core.ratelimit import RateLimiter
from app.db.enums import GenerationMode, VideoSourceType, VideoStatus
from app.db.models.video import Video
from fastapi import HTTPException


# ── rate limiter unit ────────────────────────────────────────────────────────
def test_rate_limiter_blocks_after_max():
    rl = RateLimiter(max_calls=3, period=60)
    for _ in range(3):
        rl.hit("ip-1")
    with pytest.raises(HTTPException) as exc:
        rl.hit("ip-1")
    assert exc.value.status_code == 429
    # A different key has its own independent budget.
    rl.hit("ip-2")


def test_login_endpoint_rate_limited(client, admin):
    # Use a dedicated client IP so this test is isolated from other login calls.
    hdr = {"X-Forwarded-For": "203.0.113.77"}
    saw_429 = False
    for _ in range(40):
        r = client.post("/api/v1/auth/login", headers=hdr,
                        json={"username": "admin", "password": "wrong"})
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, "login was never throttled"


# ── storage cleanup ──────────────────────────────────────────────────────────
def _age(path, days):
    old = time.time() - days * 86400
    os.utime(path, (old, old))


def test_sweep_orphans(tmp_path, db, monkeypatch):
    from app.core.config import settings
    from app.workers import cleanup

    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    (outputs / "images").mkdir(parents=True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(uploads))
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(outputs))

    # An active job still needs its source upload — must survive.
    active_src = uploads / "active.mp4"
    active_src.write_bytes(b"x")
    _age(active_src, 30)
    db.add(Video(
        source_type=VideoSourceType.upload, shorts_requested=1,
        generation_mode=GenerationMode.tool, status=VideoStatus.processing,
        file_path=str(active_src),
    ))
    db.add(Video(
        source_type=VideoSourceType.upload, shorts_requested=1,
        generation_mode=GenerationMode.tool, status=VideoStatus.completed,
        file_path=str(uploads / "done.mp4"),
    ))
    db.commit()

    # An old, unreferenced upload (its job finished) — should be removed.
    stale = uploads / "done.mp4"
    stale.write_bytes(b"x")
    _age(stale, 30)

    # A recent upload — too new to touch even though unreferenced.
    fresh = uploads / "fresh.mp4"
    fresh.write_bytes(b"x")

    # Output dirs: one for a real video id (kept), one orphaned (removed).
    real_id = db.query(Video.id).filter(Video.status == VideoStatus.completed).scalar()
    keep_dir = outputs / real_id
    keep_dir.mkdir()
    _age(keep_dir, 30)
    orphan_dir = outputs / "ghost-video-id"
    orphan_dir.mkdir()
    _age(orphan_dir, 30)

    result = cleanup.sweep_orphans(retention_days=7)

    assert active_src.exists(), "active job's upload was wrongly deleted"
    assert fresh.exists(), "recent upload was wrongly deleted"
    assert not stale.exists(), "stale upload was not cleaned"
    assert keep_dir.exists(), "live output dir was wrongly deleted"
    assert not orphan_dir.exists(), "orphan output dir was not cleaned"
    assert result["uploads"] >= 1 and result["outputs"] >= 1
