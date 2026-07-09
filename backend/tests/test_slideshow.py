"""Image-to-shorts slideshow — real ffmpeg render (skipped if ffmpeg absent)."""
import shutil
import subprocess

import pytest

from app.core.config import settings
from app.workers.ffmpeg import MediaError
from app.workers.slideshow import build_slideshow

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _make_image(path, color):
    from PIL import Image

    Image.new("RGB", (1200, 800), color).save(path)


def _duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def test_single_image_short(tmp_path):
    img = tmp_path / "a.png"
    _make_image(img, (200, 80, 80))
    out = tmp_path / "single.mp4"

    build_slideshow([str(img)], str(out))

    assert out.exists() and out.stat().st_size > 0
    assert _duration(str(out)) == pytest.approx(settings.SLIDESHOW_SECONDS_PER_IMAGE, abs=0.2)


def test_multi_image_short_duration_and_resolution(tmp_path):
    paths = []
    for i, c in enumerate([(200, 80, 80), (80, 160, 200), (120, 200, 120)]):
        p = tmp_path / f"img{i}.png"
        _make_image(p, c)
        paths.append(str(p))
    out = tmp_path / "multi.mp4"

    build_slideshow(paths, str(out))

    # 3 clips with 2 crossfades: 3*D - 2*T.
    expected = 3 * settings.SLIDESHOW_SECONDS_PER_IMAGE - 2 * settings.SLIDESHOW_TRANSITION
    assert _duration(str(out)) == pytest.approx(expected, abs=0.3)

    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(out)],
        capture_output=True, text=True,
    )
    assert res.stdout.strip() == "1080,1920"


def test_no_images_raises():
    with pytest.raises(MediaError):
        build_slideshow([], "/tmp/never.mp4")
