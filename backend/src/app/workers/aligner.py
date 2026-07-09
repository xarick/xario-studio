"""
Forced-alignment-lite: place a user-supplied transcript onto the audio timeline.

The user gives the EXACT words; Whisper gives the TIMING (word timestamps, even
if it mishears some words). We align the two word sequences by similarity:
correctly-heard words become anchors, and the user's words that Whisper missed
are interpolated between them. The result is the user's clean text with accurate
timestamps — no reliance on Whisper getting the words right.
"""
from __future__ import annotations

import difflib
import logging
import re

from app.workers.transcriber import WordTimestamp

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Split into display tokens, preserving the user's original words/casing."""
    return [tok for tok in re.split(r"\s+", text.strip()) if tok]


def _norm(token: str) -> str:
    """Normalise a token for matching (lowercase, strip punctuation)."""
    return re.sub(r"[^\w']+", "", token.lower())


def _interpolate(result: list, tokens: list[str], lo: int, hi: int,
                 t_start: float, t_end: float) -> None:
    """Spread tokens (lo..hi exclusive) evenly across [t_start, t_end]."""
    n = hi - lo
    if n <= 0:
        return
    span = max(0.0, t_end - t_start)
    step = span / n if n else 0.0
    for k, idx in enumerate(range(lo, hi)):
        s = t_start + step * k
        e = t_start + step * (k + 1) if step else t_start
        result[idx] = (round(s, 3), round(max(s + 0.05, e), 3))


def align_text(
    text: str,
    whisper_words: list[WordTimestamp],
    duration: float,
) -> list[WordTimestamp]:
    """
    Align `text` to the audio using Whisper word timings as anchors.
    Returns the user's words with timestamps. Falls back to an even spread if
    Whisper produced nothing usable.
    """
    tokens = _tokenize(text)
    if not tokens:
        return []

    if not whisper_words:
        logger.info("No Whisper timing — distributing %d words evenly", len(tokens))
        result: list = [None] * len(tokens)
        _interpolate(result, tokens, 0, len(tokens), 0.0, duration or len(tokens))
        return [WordTimestamp(tok, s, e) for tok, (s, e) in zip(tokens, result)]

    u_norm = [_norm(t) for t in tokens]
    w_norm = [_norm(w.word) for w in whisper_words]

    matcher = difflib.SequenceMatcher(None, u_norm, w_norm, autojunk=False)
    result: list = [None] * len(tokens)
    anchors: list[int] = []          # user indices that got a real timestamp

    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            ui, wi = block.a + k, block.b + k
            result[ui] = (whisper_words[wi].start, whisper_words[wi].end)
            anchors.append(ui)

    if not anchors:
        logger.info("No word matches — distributing %d words evenly", len(tokens))
        _interpolate(result, tokens, 0, len(tokens), 0.0, duration or len(tokens))
        return [WordTimestamp(tok, s, e) for tok, (s, e) in zip(tokens, result)]

    # Interpolate unmatched words before, between, and after anchors.
    first, last = anchors[0], anchors[-1]
    _interpolate(result, tokens, 0, first, 0.0, result[first][0])
    for a, b in zip(anchors, anchors[1:]):
        if b - a > 1:
            _interpolate(result, tokens, a + 1, b, result[a][1], result[b][0])
    _interpolate(result, tokens, last + 1, len(tokens), result[last][1],
                 duration or result[last][1])

    matched = len(anchors)
    logger.info("Aligned %d/%d user words to Whisper anchors", matched, len(tokens))
    return [WordTimestamp(tok, s, e) for tok, (s, e) in zip(tokens, result)]
