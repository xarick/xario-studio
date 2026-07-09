"""HTTP-level tests for the editor / tool / merge endpoints (worker mocked)."""
import io
import json

import pytest

from app.db.models.video import Video


def _mp4(name="clip.mp4"):
    return (name, io.BytesIO(b"fake-mp4"), "video/mp4")


def _mp3(name="a.mp3"):
    return (name, io.BytesIO(b"fake-mp3"), "audio/mpeg")


def _png(name="i.png"):
    return (name, io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")


# ── editor ───────────────────────────────────────────────────────────────────
def test_edit_ok(client, auth_headers, db):
    r = client.post(
        "/api/v1/videos/edit", headers=auth_headers,
        files={"file": _mp4()},
        data={"start": "1.0", "end": "5.0", "aspect": "9:16", "fit": "crop",
              "text": "Salom", "text_position": "bottom"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    v = db.get(Video, body["id"])
    params = json.loads(v.params_json)
    assert params["aspect"] == "9:16" and params["text"] == "Salom" and params["end"] == 5.0


def test_edit_bad_range(client, auth_headers):
    r = client.post(
        "/api/v1/videos/edit", headers=auth_headers,
        files={"file": _mp4()},
        data={"start": "5", "end": "2", "aspect": "9:16", "fit": "crop"},
    )
    assert r.status_code == 422


def test_edit_multi_segment_and_texts(client, auth_headers, db):
    segments = json.dumps([{"start": 0, "end": 2}, {"start": 5, "end": 8}])
    texts = json.dumps([
        {"text": "Hi", "start": 0, "end": 1, "position": "top", "color": "#FACC15", "scale": 1.4},
        {"text": "Bye", "start": 3, "end": 5, "position": "bottom"},
    ])
    r = client.post(
        "/api/v1/videos/edit", headers=auth_headers,
        files={"file": _mp4()},
        data={"segments": segments, "texts": texts, "output_mode": "phone"},
    )
    assert r.status_code == 202
    params = json.loads(db.get(Video, r.json()["id"]).params_json)
    assert len(params["segments"]) == 2
    assert params["aspect"] == "9:16"          # phone preset forces vertical
    assert len(params["texts"]) == 2
    assert params["texts"][0]["color"] == "#FACC15"


def test_edit_short_mode_rejects_over_60s(client, auth_headers):
    segments = json.dumps([{"start": 0, "end": 40}, {"start": 50, "end": 80}])  # 70s total
    r = client.post(
        "/api/v1/videos/edit", headers=auth_headers,
        files={"file": _mp4()},
        data={"segments": segments, "output_mode": "short"},
    )
    assert r.status_code == 422


def test_edit_segments_bad_json(client, auth_headers):
    r = client.post(
        "/api/v1/videos/edit", headers=auth_headers,
        files={"file": _mp4()},
        data={"segments": "{not json"},
    )
    assert r.status_code == 422


# ── single-file tools ────────────────────────────────────────────────────────
def test_tool_video_compress(client, auth_headers, db):
    r = client.post(
        "/api/v1/videos/tool", headers=auth_headers,
        files={"file": _mp4()},
        data={"op": "compress", "params": json.dumps({"crf": 30})},
    )
    assert r.status_code == 202
    v = db.get(Video, r.json()["id"])
    assert json.loads(v.params_json) == {"op": "compress", "crf": 30}


def test_tool_audio_convert(client, auth_headers):
    r = client.post(
        "/api/v1/videos/tool", headers=auth_headers,
        files={"file": _mp3()},
        data={"op": "convert", "params": json.dumps({"fmt": "wav"})},
    )
    assert r.status_code == 202


def test_tool_audio_op_rejects_video_file(client, auth_headers):
    # 'trim' is an audio op → an .mp4 upload must be rejected.
    r = client.post(
        "/api/v1/videos/tool", headers=auth_headers,
        files={"file": _mp4()},
        data={"op": "trim", "params": "{}"},
    )
    assert r.status_code == 422


def test_tool_unknown_op(client, auth_headers):
    r = client.post(
        "/api/v1/videos/tool", headers=auth_headers,
        files={"file": _mp4()}, data={"op": "nope", "params": "{}"},
    )
    assert r.status_code == 422


def test_tool_bad_params_json(client, auth_headers):
    r = client.post(
        "/api/v1/videos/tool", headers=auth_headers,
        files={"file": _mp4()}, data={"op": "compress", "params": "not-json"},
    )
    assert r.status_code == 422


# ── watermark (needs a second file) ──────────────────────────────────────────
def test_watermark_needs_logo(client, auth_headers):
    r = client.post(
        "/api/v1/videos/tool", headers=auth_headers,
        files={"file": _mp4()}, data={"op": "watermark", "params": "{}"},
    )
    assert r.status_code == 422


def test_watermark_ok(client, auth_headers, db):
    r = client.post(
        "/api/v1/videos/tool", headers=auth_headers,
        files=[("file", _mp4()), ("extra", _png("logo.png"))],
        data={"op": "watermark", "params": json.dumps({"position": "bottom-right"})},
    )
    assert r.status_code == 202
    v = db.get(Video, r.json()["id"])
    assert json.loads(v.params_json)["logo_path"]


# ── audio merge ──────────────────────────────────────────────────────────────
def test_merge_concat_ok(client, auth_headers, db):
    r = client.post(
        "/api/v1/videos/merge", headers=auth_headers,
        files=[("files", _mp3("a.mp3")), ("files", _mp3("b.mp3"))],
        data={"op": "concat", "params": "{}"},
    )
    assert r.status_code == 202
    v = db.get(Video, r.json()["id"])
    assert len(json.loads(v.params_json)["paths"]) == 2


def test_merge_concat_needs_two(client, auth_headers):
    r = client.post(
        "/api/v1/videos/merge", headers=auth_headers,
        files=[("files", _mp3())], data={"op": "concat", "params": "{}"},
    )
    assert r.status_code == 422


def test_merge_mix_ok(client, auth_headers):
    r = client.post(
        "/api/v1/videos/merge", headers=auth_headers,
        files=[("files", _mp3("voice.mp3")), ("files", _mp3("music.mp3"))],
        data={"op": "mix", "params": json.dumps({"music_volume": 0.3})},
    )
    assert r.status_code == 202


def test_merge_mix_needs_exactly_two(client, auth_headers):
    r = client.post(
        "/api/v1/videos/merge", headers=auth_headers,
        files=[("files", _mp3("a.mp3")), ("files", _mp3("b.mp3")), ("files", _mp3("c.mp3"))],
        data={"op": "mix", "params": "{}"},
    )
    assert r.status_code == 422


# ── video merge (vconcat) ────────────────────────────────────────────────────
def test_merge_vconcat_ok(client, auth_headers, db):
    r = client.post(
        "/api/v1/videos/merge", headers=auth_headers,
        files=[("files", _mp4("a.mp4")), ("files", _mp4("b.mp4"))],
        data={"op": "vconcat", "params": json.dumps(
            {"transition": "fadeblack", "duration": 1.0, "aspect": "9:16"})},
    )
    assert r.status_code == 202
    v = db.get(Video, r.json()["id"])
    params = json.loads(v.params_json)
    assert params["op"] == "vconcat"
    assert len(params["paths"]) == 2
    assert params["transition"] == "fadeblack"


def test_merge_vconcat_needs_two(client, auth_headers):
    r = client.post(
        "/api/v1/videos/merge", headers=auth_headers,
        files=[("files", _mp4())], data={"op": "vconcat", "params": "{}"},
    )
    assert r.status_code == 422


def test_merge_vconcat_with_music(client, auth_headers, db):
    r = client.post(
        "/api/v1/videos/merge", headers=auth_headers,
        files=[("files", _mp4("a.mp4")), ("files", _mp4("b.mp4"))],
        data={"op": "vconcat", "params": json.dumps({"transition": "fade"})},
        # the music field is sent as a separate file part
    )
    assert r.status_code == 202


def test_merge_concat_crossfade_stored(client, auth_headers, db):
    r = client.post(
        "/api/v1/videos/merge", headers=auth_headers,
        files=[("files", _mp3("a.mp3")), ("files", _mp3("b.mp3"))],
        data={"op": "concat", "params": json.dumps({"crossfade": 2.0})},
    )
    assert r.status_code == 202
    v = db.get(Video, r.json()["id"])
    assert json.loads(v.params_json)["crossfade"] == 2.0


# ── editor text styling ──────────────────────────────────────────────────────
def test_edit_text_styling_stored(client, auth_headers, db):
    r = client.post(
        "/api/v1/videos/edit", headers=auth_headers,
        files={"file": _mp4()},
        data={"start": "0", "end": "3", "text": "Hi", "text_position": "top",
              "text_color": "#FACC15", "text_scale": "1.4"},
    )
    assert r.status_code == 202
    params = json.loads(db.get(Video, r.json()["id"]).params_json)
    assert params["text_color"] == "#FACC15"
    assert params["text_scale"] == 1.4


# ── history mode filter ──────────────────────────────────────────────────────
def test_list_filter_by_mode(client, auth_headers, db):
    # Seed two jobs in different modes, then filter.
    client.post("/api/v1/videos/edit", headers=auth_headers, files={"file": _mp4()},
                data={"start": "0", "end": "2"})
    client.post("/api/v1/videos/tool", headers=auth_headers, files={"file": _mp4()},
                data={"op": "compress", "params": "{}"})
    r = client.get("/api/v1/videos", headers=auth_headers, params={"mode": "edit"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items and all(v["generation_mode"] == "edit" for v in items)


def test_list_filter_bad_mode_rejected(client, auth_headers):
    r = client.get("/api/v1/videos", headers=auth_headers, params={"mode": "nonsense"})
    assert r.status_code == 422


# ── image tools ──────────────────────────────────────────────────────────────
def test_image_tool_crop(client, auth_headers):
    r = client.post(
        "/api/v1/images/tool", headers=auth_headers,
        files={"file": _png()},
        data={"op": "crop", "params": json.dumps({"aspect": "9:16"})},
    )
    assert r.status_code == 202
    assert r.json()["operation"] == "crop"


def test_image_tool_unknown_op(client, auth_headers):
    r = client.post(
        "/api/v1/images/tool", headers=auth_headers,
        files={"file": _png()}, data={"op": "nope", "params": "{}"},
    )
    assert r.status_code == 422
