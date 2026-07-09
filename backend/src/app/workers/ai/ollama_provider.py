"""
Ollama provider — uses the native Ollama API (/api/chat).
Supports think=False for qwen3 and other reasoning models.
"""
import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434"
_TIMEOUT = 120


class OllamaProvider:
    def __init__(self, model: str = "llama3.1:8b", base_url: str | None = None) -> None:
        self.model = model
        self.base_url = (base_url or _DEFAULT_BASE_URL).removesuffix("/v1").rstrip("/")

    def _chat(self, prompt: str, max_tokens: int = 1024, keep_alive: str | int | None = None) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.3, "num_predict": max_tokens},
        }
        # keep_alive=0 unloads the model from the GPU right after responding — used
        # by dubbing so XTTS can claim the VRAM instead of OOM'ing behind the LLM.
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        raw = (resp.json()["message"]["content"] or "").strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return raw

    def _extract_json(self, text: str) -> Any:
        """Extract first JSON value (array or object) from text."""
        m = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if m:
            return json.loads(m.group())
        return json.loads(text)

    def suggest_shorts_count(self, duration: float, context: str = "") -> tuple[int, str]:
        """Suggest how many shorts to create."""
        prompt = (
            f"You are a social media video editor.\n"
            f"Video duration: {duration:.0f} seconds ({duration/60:.1f} minutes).\n"
            f"Content:\n{context or 'No context.'}\n\n"
            f"How many 30-60 second highlight shorts can be meaningfully extracted?\n"
            f"Consider: distinct topics, key moments, quotable segments.\n"
            f"Maximum suggested: 10. Minimum: 1.\n\n"
            f'Return ONLY JSON: {{"count": N, "reason": "one sentence explanation"}}'
        )
        try:
            raw = self._chat(prompt, max_tokens=256)
            data = self._extract_json(raw)
            count = max(1, min(10, int(data["count"])))
            reason = str(data.get("reason", ""))
            return count, reason
        except Exception as exc:
            logger.warning("suggest_shorts_count failed: %s", exc)
            default = max(1, min(10, int(duration // 60)))
            return default, "Tavsiya hisoblashda xato yuz berdi."

    def translate_batch(
        self, texts: list[str], target_lang: str, source_lang: str | None = None,
    ) -> list[str]:
        from app.workers.ai.base import build_translate_prompt, coerce_translations
        if not texts:
            return []
        try:
            raw = self._chat(build_translate_prompt(texts, target_lang, source_lang),
                             max_tokens=max(512, len(texts) * 80), keep_alive=0)
            return coerce_translations(self._extract_json(raw), texts)
        except Exception as exc:
            logger.warning("translate_batch failed (%s) — keeping source text", exc)
            return list(texts)

    def find_key_segments(
        self,
        duration: float,
        count: int,
        min_duration: int = 30,
        max_duration: int = 60,
        context: str = "",
    ) -> list[list[tuple[float, float]]]:
        """
        Return `count` compilations, each assembled from clips at different timestamps.
        Each compilation's total duration is between min_duration and max_duration seconds.
        """
        prompt = (
            f"You are an expert video editor creating social media shorts.\n"
            f"Video duration: {duration:.1f} seconds.\n"
            f"Create exactly {count} shorts, each assembled from multiple clips at DIFFERENT timestamps.\n\n"
            f"Rules:\n"
            f"- Each short: total clip duration between {min_duration}s and {max_duration}s\n"
            f"- Each short: use 2-4 clips from different parts of the video\n"
            f"- Clips must NOT overlap across ALL shorts\n"
            f"- Individual clip: 5–25 seconds\n"
            f"- All timestamps within 0–{duration:.1f}s\n"
            f"- Clips within a short should be thematically related\n\n"
            f"Video content:\n{context or 'No context provided.'}\n\n"
            f"Return ONLY a JSON array of {count} shorts.\n"
            f"Each short is an array of clip objects with 'start' and 'end' in seconds.\n"
            f"Example for 2 shorts:\n"
            f'[[{{"start":5,"end":20}},{{"start":120,"end":140}}],[{{"start":45,"end":60}},{{"start":200,"end":225}}]]'
        )

        try:
            raw = self._chat(prompt, max_tokens=1024)
            parsed = self._extract_json(raw)

            if not isinstance(parsed, list) or len(parsed) == 0:
                raise ValueError("Expected non-empty array")

            result = []
            used_intervals: list[tuple[float, float]] = []

            for short_clips in parsed[:count]:
                if not isinstance(short_clips, list):
                    continue
                clips = []
                total = 0.0
                for clip in short_clips:
                    s = float(clip["start"])
                    e = float(clip["end"])
                    dur = e - s
                    if dur < 4 or dur > 30:
                        continue
                    if s < 0 or e > duration + 1:
                        continue
                    # skip overlaps with already-used intervals
                    if any(not (e <= us or s >= ue) for us, ue in used_intervals):
                        continue
                    clips.append((round(s, 2), round(min(e, duration), 2)))
                    used_intervals.append((s, e))
                    total += dur

                if min_duration <= total <= max_duration and len(clips) >= 1:
                    result.append(clips)

            if len(result) == count:
                return result

            logger.warning("AI returned %d valid shorts (expected %d), using fallback", len(result), count)
        except Exception as exc:
            logger.warning("AI compilation failed (%s), using fallback", exc)

        return _equal_split_compilations(duration, count, min_duration, max_duration)


def _equal_split_compilations(
    duration: float, count: int, min_dur: int, max_dur: int
) -> list[list[tuple[float, float]]]:
    """Fallback: 2 clips per short evenly distributed."""
    seg = min(duration / (count * 2), max_dur / 2)
    result = []
    for i in range(count):
        base = i * (duration / count)
        mid = base + duration / count / 2
        c1 = (round(base, 2), round(base + seg, 2))
        c2 = (round(mid, 2), round(mid + seg, 2))
        result.append([c1, c2])
    return result
