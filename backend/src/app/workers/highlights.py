"""
Smart highlight engine.

Given a source video, find its most interesting moments and assemble them into
several *variations* of a short. Each variation is a chronologically-ordered
compilation of non-contiguous clips (5–12 s each). Variations share their
strongest moments but diverge afterwards, so the user can preview a few and pick
the best one.

"Interesting" is scored without any external service, so the pipeline degrades
gracefully when no LLM/GPU is available:
  * visual scene changes  → candidate clip boundaries (ffmpeg scene detection)
  * speech density         → how much is actually being said in a window
  * mild position weighting → de-emphasise intros/outros

This module is pure (no DB, no app state) and easy to unit-test.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from app.workers import ffmpeg
from app.workers.transcriber import WordTimestamp

logger = logging.getLogger(__name__)

Clip = tuple[float, float]


@dataclass(frozen=True)
class Candidate:
    start: float
    end: float
    score: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def _overlaps(a: Clip, b: Clip) -> bool:
    return not (a[1] <= b[0] or a[0] >= b[1])


def _word_count(words: list[WordTimestamp], start: float, end: float) -> int:
    return sum(1 for w in words if w.start >= start and w.end <= end)


def snap_to_speech(
    start: float,
    end: float,
    words: list[WordTimestamp],
    *,
    pause: float = 0.35,
    tail_trim: float = 1.5,
    min_keep: float = 2.0,
) -> Clip:
    """
    Align a clip's [start, end] to speech boundaries so it never cuts a word in
    half, and ideally ends on a natural pause:
      * start moves to the beginning of the first whole word in the window
        (a word straddling the cut is dropped)
      * end moves to the last whole word that fits; if a silence gap >= `pause`
        sits within the final `tail_trim` seconds, end there instead so the clip
        finishes on a sentence boundary rather than mid-speech
    Falls back to the original bounds if snapping would collapse the clip or
    there is no speech in the window.
    """
    if not words:
        return start, end
    inside = [w for w in words if w.end > start and w.start < end]
    if not inside:
        return start, end

    # Start: skip a word that straddles the cut; begin on a clean word start.
    new_start = next((w.start for w in inside if w.start >= start - 0.02), inside[0].start)

    # End: never include a word that runs past `end`.
    whole = [w for w in inside if w.end <= end + 0.02]
    if not whole:
        return start, end
    new_end = whole[-1].end

    # If speech pauses near the end, finish there (clean sentence stop).
    for w, nxt in zip(whole, whole[1:]):
        if (nxt.start - w.end) >= pause and w.end >= new_end - tail_trim:
            new_end = w.end

    if new_end - new_start < min_keep:
        return start, end
    return round(new_start, 2), round(new_end, 2)


def build_candidates(
    video_path: str,
    duration: float,
    word_timestamps: list[WordTimestamp],
    *,
    clip_min: float,
    clip_max: float,
    scene_threshold: float,
    seed: int = 0,
) -> list[Candidate]:
    """Detect and score candidate highlight clips across the whole video."""
    scenes = ffmpeg.detect_scenes(video_path, scene_threshold, duration)
    boundaries = sorted({0.0, *(s for s in scenes if 0 < s < duration), duration})
    if len(boundaries) < 2:
        boundaries = [0.0, duration]

    # 1. Slice scenes into clip-sized windows anchored at the scene start.
    raw: list[tuple[float, float, bool]] = []  # (start, end, at_scene_cut)
    for a, b in zip(boundaries, boundaries[1:]):
        span = b - a
        if span < clip_min:
            continue
        if span <= clip_max:
            raw.append((a, b, True))
            continue
        t = a
        first = True
        while t + clip_min <= b:
            end = min(t + clip_max, b)
            raw.append((round(t, 2), round(end, 2), first))
            first = False
            t = end
    if not raw:  # no usable scenes → even windows across the whole video
        t = 0.0
        while t + clip_min <= duration:
            end = min(t + clip_max, duration)
            raw.append((round(t, 2), round(end, 2), False))
            t = end

    # 1b. Snap each window to speech so clips don't cut mid-word / mid-sentence.
    if word_timestamps:
        snapped: list[tuple[float, float, bool]] = []
        seen: set[tuple[float, float]] = set()
        for s, e, at_cut in raw:
            ns, ne = snap_to_speech(s, e, word_timestamps)
            if ne - ns < clip_min * 0.6:    # too short after snapping → keep original
                ns, ne = s, e
            key = (round(ns, 1), round(ne, 1))
            if key not in seen:
                seen.add(key)
                snapped.append((ns, ne, at_cut))
        raw = snapped or raw

    # 2. Score each window. Normalise speech density across all candidates.
    densities = [
        _word_count(word_timestamps, s, e) / max(1e-6, e - s) for s, e, _ in raw
    ]
    max_density = max(densities) if densities else 0.0
    rng = random.Random(seed)

    candidates: list[Candidate] = []
    for (s, e, at_cut), density in zip(raw, densities):
        norm = (density / max_density) if max_density > 0 else 0.0
        mid = (s + e) / 2 / max(1e-6, duration)
        position = 1.0 - abs(mid - 0.5)            # peaks in the middle of the video
        score = (
            1.0
            + 2.2 * norm                            # speech-dense = engaging
            + (0.6 if at_cut else 0.0)              # right after a visual cut
            + 0.4 * position                        # avoid pure intro/outro
            + rng.uniform(0.0, 0.05)                # tie-break jitter
        )
        candidates.append(Candidate(s, e, round(score, 4)))

    candidates.sort(key=lambda c: c.score, reverse=True)
    logger.info("Highlight candidates: %d (scenes=%d)", len(candidates), len(scenes))
    return candidates


def _fill_one(
    ranked: list[Candidate],
    *,
    soft_target: float,
    target_min: float,
    target_max: float,
    max_clips: int,
) -> list[Clip] | None:
    """
    Greedily pick a non-overlapping, chronological compilation from `ranked`,
    filling up to `soft_target` seconds (never exceeding `target_max`).
    """
    chosen: list[Clip] = []
    total = 0.0
    for cand in ranked:
        clip = (cand.start, cand.end)
        if any(_overlaps(clip, c) for c in chosen):
            continue
        if total + cand.duration > target_max:
            continue
        chosen.append(clip)
        total += cand.duration
        if total >= soft_target and len(chosen) >= 3:
            break
        if len(chosen) >= max_clips:
            break
    if total < target_min or len(chosen) < 2:
        return None
    return sorted(chosen, key=lambda c: c[0])


def generate_variations(
    candidates: list[Candidate],
    count: int,
    *,
    target_min: float,
    target_max: float,
    seed: int = 0,
    max_clips: int = 6,
) -> list[list[Clip]]:
    """
    Produce `count` DISTINCT short compilations from scored candidates.

    Variation 0 uses the best candidates verbatim; later variations apply a
    growing score jitter so they share the strongest moments but continue
    differently. Falls back to evenly-spaced compilations if material is thin.
    """
    if not candidates:
        return []

    variations: list[list[Clip]] = []
    signatures: set[tuple] = set()
    attempts = 0
    max_attempts = count * 8

    while len(variations) < count and attempts < max_attempts:
        k = len(variations)
        perturb = min(0.6, 0.18 * (attempts))     # 0 for the first try, grows on retries
        rng = random.Random(seed * 1000 + attempts)
        ranked = sorted(
            candidates,
            key=lambda c: c.score * (1.0 + rng.uniform(-perturb, perturb)),
            reverse=True,
        )
        # Vary target length per variation so previews differ in pacing too.
        soft_target = rng.uniform(target_min + 3, target_max)
        compilation = _fill_one(
            ranked, soft_target=soft_target,
            target_min=target_min, target_max=target_max, max_clips=max_clips,
        )
        attempts += 1
        if not compilation:
            continue
        sig = tuple(round(s, 1) for s, _ in compilation)
        if sig in signatures:
            continue
        signatures.add(sig)
        variations.append(compilation)

    if len(variations) < count:
        logger.info(
            "Smart engine produced %d/%d variations; padding with even splits",
            len(variations), count,
        )
        variations.extend(
            _even_compilations(candidates, count - len(variations), target_min, target_max)
        )

    return variations[:count]


def _even_compilations(
    candidates: list[Candidate],
    count: int,
    target_min: float,
    target_max: float,
) -> list[list[Clip]]:
    """Deterministic fallback: 2 evenly-spaced clips per short from the timeline."""
    if not candidates:
        return []
    lo = min(c.start for c in candidates)
    hi = max(c.end for c in candidates)
    span = max(1.0, hi - lo)
    clip_len = min((target_min + target_max) / 4, span / (count * 2))
    out: list[list[Clip]] = []
    for i in range(count):
        base = lo + (span / count) * i
        mid = base + span / count / 2
        c1 = (round(base, 2), round(base + clip_len, 2))
        c2 = (round(mid, 2), round(mid + clip_len, 2))
        out.append([c1, c2])
    return out
