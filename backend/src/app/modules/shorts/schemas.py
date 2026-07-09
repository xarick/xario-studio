import json
from pydantic import BaseModel, model_validator
from datetime import datetime
from app.db.enums import ShortStatus

_AUDIO_EXT = {"mp3", "wav", "m4a", "aac", "ogg", "flac", "opus"}
_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
_VIDEO_EXT = {"mp4", "mov", "avi", "mkv", "webm", "m4v"}


def _kind_from_path(path: str | None) -> tuple[str, str]:
    """Return (ext, kind) for an output file path. `kind` is one of
    video|audio|image — the UI uses it to pick the right player + label."""
    ext = path.rsplit(".", 1)[-1].lower() if path and "." in path else ""
    if ext in _AUDIO_EXT:
        return ext, "audio"
    if ext in _IMAGE_EXT:
        return ext, "image"
    if ext in _VIDEO_EXT:
        return ext, "video"
    return (ext or "mp4"), "video"


class ShortResponse(BaseModel):
    id: str
    video_id: str
    index_number: int
    start_time: float
    end_time: float
    duration_seconds: float
    clips: list[dict] = []
    status: ShortStatus
    created_at: datetime
    kind: str = "video"     # video | audio | image — drives the result player/label
    ext: str = "mp4"        # real output extension, for accurate download names

    @model_validator(mode="before")
    @classmethod
    def _prepare(cls, data):
        if isinstance(data, dict):
            raw = data.get("clips_json")
            clips = data.get("clips")
            if not clips and raw:
                try:
                    clips = json.loads(raw)
                except Exception:
                    clips = []
            ext, kind = _kind_from_path(data.get("file_path"))
            return {**data, "clips": clips or [], "ext": ext, "kind": kind}

        # SQLAlchemy ORM object → build a plain dict with derived fields.
        raw = getattr(data, "clips_json", None)
        clips = []
        if raw:
            try:
                clips = json.loads(raw)
            except Exception:
                clips = []
        ext, kind = _kind_from_path(getattr(data, "file_path", None))
        return {
            "id": data.id,
            "video_id": data.video_id,
            "index_number": data.index_number,
            "start_time": data.start_time,
            "end_time": data.end_time,
            "duration_seconds": data.duration_seconds,
            "clips": clips,
            "status": data.status,
            "created_at": data.created_at,
            "ext": ext,
            "kind": kind,
        }

    model_config = {"from_attributes": True}
