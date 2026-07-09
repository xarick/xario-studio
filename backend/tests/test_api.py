"""API smoke tests — health, auth, and job enqueue (worker mocked)."""
import io


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_success(client, admin):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client, admin):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_with_token(client, auth_headers):
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_videos_list_requires_auth(client):
    assert client.get("/api/v1/videos").status_code == 401


def test_video_upload_enqueues_job(client, auth_headers, enqueued):
    r = client.post(
        "/api/v1/videos/upload",
        headers=auth_headers,
        files={"file": ("clip.mp4", io.BytesIO(b"fake-mp4-bytes"), "video/mp4")},
        data={"shorts_count": "3", "generation_mode": "smart"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    # `smart` runs whisper, so it belongs on the heavy lane.
    assert enqueued == [{"kind": "video", "id": body["id"], "queue": "heavy"}]


def test_plain_tool_job_goes_to_the_cheap_lane(client, auth_headers, enqueued):
    r = client.post(
        "/api/v1/videos/upload",
        headers=auth_headers,
        files={"file": ("clip.mp4", io.BytesIO(b"fake-mp4-bytes"), "video/mp4")},
        data={"shorts_count": "1", "generation_mode": "simple", "subtitles_enabled": "false"},
    )
    assert r.status_code == 202
    assert enqueued[0]["queue"] == "media"


def test_video_upload_rejects_bad_extension(client, auth_headers):
    r = client.post(
        "/api/v1/videos/upload",
        headers=auth_headers,
        files={"file": ("evil.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
        data={"shorts_count": "3", "generation_mode": "smart"},
    )
    assert r.status_code == 422  # ValidationError — unsupported format


def test_list_filters_by_a_set_of_modes(client, auth_headers, db, admin):
    """The audio history page asks for only its own job types in one query."""
    from app.db.enums import GenerationMode, VideoSourceType, VideoStatus
    from app.db.models.video import Video

    for mode in (GenerationMode.tts, GenerationMode.dub, GenerationMode.smart):
        db.add(Video(user_id=admin.id, source_type=VideoSourceType.upload,
                     shorts_requested=1, generation_mode=mode, status=VideoStatus.completed))
    db.commit()

    r = client.get("/api/v1/videos?mode=tts,dub", headers=auth_headers)
    assert r.status_code == 200
    assert sorted(v["generation_mode"] for v in r.json()["items"]) == ["dub", "tts"]

    r = client.get("/api/v1/videos?mode=tts", headers=auth_headers)
    assert [v["generation_mode"] for v in r.json()["items"]] == ["tts"]


def test_list_rejects_an_unknown_mode(client, auth_headers):
    assert client.get("/api/v1/videos?mode=tts,nosuch", headers=auth_headers).status_code == 422
    # Shape is enforced before the service sees it.
    assert client.get("/api/v1/videos?mode=tts;drop", headers=auth_headers).status_code == 422


def test_image_bg_remove_enqueues_job(client, auth_headers, enqueued):
    r = client.post(
        "/api/v1/images/bg-remove",
        headers=auth_headers,
        files={"file": ("pic.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert enqueued == [{"kind": "image", "id": body["id"], "queue": "media"}]


def test_image_to_shorts_enqueues_job(client, auth_headers, enqueued):
    files = [
        ("files", ("a.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")),
        ("files", ("b.jpg", io.BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")),
    ]
    r = client.post("/api/v1/images/to-shorts", headers=auth_headers, files=files)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["operation"] == "image_to_shorts"
    assert enqueued == [{"kind": "image", "id": body["id"], "queue": "media"}]


def test_image_response_exposes_the_output_extension(client, auth_headers, db, admin):
    """The geometry tools keep the source format, so the client must be told what
    it is — naming a JPEG result ".png" hands the user a broken file."""
    from app.db.enums import ImageOperation, ImageStatus
    from app.db.models.image import Image

    img = Image(user_id=admin.id, operation=ImageOperation.crop, status=ImageStatus.completed,
                original_filename="photo.jpg", output_path="/tmp/out/cropped.jpg")
    db.add(img)
    db.commit()

    r = client.get(f"/api/v1/images/{img.id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["output_ext"] == "jpg"


def test_image_response_has_no_extension_before_it_finishes(client, auth_headers, db, admin):
    from app.db.enums import ImageOperation, ImageStatus
    from app.db.models.image import Image

    img = Image(user_id=admin.id, operation=ImageOperation.crop, status=ImageStatus.pending)
    db.add(img)
    db.commit()

    r = client.get(f"/api/v1/images/{img.id}", headers=auth_headers)
    assert r.json()["output_ext"] is None
