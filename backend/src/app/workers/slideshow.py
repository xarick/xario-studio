"""Image-to-shorts — build a 9:16 portrait video from still images.

Each image is shown for a few seconds with a slow ken-burns zoom, and adjacent
images are joined with a crossfade. Output is a 1080×1920 H.264 MP4. Pure ffmpeg,
no external service.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.workers.ffmpeg import MediaError, run_ffmpeg  # noqa: F401

logger = logging.getLogger(__name__)

_FPS = 30
_W, _H = 1080, 1920
_TIMEOUT = 1200


def _image_filter(idx: int, dur: float, label: str) -> str:
    """Scale/crop an image to fill 1080×1920, apply a slow centred zoom, and trim
    it to exactly `dur` seconds."""
    frames = max(1, int(dur * _FPS))
    return (
        f"[{idx}:v]scale={_W}:{_H}:force_original_aspect_ratio=increase,"
        f"crop={_W}:{_H},"
        f"zoompan=z='min(zoom+0.0012,1.15)':d={frames}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={_W}x{_H}:fps={_FPS},"
        f"trim=duration={dur},setpts=PTS-STARTPTS,format=yuv420p[{label}]"
    )


def build_slideshow(image_paths: list[str], output_path: str) -> str:
    """Render `image_paths` into a portrait short at `output_path`. Returns the
    output path. Raises MediaError on failure."""
    if not image_paths:
        raise MediaError("build_slideshow called with no images")

    dur = settings.SLIDESHOW_SECONDS_PER_IMAGE
    trans = min(settings.SLIDESHOW_TRANSITION, dur / 2)
    n = len(image_paths)

    cmd: list[str] = ["ffmpeg", "-y"]
    for path in image_paths:
        cmd += ["-loop", "1", "-i", path]

    parts: list[str] = []
    if n == 1:
        parts.append(_image_filter(0, dur, "vout"))
    else:
        for i in range(n):
            parts.append(_image_filter(i, dur, f"v{i}"))
        # Crossfade-chain the clips: each xfade offset sits at the end of the
        # stream built so far (i*(dur-trans)).
        prev = "v0"
        for i in range(1, n):
            offset = i * (dur - trans)
            out = "vout" if i == n - 1 else f"x{i}"
            parts.append(
                f"[{prev}][v{i}]xfade=transition=fade:duration={trans:.3f}"
                f":offset={offset:.3f}[{out}]"
            )
            prev = out

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[vout]",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", output_path,
    ]

    logger.info("Building slideshow short from %d image(s) → %s", n, output_path)
    run_ffmpeg(cmd, "Slideshow build", timeout=_TIMEOUT)
    return output_path
