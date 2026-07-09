"""
Translate + dub assembly.

Given the original media, the source segments' timing, and a WAV of synthesised
speech per segment (see tts.synthesize_batch), this:
  1. time-fits each spoken clip to its original segment window (atempo, clamped),
  2. lays every clip onto the timeline at its original start time, and
  3. muxes the new track back onto the video (or returns dubbed audio).

The whisper → translate → TTS steps live in video_processor._run_dub_mode; this
module only does the audio carpentry.

Assembly runs as a SINGLE ffmpeg command. Delaying every clip and `amix`-ing them
together is quadratic in the number of segments (600 clips took ~63 s), so the
clips are instead packed into "lanes" of non-overlapping speech and each lane is
built with a linear `concat` of silence + clip (~4 s for the same 600).
"""
from __future__ import annotations

import contextlib
import logging
import os
import shutil
import wave
from dataclasses import dataclass

from app.core.config import settings
from app.workers import ffmpeg

logger = logging.getLogger(__name__)

_SR = 24000   # XTTS output sample rate
# ffmpeg's atempo filter only accepts this range in a single pass.
_ATEMPO_MIN, _ATEMPO_MAX = 0.5, 2.0


@dataclass(frozen=True)
class Placement:
    """One synthesised clip, time-fitted and pinned to its source start time."""
    index: int      # ffmpeg input index
    wav: str
    start: float    # seconds on the output timeline
    tempo: float    # atempo factor applied to the clip
    fitted: float   # clip length after the tempo change

    @property
    def end(self) -> float:
        return self.start + self.fitted


def _wav_duration(path: str) -> float:
    """Length of a PCM WAV, read from its header — no subprocess per clip."""
    try:
        with contextlib.closing(wave.open(path, "rb")) as w:
            rate = w.getframerate()
            return w.getnframes() / float(rate) if rate else 0.0
    except (wave.Error, OSError) as exc:
        logger.warning("Could not read WAV header for %s: %s", path, exc)
        return 0.0


def extract_reference(input_path: str, out_wav: str, max_seconds: int) -> str | None:
    """Pull the first `max_seconds` of the source audio as a mono WAV — used to
    clone the original speaker's voice. Returns None if the source has no audio."""
    if not ffmpeg._has_audio(input_path):
        return None
    try:
        ffmpeg.run_ffmpeg(
            ["ffmpeg", "-y", "-t", str(max_seconds), "-i", input_path,
             "-vn", "-ac", "1", "-ar", str(_SR), out_wav],
            "Reference extraction", timeout=ffmpeg.timeout_for(max_seconds),
        )
    except ffmpeg.MediaError as exc:
        logger.warning("Reference extraction failed: %s", exc)
        return None
    return out_wav if os.path.exists(out_wav) else None


def plan_placements(segments: list[dict], wavs: list[str | None],
                    total_duration: float) -> list[Placement]:
    """Time-fit each synthesised clip to the window of the segment it replaces.

    The tempo is clamped so a long translation never turns into chipmunk speech —
    it simply overruns its window, which the lane packing then accommodates.
    """
    lo = max(_ATEMPO_MIN, settings.DUB_MIN_TEMPO)
    hi = min(_ATEMPO_MAX, settings.DUB_MAX_TEMPO)

    out: list[Placement] = []
    for seg, wav in zip(segments, wavs):
        if not wav or not os.path.exists(wav):
            continue
        start = float(seg["start"])
        if start >= total_duration:
            continue
        natural = _wav_duration(wav)
        if natural <= 0:
            continue
        window = max(0.3, float(seg["end"]) - start)
        tempo = min(hi, max(lo, natural / window))
        out.append(Placement(index=len(out), wav=wav, start=start,
                             tempo=tempo, fitted=natural / tempo))
    out.sort(key=lambda p: p.start)
    # `index` must follow the order the inputs are passed to ffmpeg.
    return [Placement(i, p.wav, p.start, p.tempo, p.fitted) for i, p in enumerate(out)]


def assign_lanes(placements: list[Placement]) -> list[list[Placement]]:
    """Pack clips into the fewest lanes in which no two clips overlap.

    Speech almost never overlaps, so this is normally a single lane; a lane is
    then just silence-then-clip repeated, which `concat` builds in linear time.
    Overruns from the tempo clamp spill into a second lane and get mixed back in.
    """
    lanes: list[list[Placement]] = []
    cursors: list[float] = []
    for p in placements:
        for i, cursor in enumerate(cursors):
            if cursor <= p.start + 1e-3:
                lanes[i].append(p)
                cursors[i] = p.end
                break
        else:
            lanes.append([p])
            cursors.append(p.end)
    return lanes


def build_filtergraph(lanes: list[list[Placement]]) -> str:
    """ffmpeg filtergraph that renders `lanes` into a single [out] track."""
    parts: list[str] = []
    lane_labels: list[str] = []

    for li, lane in enumerate(lanes):
        cursor = 0.0
        labels: list[str] = []
        for p in lane:
            gap_ms = int(round(max(0.0, p.start - cursor) * 1000))
            parts.append(
                f"[{p.index}:a]aformat=sample_rates={_SR}:channel_layouts=mono,"
                f"atempo={p.tempo:.4f},adelay={gap_ms}|{gap_ms}[c{p.index}]"
            )
            labels.append(f"[c{p.index}]")
            cursor = p.end
        parts.append("".join(labels) + f"concat=n={len(lane)}:v=0:a=1[lane{li}]")
        lane_labels.append(f"[lane{li}]")

    if len(lane_labels) == 1:
        parts.append(f"{lane_labels[0]}apad[out]")
    else:
        # normalize=0 keeps each lane at its own level; lanes rarely overlap, so
        # summing them cannot pile up enough gain to clip.
        parts.append("".join(lane_labels)
                     + f"amix=inputs={len(lane_labels)}:normalize=0:duration=longest[mixed]")
        parts.append("[mixed]apad[out]")
    return ";".join(parts)


def build_dubbed_audio(
    segments: list[dict],
    wavs: list[str | None],
    output_dir: str,
    total_duration: float,
) -> str:
    """
    Place each (time-fitted) spoken clip at its segment start and pad the track
    to exactly `total_duration`. Returns the path to the assembled dubbed WAV.
    """
    out_wav = os.path.join(output_dir, "dub.wav")
    placements = plan_placements(segments, wavs, total_duration)

    if not placements:
        # Nothing synthesised → a silent track of the right length still muxes.
        logger.warning("Dub assembly: no usable clips, writing a silent track")
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={_SR}:cl=mono"]
    else:
        lanes = assign_lanes(placements)
        logger.info("Dub assembly: %d clip(s) in %d lane(s)", len(placements), len(lanes))
        cmd = ["ffmpeg", "-y"]
        for p in placements:
            cmd += ["-i", p.wav]
        cmd += ["-filter_complex", build_filtergraph(lanes), "-map", "[out]"]

    cmd += ["-t", f"{total_duration:.3f}", "-ac", "1", "-ar", str(_SR), out_wav]
    ffmpeg.run_ffmpeg(cmd, "Dub assembly", timeout=ffmpeg.timeout_for(total_duration))
    return out_wav


def mux(input_path: str, dub_wav: str, output_path: str, *, has_video: bool,
        duration: float = 0.0) -> None:
    """Replace the media's audio with the dubbed track (video kept as-is)."""
    if has_video:
        cmd = ["ffmpeg", "-y", "-i", input_path, "-i", dub_wav,
               "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
               "-c:a", "aac", "-b:a", "192k", "-shortest",
               "-movflags", "+faststart", output_path]
    else:
        cmd = ["ffmpeg", "-y", "-i", dub_wav, "-c:a", "libmp3lame", "-b:a", "192k", output_path]
    ffmpeg.run_ffmpeg(cmd, "Dub mux", timeout=ffmpeg.timeout_for(duration))


def cleanup_intermediates(output_dir: str) -> None:
    """Drop the per-segment WAVs and the assembled track once the final file is
    muxed. A dubbed hour of speech leaves ~700 of them behind otherwise."""
    for name in ("seg", "fit"):
        path = os.path.join(output_dir, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    for name in ("dub.wav", "ref.wav"):
        path = os.path.join(output_dir, name)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
