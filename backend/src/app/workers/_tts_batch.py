"""
XTTS-v2 batch synthesis worker — invoked as a subprocess:

    python -m app.workers._tts_batch <job.json>

Loads the (~1.8 GB) model ONCE and synthesises every text in the job, so dubbing
a video with many segments doesn't reload the model per line. Kept in its own
process so torch / transformers never import into the web app.

Job JSON: {model, device, language, voice, speaker_wav?, texts:[...],
           out_dir, result_path}
Writes seg_<i>.wav for each text and a result JSON {"wavs": [path|null, ...]}.
"""
import json
import os
import sys


def _is_oom(exc: Exception) -> bool:
    return "out of memory" in str(exc).lower() or exc.__class__.__name__ == "OutOfMemoryError"


def _run(job: dict, device: str) -> list:
    """Load XTTS on `device` and synthesise every line. Raises on a load/OOM error."""
    from TTS.api import TTS
    tts = TTS(job["model"]).to(device)

    speaker_wav = job.get("speaker_wav") or None
    voice = job.get("voice") or "Ana Florence"
    language = job["language"]

    wavs: list = []
    for i, text in enumerate(job["texts"]):
        text = (text or "").strip()
        out = os.path.join(job["out_dir"], f"seg_{i}.wav")
        if not text:
            wavs.append(None)
            continue
        kwargs = {"text": text, "language": language, "file_path": out}
        if speaker_wav:
            kwargs["speaker_wav"] = speaker_wav
        else:
            kwargs["speaker"] = voice
        try:
            tts.tts_to_file(**kwargs)
            wavs.append(out if os.path.exists(out) else None)
        except Exception as exc:
            if _is_oom(exc):
                raise   # bubble up so the whole batch retries on CPU
            sys.stderr.write(f"[tts_batch] segment {i} failed: {exc}\n")
            wavs.append(None)
    return wavs


def main(job_path: str) -> None:
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)

    os.environ.setdefault("COQUI_TOS_AGREED", "1")
    os.makedirs(job["out_dir"], exist_ok=True)

    device = job["device"]
    try:
        wavs = _run(job, device)
    except Exception as exc:
        # GPU contention (e.g. an LLM still resident) → fall back to CPU so the
        # job still completes, just slower. Mirrors the whisper CPU fallback.
        if device == "cuda" and _is_oom(exc):
            sys.stderr.write(f"[tts_batch] CUDA OOM ({exc}); retrying on CPU\n")
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
            wavs = _run(job, "cpu")
        else:
            raise

    with open(job["result_path"], "w", encoding="utf-8") as f:
        json.dump({"wavs": wavs}, f)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("usage: python -m app.workers._tts_batch <job.json>\n")
        sys.exit(2)
    main(sys.argv[1])
