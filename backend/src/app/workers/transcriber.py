"""
faster-whisper transcription wrapper.
Returns word-level timestamps for the full audio track.
Falls back to empty list on any error so the pipeline continues without subtitles.

GPU: when device="cuda" the required CUDA libraries (cuBLAS / cuDNN) shipped as
pip packages are preloaded at runtime, so no LD_LIBRARY_PATH setup is needed.
If the GPU is unavailable or out of memory, transcription transparently retries
on CPU.
"""
import ctypes
import glob
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_cuda_preloaded = False


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float


def _preload_cuda_libs() -> None:
    """Load the pip-provided CUDA libs into the global symbol namespace so
    CTranslate2 finds cuBLAS / cuDNN by soname without LD_LIBRARY_PATH.

    Once a library is dlopen'd by full path with RTLD_GLOBAL, a later dlopen by
    soname (as CTranslate2 does) reuses the already-loaded handle.
    """
    global _cuda_preloaded
    if _cuda_preloaded:
        return
    try:
        import nvidia  # namespace package; .so files live under nvidia/*/lib/
    except ImportError:
        logger.debug("nvidia CUDA pip packages not installed — GPU may be unavailable")
        return

    loaded = 0
    # cublas before cudnn (cudnn depends on cublas).
    for sub in ("cublas", "cudnn", "cuda_nvrtc"):
        for base in list(nvidia.__path__):
            for so in sorted(glob.glob(os.path.join(base, sub, "lib", "*.so*"))):
                try:
                    ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
                    loaded += 1
                except OSError:
                    pass
    _cuda_preloaded = loaded > 0
    logger.info("Preloaded %d CUDA libraries for GPU transcription", loaded)


def _child_guard() -> dict:
    """Don't let a killed worker leave a decoding ffmpeg behind."""
    from app.workers.ffmpeg import CHILD_GUARD

    return CHILD_GUARD


def _extract_audio(video_path: str, audio_path: str) -> None:
    """Extract mono 16 kHz PCM WAV — optimal input for Whisper."""
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-ar", "16000", "-ac", "1", "-f", "wav", audio_path,
        ],
        capture_output=True, text=True, timeout=300,
        **_child_guard(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr.strip()}")


def _run_whisper(audio_path, model_size, device, compute_type, language):
    """One transcription attempt; returns materialized faster-whisper segments."""
    from faster_whisper import WhisperModel

    if device == "cuda":
        _preload_cuda_libs()

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        audio_path,
        word_timestamps=True,
        language=language or None,
        vad_filter=True,   # drop long silences → better word timing
    )
    return list(segments)


def _transcribe_attempts(video_path, model_size, device, language, compute_type):
    """Extract audio + transcribe, retrying on CPU if the GPU fails. Returns segments or []."""
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        logger.warning("faster-whisper not installed — skipping transcription")
        return []

    if device == "cuda":
        attempts = [("cuda", compute_type or "int8_float16"), ("cpu", "int8")]
    else:
        attempts = [("cpu", compute_type or "int8")]

    audio_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            audio_path = tf.name
        logger.info("Extracting audio for transcription: %s", video_path)
        _extract_audio(video_path, audio_path)

        last_exc = None
        for dev, ct in attempts:
            try:
                segs = _run_whisper(audio_path, model_size, dev, ct, language)
                logger.info("Transcribed %d segments (model=%s, device=%s/%s)",
                            len(segs), model_size, dev, ct)
                return segs
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Whisper failed on %s/%s: %s%s",
                    dev, ct, str(exc)[:200],
                    " — retrying on CPU" if dev == "cuda" else "",
                )
        logger.warning("Transcription failed on all devices: %s", last_exc)
        return []
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass


def transcribe(
    video_path: str,
    model_size: str = "base",
    device: str = "cpu",
    language: str = "",
    compute_type: str = "",
) -> list[WordTimestamp]:
    """Word-level timestamps for the audio track (empty list on failure)."""
    segs = _transcribe_attempts(video_path, model_size, device, language, compute_type)
    words: list[WordTimestamp] = []
    for seg in segs:
        for w in (seg.words or []):
            words.append(WordTimestamp(word=w.word.strip(), start=float(w.start), end=float(w.end)))
    return words


def transcribe_segments(
    video_path: str,
    model_size: str = "base",
    device: str = "cpu",
    language: str = "",
    compute_type: str = "",
) -> list[dict]:
    """
    Segment-level transcript: [{start, end, text}] — ideal for TXT/SRT/VTT export.
    Works for both audio and video inputs. Empty list on failure.
    """
    segs = _transcribe_attempts(video_path, model_size, device, language, compute_type)
    out: list[dict] = []
    for s in segs:
        text = (s.text or "").strip()
        if text:
            out.append({"start": round(float(s.start), 3),
                        "end": round(float(s.end), 3),
                        "text": text})
    return out
