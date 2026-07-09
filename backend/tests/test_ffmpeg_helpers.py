"""Unit tests for the ffmpeg command builders and the watchdog budget."""
import subprocess

import pytest

from app.core.config import settings
from app.workers import ffmpeg as ffmpeg_mod
from app.workers.ffmpeg import MediaError, clean_audio, run_ffmpeg, seek_inputs, timeout_for


def test_timeout_floor_applies_to_short_work():
    assert timeout_for(0) == settings.FFMPEG_MIN_TIMEOUT
    assert timeout_for(10) == settings.FFMPEG_MIN_TIMEOUT


def test_timeout_scales_with_the_work():
    """A long source gets a proportionally longer budget, not a flat 10 minutes."""
    assert timeout_for(3600) == int(3600 * settings.FFMPEG_TIMEOUT_FACTOR)
    assert timeout_for(3600) > timeout_for(600) > settings.FFMPEG_MIN_TIMEOUT


def test_seek_inputs_emits_one_seeked_input_per_clip():
    args = seek_inputs("in.mp4", [(1.5, 4.0), (10.0, 12.25)])
    assert args == [
        "-ss", "1.500", "-t", "2.500", "-i", "in.mp4",
        "-ss", "10.000", "-t", "2.250", "-i", "in.mp4",
    ]


def test_seek_inputs_never_emits_a_zero_length_clip():
    """A degenerate clip would make ffmpeg produce an empty stream and the
    concat filter fail with an unhelpful error."""
    args = seek_inputs("in.mp4", [(5.0, 5.0)])
    assert float(args[3]) > 0


def test_run_ffmpeg_raises_media_error_on_timeout(monkeypatch):
    """The watchdog must surface as MediaError — callers only catch that."""
    def slow(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)

    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(MediaError, match="timed out"):
        run_ffmpeg(["ffmpeg", "-i", "x"], "test op", timeout=1)


def test_run_ffmpeg_raises_media_error_on_bad_exit(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 1, "", "no such file"),
    )
    with pytest.raises(MediaError, match="no such file"):
        run_ffmpeg(["ffmpeg", "-i", "x"], "test op")


def test_blur_background_blurs_a_downscaled_copy():
    """Blurring at full size costs more than the H.264 encode itself, so the
    background is blurred small and scaled back up."""
    chain = ffmpeg_mod.blur_background(1080, 1920)
    assert chain.startswith("scale=270:480:")     # quarter size
    assert "gblur=sigma=6.25" in chain            # sigma scales with resolution
    assert chain.endswith("scale=1080:1920")      # …then back to full size


def test_blur_background_keeps_dimensions_even():
    """libx264 rejects odd dimensions; the downscale must not create them."""
    for w, h in [(1080, 1920), (1080, 1080), (1920, 1080), (642, 362), (10, 10)]:
        chain = ffmpeg_mod.blur_background(w, h)
        small = chain.split(":")[0].removeprefix("scale=")
        bw = int(small)
        bh = int(chain.split("crop=")[1].split(",")[0].split(":")[1])
        assert bw % 2 == 0 and bh % 2 == 0, (w, h, chain)
        assert bw >= 2 and bh >= 2


def _captured_af(monkeypatch, **kwargs) -> str:
    seen: list[list[str]] = []
    monkeypatch.setattr(ffmpeg_mod, "run_ffmpeg", lambda cmd, *_a, **_kw: seen.append(cmd))
    clean_audio("in.mp4", "out.mp4", **kwargs)
    cmd = seen[0]
    return cmd[cmd.index("-af") + 1]


def test_clean_audio_pins_the_channel_layout(monkeypatch):
    """loudnorm leaves the layout unspecified; without aformat the aac/mp3
    encoder refuses to link and the whole cleanup job dies."""
    af = _captured_af(monkeypatch, has_video=True)
    assert af.endswith("aformat=channel_layouts=mono|stereo")
    assert af.index("loudnorm") < af.index("aformat")


def test_clean_audio_only_trims_silence_without_video(monkeypatch):
    """Trimming silence out of a video would desync the picture."""
    assert "silenceremove" not in _captured_af(monkeypatch, has_video=True)
    assert "silenceremove" in _captured_af(monkeypatch, has_video=False)
