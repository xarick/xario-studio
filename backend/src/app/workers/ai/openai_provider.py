import json
import logging
import re
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _chat(self, system: str, user: str, max_tokens: int = 512) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            # Disable thinking mode for qwen3 — thinking tokens eat max_tokens budget
            # and Ollama returns empty content when the budget runs out mid-think.
            extra_body={"think": False},
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            # Fallback: merge into single user message (some model/version combos
            # ignore system role via the OpenAI-compatible endpoint)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": f"{system}\n\n{user}"}],
                temperature=0.3,
                max_tokens=max_tokens,
                extra_body={"think": False},
            )
            content = (response.choices[0].message.content or "").strip()
        return content

    def _extract_json(self, text: str) -> Any:
        """Extract first JSON value (array or object) from text."""
        m = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if m:
            return json.loads(m.group())
        return json.loads(text)

    def suggest_shorts_count(self, duration: float, context: str = "") -> tuple[int, str]:
        """Suggest how many shorts to create."""
        system = (
            "You are a social media video editor. "
            "Respond ONLY with valid JSON — no explanation, no markdown."
        )
        user = (
            f"Video duration: {duration:.0f} seconds ({duration/60:.1f} minutes).\n"
            f"Content:\n{context or 'No context.'}\n\n"
            f"How many 30-60 second highlight shorts can be meaningfully extracted?\n"
            f"Consider: distinct topics, key moments, quotable segments.\n"
            f"Maximum suggested: 10. Minimum: 1.\n\n"
            f'Return ONLY JSON: {{"count": N, "reason": "one sentence explanation"}}'
        )
        try:
            raw = self._chat(system, user, max_tokens=256)
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
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
        system = ("You are a professional subtitle translator. "
                  "Respond ONLY with a valid JSON array of strings — no markdown, no commentary.")
        try:
            raw = self._chat(system, build_translate_prompt(texts, target_lang, source_lang),
                             max_tokens=max(512, len(texts) * 80))
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            return coerce_translations(self._extract_json(raw), texts)
        except Exception as exc:
            logger.warning("translate_batch failed (%s) — keeping source text", exc)
            return list(texts)

    def find_key_segments(
        self,
        duration: float,
        count: int,
        min_duration: int,
        max_duration: int = 60,
        context: str = "",
    ) -> list[list[tuple[float, float]]]:
        """Return `count` compilations, each assembled from clips at different timestamps."""

        system = (
            "You are an expert video editor creating social media shorts. "
            "Respond ONLY with a valid JSON array — no explanation, no markdown."
        )
        user = (
            f"Video duration: {duration:.1f} seconds.\n"
            f"Create exactly {count} shorts, each assembled from multiple clips at DIFFERENT timestamps.\n\n"
            f"Rules:\n"
            f"- Each short: total clip duration between {min_duration}s and {max_duration}s\n"
            f"- Each short: use 2-4 clips from different parts of the video\n"
            f"- Clips must NOT overlap across ALL shorts\n"
            f"- Individual clip: 5–25 seconds\n"
            f"- All timestamps within 0–{duration:.1f}s\n"
            f"- Clips within a short should be thematically related\n\n"
            f"Video content:\n{context or 'No additional context provided.'}\n\n"
            f"Return ONLY a JSON array of {count} shorts.\n"
            f"Each short is an array of clip objects with 'start' and 'end' in seconds.\n"
            f"Example for 2 shorts:\n"
            f'[[{{"start":5,"end":20}},{{"start":120,"end":140}}],[{{"start":45,"end":60}},{{"start":200,"end":225}}]]'
        )

        try:
            raw = self._chat(system, user, max_tokens=1024)
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
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
