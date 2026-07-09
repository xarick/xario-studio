"""Unit tests for the dub assembly planner.

The assembly runs as one ffmpeg command built from these pure functions, so the
timeline maths is tested here rather than by decoding audio.
"""
import pytest

from app.core.config import settings
from app.workers import dub
from app.workers.dub import Placement, assign_lanes, build_filtergraph, plan_placements


@pytest.fixture
def wavs(tmp_path, monkeypatch):
    """Two clips whose natural length is 2.5s, without touching the disk."""
    paths = []
    for i in range(3):
        p = tmp_path / f"seg_{i}.wav"
        p.write_bytes(b"")
        paths.append(str(p))
    monkeypatch.setattr(dub, "_wav_duration", lambda _p: 2.5)
    return paths


def test_clip_is_sped_up_to_fit_a_short_window(wavs):
    segs = [{"start": 0.0, "end": 2.0}]          # 2.5s of speech into a 2.0s hole
    (p,) = plan_placements(segs, wavs[:1], 60.0)
    assert p.tempo == pytest.approx(1.25)
    assert p.fitted == pytest.approx(2.0)


def test_tempo_is_clamped_so_speech_never_becomes_chipmunk(wavs):
    segs = [{"start": 0.0, "end": 0.5}]          # would need tempo 5.0
    (p,) = plan_placements(segs, wavs[:1], 60.0)
    assert p.tempo == pytest.approx(settings.DUB_MAX_TEMPO)
    # Clamped tempo means the clip overruns its window rather than distorting.
    assert p.end > 0.5


def test_clips_past_the_end_of_the_media_are_dropped(wavs):
    segs = [{"start": 1.0, "end": 3.0}, {"start": 99.0, "end": 101.0}]
    placements = plan_placements(segs, wavs[:2], total_duration=10.0)
    assert [p.start for p in placements] == [1.0]


def test_missing_wavs_are_skipped_and_indices_stay_contiguous(wavs, monkeypatch):
    segs = [{"start": 0.0, "end": 3.0}, {"start": 5.0, "end": 8.0}, {"start": 10.0, "end": 13.0}]
    placements = plan_placements(segs, [wavs[0], None, wavs[2]], 60.0)
    # ffmpeg numbers its inputs 0..n-1 in the order they are passed.
    assert [p.index for p in placements] == [0, 1]
    assert [p.start for p in placements] == [0.0, 10.0]


def test_non_overlapping_speech_packs_into_one_lane(wavs):
    segs = [{"start": 0.0, "end": 3.0}, {"start": 5.0, "end": 8.0}]
    lanes = assign_lanes(plan_placements(segs, wavs[:2], 60.0))
    assert len(lanes) == 1


def test_an_overrunning_clip_spills_into_a_second_lane(wavs):
    """A clamped tempo can push a clip past the next one's start; mixing the two
    lanes keeps both audible instead of shifting the whole timeline."""
    segs = [{"start": 0.0, "end": 0.5}, {"start": 0.6, "end": 3.0}]
    lanes = assign_lanes(plan_placements(segs, wavs[:2], 60.0))
    assert len(lanes) == 2


def test_filtergraph_delays_each_clip_by_its_gap():
    lane = [
        Placement(index=0, wav="a.wav", start=5.0, tempo=1.0, fitted=3.0),
        Placement(index=1, wav="b.wav", start=20.0, tempo=1.0, fitted=2.0),
    ]
    fg = build_filtergraph([lane])
    assert "adelay=5000|5000[c0]" in fg          # 5s of leading silence
    assert "adelay=12000|12000[c1]" in fg        # 20 - (5 + 3) = 12s gap
    assert "concat=n=2:v=0:a=1[lane0]" in fg
    assert "amix" not in fg                       # one lane needs no mixing


def test_filtergraph_mixes_multiple_lanes():
    lanes = [
        [Placement(0, "a.wav", 0.0, 1.0, 2.0)],
        [Placement(1, "b.wav", 1.0, 1.0, 2.0)],
    ]
    fg = build_filtergraph(lanes)
    assert "amix=inputs=2:normalize=0:duration=longest" in fg


def test_assembly_is_linear_not_quadratic_in_clip_count():
    """Regression guard: the old build delayed every clip and amix'd them all
    together, which cost ~63s for 600 clips. One concat per lane keeps the
    filtergraph proportional to the clip count."""
    lane = [Placement(i, f"{i}.wav", i * 3.0, 1.0, 2.0) for i in range(600)]
    fg = build_filtergraph([lane])
    assert fg.count("adelay=") == 600
    assert fg.count("concat=") == 1
    assert "amix" not in fg


def test_silent_track_when_nothing_was_synthesised(wavs, tmp_path, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(dub.ffmpeg, "run_ffmpeg", lambda cmd, *_a, **_kw: calls.append(cmd))

    out = dub.build_dubbed_audio([], [], str(tmp_path), total_duration=12.5)

    assert out.endswith("dub.wav")
    cmd = calls[0]
    assert "anullsrc=r=24000:cl=mono" in cmd
    assert cmd[cmd.index("-t") + 1] == "12.500"


def test_cleanup_removes_the_per_segment_wavs(tmp_path):
    (tmp_path / "seg").mkdir()
    (tmp_path / "seg" / "seg_0.wav").write_bytes(b"x")
    (tmp_path / "dub.wav").write_bytes(b"x")
    (tmp_path / "ref.wav").write_bytes(b"x")
    (tmp_path / "dubbed.mp4").write_bytes(b"keep me")

    dub.cleanup_intermediates(str(tmp_path))

    assert not (tmp_path / "seg").exists()
    assert not (tmp_path / "dub.wav").exists()
    assert not (tmp_path / "ref.wav").exists()
    assert (tmp_path / "dubbed.mp4").exists()
