"""snap_to_speech — clips align to whole words / natural pauses."""
from app.workers.highlights import snap_to_speech
from app.workers.transcriber import WordTimestamp


def _w(start, end, word="x"):
    return WordTimestamp(word=word, start=start, end=end)


def test_no_words_returns_input():
    assert snap_to_speech(10.0, 20.0, []) == (10.0, 20.0)


def test_drops_word_straddling_the_start():
    # Long enough window that snapping doesn't collapse below min_keep.
    words = [_w(9.5, 10.5), _w(11.0, 12.0), _w(13.0, 14.0), _w(20.0, 21.0), _w(24.0, 25.0)]
    start, end = snap_to_speech(10.0, 30.0, words)
    # The 9.5–10.5 word straddles the cut and is dropped; start snaps to 11.0.
    assert start == 11.0
    assert end <= 30.0


def test_never_includes_word_past_end():
    words = [_w(10.0, 11.0), _w(12.0, 13.0), _w(15.0, 16.0), _w(28.0, 29.0), _w(31.0, 33.0)]
    start, end = snap_to_speech(10.0, 30.0, words)
    # The 31.0–33.0 word runs past 30.0 → excluded; end never exceeds it.
    assert end == 29.0
    assert start == 10.0


def test_falls_back_when_window_has_no_speech():
    words = [_w(0.0, 1.0), _w(1.0, 2.0)]
    assert snap_to_speech(50.0, 60.0, words) == (50.0, 60.0)
