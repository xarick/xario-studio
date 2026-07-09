"""
FFmpeg and yt-dlp utilities.
Pure functions — no DB, no app state. Easy to test and swap out.
"""
import glob
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

_YTDLP_TIMEOUT = 600
_YTDLP_INFO_TIMEOUT = 60
_FFPROBE_TIMEOUT = 60
_FFMPEG_TIMEOUT = 600

# A progress callback receives the completed fraction (0.0–1.0).
ProgressCB = Callable[[float], None]

# Resolve yt-dlp: prefer venv sibling of the running Python, fall back to PATH.
def _find_ytdlp() -> str:
    venv_ytdlp = os.path.join(os.path.dirname(sys.executable), "yt-dlp")
    if os.path.isfile(venv_ytdlp):
        return venv_ytdlp
    return shutil.which("yt-dlp") or "yt-dlp"

_YTDLP_BIN = _find_ytdlp()


class MediaError(RuntimeError):
    """Raised when ffmpeg / ffprobe / yt-dlp fails.

    Every ffmpeg failure — including a watchdog timeout — surfaces as this type,
    so callers only ever need one `except` clause.
    """


def _die_with_parent() -> None:  # pragma: no cover — runs in the forked child
    """Ask the kernel to kill this child as soon as its parent dies.

    A worker killed with SIGKILL cannot clean up after itself, and an orphaned
    ffmpeg then spins at 100% CPU forever with nothing left to reap it.
    PR_SET_PDEATHSIG makes the kernel do the cleanup instead. Linux only; a
    no-op everywhere else.
    """
    if sys.platform != "linux":
        return
    try:
        import ctypes
        import signal

        _PR_SET_PDEATHSIG = 1
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(_PR_SET_PDEATHSIG, signal.SIGKILL)
    except Exception:  # noqa: BLE001 — best effort; never block the exec
        pass


# Pass to every long-running subprocess so it cannot outlive its worker.
CHILD_GUARD = {"preexec_fn": _die_with_parent}


def timeout_for(work_seconds: float) -> int:
    """Watchdog budget for an ffmpeg command that must process `work_seconds` of
    media. A flat cap would kill healthy long jobs, so the budget grows with the
    work; the floor keeps short commands from being cut off by a slow machine."""
    from app.core.config import settings

    return int(max(settings.FFMPEG_MIN_TIMEOUT,
                   max(0.0, work_seconds) * settings.FFMPEG_TIMEOUT_FACTOR))


def run_ffmpeg(
    cmd: list[str],
    what: str,
    *,
    on_progress: ProgressCB | None = None,
    total_dur: float | None = None,
    timeout: int | None = None,
) -> None:
    """Run an ffmpeg command, raising MediaError on failure or timeout.

    With `on_progress` + `total_dur`, ffmpeg's `-progress` stream is parsed and
    the callback fires with the completed fraction (throttled to ~1% steps) so
    callers can report live progress. Without them this is a blocking
    subprocess.run.
    """
    limit = _FFMPEG_TIMEOUT if timeout is None else timeout
    # Without this, ffmpeg's build-configuration banner fills the captured
    # stderr and pushes the actual error out of the message we show the user.
    cmd = [cmd[0], "-hide_banner", *cmd[1:]]

    if not on_progress or not total_dur or total_dur <= 0:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=limit,
                                    **CHILD_GUARD)
        except subprocess.TimeoutExpired as exc:
            raise MediaError(f"{what} timed out after {limit}s") from exc
        if result.returncode != 0:
            raise MediaError(f"{what} failed: {result.stderr[-1000:]}")
        return

    # Progress-reporting path: stream `-progress pipe:1`, keep stderr in a temp
    # file so a chatty encoder can't deadlock on a full pipe.
    pcmd = cmd[:1] + ["-nostats", "-loglevel", "error", "-progress", "pipe:1"] + cmd[1:]
    err = tempfile.TemporaryFile(mode="w+")
    proc = subprocess.Popen(pcmd, stdout=subprocess.PIPE, stderr=err, text=True, **CHILD_GUARD)
    started = time.monotonic()
    last = 0.0
    try:
        for line in proc.stdout or ():
            if time.monotonic() - started > limit:
                proc.kill()
                raise MediaError(f"{what} timed out after {limit}s")
            line = line.strip()
            # out_time_us / out_time_ms are both microseconds in ffmpeg.
            if line.startswith(("out_time_us=", "out_time_ms=")):
                try:
                    us = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                frac = max(0.0, min(1.0, (us / 1_000_000.0) / total_dur))
                if frac - last >= 0.01:
                    last = frac
                    try:
                        on_progress(frac)
                    except Exception:  # noqa: BLE001 — progress must never break the job
                        pass
        try:
            proc.wait(timeout=max(1, limit - int(time.monotonic() - started)))
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            raise MediaError(f"{what} timed out after {limit}s") from exc
    finally:
        if proc.stdout:
            proc.stdout.close()
    if proc.returncode != 0:
        err.seek(0)
        raise MediaError(f"{what} failed: {err.read()[-1000:]}")
    try:
        on_progress(1.0)
    except Exception:  # noqa: BLE001
        pass


@dataclass(frozen=True)
class VideoMeta:
    duration: float
    width: int
    height: int


@dataclass
class VideoInfo:
    title: str = ""
    description: str = ""
    duration: float = 0.0
    chapters: list = field(default_factory=list)  # [{title, start_time, end_time}]
    transcript: str = ""                           # cleaned subtitle text


def probe(file_path: str) -> VideoMeta:
    """Return basic metadata for a local video file."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                file_path,
            ],
            capture_output=True, text=True, timeout=_FFPROBE_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"ffprobe timed out on {file_path}") from exc
    if result.returncode != 0:
        raise MediaError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    video_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    fmt = data.get("format", {})

    duration = 0.0
    if video_streams:
        duration = float(video_streams[0].get("duration") or 0)
    if not duration:
        duration = float(fmt.get("duration") or 0)
    if not duration:
        raise MediaError("Could not determine video duration")

    width = int(video_streams[0].get("width", 0)) if video_streams else 0
    height = int(video_streams[0].get("height", 0)) if video_streams else 0
    return VideoMeta(duration=duration, width=width, height=height)


def _ytdlp_base_cmd(cookies_file: str = "", cookies_browser: str = "") -> list[str]:
    cmd = [_YTDLP_BIN]
    if cookies_file:
        cmd += ["--cookies", cookies_file]
    elif cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    return cmd


def get_yt_info(url: str, cookies_file: str = "", cookies_browser: str = "") -> VideoInfo:
    """Fetch title, description, chapters, and transcript for a video URL."""
    base = _ytdlp_base_cmd(cookies_file, cookies_browser)
    info = VideoInfo()

    # 1. Metadata
    try:
        res = subprocess.run(
            base + ["--dump-json", "--no-playlist", url],
            capture_output=True, text=True, timeout=_YTDLP_INFO_TIMEOUT,
        )
        if res.returncode == 0:
            data = json.loads(res.stdout)
            info.title = data.get("title", "")
            info.description = (data.get("description") or "")[:600]
            info.chapters = data.get("chapters") or []
            info.duration = float(data.get("duration") or 0)
    except Exception as exc:
        logger.warning("get_yt_info metadata failed: %s", exc)

    # 2. Auto-subtitles → transcript
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                base + [
                    "--write-auto-subs", "--sub-langs", "en.*",
                    "--convert-subs", "srt",
                    "--skip-download", "--no-playlist",
                    "--output", os.path.join(tmpdir, "sub"),
                    url,
                ],
                capture_output=True, text=True, timeout=_YTDLP_INFO_TIMEOUT,
            )
            srt_files = glob.glob(os.path.join(tmpdir, "*.srt"))
            if srt_files:
                raw = open(srt_files[0]).read()
                # Strip SRT index/timestamps, keep text
                text = re.sub(r"\d+\n[\d:,]+ --> [\d:,]+\n", "", raw)
                text = re.sub(r"<[^>]+>", "", text)          # remove html tags
                text = re.sub(r"\n{2,}", " ", text).strip()
                info.transcript = text[:4000]
    except Exception as exc:
        logger.warning("get_yt_info subtitles failed: %s", exc)

    return info


def _escape_subtitle_path(path: str) -> str:
    """Escape a filename for use inside an ffmpeg filtergraph (ass/subtitles filter)."""
    escaped = path.replace("\\", "/")
    # Escape the drive colon on Windows; Linux paths have no colon → no-op.
    if ":" in escaped:
        drive, rest = escaped.split(":", 1)
        escaped = drive + "\\:" + rest
    return escaped.replace("'", r"\'")


def detect_scenes(input_path: str, threshold: float = 0.27, duration: float = 0.0) -> list[float]:
    """
    Return timestamps (seconds) where a visual scene change occurs.

    Uses ffmpeg's `select='gt(scene,threshold)'` and parses showinfo output.
    Returns an empty list on failure — callers must tolerate that.
    """
    try:
        # Downscale before scoring — scene changes are detectable at low res and
        # this keeps detection fast on long / high-resolution videos.
        result = subprocess.run(
            [
                "ffmpeg", "-i", input_path,
                "-filter:v", f"scale=640:-2,select='gt(scene,{threshold})',showinfo",
                "-an", "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=timeout_for(duration),
        )
        times = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", result.stderr)]
        return sorted(set(times))
    except Exception as exc:
        logger.warning("Scene detection failed: %s", exc)
        return []


# Blurred letterbox background. Blurring at full 1080×1920 costs more CPU than
# the H.264 encode itself; blurring a quarter-size copy and scaling it back up is
# visually indistinguishable (SSIM 0.998, PSNR 44.6 dB) and ~1.8× faster overall.
# Sigma scales with the resolution, so it drops by the same factor.
_BLUR_SIGMA = 25.0
_BLUR_DOWNSCALE = 4


def blur_background(width: int, height: int) -> str:
    """Filter chain turning an input into a blurred `width`×`height` fill."""
    bw = max(2, (width // _BLUR_DOWNSCALE) // 2 * 2)
    bh = max(2, (height // _BLUR_DOWNSCALE) // 2 * 2)
    sigma = _BLUR_SIGMA / _BLUR_DOWNSCALE
    return (
        f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
        f"gblur=sigma={sigma:.2f},scale={width}:{height}"
    )


def seek_inputs(input_path: str, clips: list[tuple[float, float]]) -> list[str]:
    """Build one `-ss START -t LEN -i FILE` input per clip.

    Seeking at the *input* means the demuxer jumps to the keyframe before START
    and only decodes from there. The alternative — feeding the whole stream to a
    `trim` filter — decodes every frame of the source and throws most of them
    away, which costs the full decode time of the file for every short we cut.
    With re-encoding, input seeking is still frame-accurate.
    """
    args: list[str] = []
    for start, end in clips:
        args += ["-ss", f"{start:.3f}", "-t", f"{max(0.001, end - start):.3f}", "-i", input_path]
    return args


def download_url(url: str, output_path: str) -> None:
    """Download a video from URL using yt-dlp into output_path."""
    from app.core.config import settings

    cmd = _ytdlp_base_cmd(settings.YTDLP_COOKIES_FILE, settings.YTDLP_COOKIES_FROM_BROWSER) + [
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", output_path,
        "--no-playlist",
        "--no-warnings",
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=_YTDLP_TIMEOUT)

    # yt-dlp exits with code 1 on non-fatal warnings (e.g. secretstorage missing).
    # Treat as success if the output file was actually created.
    if result.returncode != 0 and not (os.path.exists(output_path) and os.path.getsize(output_path) > 0):
        raise MediaError(f"Download failed: {result.stderr.strip()}")


def clean_audio(input_path: str, output_path: str, has_video: bool, duration: float = 0.0) -> None:
    """
    Professional audio cleanup with ffmpeg only:
      * afftdn   — FFT noise reduction (removes hiss / hum / background noise)
      * loudnorm — EBU R128 loudness normalisation (consistent, broadcast-safe level)
      * silenceremove — trim long (>1s) silences (audio-only; skipped for video to
        keep audio/video in sync)
      * aresample — restore a clean 48 kHz rate after loudnorm
      * aformat   — loudnorm leaves the channel layout unspecified, and the
        encoder then refuses to link ("Cannot select channel layout"). Pinning
        the layout here keeps the chain valid for both mono and stereo sources.

    Video input: the video stream is copied untouched, only the audio is cleaned.
    Audio input: re-encoded to MP3.
    """
    chain = ["afftdn=nr=10"]
    if not has_video:
        chain.append("silenceremove=stop_periods=-1:stop_duration=1:stop_threshold=-40dB")
    chain += ["loudnorm=I=-16:TP=-1.5:LRA=11", "aresample=48000",
              "aformat=channel_layouts=mono|stereo"]
    af = ",".join(chain)

    cmd = ["ffmpeg", "-y", "-i", input_path, "-af", af]
    if has_video:
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
    else:
        cmd += ["-c:a", "libmp3lame", "-b:a", "192k"]
    cmd += [output_path]

    run_ffmpeg(cmd, "Audio cleanup", timeout=timeout_for(duration))


def _has_audio(input_path: str) -> bool:
    """Return True if the file has at least one audio stream."""
    res = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", input_path],
        capture_output=True, text=True, timeout=_FFPROBE_TIMEOUT,
    )
    return bool(res.stdout.strip())


def concat_clips_as_short(
    input_path: str,
    output_path: str,
    clips: list[tuple[float, float]],
    subtitle_path: str | None = None,
    on_progress: ProgressCB | None = None,
) -> None:
    """
    Build a 9:16 portrait short from one or more clips.

    Each clip is a separately-seeked input (see `seek_inputs`), concatenated in
    order, letterboxed onto a blurred 1080×1920 background, and — if
    `subtitle_path` is given — has ASS subtitles burned in within the SAME
    encode pass (no quality loss, perfect A/V/subtitle sync).
    """
    if not clips:
        raise MediaError("concat_clips_as_short called with no clips")

    n = len(clips)
    has_audio = _has_audio(input_path)
    total_dur = sum(e - s for s, e in clips)
    parts: list[str] = []

    # 1. Each clip arrives as its own input; reset its PTS to start at 0.
    for i in range(n):
        parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
        if has_audio:
            parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")

    # 2. Concatenate clips (n==1 → single concat is a cheap pass-through).
    v_inputs = "".join(f"[v{i}]" for i in range(n))
    parts.append(f"{v_inputs}concat=n={n}:v=1:a=0[rawv]")
    if has_audio:
        a_inputs = "".join(f"[a{i}]" for i in range(n))
        parts.append(f"{a_inputs}concat=n={n}:v=0:a=1[aout]")

    # 3. Portrait: blurred fill background + centered original overlay.
    parts.append("[rawv]split[bg_in][fg_in]")
    parts.append(f"[bg_in]{blur_background(1080, 1920)}[bg]")
    parts.append("[fg_in]scale=1080:1920:force_original_aspect_ratio=decrease[fg]")

    # 4. Optionally burn subtitles in the same pass.
    if subtitle_path:
        parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2[vov]")
        parts.append(f"[vov]ass={_escape_subtitle_path(subtitle_path)}[vout]")
    else:
        parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2[vout]")

    cmd = ["ffmpeg", "-y", *seek_inputs(input_path, clips),
           "-filter_complex", ";".join(parts),
           "-map", "[vout]"]
    if has_audio:
        cmd += ["-map", "[aout]", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-movflags", "+faststart", output_path]

    run_ffmpeg(cmd, "ffmpeg concat", on_progress=on_progress, total_dur=total_dur,
               timeout=timeout_for(total_dur))


# Target frame for each editor aspect (None = keep the source frame untouched).
ASPECT_DIMS = {
    "9:16": (1080, 1920),
    "1:1":  (1080, 1080),
    "16:9": (1920, 1080),
    "original": None,
}


def edit_video(
    input_path: str,
    output_path: str,
    *,
    start: float = 0.0,
    end: float = 0.0,
    aspect: str = "9:16",
    fit: str = "crop",
    subtitle_path: str | None = None,
    segments: list[tuple[float, float]] | None = None,
    on_progress: ProgressCB | None = None,
) -> None:
    """
    Manual montage in a single encode pass:
      1. cut one or more [start, end] segments from the source and join them in
         order (frame-accurate). A single [start, end] is the common case; pass
         `segments=[(s,e), …]` to keep several pieces and drop the gaps,
      2. fit to `aspect` — "crop" center-fills, "pad" fits onto a blurred copy,
         "original" keeps the source frame,
      3. optionally burn text overlays (`subtitle_path`, an ASS file).
    """
    segs = list(segments) if segments else [(start, end)]
    segs = [(float(s), float(e)) for s, e in segs if e > s]
    if not segs:
        raise MediaError("edit_video: no valid segment (end must be greater than start)")

    dims = ASPECT_DIMS.get(aspect, ASPECT_DIMS["9:16"])
    has_audio = _has_audio(input_path)
    total_dur = sum(e - s for s, e in segs)

    # Build the (possibly multi-segment) trimmed video as [vt] (+ audio [aout]).
    # Every segment is its own seeked input — see `seek_inputs`.
    parts: list[str] = []
    if len(segs) == 1:
        parts.append("[0:v]setpts=PTS-STARTPTS[vt]")
        if has_audio:
            parts.append("[0:a]asetpts=PTS-STARTPTS[aout]")
    else:
        for i in range(len(segs)):
            parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
            if has_audio:
                parts.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
        if has_audio:
            parts.append("".join(f"[v{i}][a{i}]" for i in range(len(segs)))
                         + f"concat=n={len(segs)}:v=1:a=1[vt][aout]")
        else:
            parts.append("".join(f"[v{i}]" for i in range(len(segs)))
                         + f"concat=n={len(segs)}:v=1:a=0[vt]")

    if dims is None:
        # Keep the source frame; just guarantee even dimensions for libx264.
        parts.append("[vt]scale=trunc(iw/2)*2:trunc(ih/2)*2[vfit]")
    else:
        w, h = dims
        if fit == "pad":
            parts.append("[vt]split[bg_in][fg_in]")
            parts.append(f"[bg_in]{blur_background(w, h)}[bg]")
            parts.append(f"[fg_in]scale={w}:{h}:force_original_aspect_ratio=decrease[fg]")
            parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2[vfit]")
        else:  # crop / fill
            parts.append(f"[vt]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[vfit]")

    if subtitle_path:
        parts.append(f"[vfit]ass={_escape_subtitle_path(subtitle_path)}[vout]")
    else:
        parts.append("[vfit]null[vout]")

    cmd = ["ffmpeg", "-y", *seek_inputs(input_path, segs),
           "-filter_complex", ";".join(parts),
           "-map", "[vout]"]
    if has_audio:
        cmd += ["-map", "[aout]", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-movflags", "+faststart", output_path]

    run_ffmpeg(cmd, "ffmpeg edit", on_progress=on_progress, total_dur=total_dur,
               timeout=timeout_for(total_dur))
