"""Image tools: keep the source format, never shrink an upscale."""
import os

import pytest
from PIL import Image

from app.workers import imaging


@pytest.fixture
def photo(tmp_path) -> str:
    """A JPEG that PNG cannot compress anywhere near as well."""
    import random

    random.seed(0)
    im = Image.new("RGB", (600, 400))
    im.putdata([(random.randrange(256), random.randrange(256), random.randrange(256))
                for _ in range(600 * 400)])
    path = tmp_path / "photo.jpg"
    im.save(path, "JPEG", quality=88)
    return str(path)


def test_geometry_tools_keep_the_source_format(photo, tmp_path):
    """A JPEG re-encoded as PNG grows several times over for no benefit."""
    out = imaging.keep_format_path(photo, str(tmp_path), "cropped")
    assert out.endswith(".jpg")

    imaging.crop_to_aspect(photo, out, "1:1")
    with Image.open(out) as im:
        assert im.format == "JPEG"
        assert im.size == (400, 400)


def test_a_png_stays_a_png(tmp_path):
    src = tmp_path / "logo.png"
    Image.new("RGBA", (40, 20), (0, 0, 0, 0)).save(src)
    out = imaging.keep_format_path(str(src), str(tmp_path), "resized")
    assert out.endswith(".png")


def test_unwritable_source_formats_fall_back_to_png(tmp_path):
    src = tmp_path / "scan.bmp"
    Image.new("RGB", (10, 10)).save(src)
    assert imaging.keep_format_path(str(src), str(tmp_path), "cropped").endswith(".png")


def test_upscale_never_shrinks_an_oversized_image(tmp_path):
    """An image already past the 8000px cap must come back untouched, not smaller."""
    src = tmp_path / "wide.png"
    Image.new("RGB", (9000, 300)).save(src)
    out = str(tmp_path / "up.png")

    imaging.upscale_image(str(src), out, 2)
    with Image.open(out) as im:
        assert im.size == (9000, 300)


def test_upscale_stops_at_the_cap(tmp_path):
    src = tmp_path / "mid.png"
    Image.new("RGB", (5000, 1000)).save(src)
    out = str(tmp_path / "up.png")

    imaging.upscale_image(str(src), out, 2)
    with Image.open(out) as im:
        assert im.size == (8000, 1600)


def test_upscale_doubles_a_small_image(tmp_path):
    src = tmp_path / "small.png"
    Image.new("RGB", (100, 50)).save(src)
    out = str(tmp_path / "up.png")

    imaging.upscale_image(str(src), out, 2)
    with Image.open(out) as im:
        assert im.size == (200, 100)


def test_transparency_becomes_white_not_black_on_jpeg(tmp_path):
    """PIL's plain RGBA→RGB drop renders transparent pixels black."""
    src = tmp_path / "t.png"
    Image.new("RGBA", (20, 20), (255, 0, 0, 0)).save(src)
    out = str(tmp_path / "t.jpg")

    imaging.convert_image(str(src), out, "jpg")
    with Image.open(out) as im:
        r, g, b = im.convert("RGB").getpixel((10, 10))
        assert r > 240 and g > 240 and b > 240


def test_enhance_keeps_the_format_and_the_alpha_channel(tmp_path):
    src = tmp_path / "icon.png"
    Image.new("RGBA", (30, 30), (10, 200, 10, 128)).save(src)
    out = imaging.keep_format_path(str(src), str(tmp_path), "enhanced")

    imaging.enhance_image(str(src), out)
    with Image.open(out) as im:
        assert im.format == "PNG"
        assert im.mode == "RGBA"


def test_a_photo_does_not_balloon(photo, tmp_path):
    """Regression guard for the old always-PNG behaviour."""
    out = imaging.keep_format_path(photo, str(tmp_path), "cropped")
    imaging.crop_to_aspect(photo, out, "1:1")

    as_png = str(tmp_path / "cropped_forced.png")
    imaging.crop_to_aspect(photo, as_png, "1:1")

    assert os.path.getsize(out) < os.path.getsize(as_png)
