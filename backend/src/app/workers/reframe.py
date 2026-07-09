"""
Pro / "Kuzatuv" mode reframing: crop landscape footage to 9:16 and pan to keep
the subject in frame, instead of shrinking the whole frame between blurred bars.

The pan target each moment is chosen by, in order of preference:
  1. Face / person  — the largest, most stable face (cv2 Haar cascade). Best for
     talking-head and music videos where there's no cursor.
  2. Motion centroid — where the action is (frame differencing). Catches the
     moving mouse in screen recordings and motion in general.
  3. Hold           — if nothing is found, stay where we are.

The raw target is then stabilised: a dead-zone ignores tiny wobble, hard scene
cuts snap instantly, and everything else is EMA-smoothed into a gentle pan.
Frames are sampled at low resolution via an ffmpeg pipe into numpy — only the
horizontal axis is panned (full height is kept, so the subject never leaves the
frame vertically).

Sources that aren't clearly landscape (already portrait/square, e.g. a phone
clip) skip reframing and use the standard blurred-portrait renderer.
"""
from __future__ import annotations

import logging
import subprocess

import numpy as np

from app.core.config import settings
from app.workers import ffmpeg

logger = logging.getLogger(__name__)

_ANALYZE_W = 480
_ANALYZE_H = 270
_TARGET_AR = 9 / 16          # width / height of a vertical short
_LANDSCAPE_MIN_AR = 1.05     # only reframe when clearly wider than tall (w > h)
_DEADZONE = 0.015            # ignore target moves smaller than this (fraction of width)
_CUT_MEANDIFF = 18.0         # mean frame diff above this ≈ a hard scene cut → snap
_PIPE_TIMEOUT = 300

_face_cascade = None
_face_cascade_loaded = False


def _even(x: float) -> int:
    return int(round(x / 2)) * 2


def _load_face_cascade():
    """Lazily load the Haar frontal-face cascade (bundled with opencv)."""
    global _face_cascade, _face_cascade_loaded
    if _face_cascade_loaded:
        return _face_cascade
    _face_cascade_loaded = True
    try:
        import cv2

        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(path)
        _face_cascade = None if cascade.empty() else cascade
    except Exception as exc:
        logger.info("Face detection unavailable (%s) — motion-only reframing", exc)
        _face_cascade = None
    return _face_cascade


def _read_gray_frames(input_path: str, start: float, end: float, sample_fps: float):
    """Return (frames[n, H, W] uint8, dur) sampled from [start, end]."""
    dur = max(0.1, end - start)
    cmd = [
        "ffmpeg", "-ss", str(start), "-t", str(dur), "-i", input_path,
        "-vf", f"fps={sample_fps},scale={_ANALYZE_W}:{_ANALYZE_H},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=_PIPE_TIMEOUT, **ffmpeg.CHILD_GUARD)
        buf = np.frombuffer(proc.stdout, dtype=np.uint8)
    except Exception as exc:
        logger.warning("Frame sampling failed (%s)", exc)
        return np.empty((0, _ANALYZE_H, _ANALYZE_W), dtype=np.uint8), dur
    frame_px = _ANALYZE_W * _ANALYZE_H
    n = buf.size // frame_px
    if n == 0:
        return np.empty((0, _ANALYZE_H, _ANALYZE_W), dtype=np.uint8), dur
    return buf[: n * frame_px].reshape(n, _ANALYZE_H, _ANALYZE_W), dur


def _pick_face(faces, cx: float) -> float | None:
    """Pick the best face centre-x (0..1): large + close to the current crop."""
    best, best_score = None, -1e9
    for (x, _y, fw, fh) in faces:
        area = (fw * fh) / float(_ANALYZE_W * _ANALYZE_H)
        center = (x + fw / 2) / _ANALYZE_W
        score = area - 0.25 * abs(center - cx)
        if score > best_score:
            best_score, best = score, center
    return best


def _focus_path(
    input_path: str,
    start: float,
    end: float,
    *,
    sample_fps: float,
    smoothing: float,
) -> list[tuple[float, float]]:
    """Smoothed [(t_local, cx_norm)] path following faces, then motion."""
    frames, dur = _read_gray_frames(input_path, start, end, sample_fps)
    if len(frames) < 2:
        return [(0.0, 0.5), (dur, 0.5)]

    cascade = _load_face_cascade()
    cols = np.arange(_ANALYZE_W)
    min_face = (int(_ANALYZE_W * 0.06), int(_ANALYZE_H * 0.06))

    cx = 0.5
    ema = 0.5
    path: list[tuple[float, float]] = [(0.0, 0.5)]
    frames_i16 = frames.astype(np.int16)

    for i in range(1, len(frames)):
        target = None

        # 1. Face — most reliable subject anchor.
        if cascade is not None:
            faces = cascade.detectMultiScale(frames[i], scaleFactor=1.1,
                                             minNeighbors=5, minSize=min_face)
            if len(faces):
                target = _pick_face(faces, cx)

        # 2. Motion centroid fallback.
        diff = np.abs(frames_i16[i] - frames_i16[i - 1])
        meandiff = float(diff.mean())
        if target is None:
            colmass = diff.sum(axis=0).astype(float)
            if colmass.sum() > _ANALYZE_H * 4:
                target = float((colmass * cols).sum() / colmass.sum() / _ANALYZE_W)

        # 3. Update with dead-zone; snap on hard cuts.
        if target is not None and abs(target - cx) > _DEADZONE:
            cx = target
        if meandiff > _CUT_MEANDIFF:      # scene cut → jump, don't drift
            ema = cx
        else:
            ema = smoothing * ema + (1 - smoothing) * cx

        path.append((round(i / sample_fps, 3), round(min(1.0, max(0.0, ema)), 4)))
    return path


def _crop_x_expr(path: list[tuple[float, float]], src_w: int, crop_w: int) -> str:
    """ffmpeg crop-`x` expression: continuous piecewise-linear pan in src pixels."""
    max_x = max(0, src_w - crop_w)
    keys = [(t, min(max_x, max(0.0, cx * src_w - crop_w / 2))) for t, cx in path]

    pruned = [keys[0]]
    for t, x in keys[1:]:
        pt, px = pruned[-1]
        if (t - pt) >= 0.25 or abs(x - px) >= 4:
            pruned.append((t, x))
    if len(pruned) < 2:
        return f"{pruned[0][1]:.1f}"

    terms = [f"{pruned[0][1]:.1f}"]
    for (t0, x0), (t1, x1) in zip(pruned, pruned[1:]):
        dt = max(1e-3, t1 - t0)
        slope = (x1 - x0) / dt
        if abs(slope) < 1e-6:
            continue
        terms.append(f"{slope:.3f}*clip(t-{t0:.3f}\\,0\\,{dt:.3f})")
    return "+".join(terms)


def render_reframed_short(
    input_path: str,
    output_path: str,
    clips: list[tuple[float, float]],
    subtitle_path: str | None = None,
    on_progress: ffmpeg.ProgressCB | None = None,
) -> None:
    """
    Render a 9:16 short from `clips`, panning a crop window to follow the
    subject. Non-landscape sources fall back to the blurred-portrait renderer.
    """
    if not clips:
        raise ffmpeg.MediaError("render_reframed_short called with no clips")

    meta = ffmpeg.probe(input_path)
    src_w, src_h = meta.width, meta.height
    if not src_w or not src_h or (src_w / src_h) < _LANDSCAPE_MIN_AR:
        logger.info("Source %dx%d not landscape — using blur portrait", src_w, src_h)
        ffmpeg.concat_clips_as_short(input_path, output_path, clips, subtitle_path, on_progress)
        return

    crop_w = _even(min(src_w, src_h * _TARGET_AR))
    crop_h = _even(src_h)
    has_audio = ffmpeg._has_audio(input_path)
    total_dur = sum(e - s for s, e in clips)

    # Each clip is its own seeked input, so ffmpeg decodes only the frames it
    # needs instead of the whole source once per clip.
    parts: list[str] = []
    for i, (s, e) in enumerate(clips):
        path = _focus_path(
            input_path, s, e,
            sample_fps=settings.REFRAME_SAMPLE_FPS,
            smoothing=settings.REFRAME_SMOOTHING,
        )
        x_expr = _crop_x_expr(path, src_w, crop_w)
        parts.append(
            f"[{i}:v]setpts=PTS-STARTPTS,"
            f"crop={crop_w}:{crop_h}:x='{x_expr}':y=0,"
            f"scale=1080:1920,setsar=1[v{i}]"
        )
        if has_audio:
            parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")

    n = len(clips)
    v_inputs = "".join(f"[v{i}]" for i in range(n))
    if subtitle_path:
        parts.append(f"{v_inputs}concat=n={n}:v=1:a=0[vc]")
        parts.append(f"[vc]ass={ffmpeg._escape_subtitle_path(subtitle_path)}[vout]")
    else:
        parts.append(f"{v_inputs}concat=n={n}:v=1:a=0[vout]")

    if has_audio:
        a_inputs = "".join(f"[a{i}]" for i in range(n))
        parts.append(f"{a_inputs}concat=n={n}:v=0:a=1[aout]")

    cmd = ["ffmpeg", "-y", *ffmpeg.seek_inputs(input_path, clips),
           "-filter_complex", ";".join(parts),
           "-map", "[vout]"]
    if has_audio:
        cmd += ["-map", "[aout]", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-movflags", "+faststart", output_path]

    ffmpeg.run_ffmpeg(cmd, "reframe render", on_progress=on_progress, total_dur=total_dur,
                      timeout=ffmpeg.timeout_for(total_dur))
