"""Simple-mode segment maths + feasibility validation (pure logic)."""
import pytest

from app.core.config import settings
from app.db.enums import GenerationMode
from app.workers.video_processor import _simple_segments, _validate_feasibility


def test_simple_segments_count_and_bounds():
    duration = 600.0
    count = 5
    segments = _simple_segments(duration, count)

    assert len(segments) == count
    for clip_list in segments:
        # Each simple short is exactly one contiguous clip.
        assert len(clip_list) == 1
        start, end = clip_list[0]
        assert 0 <= start < end <= duration
        length = end - start
        # Within the configured min/max (allow a small rounding slack).
        assert length <= settings.MAX_SHORT_DURATION + 0.5


def test_simple_segments_are_chronological_and_non_overlapping():
    segments = _simple_segments(600.0, 4)
    flat = [clip[0] for clip in segments]
    starts = [s for s, _ in flat]
    assert starts == sorted(starts)
    for (s1, e1), (s2, e2) in zip(flat, flat[1:]):
        assert e1 <= s2 + 0.01


def test_simple_segments_deterministic():
    # Seeded by int(duration) → same input gives same output.
    assert _simple_segments(450.0, 3) == _simple_segments(450.0, 3)


def test_feasibility_smart_needs_min_duration():
    short = settings.MIN_SHORT_DURATION - 1
    with pytest.raises(ValueError):
        _validate_feasibility(short, 1, GenerationMode.smart)
    # Long enough → no raise.
    _validate_feasibility(settings.MIN_SHORT_DURATION + 10, 5, GenerationMode.smart)


def test_feasibility_simple_rejects_too_many_shorts():
    # 100s into 10 shorts → 10s each, below the 30s floor.
    with pytest.raises(ValueError):
        _validate_feasibility(100.0, 10, GenerationMode.simple)


def test_feasibility_simple_accepts_reasonable_split():
    _validate_feasibility(600.0, 5, GenerationMode.simple)  # 120s each — fine
