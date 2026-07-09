"""
Single-purpose media tools (ffmpeg only).

Each function does ONE focused operation and writes a single output file. They
are dispatched by video_processor._run_tool_mode from params_json["op"]. Keep
them small and dependency-free so new tools are cheap to add.
"""
from app.workers.ffmpeg import (  # noqa: F401
    ASPECT_DIMS, MediaError, ProgressCB, _has_audio, edit_video,
    run_ffmpeg as _run, timeout_for,
)


def _atempo_chain(factor: float) -> str:
    """ffmpeg atempo accepts 0.5–2.0; chain filters to cover wider speeds."""
    factor = max(0.25, min(4.0, factor))
    parts = []
    remaining = factor
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.4f}")
    return ",".join(parts)


# ── Video ────────────────────────────────────────────────────────────────────
def compress(input_path: str, output_path: str, *, crf: int = 28, max_height: int = 720,
             on_progress: ProgressCB | None = None, total_dur: float | None = None) -> None:
    """Re-encode at a higher CRF and cap the height — smaller file, decent quality."""
    crf = max(18, min(40, int(crf)))
    vf = f"scale=-2:'min({max_height},ih)'"
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf)]
    if _has_audio(input_path):
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-movflags", "+faststart", output_path]
    _run(cmd, "compress", on_progress=on_progress, total_dur=total_dur,
         timeout=timeout_for(total_dur or 0))


def change_speed(input_path: str, output_path: str, *, factor: float = 1.0) -> None:
    """Speed the video up / slow it down (video PTS + audio atempo, kept in sync)."""
    from app.workers.ffmpeg import probe

    factor = max(0.25, min(4.0, float(factor)))
    has_audio = _has_audio(input_path)
    source_dur = probe(input_path).duration
    parts = [f"[0:v]setpts={1/factor:.5f}*PTS[v]"]
    maps = ["-map", "[v]"]
    if has_audio:
        parts.append(f"[0:a]{_atempo_chain(factor)}[a]")
        maps += ["-map", "[a]", "-c:a", "aac"]
    cmd = ["ffmpeg", "-y", "-i", input_path, "-filter_complex", ";".join(parts),
           *maps, "-c:v", "libx264", "-preset", "fast", "-movflags", "+faststart", output_path]
    _run(cmd, "speed", timeout=timeout_for(source_dur))


def to_gif(input_path: str, output_path: str, *, start: float = 0.0, end: float | None = None,
           fps: int = 12, width: int = 480) -> None:
    """Make a high-quality GIF (palettegen/paletteuse) from a clip."""
    fps = max(5, min(30, int(fps)))
    width = max(120, min(1080, int(width)))
    trim = ["-ss", str(start)]
    if end and end > start:
        trim += ["-t", str(end - start)]
    vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
    cmd = ["ffmpeg", "-y", *trim, "-i", input_path, "-vf", vf, "-loop", "0", output_path]
    _run(cmd, "gif")


_WM_POS = {
    "top-left":     "10:10",
    "top-right":    "main_w-overlay_w-10:10",
    "bottom-left":  "10:main_h-overlay_h-10",
    "bottom-right": "main_w-overlay_w-10:main_h-overlay_h-10",
    "center":       "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
}


def watermark(input_path: str, output_path: str, *, logo_path: str,
              position: str = "bottom-right", opacity: float = 1.0, scale: float = 0.2,
              on_progress: ProgressCB | None = None, total_dur: float | None = None) -> None:
    """Overlay a logo image onto the video at a corner/center, sized to `scale`
    of the video width, with the given opacity."""
    opacity = max(0.05, min(1.0, float(opacity)))
    scale = max(0.02, min(0.8, float(scale)))
    pos = _WM_POS.get(position, _WM_POS["bottom-right"])
    fc = (
        f"[1:v]format=rgba,colorchannelmixer=aa={opacity:.3f}[lg];"
        f"[lg][0:v]scale2ref=w='main_w*{scale}':h='main_w*{scale}*ih/iw'[wm][base];"
        f"[base][wm]overlay={pos}[vout]"
    )
    cmd = ["ffmpeg", "-y", "-i", input_path, "-i", logo_path,
           "-filter_complex", fc, "-map", "[vout]"]
    if _has_audio(input_path):
        cmd += ["-map", "0:a", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-movflags", "+faststart", output_path]
    _run(cmd, "watermark", on_progress=on_progress, total_dur=total_dur,
         timeout=timeout_for(total_dur or 0))


def extract_audio(input_path: str, output_path: str) -> None:
    """Pull the audio track out of a video as MP3."""
    if not _has_audio(input_path):
        raise MediaError("This video has no audio track.")
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vn",
           "-c:a", "libmp3lame", "-b:a", "192k", output_path]
    _run(cmd, "extract_audio")


def convert_aspect(input_path: str, output_path: str, *, aspect: str = "9:16",
                   fit: str = "crop", duration: float = 0.0) -> None:
    """Reframe the WHOLE video to a target aspect (reuses the editor's engine)."""
    if duration <= 0:
        from app.workers.ffmpeg import probe
        duration = probe(input_path).duration
    edit_video(input_path, output_path, start=0.0, end=duration, aspect=aspect, fit=fit)


# ── Audio ────────────────────────────────────────────────────────────────────
def trim_audio(input_path: str, output_path: str, *, start: float = 0.0, end: float | None = None) -> None:
    """Cut an audio region → MP3."""
    trim = ["-ss", str(start)]
    if end and end > start:
        trim += ["-t", str(end - start)]
    cmd = ["ffmpeg", "-y", *trim, "-i", input_path,
           "-c:a", "libmp3lame", "-b:a", "192k", output_path]
    _run(cmd, "trim_audio")


_AUDIO_CODECS = {
    "mp3":  ["-c:a", "libmp3lame", "-b:a", "192k"],
    "wav":  ["-c:a", "pcm_s16le"],
    "m4a":  ["-c:a", "aac", "-b:a", "192k"],
    "ogg":  ["-c:a", "libvorbis", "-q:a", "5"],
    "flac": ["-c:a", "flac"],
}


def convert_audio(input_path: str, output_path: str, *, fmt: str = "mp3") -> None:
    """Convert audio to another format."""
    codec = _AUDIO_CODECS.get(fmt)
    if not codec:
        raise MediaError(f"Unsupported audio format: {fmt}")
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", *codec, output_path]
    _run(cmd, "convert_audio")


def adjust_volume(input_path: str, output_path: str, *, db: float = 0.0) -> None:
    """Boost / cut loudness by N decibels → MP3."""
    db = max(-30.0, min(30.0, float(db)))
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-af", f"volume={db}dB",
           "-c:a", "libmp3lame", "-b:a", "192k", output_path]
    _run(cmd, "volume")


_AFMT = "aformat=sample_rates=44100:channel_layouts=stereo"


def concat_audio(input_paths: list[str], output_path: str, *, crossfade: float = 0.0) -> None:
    """Join several audio files into one MP3 (normalised to 44.1k stereo). With
    `crossfade > 0` consecutive tracks blend over that many seconds (acrossfade)
    instead of a hard cut, for a smoother transition."""
    if len(input_paths) < 2:
        raise MediaError("Concat needs at least two audio files.")
    cmd = ["ffmpeg", "-y"]
    for p in input_paths:
        cmd += ["-i", p]
    n = len(input_paths)
    parts = [f"[{i}:a]{_AFMT}[a{i}]" for i in range(n)]
    if crossfade and crossfade > 0:
        d = max(0.1, float(crossfade))
        cur = "a0"
        for i in range(1, n):
            out = f"ax{i}" if i < n - 1 else "a"
            parts.append(f"[{cur}][a{i}]acrossfade=d={d:.3f}:c1=tri:c2=tri[{out}]")
            cur = out
    else:
        parts.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[a]",
            "-c:a", "libmp3lame", "-b:a", "192k", output_path]
    _run(cmd, "concat_audio")


# xfade transition names we expose in the UI. "none" means a plain hard cut.
# Maps a friendly id -> the ffmpeg `xfade` transition name.
VIDEO_TRANSITIONS = {
    "none":       None,            # hard cut, no animation
    "fade":       "fade",          # cross-dissolve
    "fadeblack":  "fadeblack",     # dip to black
    "fadewhite":  "fadewhite",     # dip to white
    "dissolve":   "dissolve",      # grainy dissolve
    "wipeleft":   "wipeleft",
    "wiperight":  "wiperight",
    "slideup":    "slideup",
    "slidedown":  "slidedown",
    "slideleft":  "slideleft",
    "slideright": "slideright",
    "circleopen": "circleopen",
    "radial":     "radial",
    "smoothleft": "smoothleft",    # wave-like sweep
    "smoothright":"smoothright",
    "pixelize":   "pixelize",
    "wave":       "smoothright",   # friendly alias for the wave-style sweep
}


def concat_videos(
    input_paths: list[str],
    output_path: str,
    *,
    transition: str = "fade",
    duration: float = 1.0,
    aspect: str = "9:16",
    music_path: str | None = None,
    music_volume: float = 0.5,
    on_progress: ProgressCB | None = None,
) -> None:
    """
    Join several videos end-to-end, optionally animating each cut with an
    `xfade` transition (fade to black/white, dissolve, slide, wave-like sweep…).

    Every clip is first normalised to one canvas (target aspect, 30 fps, yuv420p,
    stereo 44.1k audio) so xfade/acrossfade can stitch them seamlessly. Clips
    without an audio track get matching silence so the soundtrack stays in sync.
    `transition="none"` produces a plain hard-cut concat (no animation).
    """
    from app.workers.ffmpeg import probe

    paths = [p for p in input_paths if p]
    if len(paths) < 2:
        raise MediaError("Video merge needs at least two videos.")

    name = VIDEO_TRANSITIONS.get(transition, "fade") if transition != "none" else None

    # Target canvas. "original" falls back to the first clip's real dimensions.
    dims = ASPECT_DIMS.get(aspect)
    if dims is None:
        meta0 = probe(paths[0])
        w = meta0.width or 1080
        h = meta0.height or 1920
        w -= w % 2
        h -= h % 2
    else:
        w, h = dims

    durs = [max(0.1, probe(p).duration) for p in paths]
    has_audio = [_has_audio(p) for p in paths]

    fps = 30
    vn = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},"
        f"format=yuv420p,settb=AVTB"
    )

    parts = []
    for i in range(len(paths)):
        parts.append(f"[{i}:v]{vn}[v{i}]")
        if has_audio[i]:
            parts.append(f"[{i}:a]{_AFMT},asetpts=PTS-STARTPTS,asettb=AVTB[a{i}]")
        else:
            parts.append(
                f"anullsrc=r=44100:cl=stereo,atrim=duration={durs[i]:.3f},"
                f"asettb=AVTB[a{i}]"
            )

    if name is None:
        # Hard cut: plain concat of the normalised streams.
        parts.append(
            "".join(f"[v{i}][a{i}]" for i in range(len(paths)))
            + f"concat=n={len(paths)}:v=1:a=1[v][a]"
        )
        total_dur = sum(durs)
    else:
        # Clamp the overlap so it never exceeds the shortest clip.
        d = max(0.2, min(float(duration), min(durs) - 0.1))
        vcur, acur = "v0", "a0"
        running = durs[0]
        for i in range(1, len(paths)):
            offset = running - d
            vout = f"vx{i}" if i < len(paths) - 1 else "v"
            aout = f"ax{i}" if i < len(paths) - 1 else "a"
            parts.append(
                f"[{vcur}][v{i}]xfade=transition={name}:duration={d:.3f}:"
                f"offset={offset:.3f}[{vout}]"
            )
            parts.append(f"[{acur}][a{i}]acrossfade=d={d:.3f}:c1=tri:c2=tri[{aout}]")
            vcur, acur = vout, aout
            running = running + durs[i] - d
        total_dur = running

    # Optional background music ducked under the merged soundtrack. The music
    # input is added last so its index is len(paths); it's trimmed to the video
    # length (duration=first) so it never runs past the picture.
    amap = "[a]"
    if music_path:
        mv = max(0.0, min(1.0, float(music_volume)))
        midx = len(paths)
        parts.append(f"[{midx}:a]{_AFMT},volume={mv:.3f}[mus]")
        parts.append("[a][mus]amix=inputs=2:duration=first:dropout_transition=2[aout]")
        amap = "[aout]"

    cmd = ["ffmpeg", "-y"]
    for p in paths:
        cmd += ["-i", p]
    if music_path:
        cmd += ["-i", music_path]
    cmd += ["-filter_complex", ";".join(parts),
            "-map", "[v]", "-map", amap,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", output_path]
    _run(cmd, "concat_videos", on_progress=on_progress, total_dur=total_dur,
         timeout=timeout_for(total_dur))


def mix_audio(voice_path: str, music_path: str, output_path: str, *, music_volume: float = 0.25) -> None:
    """Overlay background music under a main (voice) track. Music is lowered to
    `music_volume`; the result lasts as long as the voice track."""
    music_volume = max(0.0, min(1.0, float(music_volume)))
    fc = (
        f"[0:a]{_AFMT}[v];"
        f"[1:a]{_AFMT},volume={music_volume:.3f}[m];"
        f"[v][m]amix=inputs=2:duration=first:dropout_transition=2[a]"
    )
    cmd = ["ffmpeg", "-y", "-i", voice_path, "-i", music_path,
           "-filter_complex", fc, "-map", "[a]",
           "-c:a", "libmp3lame", "-b:a", "192k", output_path]
    _run(cmd, "mix_audio")


def change_pitch(input_path: str, output_path: str, *, semitones: float = 0.0) -> None:
    """Shift pitch by N semitones while keeping the same duration → MP3."""
    semitones = max(-12.0, min(12.0, float(semitones)))
    ratio = 2 ** (semitones / 12.0)
    sr = 44100
    af = f"asetrate={int(sr*ratio)},aresample={sr},{_atempo_chain(1/ratio)}"
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-af", af,
           "-c:a", "libmp3lame", "-b:a", "192k", output_path]
    _run(cmd, "pitch")
