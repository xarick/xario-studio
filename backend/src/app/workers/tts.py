"""
Text-to-speech with Coqui XTTS-v2.

Synthesises an audio clip from text in one of XTTS's supported languages. A
voice can be picked from the model's built-in studio speakers, or cloned from a
short reference recording (``speaker_wav``).

Runs on GPU when a compatible torch/CUDA build is available, otherwise CPU
(slower but identical result). XTTS downloads its model (~1.8 GB) on first use;
COQUI_TOS_AGREED is exported so the download is non-interactive.

The heavy model is invoked in a subprocess (``python -m app.workers._tts_batch``,
which loads XTTS once and synthesises a whole list), like Demucs in separate.py,
so torch / transformers never get imported into the web process.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

from app.core.config import settings
from app.workers import ffmpeg

logger = logging.getLogger(__name__)

# Languages XTTS-v2 natively supports (ISO codes the model expects).
SUPPORTED_LANGS = {
    "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl",
    "cs", "ar", "zh-cn", "hu", "ko", "ja", "hi",
}

# Built-in XTTS-v2 studio speakers offered in the UI (curated subset).
BUILTIN_VOICES = [
    "Ana Florence", "Claribel Dervla", "Alison Dietlinde", "Sofia Hellen",
    "Tammie Ema", "Asya Anara", "Daisy Studious",
    "Andrew Chipper", "Damien Black", "Viktor Eka", "Craig Gutsy",
    "Eugenio Mataracı", "Ilkin Urumov", "Badr Odhiambo",
]


def _device() -> str:
    if settings.TTS_DEVICE.lower() != "cuda":
        return "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception as exc:
        logger.info("torch CUDA check failed (%s) — using CPU for TTS", exc)
    return "cpu"


def resolve_language(language: str | None) -> str:
    """Map a requested language to an XTTS-supported token.

    Uzbek has no native XTTS voice, so it is read with the phonetically-closest
    supported language (Turkish by default, configurable). Unknown / empty
    languages fall back to English.
    """
    lang = (language or "").strip().lower()
    if lang in ("uz", "uz-latn", "uzbek"):
        return settings.TTS_UZBEK_PROXY_LANG
    if lang in SUPPORTED_LANGS:
        return lang
    return "en"


def _to_mp3(wav_path: str, mp3_path: str) -> None:
    ffmpeg.run_ffmpeg(
        ["ffmpeg", "-y", "-i", wav_path, "-c:a", "libmp3lame", "-b:a", "192k", mp3_path],
        "mp3 encode",
    )


def synthesize_batch(
    texts: list[str],
    output_dir: str,
    *,
    language: str | None,
    voice: str | None = None,
    speaker_wav: str | None = None,
) -> list[str | None]:
    """
    Synthesise each string in `texts` to a WAV under `output_dir`, loading the
    XTTS model ONCE (see _tts_batch). `speaker_wav` (voice clone) wins over
    `voice` (built-in studio speaker). Returns a list aligned with `texts`;
    entries are WAV paths, or None for empty / failed lines.
    """
    os.makedirs(output_dir, exist_ok=True)
    lang = resolve_language(language)
    device = _device()

    job_path = os.path.join(output_dir, "_tts_job.json")
    result_path = os.path.join(output_dir, "_tts_result.json")
    job = {
        "model": settings.TTS_MODEL,
        "device": device,
        "language": lang,
        "voice": voice or settings.TTS_DEFAULT_VOICE,
        "speaker_wav": speaker_wav if (speaker_wav and os.path.exists(speaker_wav)) else None,
        "texts": texts,
        "out_dir": output_dir,
        "result_path": result_path,
    }
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False)

    logger.info("TTS batch: %d line(s), lang=%s, %s, %s",
                len(texts), lang, device, "clone" if job["speaker_wav"] else f"voice={job['voice']!r}")
    env = {
        **os.environ,
        "COQUI_TOS_AGREED": "1",
        # Reduce CUDA fragmentation so XTTS fits alongside other allocations;
        # a genuine OOM still triggers the CPU fallback inside _tts_batch.
        "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    }
    try:
        res = subprocess.run(
            [sys.executable, "-m", "app.workers._tts_batch", job_path],
            capture_output=True, text=True, timeout=settings.TTS_TIMEOUT, env=env,
            **ffmpeg.CHILD_GUARD,
        )
    except subprocess.TimeoutExpired as exc:
        raise ffmpeg.MediaError(
            f"TTS synthesis timed out after {settings.TTS_TIMEOUT}s "
            f"({len(texts)} line(s)). Raise TTS_TIMEOUT or use a GPU."
        ) from exc
    if res.returncode != 0 or not os.path.exists(result_path):
        raise ffmpeg.MediaError(f"TTS synthesis failed: {res.stderr[-1000:]}")

    with open(result_path, encoding="utf-8") as f:
        wavs = json.load(f).get("wavs", [])
    for path in (job_path, result_path):
        try:
            os.remove(path)
        except OSError:
            pass
    return wavs


def synthesize(
    text: str,
    output_dir: str,
    *,
    language: str | None,
    voice: str | None = None,
    speaker_wav: str | None = None,
) -> dict:
    """
    Synthesise `text` into a spoken-audio MP3 under `output_dir`.

    Either `speaker_wav` (clone a voice from a reference recording) or `voice`
    (a built-in XTTS studio speaker) selects the voice; `speaker_wav` wins.
    Returns {"audio": mp3_path}.
    """
    text = (text or "").strip()
    if not text:
        raise ffmpeg.MediaError("No text supplied to synthesise.")
    if len(text) > settings.TTS_MAX_CHARS:
        raise ffmpeg.MediaError(
            f"Text is too long ({len(text)} chars; max {settings.TTS_MAX_CHARS})."
        )

    wavs = synthesize_batch([text], output_dir, language=language, voice=voice, speaker_wav=speaker_wav)
    wav = wavs[0] if wavs else None
    if not wav or not os.path.exists(wav):
        raise ffmpeg.MediaError("TTS produced no audio.")

    mp3 = os.path.join(output_dir, "speech.mp3")
    _to_mp3(wav, mp3)
    if os.path.exists(wav):
        try:
            os.remove(wav)
        except OSError:
            pass

    return {"audio": mp3}
