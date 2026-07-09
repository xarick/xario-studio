import json
import os
import shutil
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.exceptions import ValidationError, NotFoundError
from app.core.uploads import save_upload
from app.db.models.video import Video
from app.db.enums import VideoSourceType, VideoStatus, GenerationMode
from app.modules.videos.repository import VideoRepository
from app.modules.videos.schemas import VideoSubmitURL, VideoListResponse, VideoResponse, VideoStatsResponse

_ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}


class VideoService:
    def __init__(self, db: Session) -> None:
        self.repo = VideoRepository(db)

    async def submit_url(self, payload: VideoSubmitURL, user_id: str) -> Video:
        video = Video(
            user_id=user_id,
            source_type=VideoSourceType.url,
            source_url=payload.url,
            shorts_requested=payload.shorts_count,
            subtitles_enabled=payload.subtitles_enabled,
            subtitle_language=(payload.subtitle_language or None),
            generation_mode=payload.generation_mode,
            transcript_text=(payload.transcript_text or None),
            status=VideoStatus.pending,
        )
        return self.repo.create(video)

    async def submit_upload(
        self,
        file: UploadFile,
        shorts_count: int,
        user_id: str,
        subtitles_enabled: bool = True,
        subtitle_language: str | None = None,
        generation_mode: GenerationMode = GenerationMode.smart,
        transcript_text: str | None = None,
    ) -> Video:
        if not (1 <= shorts_count <= settings.MAX_SHORTS_COUNT):
            raise ValidationError(f"shorts_count must be between 1 and {settings.MAX_SHORTS_COUNT}")

        # Transcribe / cleanup / separate accept audio too; other modes video-only.
        allowed = _ALLOWED_EXTENSIONS
        if generation_mode in (GenerationMode.transcribe, GenerationMode.cleanup, GenerationMode.separate):
            allowed = _ALLOWED_EXTENSIONS | _AUDIO_EXTENSIONS
        file_path = await save_upload(file, allowed)

        video = Video(
            user_id=user_id,
            source_type=VideoSourceType.upload,
            original_filename=file.filename,
            file_path=file_path,
            shorts_requested=shorts_count,
            subtitles_enabled=subtitles_enabled,
            subtitle_language=(subtitle_language or None),
            generation_mode=generation_mode,
            transcript_text=(transcript_text or None),
            status=VideoStatus.pending,
        )
        return self.repo.create(video)

    async def submit_tts(
        self,
        text: str,
        user_id: str,
        language: str | None = None,
        voice: str | None = None,
        reference_audio: UploadFile | None = None,
    ) -> Video:
        text = (text or "").strip()
        if not text:
            raise ValidationError("Text is required for text-to-speech.")
        if len(text) > settings.TTS_MAX_CHARS:
            raise ValidationError(
                f"Text is too long ({len(text)} chars; max {settings.TTS_MAX_CHARS})."
            )

        # Optional voice-clone reference recording (a short, clean audio clip).
        ref_path: str | None = None
        if reference_audio is not None and reference_audio.filename:
            ref_path = await save_upload(reference_audio, _AUDIO_EXTENSIONS)

        video = Video(
            user_id=user_id,
            source_type=VideoSourceType.upload,
            original_filename=(text[:120] or None),
            file_path=ref_path,
            shorts_requested=1,
            subtitles_enabled=False,
            subtitle_language=(language or None),
            generation_mode=GenerationMode.tts,
            transcript_text=text,
            tts_voice=(voice or None),
            status=VideoStatus.pending,
        )
        return self.repo.create(video)

    async def submit_dub(
        self,
        file: UploadFile,
        target_language: str,
        user_id: str,
        source_language: str | None = None,
        voice: str | None = None,
    ) -> Video:
        target_language = (target_language or "").strip()
        if not target_language:
            raise ValidationError("A target language is required for dubbing.")

        # Dub accepts audio or video (audio → dubbed audio out).
        file_path = await save_upload(file, _ALLOWED_EXTENSIONS | _AUDIO_EXTENSIONS)

        video = Video(
            user_id=user_id,
            source_type=VideoSourceType.upload,
            original_filename=file.filename,
            file_path=file_path,
            shorts_requested=1,
            subtitles_enabled=False,
            subtitle_language=(source_language or None),   # whisper source language
            dub_target_language=target_language,
            tts_voice=(voice or None),                     # "" / None → clone original speaker
            generation_mode=GenerationMode.dub,
            status=VideoStatus.pending,
        )
        return self.repo.create(video)

    _SHORT_MAX_SECONDS = 60.5  # YouTube Shorts / Reels / TikTok cap (+ epsilon)

    async def submit_edit(
        self,
        file: UploadFile,
        user_id: str,
        *,
        aspect: str = "9:16",
        fit: str = "crop",
        output_mode: str = "custom",
        segments: list | None = None,
        texts: list | None = None,
        # Legacy single-clip fields (kept so older clients keep working).
        start: float = 0.0,
        end: float = 0.0,
        text: str = "",
        text_position: str = "bottom",
        text_color: str = "",
        text_scale: float = 1.0,
    ) -> Video:
        if fit not in {"crop", "pad"}:
            raise ValidationError("Unsupported fit mode.")
        if output_mode not in {"custom", "short", "phone"}:
            raise ValidationError("Unsupported output mode.")
        # Short/phone presets are always vertical; otherwise honour the picker.
        if output_mode in {"short", "phone"}:
            aspect = "9:16"
        if aspect not in {"9:16", "1:1", "16:9", "original"}:
            raise ValidationError("Unsupported aspect ratio.")

        # The editor is a video-only tool.
        file_path = await save_upload(file, _ALLOWED_EXTENSIONS)

        if segments:
            # ── New multi-segment montage model ──────────────────────────────
            norm_segs = self._normalise_segments(segments)
            if not norm_segs:
                raise ValidationError("At least one valid segment is required.")
            total = sum(s["end"] - s["start"] for s in norm_segs)
            if output_mode == "short" and total > self._SHORT_MAX_SECONDS:
                raise ValidationError(
                    "Short mode allows up to 60 seconds — trim your segments."
                )
            params = {
                "segments": norm_segs,
                "aspect": aspect,
                "fit": fit,
                "output_mode": output_mode,
            }
            norm_texts = self._normalise_texts(texts)
            if norm_texts:
                params["texts"] = norm_texts
        else:
            # ── Legacy single-trim model (unchanged behaviour) ───────────────
            if end <= start:
                raise ValidationError("Trim end must be after start.")
            if text_position not in {"top", "center", "bottom"}:
                raise ValidationError("Unsupported text position.")
            params = {
                "start": round(float(start), 3),
                "end": round(float(end), 3),
                "aspect": aspect,
                "fit": fit,
                "text": (text or "").strip(),
                "text_position": text_position,
                "text_color": (text_color or "").strip(),
                "text_scale": max(0.5, min(2.0, float(text_scale))),
            }

        video = Video(
            user_id=user_id,
            source_type=VideoSourceType.upload,
            original_filename=file.filename,
            file_path=file_path,
            shorts_requested=1,
            subtitles_enabled=False,
            generation_mode=GenerationMode.edit,
            params_json=json.dumps(params),
            status=VideoStatus.pending,
        )
        return self.repo.create(video)

    @staticmethod
    def _normalise_segments(segments: list) -> list[dict]:
        out = []
        for seg in segments or []:
            try:
                s = max(0.0, float(seg["start"]))
                e = float(seg["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if e > s:
                out.append({"start": round(s, 3), "end": round(e, 3)})
        return out

    @staticmethod
    def _normalise_texts(texts: list | None) -> list[dict]:
        out = []
        for it in texts or []:
            if not isinstance(it, dict):
                continue
            t = (str(it.get("text", "")) or "").strip()
            if not t:
                continue
            try:
                s = float(it.get("start", 0.0))
                e = float(it.get("end", 0.0))
            except (TypeError, ValueError):
                continue
            if e <= s:
                continue
            pos = it.get("position", "bottom")
            if pos not in {"top", "center", "bottom"}:
                pos = "bottom"
            try:
                scale = max(0.5, min(2.0, float(it.get("scale", 1.0) or 1.0)))
            except (TypeError, ValueError):
                scale = 1.0
            out.append({
                "text": t[:500],
                "start": round(s, 3),
                "end": round(e, 3),
                "position": pos,
                "color": str(it.get("color", ""))[:9],
                "scale": scale,
            })
        return out

    # Which ops operate on video vs audio (decides the accepted upload types).
    _VIDEO_TOOL_OPS = {"compress", "speed", "gif", "extract_audio", "aspect", "watermark"}
    _AUDIO_TOOL_OPS = {"trim", "convert", "volume", "pitch"}

    async def submit_tool(
        self, file: UploadFile, op: str, params: dict, user_id: str,
        extra: UploadFile | None = None,
    ) -> Video:
        if op in self._VIDEO_TOOL_OPS:
            allowed = _ALLOWED_EXTENSIONS
        elif op in self._AUDIO_TOOL_OPS:
            allowed = _AUDIO_EXTENSIONS
        else:
            raise ValidationError(f"Unknown tool: {op}")

        file_path = await save_upload(file, allowed)
        params = dict(params or {})

        # Watermark needs a logo image as a second upload.
        if op == "watermark":
            if not (extra and extra.filename):
                raise ValidationError("A logo image is required for the watermark tool.")
            params["logo_path"] = await save_upload(extra, {".png", ".jpg", ".jpeg", ".webp"})

        payload = {"op": op, **params}
        video = Video(
            user_id=user_id,
            source_type=VideoSourceType.upload,
            original_filename=file.filename,
            file_path=file_path,
            shorts_requested=1,
            subtitles_enabled=False,
            generation_mode=GenerationMode.tool,
            params_json=json.dumps(payload),
            status=VideoStatus.pending,
        )
        return self.repo.create(video)

    async def submit_merge(
        self, files: list[UploadFile], op: str, params: dict, user_id: str,
        music: UploadFile | None = None,
    ) -> Video:
        files = [f for f in files if f and f.filename]
        if op == "concat":
            if len(files) < 2:
                raise ValidationError("Concat needs at least two audio files.")
        elif op == "mix":
            if len(files) != 2:
                raise ValidationError("Mix needs exactly two files (voice + music).")
        elif op == "vconcat":
            if len(files) < 2:
                raise ValidationError("Video merge needs at least two videos.")
        else:
            raise ValidationError(f"Unknown merge op: {op}")
        if len(files) > 20:
            raise ValidationError("Too many files (max 20).")

        allowed = _ALLOWED_EXTENSIONS if op == "vconcat" else _AUDIO_EXTENSIONS
        paths = [await save_upload(f, allowed) for f in files]
        params = dict(params or {})
        # Optional background music for the video merge.
        if op == "vconcat" and music and music.filename:
            params["music_path"] = await save_upload(music, _AUDIO_EXTENSIONS)
        payload = {"op": op, "paths": paths, **params}
        video = Video(
            user_id=user_id,
            source_type=VideoSourceType.upload,
            original_filename=files[0].filename,
            file_path=paths[0],          # so probe() has a valid input
            shorts_requested=1,
            subtitles_enabled=False,
            generation_mode=GenerationMode.tool,
            params_json=json.dumps(payload),
            status=VideoStatus.pending,
        )
        return self.repo.create(video)

    @staticmethod
    def parse_modes(mode: str | None) -> list[GenerationMode] | None:
        """"dub,tts" → [dub, tts]. Unknown names are a client error."""
        if not mode:
            return None
        try:
            return [GenerationMode(m) for m in (p.strip() for p in mode.split(",")) if m]
        except ValueError as exc:
            raise ValidationError(f"Unknown generation mode: {exc}") from exc

    def get_video(self, video_id: str, owner_id: str | None = None) -> Video:
        video = self.repo.get_by_id(video_id)
        # Hide other users' rows behind a 404 rather than leaking their existence.
        if not video or (owner_id is not None and video.user_id != owner_id):
            raise NotFoundError(f"Video {video_id} not found")
        return video

    def list_videos(
        self,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        status: str | None = None,
        mode: str | None = None,
        owner_id: str | None = None,
    ) -> VideoListResponse:
        """`mode` accepts one mode or a comma-separated set, so a module's
        history page (audio, video) can ask for just its own job types."""
        limit = min(limit, 100)
        status_enum = VideoStatus(status) if status else None
        modes = self.parse_modes(mode)
        items, total = self.repo.list_paginated(page, limit, search, status_enum, modes, owner_id)
        pages = (total + limit - 1) // limit if total else 0
        return VideoListResponse(
            items=[VideoResponse.model_validate(v) for v in items],
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    def get_stats(self, owner_id: str | None = None) -> VideoStatsResponse:
        return VideoStatsResponse(**self.repo.get_stats(owner_id))

    # Written into error_message so the UI (and the user) can tell a cancelled
    # job from a crashed one without adding a status enum value.
    CANCEL_MESSAGE = "Cancelled by the user."
    _ACTIVE_STATES = (VideoStatus.pending, VideoStatus.downloading, VideoStatus.processing)

    def cancel_video(self, video_id: str, owner_id: str | None = None) -> Video:
        """Stop a queued or running job.

        A queued task is revoked and never starts. A running one is marked
        terminal here; the worker sees that at its next stage boundary and
        unwinds. Killing it outright would orphan the ffmpeg child process.
        """
        from app.workers.queues import revoke

        video = self.get_video(video_id, owner_id)
        if video.status not in self._ACTIVE_STATES:
            raise ValidationError("This job has already finished.")

        revoke(video.id)
        self.repo.update_status(video.id, VideoStatus.failed, error_message=self.CANCEL_MESSAGE)
        return self.get_video(video_id, owner_id)

    def delete_video(self, video_id: str, owner_id: str | None = None) -> None:
        import logging
        log = logging.getLogger(__name__)
        video = self.get_video(video_id, owner_id)

        # Removing the output directory under a running worker would make it
        # fail mid-encode on a missing path. Stop the job first.
        if video.status in self._ACTIVE_STATES:
            log.info("Cancelling active job %s before deleting it", video_id)
            self.cancel_video(video_id, owner_id)

        # Delete all processed shorts
        output_dir = os.path.join(settings.OUTPUT_DIR, video_id)
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
            log.info("Deleted output dir: %s", output_dir)

        # Delete original uploaded / downloaded file
        if video.file_path and os.path.exists(video.file_path):
            try:
                os.remove(video.file_path)
                log.info("Deleted upload file: %s", video.file_path)
            except OSError as exc:
                log.warning("Could not delete upload file %s: %s", video.file_path, exc)

        self.repo.delete(video)
