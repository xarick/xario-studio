"""
Image processing operations (driver).

Thin wrapper that runs the heavy image work (`_imaging_run`) in a subprocess,
keeping onnxruntime / rembg out of the web process — mirrors tts.synthesize_batch
driving _tts_batch.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys

from app.core.config import settings
from app.workers import ffmpeg   # reuse MediaError for a consistent failure type

logger = logging.getLogger(__name__)


_ASPECT_FRACTIONS = {
    "1:1": (1, 1), "9:16": (9, 16), "16:9": (16, 9), "3:4": (3, 4), "4:3": (4, 3),
}

_PIL_FORMATS = {
    "png": ("PNG", "png"), "jpg": ("JPEG", "jpg"),
    "jpeg": ("JPEG", "jpg"), "webp": ("WEBP", "webp"),
}

# Formats we can write back. Anything else (bmp, …) becomes a PNG.
_EXT_TO_FORMAT = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
_MAX_SIDE = 8000


def _save_as(im, output_path: str, fmt: str | None = None) -> str:
    """Save `im` at `output_path`, deriving the format from its extension.

    Re-encoding a photo as PNG inflates it several times over (a 406 KB JPEG
    becomes a 2.6 MB PNG), so the geometry tools keep the source format. JPEG
    has no alpha, so a transparent image is flattened onto white first — PIL's
    plain RGBA→RGB drop would show the transparent areas as black.
    """
    from PIL import Image

    if fmt is None:
        ext = os.path.splitext(output_path)[1].lower()
        fmt = _EXT_TO_FORMAT.get(ext, "PNG")
    if fmt == "JPEG" and im.mode in ("RGBA", "LA", "P"):
        rgba = im.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.split()[-1])
        im = flat
    kwargs = {"quality": 92} if fmt == "JPEG" else {}
    im.save(output_path, fmt, **kwargs)
    return output_path


def keep_format_path(input_path: str, output_dir: str, stem: str) -> str:
    """Output path for `stem` that reuses the input's format when we can write
    it, so a JPEG in stays a JPEG out."""
    ext = os.path.splitext(input_path)[1].lower()
    return os.path.join(output_dir, f"{stem}{ext if ext in _EXT_TO_FORMAT else '.png'}")


def crop_to_aspect(input_path: str, output_path: str, aspect: str = "1:1") -> str:
    """Center-crop an image to the given aspect ratio."""
    from PIL import Image

    aw, ah = _ASPECT_FRACTIONS.get(aspect, (1, 1))
    with Image.open(input_path) as im:
        w, h = im.size
        target = aw / ah
        if w / h > target:                 # too wide → trim sides
            new_w = int(h * target)
            left = (w - new_w) // 2
            box = (left, 0, left + new_w, h)
        else:                              # too tall → trim top/bottom
            new_h = int(w / target)
            top = (h - new_h) // 2
            box = (0, top, w, top + new_h)
        return _save_as(im.crop(box), output_path)


def resize_image(input_path: str, output_path: str, width: int = 1080) -> str:
    """Resize to `width` px, keeping the aspect ratio."""
    from PIL import Image

    width = max(16, min(_MAX_SIDE, int(width)))
    with Image.open(input_path) as im:
        w, h = im.size
        height = max(1, round(h * width / w))
        return _save_as(im.resize((width, height), Image.LANCZOS), output_path)


def convert_image(input_path: str, output_path: str, fmt: str = "png") -> str:
    """Convert an image to another format (png/jpg/webp)."""
    from PIL import Image

    pil_fmt = _PIL_FORMATS.get(fmt, ("PNG", "png"))[0]
    with Image.open(input_path) as im:
        return _save_as(im, output_path, pil_fmt)


def upscale_image(input_path: str, output_path: str, factor: int = 2) -> str:
    """Enlarge an image by `factor`× using high-quality Lanczos resampling.

    The long side is capped at 8000px. An image already at or over the cap is
    left at its own size — an *upscale* tool must never shrink the picture.
    """
    from PIL import Image

    factor = 4 if int(factor) >= 4 else 2
    with Image.open(input_path) as im:
        w, h = im.size
        longest = max(w, h)
        headroom = max(1.0, _MAX_SIDE / longest) if longest else float(factor)
        scale = min(float(factor), headroom)
        target = (max(1, round(w * scale)), max(1, round(h * scale)))
        return _save_as(im.resize(target, Image.LANCZOS), output_path)


def enhance_image(input_path: str, output_path: str, *, sharpness: float = 1.5,
                  contrast: float = 1.1, color: float = 1.1) -> str:
    """Improve an image: sharpen + adjust contrast/saturation (PIL ImageEnhance).
    Each factor is 1.0 = unchanged, >1 = stronger."""
    from PIL import Image, ImageEnhance

    with Image.open(input_path) as im:
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        im = ImageEnhance.Sharpness(im).enhance(max(0.0, min(4.0, float(sharpness))))
        im = ImageEnhance.Contrast(im).enhance(max(0.5, min(2.0, float(contrast))))
        im = ImageEnhance.Color(im).enhance(max(0.0, min(2.0, float(color))))
        return _save_as(im, output_path)


def output_ext_for_format(fmt: str) -> str:
    """Map a requested format to a file extension."""
    return _PIL_FORMATS.get(fmt, ("PNG", "png"))[1]


def remove_background(input_path: str, output_path: str) -> str:
    """Remove the background from `input_path`, writing a transparent PNG to
    `output_path`. Returns the output path."""
    logger.info("Removing background: %s → %s", input_path, output_path)
    try:
        res = subprocess.run(
            [sys.executable, "-m", "app.workers._imaging_run", "bg_remove", input_path, output_path],
            capture_output=True, text=True, timeout=settings.IMAGE_TIMEOUT,
            **ffmpeg.CHILD_GUARD,
        )
    except subprocess.TimeoutExpired as exc:
        raise ffmpeg.MediaError(
            f"Background removal timed out after {settings.IMAGE_TIMEOUT}s. "
            "Try a smaller image or raise IMAGE_TIMEOUT."
        ) from exc
    if res.returncode != 0 or not os.path.exists(output_path):
        raise ffmpeg.MediaError(f"Background removal failed: {res.stderr[-1000:]}")
    return output_path
