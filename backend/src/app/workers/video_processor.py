"""
Video processing pipeline.
Orchestrates: download → probe → validate → transcribe → segment → cut.
"""
import logging
import os
import random
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import VideoSourceType, VideoStatus, ShortStatus, NotificationType, GenerationMode
from app.db.models.short import Short
from app.db.models.notification import Notification
from app.db.session import SessionLocal
from app.modules.videos.repository import VideoRepository
from app.modules.shorts.repository import ShortRepository
from app.modules.notifications.repository import NotificationRepository
from app.workers import ffmpeg, highlights, reframe

logger = logging.getLogger(__name__)


class JobCancelled(RuntimeError):
    """The job row was marked terminal by a cancel request while it was running."""


def _raise_if_cancelled(video_repo, video_id: str) -> None:
    """Cooperative cancellation checkpoint.

    Killing the worker mid-encode would orphan its ffmpeg child, so a cancel
    only marks the row; the pipeline notices at the next stage boundary and
    stops. `revoke()` already prevents a still-queued job from ever starting.
    """
    status = video_repo.current_status(video_id)
    if status is None or status is VideoStatus.failed:
        raise JobCancelled(video_id)


def _progress_reporter(video_repo, video_id: str, *, lo: int = 55, hi: int = 99):
    """Build a callback that maps an ffmpeg completion fraction (0..1) onto a
    DB progress percent in the [lo, hi] band, so long encodes show live motion
    instead of sitting at 55% until they finish. Best-effort — never raises."""
    span = hi - lo

    def report(frac: float) -> None:
        try:
            video_repo.update_progress(video_id, lo + int(max(0.0, min(1.0, frac)) * span))
        except Exception:  # noqa: BLE001 — progress writes must not fail the job
            pass

    return report


def _create_notification(db, video, *, completed: bool, shorts_count: int = 0) -> None:
    try:
        title = (video.original_filename or video.source_url or "Video")[:200]
        notif = Notification(
            user_id=video.user_id,
            type=NotificationType.job_completed if completed else NotificationType.job_failed,
            title=title,
            shorts_count=shorts_count,
            video_id=video.id,
        )
        repo = NotificationRepository(db)
        repo.create(notif)
        repo.delete_old(video.user_id, keep=50)
    except Exception as exc:
        logger.warning("Could not create notification: %s", exc)


def _fail(db, video, video_repo, exc: Exception) -> None:
    """Mark a job failed and notify its owner — the single place every pipeline
    stage reports a failure, so the behaviour stays consistent."""
    video_repo.update_status(video.id, VideoStatus.failed, error_message=str(exc))
    if video.user_id:
        _create_notification(db, video, completed=False)


def _validate_feasibility(duration: float, shorts_count: int, mode: GenerationMode) -> None:
    min_dur = settings.MIN_SHORT_DURATION

    # Smart/Pro produce VARIATIONS of the same footage, so any number of shorts
    # is fine as long as the video is long enough for a single highlight short.
    if mode in (GenerationMode.smart, GenerationMode.pro):
        if duration < min_dur:
            raise ValueError(
                f"Video is only {duration:.1f}s — need at least {min_dur}s to build a short."
            )
        return

    # Simple mode slices the video into distinct contiguous parts.
    per_short = duration / shorts_count
    if per_short < min_dur:
        max_possible = int(duration // min_dur)
        raise ValueError(
            f"Video is {duration:.1f}s but {shorts_count} shorts would each be only "
            f"{per_short:.1f}s (minimum {min_dur}s per short). "
            f"Maximum {max_possible} short(s) possible — or switch to Smart mode."
        )


def process_video(video_id: str) -> None:
    db: Session = SessionLocal()
    try:
        _run_pipeline(db, video_id)
    except JobCancelled:
        # The row is already terminal and carries the cancel message; leave it.
        logger.info("Video %s cancelled — stopping the pipeline", video_id)
    except Exception as exc:
        logger.exception("Unexpected error processing video %s", video_id)
        try:
            video_repo = VideoRepository(db)
            video = video_repo.get_by_id(video_id)
            if video is not None:
                # Route through _fail so the owner is notified here too, exactly
                # as they are when a pipeline stage reports the failure itself.
                _fail(db, video, video_repo, exc)
            else:
                video_repo.update_status(video_id, VideoStatus.failed, error_message=str(exc))
        except Exception:
            logger.exception("Could not mark video %s failed", video_id)
    finally:
        db.close()


def _simple_segments(
    duration: float,
    count: int,
    word_timestamps=None,
) -> list[list[tuple[float, float]]]:
    """
    Simple mode: each short is ONE contiguous clip, evenly spread across the
    video. Each clip varies in length between SIMPLE_MIN_DURATION and
    MAX_SHORT_DURATION (so they're not all exactly 60s), is centered in its
    window, and — when a transcript is available — snaps to speech boundaries
    so it doesn't start/end mid-word.
    """
    rng = random.Random(int(duration))
    window = duration / count
    segments = []
    for i in range(count):
        target = rng.uniform(settings.SIMPLE_MIN_DURATION, settings.MAX_SHORT_DURATION)
        clip_len = min(window, target)
        start = max(0.0, i * window + (window - clip_len) / 2)
        end = min(start + clip_len, duration)
        if word_timestamps:
            start, end = highlights.snap_to_speech(start, end, word_timestamps)
        segments.append([(round(start, 2), round(end, 2))])
    return segments


def _smart_segments(
    video_path: str,
    duration: float,
    word_timestamps,
    count: int,
) -> list[list[tuple[float, float]]]:
    """
    Smart mode: find highlight moments (scene changes + speech density) and
    assemble `count` distinct variations of a compilation short.
    Falls back to simple splits if no usable highlights are found.
    """
    candidates = highlights.build_candidates(
        video_path,
        duration,
        word_timestamps,
        clip_min=settings.SMART_CLIP_MIN,
        clip_max=settings.SMART_CLIP_MAX,
        scene_threshold=settings.SCENE_DETECT_THRESHOLD,
        seed=int(duration),
    )
    variations = highlights.generate_variations(
        candidates,
        count,
        target_min=settings.MIN_SHORT_DURATION,
        target_max=settings.MAX_SHORT_DURATION,
        seed=int(duration),
    )
    if len(variations) != count:
        logger.warning("Smart engine returned %d/%d shorts — using simple splits",
                       len(variations), count)
        return _simple_segments(duration, count, word_timestamps)
    return variations


def _run_subtitle_mode(db, video, meta, video_repo, short_repo) -> None:
    """
    Subtitle (align) mode: the user supplied the exact transcript. Whisper gives
    timing, we force-align the user's text to it, and burn subtitles onto the
    WHOLE video at its original size (no splitting, no cropping).
    """
    import json as _json
    from app.workers.transcriber import transcribe as _transcribe
    from app.workers import aligner
    from app.workers.subtitle import build_ass_for_clips, burn_subtitles

    text = (video.transcript_text or "").strip()
    if not text:
        raise ValueError("Subtitle mode requires transcript text.")

    # 1. Whisper — timing reference only (its words may be wrong; we don't use them as text).
    video_repo.update_status(video.id, VideoStatus.processing, progress=30)
    lang = video.subtitle_language or settings.WHISPER_LANGUAGE
    logger.info("Subtitle mode: transcribing %s for timing (lang=%s)", video.id, lang or "auto")
    whisper_words = _transcribe(
        video.file_path,
        model_size=settings.WHISPER_MODEL_SIZE,
        device=settings.WHISPER_DEVICE,
        language=lang,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )

    # 2. Align the user's text onto the timeline.
    video_repo.update_status(video.id, VideoStatus.processing, progress=60)
    words = aligner.align_text(text, whisper_words, meta.duration)

    # 3. Build ASS at the video's real size and burn onto the full video.
    video_repo.update_status(video.id, VideoStatus.processing, progress=72)
    ass = build_ass_for_clips(
        words, [(0.0, meta.duration)],
        words_per_line=settings.SUBTITLE_WORDS_PER_LINE,
        style=settings.SUBTITLE_STYLE,
        play_w=meta.width or 1080,
        play_h=meta.height or 1920,
    )

    output_dir = os.path.join(settings.OUTPUT_DIR, video.id)
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, "subtitled.mp4")

    short = short_repo.bulk_create([Short(
        video_id=video.id, index_number=1,
        start_time=0.0, end_time=meta.duration, duration_seconds=meta.duration,
        clips_json=_json.dumps([{"start": 0.0, "end": meta.duration}]),
        status=ShortStatus.processing,
    )])[0]

    burn_subtitles(video.file_path, out_file, ass)   # copies unchanged if ass is empty
    short_repo.update_status(short.id, ShortStatus.completed, file_path=out_file)

    video_repo.update_status(video.id, VideoStatus.completed, progress=100)
    logger.info("Subtitle mode done for %s", video.id)
    if video.user_id:
        _create_notification(db, video, completed=True, shorts_count=1)


def _run_edit_mode(db, video, meta, video_repo, short_repo) -> None:
    """
    Manual montage: keep one or more [start, end] segments of the source, join
    them, fit to a target aspect, and burn timed text overlays. Params come from
    video.params_json:
      { segments:[{start,end}], aspect, fit, output_mode,
        texts:[{text,start,end,position,color,scale}] }
    Legacy single-clip params { start, end, text, text_position, … } are still
    accepted. Produces one edited video Short.
    """
    import json as _json
    from app.workers import ffmpeg as _ffmpeg
    from app.workers.subtitle import (
        build_static_text_ass, build_multi_text_ass, write_temp_ass,
    )

    params = _json.loads(video.params_json or "{}")

    # Segments — new multi-cut model, with a fallback to the legacy single trim.
    raw_segments = params.get("segments")
    if raw_segments:
        segments = []
        for seg in raw_segments:
            try:
                s = max(0.0, float(seg.get("start", 0.0)))
                e = min(float(seg.get("end", meta.duration)), meta.duration)
            except (TypeError, ValueError):
                continue
            if e > s:
                segments.append((s, e))
    else:
        s = max(0.0, float(params.get("start", 0.0)))
        e = min(float(params.get("end", meta.duration) or meta.duration), meta.duration)
        segments = [(s, e)] if e > s else []
    if not segments:
        raise ValueError("Invalid edit: at least one valid segment is required.")

    aspect = params.get("aspect", "9:16")
    fit = params.get("fit", "crop")
    total_dur = sum(e - s for s, e in segments)

    # Size the text overlay to the OUTPUT frame so it scales correctly.
    dims = _ffmpeg.ASPECT_DIMS.get(aspect)
    play_w, play_h = dims if dims else (meta.width or 1080, meta.height or 1920)

    # Text overlays — new timed list, with a fallback to the legacy single text.
    ass = ""
    raw_texts = params.get("texts")
    if raw_texts:
        ass = build_multi_text_ass(raw_texts, play_w=play_w, play_h=play_h)
    elif (params.get("text") or "").strip():
        ass = build_static_text_ass(
            params["text"].strip(), total_dur, params.get("text_position", "bottom"),
            play_w=play_w, play_h=play_h,
            color=params.get("text_color", ""), font_scale=float(params.get("text_scale", 1.0)),
        )
    ass_path = write_temp_ass(ass) if ass else None

    output_dir = os.path.join(settings.OUTPUT_DIR, video.id)
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, "edited.mp4")

    short = short_repo.bulk_create([Short(
        video_id=video.id, index_number=1,
        start_time=segments[0][0], end_time=segments[-1][1], duration_seconds=round(total_dur, 3),
        clips_json=_json.dumps([{"start": s, "end": e} for s, e in segments]),
        status=ShortStatus.processing,
    )])[0]

    video_repo.update_status(video.id, VideoStatus.processing, progress=55)
    logger.info("Edit mode: %s segments=%d total=%.2fs aspect=%s fit=%s texts=%s",
                video.id, len(segments), total_dur, aspect, fit,
                len(raw_texts) if raw_texts else bool(ass))
    try:
        _ffmpeg.edit_video(
            video.file_path, out_file,
            aspect=aspect, fit=fit, subtitle_path=ass_path, segments=segments,
            on_progress=_progress_reporter(video_repo, video.id),
        )
    finally:
        if ass_path and os.path.exists(ass_path):
            try:
                os.remove(ass_path)
            except OSError:
                pass

    short_repo.update_status(short.id, ShortStatus.completed, file_path=out_file)
    video_repo.update_status(video.id, VideoStatus.completed, progress=100)
    logger.info("Edit mode done for %s", video.id)
    if video.user_id:
        _create_notification(db, video, completed=True, shorts_count=1)


def _run_tool_mode(db, video, meta, video_repo, short_repo) -> None:
    """
    Single-purpose media tool. params_json["op"] selects the operation; the rest
    of params_json are its arguments. Produces one downloadable Short whose
    extension depends on the op.
    """
    import json as _json
    from app.workers import tools

    params = _json.loads(video.params_json or "{}")
    op = params.get("op")

    output_dir = os.path.join(settings.OUTPUT_DIR, video.id)
    os.makedirs(output_dir, exist_ok=True)

    # Multi-file ops (audio merge / video merge) read inputs from params["paths"].
    if op in ("concat", "mix", "vconcat"):
        out_ext = "mp4" if op == "vconcat" else "mp3"
        out_file = os.path.join(output_dir, f"{op}.{out_ext}")
        short = short_repo.bulk_create([Short(
            video_id=video.id, index_number=1,
            start_time=0.0, end_time=meta.duration, duration_seconds=meta.duration,
            clips_json=_json.dumps([{"start": 0.0, "end": meta.duration}]),
            status=ShortStatus.processing,
        )])[0]
        video_repo.update_status(video.id, VideoStatus.processing, progress=55)
        paths = params.get("paths") or []
        logger.info("Tool mode: %s op=%s files=%d", video.id, op, len(paths))
        if op == "concat":
            tools.concat_audio(paths, out_file, crossfade=float(params.get("crossfade", 0.0)))
        elif op == "vconcat":
            tools.concat_videos(
                paths, out_file,
                transition=params.get("transition", "fade"),
                duration=float(params.get("duration", 1.0)),
                aspect=params.get("aspect", "9:16"),
                music_path=params.get("music_path"),
                music_volume=float(params.get("music_volume", 0.5)),
                on_progress=_progress_reporter(video_repo, video.id),
            )
        else:
            tools.mix_audio(paths[0], paths[1], out_file,
                            music_volume=float(params.get("music_volume", 0.25)))
        short_repo.update_status(short.id, ShortStatus.completed, file_path=out_file)
        video_repo.update_status(video.id, VideoStatus.completed, progress=100)
        if video.user_id:
            _create_notification(db, video, completed=True, shorts_count=1)
        return

    # op -> (callable, output extension, kwargs)
    handlers = {
        "compress":      (tools.compress,       "mp4", {"crf": int(params.get("crf", 28))}),
        "speed":         (tools.change_speed,   "mp4", {"factor": float(params.get("factor", 1.0))}),
        "gif":           (tools.to_gif,         "gif", {"start": float(params.get("start", 0.0)),
                                                        "end": params.get("end"),
                                                        "fps": int(params.get("fps", 12)),
                                                        "width": int(params.get("width", 480))}),
        "extract_audio": (tools.extract_audio,  "mp3", {}),
        "watermark":     (tools.watermark,      "mp4", {"logo_path": params.get("logo_path"),
                                                        "position": params.get("position", "bottom-right"),
                                                        "opacity": float(params.get("opacity", 1.0)),
                                                        "scale": float(params.get("scale", 0.2))}),
        "aspect":        (tools.convert_aspect, "mp4", {"aspect": params.get("aspect", "9:16"),
                                                        "fit": params.get("fit", "crop"),
                                                        "duration": meta.duration}),
        "trim":          (tools.trim_audio,     "mp3", {"start": float(params.get("start", 0.0)),
                                                        "end": params.get("end")}),
        "convert":       (tools.convert_audio,  params.get("fmt", "mp3"),
                                                       {"fmt": params.get("fmt", "mp3")}),
        "volume":        (tools.adjust_volume,  "mp3", {"db": float(params.get("db", 0.0))}),
        "pitch":         (tools.change_pitch,   "mp3", {"semitones": float(params.get("semitones", 0.0))}),
    }
    entry = handlers.get(op)
    if entry is None:
        raise ValueError(f"Unknown tool op: {op}")
    fn, ext, kwargs = entry

    out_file = os.path.join(output_dir, f"{op}.{ext}")

    short = short_repo.bulk_create([Short(
        video_id=video.id, index_number=1,
        start_time=0.0, end_time=meta.duration, duration_seconds=meta.duration,
        clips_json=_json.dumps([{"start": 0.0, "end": meta.duration}]),
        status=ShortStatus.processing,
    )])[0]

    video_repo.update_status(video.id, VideoStatus.processing, progress=55)
    logger.info("Tool mode: %s op=%s -> %s", video.id, op, out_file)
    # Slow re-encodes report live progress (output length ≈ source length).
    if op in ("compress", "watermark"):
        kwargs = {**kwargs, "on_progress": _progress_reporter(video_repo, video.id),
                  "total_dur": meta.duration}
    fn(video.file_path, out_file, **kwargs)

    short_repo.update_status(short.id, ShortStatus.completed, file_path=out_file)
    video_repo.update_status(video.id, VideoStatus.completed, progress=100)
    logger.info("Tool mode done for %s (%s)", video.id, op)
    if video.user_id:
        _create_notification(db, video, completed=True, shorts_count=1)


def _run_transcribe_mode(db, video, meta, video_repo, short_repo=None) -> None:
    """
    Speech-to-text: transcribe an audio/video file into timed segments and store
    them. No media output — the result is a downloadable transcript.
    """
    import json as _json
    from app.workers.transcriber import transcribe_segments

    video_repo.update_status(video.id, VideoStatus.processing, progress=35)
    lang = video.subtitle_language or settings.WHISPER_LANGUAGE
    logger.info("Transcribe mode: %s (lang=%s)", video.id, lang or "auto")
    segments = transcribe_segments(
        video.file_path,
        model_size=settings.WHISPER_MODEL_SIZE,
        device=settings.WHISPER_DEVICE,
        language=lang,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )
    if not segments:
        raise ValueError("No speech detected in the file.")

    text = "\n".join(s["text"] for s in segments).strip()
    video_repo.save_transcript(video.id, text, _json.dumps(segments, ensure_ascii=False))
    video_repo.update_status(video.id, VideoStatus.completed, progress=100)
    logger.info("Transcribe mode done for %s (%d segments)", video.id, len(segments))
    if video.user_id:
        _create_notification(db, video, completed=True, shorts_count=0)


def _run_cleanup_mode(db, video, meta, video_repo, short_repo) -> None:
    """
    Audio cleanup: loudness-normalise + denoise (+ trim silence for audio-only).
    Video keeps its video stream; audio-only outputs MP3.
    """
    import json as _json

    has_video = bool(meta.width and meta.height)
    out_ext = "mp4" if has_video else "mp3"
    output_dir = os.path.join(settings.OUTPUT_DIR, video.id)
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"cleaned.{out_ext}")

    short = short_repo.bulk_create([Short(
        video_id=video.id, index_number=1,
        start_time=0.0, end_time=meta.duration, duration_seconds=meta.duration,
        clips_json=_json.dumps([{"start": 0.0, "end": meta.duration}]),
        status=ShortStatus.processing,
    )])[0]

    video_repo.update_status(video.id, VideoStatus.processing, progress=45)
    logger.info("Cleanup mode: %s (video=%s)", video.id, has_video)
    ffmpeg.clean_audio(video.file_path, out_file, has_video, duration=meta.duration)

    short_repo.update_status(short.id, ShortStatus.completed, file_path=out_file)
    video_repo.update_status(video.id, VideoStatus.completed, progress=100)
    logger.info("Cleanup mode done for %s", video.id)
    if video.user_id:
        _create_notification(db, video, completed=True, shorts_count=1)


def _run_separate_mode(db, video, meta, video_repo, short_repo) -> None:
    """
    Vocal/music separation (Demucs). Produces vocals + instrumental (and a
    karaoke video for video input), each stored as a downloadable Short:
    index 1 = vocals, 2 = instrumental, 3 = karaoke.
    """
    import json as _json
    from app.workers import separate as _separate

    has_video = bool(meta.width and meta.height)
    output_dir = os.path.join(settings.OUTPUT_DIR, video.id)
    video_repo.update_status(video.id, VideoStatus.processing, progress=45)
    logger.info("Separate mode: %s (video=%s)", video.id, has_video)

    result = _separate.separate(video.file_path, output_dir, has_video=has_video)

    ordered = [("vocals", result.get("vocals")),
               ("instrumental", result.get("instrumental")),
               ("karaoke", result.get("karaoke"))]
    idx = 0
    for _name, path in ordered:
        if not path:
            continue
        idx += 1
        short = short_repo.bulk_create([Short(
            video_id=video.id, index_number=idx,
            start_time=0.0, end_time=meta.duration, duration_seconds=meta.duration,
            clips_json=_json.dumps([{"start": 0.0, "end": meta.duration}]),
            status=ShortStatus.completed,
        )])[0]
        short_repo.update_status(short.id, ShortStatus.completed, file_path=path)

    video_repo.update_status(video.id, VideoStatus.completed, progress=100)
    logger.info("Separate mode done for %s (%d stems)", video.id, idx)
    if video.user_id:
        _create_notification(db, video, completed=True, shorts_count=idx)


def _run_dub_mode(db, video, meta, video_repo, short_repo) -> None:
    """
    Translate + dub: transcribe the source, translate each segment to the target
    language, re-voice it with XTTS (cloning the original speaker unless a
    built-in voice was chosen), time-fit to the original timing, and mux back.
    Produces ONE Short: the dubbed video (or dubbed audio for audio input).
    """
    import json as _json
    from app.workers.transcriber import transcribe_segments
    from app.workers import tts as _tts, dub as _dub
    from app.workers.ai.factory import get_ai_provider

    target = (video.dub_target_language or "").strip()
    if not target:
        raise ValueError("Dub mode requires a target language.")

    has_video = bool(meta.width and meta.height)
    output_dir = os.path.join(settings.OUTPUT_DIR, video.id)
    os.makedirs(output_dir, exist_ok=True)

    # 1. Transcribe the source into timed segments.
    video_repo.update_status(video.id, VideoStatus.processing, progress=25)
    src_lang = video.subtitle_language or settings.WHISPER_LANGUAGE
    logger.info("Dub mode: transcribing %s (src=%s → %s)", video.id, src_lang or "auto", target)
    segments = transcribe_segments(
        video.file_path,
        model_size=settings.WHISPER_MODEL_SIZE,
        device=settings.WHISPER_DEVICE,
        language=src_lang,
        compute_type=settings.WHISPER_COMPUTE_TYPE,
    )
    if not segments:
        raise ValueError("No speech detected to dub.")

    # 2. Translate each segment to the target language.
    video_repo.update_status(video.id, VideoStatus.processing, progress=45)
    texts = [s["text"] for s in segments]
    translated = get_ai_provider().translate_batch(texts, target, src_lang or None)
    logger.info("Dub mode: translated %d segments → %s", len(translated), target)

    # 3. Synthesise — clone the original speaker unless a built-in voice was chosen.
    video_repo.update_status(video.id, VideoStatus.processing, progress=55)
    speaker_wav = None
    if not (video.tts_voice or "").strip():
        ref = os.path.join(output_dir, "ref.wav")
        speaker_wav = _dub.extract_reference(video.file_path, ref, settings.DUB_REF_MAX_SECONDS)
    wavs = _tts.synthesize_batch(
        translated, os.path.join(output_dir, "seg"),
        language=target, voice=(video.tts_voice or None), speaker_wav=speaker_wav,
    )

    # 4. Assemble the dubbed track on the original timeline + mux back.
    video_repo.update_status(video.id, VideoStatus.processing, progress=80)
    seg_dicts = [{"start": s["start"], "end": s["end"], "text": t}
                 for s, t in zip(segments, translated)]
    dub_wav = _dub.build_dubbed_audio(seg_dicts, wavs, output_dir, meta.duration)
    out_ext = "mp4" if has_video else "mp3"
    out_file = os.path.join(output_dir, f"dubbed.{out_ext}")
    _dub.mux(video.file_path, dub_wav, out_file, has_video=has_video, duration=meta.duration)
    # The per-segment WAVs are worthless once muxed, and there are one per line.
    _dub.cleanup_intermediates(output_dir)

    # Keep the translated transcript for transparency / future subtitle overlay.
    full = [{"start": s["start"], "end": s["end"], "text": s["text"], "translated": t}
            for s, t in zip(segments, translated)]
    video_repo.save_transcript(video.id, "\n".join(translated), _json.dumps(full, ensure_ascii=False))

    short = short_repo.bulk_create([Short(
        video_id=video.id, index_number=1,
        start_time=0.0, end_time=meta.duration, duration_seconds=meta.duration,
        clips_json=_json.dumps([{"start": 0.0, "end": meta.duration}]),
        status=ShortStatus.processing,
    )])[0]
    short_repo.update_status(short.id, ShortStatus.completed, file_path=out_file)

    video_repo.update_status(video.id, VideoStatus.completed, progress=100)
    logger.info("Dub mode done for %s", video.id)
    if video.user_id:
        _create_notification(db, video, completed=True, shorts_count=1)


def _run_tts_mode(db, video, video_repo, short_repo) -> None:
    """
    Text-to-speech (Coqui XTTS-v2). No input media: the user supplied text + a
    language (+ optionally a reference voice in video.file_path). Synthesises one
    audio clip, stored as a single downloadable Short.
    """
    import json as _json
    from app.workers import tts as _tts

    text = (video.transcript_text or "").strip()
    if not text:
        raise ValueError("TTS mode requires text to synthesise.")

    output_dir = os.path.join(settings.OUTPUT_DIR, video.id)
    video_repo.update_status(video.id, VideoStatus.processing, progress=30)
    logger.info("TTS mode: %s (lang=%s, %d chars)", video.id, video.subtitle_language, len(text))

    speaker_wav = video.file_path if (video.file_path and os.path.exists(video.file_path)) else None
    result = _tts.synthesize(
        text, output_dir,
        language=video.subtitle_language,
        voice=video.tts_voice,
        speaker_wav=speaker_wav,
    )
    audio_path = result["audio"]

    # Probe the produced audio for its real duration.
    try:
        duration = ffmpeg.probe(audio_path).duration
    except Exception:
        duration = 0.0
    video_repo.update_file_info(video.id, video.file_path, duration)

    short = short_repo.bulk_create([Short(
        video_id=video.id, index_number=1,
        start_time=0.0, end_time=duration, duration_seconds=duration,
        clips_json=_json.dumps([{"start": 0.0, "end": duration}]),
        status=ShortStatus.processing,
    )])[0]
    short_repo.update_status(short.id, ShortStatus.completed, file_path=audio_path)

    video_repo.update_status(video.id, VideoStatus.completed, progress=100)
    logger.info("TTS mode done for %s (%.1fs)", video.id, duration)
    if video.user_id:
        _create_notification(db, video, completed=True, shorts_count=1)


# Modes that produce their own output and short-circuit the normal shorts
# pipeline. Each handler has the signature (db, video, meta, video_repo,
# short_repo). TTS is NOT here — it runs before probe (it has no input media).
_SPECIAL_MODES = {
    GenerationMode.subtitle: _run_subtitle_mode,
    GenerationMode.transcribe: _run_transcribe_mode,
    GenerationMode.cleanup: _run_cleanup_mode,
    GenerationMode.separate: _run_separate_mode,
    GenerationMode.dub: _run_dub_mode,
    GenerationMode.edit: _run_edit_mode,
    GenerationMode.tool: _run_tool_mode,
}


def _run_pipeline(db: Session, video_id: str) -> None:
    video_repo = VideoRepository(db)
    short_repo = ShortRepository(db)

    video = video_repo.get_by_id(video_id)
    if not video:
        logger.error("Video %s not found — skipping", video_id)
        return

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    # ── 0. TTS mode: no input media — synthesise speech from text ─────────────
    if video.generation_mode is GenerationMode.tts:
        try:
            _run_tts_mode(db, video, video_repo, short_repo)
        except Exception as exc:
            logger.exception("tts mode failed for %s", video_id)
            _fail(db, video, video_repo, exc)
        return

    # ── 1. Fetch video info (URL source) ─────────────────────────────────────
    video_info = ffmpeg.VideoInfo()
    if video.source_type is VideoSourceType.url:
        video_repo.update_status(video_id, VideoStatus.downloading, progress=5)
        logger.info("Fetching metadata for %s", video.source_url)
        try:
            video_info = ffmpeg.get_yt_info(
                video.source_url,
                cookies_file=settings.YTDLP_COOKIES_FILE,
                cookies_browser=settings.YTDLP_COOKIES_FROM_BROWSER,
            )
            logger.info("Got info: title=%r, chapters=%d, transcript_len=%d",
                        video_info.title, len(video_info.chapters), len(video_info.transcript))
        except Exception as exc:
            logger.warning("Could not fetch video info: %s", exc)

    # ── 2. Download (URL source only) ─────────────────────────────────────────
    if video.source_type is VideoSourceType.url:
        dest = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4()}.mp4")
        try:
            ffmpeg.download_url(video.source_url, dest)
        except ffmpeg.MediaError as exc:
            _fail(db, video, video_repo, exc)
            return
        video_repo.update_file_info(video_id, dest, 0)
        video.file_path = dest

    # ── 3. Probe ──────────────────────────────────────────────────────────────
    video_repo.update_status(video_id, VideoStatus.processing, progress=25)
    try:
        meta = ffmpeg.probe(video.file_path)
    except ffmpeg.MediaError as exc:
        _fail(db, video, video_repo, exc)
        return

    _raise_if_cancelled(video_repo, video_id)

    # ── 3b. Single-output modes: each produces its own file(s) and short-circuits
    #        the normal shorts pipeline. Dispatched by mode via _SPECIAL_MODES.
    handler = _SPECIAL_MODES.get(video.generation_mode)
    if handler is not None:
        video_repo.update_file_info(video_id, video.file_path, meta.duration)
        try:
            handler(db, video, meta, video_repo, short_repo)
        except JobCancelled:
            raise
        except Exception as exc:
            logger.exception("%s mode failed for %s", video.generation_mode.value, video_id)
            _fail(db, video, video_repo, exc)
        return

    # ── 4. Validate ───────────────────────────────────────────────────────────
    try:
        _validate_feasibility(meta.duration, video.shorts_requested, video.generation_mode)
    except ValueError as exc:
        _fail(db, video, video_repo, exc)
        return

    video_repo.update_file_info(video_id, video.file_path, meta.duration)

    # ── 5. Transcribe (needed for subtitles + smart speech-density scoring) ────
    from app.workers.transcriber import transcribe as _transcribe
    word_timestamps = []
    need_transcript = video.subtitles_enabled or video.generation_mode in (
        GenerationMode.smart, GenerationMode.pro,
    )
    if need_transcript:
        video_repo.update_status(video_id, VideoStatus.processing, progress=30)
        lang = video.subtitle_language or settings.WHISPER_LANGUAGE
        logger.info("Transcribing %s (subtitles=%s, lang=%s)",
                    video_id, video.subtitles_enabled, lang or "auto")
        word_timestamps = _transcribe(
            video.file_path,
            model_size=settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            language=lang,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
        logger.info("Transcription produced %d words for %s", len(word_timestamps), video_id)
        if video.subtitles_enabled and not word_timestamps:
            logger.warning(
                "Subtitles enabled but no speech detected for %s — shorts will have no captions",
                video_id,
            )

    # ── 6. Segment detection (simple = contiguous splits, smart/pro = highlights) ─
    video_repo.update_status(video_id, VideoStatus.processing, progress=40)
    if video.generation_mode in (GenerationMode.smart, GenerationMode.pro):
        logger.info("%s mode: detecting highlights for %s", video.generation_mode.value, video_id)
        segments = _smart_segments(
            video.file_path, meta.duration, word_timestamps, video.shorts_requested
        )
    else:
        segments = _simple_segments(meta.duration, video.shorts_requested, word_timestamps)
    logger.info("Mode=%s → %d shorts: %s", video.generation_mode.value, len(segments), segments)

    # ── 7. Create Short records ───────────────────────────────────────────────
    import json as _json
    short_records = []
    for i, clips in enumerate(segments):
        start = clips[0][0]
        end = clips[-1][1]
        total_dur = round(sum(e - s for s, e in clips), 3)
        short_records.append(Short(
            video_id=video_id,
            index_number=i + 1,
            start_time=start,
            end_time=end,
            duration_seconds=total_dur,
            clips_json=_json.dumps([{"start": s, "end": e} for s, e in clips]),
            status=ShortStatus.pending,
        ))
    shorts = short_repo.bulk_create(short_records)

    # ── 8. Cut segments ───────────────────────────────────────────────────────
    output_dir = os.path.join(settings.OUTPUT_DIR, video_id)
    os.makedirs(output_dir, exist_ok=True)

    from app.workers.subtitle import build_ass_for_clips, write_temp_ass

    # Each short owns a slice of the [40, 98] progress band, and reports live
    # encode progress inside it — a single long short no longer sits at 40%.
    band = 58 / len(shorts)
    completed = 0
    last_error: Exception | None = None

    for idx, (short, clips) in enumerate(zip(shorts, segments)):
        _raise_if_cancelled(video_repo, video_id)
        short_repo.update_status(short.id, ShortStatus.processing)
        out_file = os.path.join(output_dir, f"short_{short.index_number}.mp4")

        # Build subtitles up-front so they burn in the SAME encode pass as the cut
        # (no second re-encode → no quality loss, perfect sync).
        ass_path = None
        if video.subtitles_enabled and word_timestamps:
            ass = build_ass_for_clips(
                word_timestamps, clips,
                words_per_line=settings.SUBTITLE_WORDS_PER_LINE,
                style=settings.SUBTITLE_STYLE,
            )
            if ass:
                ass_path = write_temp_ass(ass)
                logger.info("Short %s: burning subtitles", short.index_number)
            else:
                logger.info("Short %s: no words in clip range — no subtitles",
                            short.index_number)

        lo = 40 + int(idx * band)
        on_progress = _progress_reporter(video_repo, video_id, lo=lo, hi=40 + int((idx + 1) * band))
        try:
            if video.generation_mode is GenerationMode.pro:
                reframe.render_reframed_short(video.file_path, out_file, clips,
                                              subtitle_path=ass_path, on_progress=on_progress)
            else:
                ffmpeg.concat_clips_as_short(video.file_path, out_file, clips,
                                             subtitle_path=ass_path, on_progress=on_progress)
            short_repo.update_status(short.id, ShortStatus.completed, file_path=out_file)
            completed += 1
        except Exception as exc:  # noqa: BLE001 — one bad short must not kill the rest
            logger.exception("Failed to cut short %s", short.id)
            short_repo.update_status(short.id, ShortStatus.failed)
            last_error = exc
        finally:
            if ass_path and os.path.exists(ass_path):
                try:
                    os.remove(ass_path)
                except OSError:
                    pass

    _raise_if_cancelled(video_repo, video_id)

    # A video whose every short failed produced nothing downloadable — reporting
    # it as "completed" would hand the user a green job with no output.
    if completed == 0:
        raise last_error or ffmpeg.MediaError("No shorts could be produced from this video.")

    video_repo.update_status(video_id, VideoStatus.completed, progress=100)
    logger.info("Video %s → %d/%d shorts completed", video_id, completed, len(shorts))

    if video.user_id:
        _create_notification(db, video, completed=True, shorts_count=completed)
