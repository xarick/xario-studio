"""
Vocal / music separation with Demucs.

Splits an audio (or a video's audio) into two stems:
  * vocals       — the isolated voice
  * instrumental — everything else (music / background)

For a video, an extra karaoke clip is produced: the original picture with the
instrumental track (vocals removed).

Runs on GPU when a compatible torch/CUDA build is available, otherwise CPU
(slower but identical result). Demucs downloads its model (~80 MB) on first use.
"""
from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import sys

from app.workers import ffmpeg

logger = logging.getLogger(__name__)

_DEMUCS_TIMEOUT = 1800   # separation can be slow on CPU
_MODEL = "htdemucs"


def _device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception as exc:
        logger.info("torch CUDA check failed (%s) — using CPU", exc)
    return "cpu"


def _to_mp3(wav_path: str, mp3_path: str) -> None:
    ffmpeg.run_ffmpeg(
        ["ffmpeg", "-y", "-i", wav_path, "-c:a", "libmp3lame", "-b:a", "256k", mp3_path],
        "mp3 encode",
    )


def separate(input_path: str, output_dir: str, *, has_video: bool) -> dict:
    """
    Separate `input_path` into stems under `output_dir`.
    Returns {"vocals": path, "instrumental": path[, "karaoke": path]}.
    """
    os.makedirs(output_dir, exist_ok=True)
    if not ffmpeg._has_audio(input_path):
        raise ffmpeg.MediaError("The file has no audio track to separate.")

    duration = ffmpeg.probe(input_path).duration
    wav = os.path.join(output_dir, "source.wav")

    # 1. Extract a clean stereo WAV (Demucs works on audio).
    ffmpeg.run_ffmpeg(
        ["ffmpeg", "-y", "-i", input_path, "-vn", "-ar", "44100", "-ac", "2", "-f", "wav", wav],
        "Audio extraction", timeout=ffmpeg.timeout_for(duration),
    )

    # 2. Run Demucs (2-stem: vocals vs the rest).
    device = _device()
    stems_dir = os.path.join(output_dir, "stems")
    logger.info("Demucs separating %s on %s", input_path, device)
    try:
        res = subprocess.run(
            [sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", _MODEL,
             "--device", device, "-o", stems_dir, wav],
            capture_output=True, text=True, timeout=_DEMUCS_TIMEOUT,
            **ffmpeg.CHILD_GUARD,
        )
    except subprocess.TimeoutExpired as exc:
        raise ffmpeg.MediaError(
            f"Demucs timed out after {_DEMUCS_TIMEOUT}s on {device}."
        ) from exc
    if res.returncode != 0:
        raise ffmpeg.MediaError(f"Demucs failed: {res.stderr[-1000:]}")

    track = os.path.splitext(os.path.basename(wav))[0]
    base = os.path.join(stems_dir, _MODEL, track)
    vocals_wav = os.path.join(base, "vocals.wav")
    instr_wav = os.path.join(base, "no_vocals.wav")
    if not (os.path.exists(vocals_wav) and os.path.exists(instr_wav)):
        found = glob.glob(os.path.join(stems_dir, "**", "*.wav"), recursive=True)
        raise ffmpeg.MediaError(f"Demucs output not found. Got: {found}")

    # 3. Encode stems to mp3.
    result: dict = {}
    result["vocals"] = os.path.join(output_dir, "vocals.mp3")
    result["instrumental"] = os.path.join(output_dir, "instrumental.mp3")
    _to_mp3(vocals_wav, result["vocals"])
    _to_mp3(instr_wav, result["instrumental"])

    # 4. Video → karaoke clip (original picture + instrumental track).
    if has_video:
        karaoke = os.path.join(output_dir, "karaoke.mp4")
        try:
            ffmpeg.run_ffmpeg(
                ["ffmpeg", "-y", "-i", input_path, "-i", instr_wav,
                 "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
                 "-b:a", "192k", "-shortest", "-movflags", "+faststart", karaoke],
                "Karaoke mux", timeout=ffmpeg.timeout_for(duration),
            )
            result["karaoke"] = karaoke
        except ffmpeg.MediaError as exc:
            # The stems are still useful — a missing karaoke clip is not fatal.
            logger.warning("Karaoke mux failed: %s", exc)

    # 5. Clean up intermediates.
    for path in (wav,):
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    if os.path.isdir(stems_dir):
        shutil.rmtree(stems_dir, ignore_errors=True)

    return result
