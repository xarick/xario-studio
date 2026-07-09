"""
Google Gemini provider.
Install: uv add google-generativeai
"""
import json
import logging
import re

logger = logging.getLogger(__name__)


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", base_url: str | None = None) -> None:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._genai = genai
            self.model_name = model
        except ImportError:
            raise RuntimeError("google-generativeai not installed. Run: uv add google-generativeai")

    def _generate(self, prompt: str) -> str:
        model = self._genai.GenerativeModel(self.model_name)
        response = model.generate_content(prompt)
        return response.text.strip()

    def translate_batch(
        self, texts: list[str], target_lang: str, source_lang: str | None = None,
    ) -> list[str]:
        from app.workers.ai.base import build_translate_prompt, coerce_translations
        if not texts:
            return []
        try:
            raw = self._generate(build_translate_prompt(texts, target_lang, source_lang))
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            parsed = json.loads(m.group() if m else raw)
            return coerce_translations(parsed, texts)
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
    ) -> list[tuple[float, float]]:
        prompt = (
            f"You are an expert video editor. Video duration: {duration:.1f}s.\n"
            f"Find exactly {count} most engaging segments, each at least {min_duration}s long.\n"
            f"Segments must not overlap and stay within 0–{duration:.1f}s.\n"
            f"Content:\n{context or 'No context provided.'}\n\n"
            f"Return ONLY a JSON array of {count} objects with \"start\" and \"end\" in seconds. "
            f"No explanation."
        )
        try:
            raw = self._generate(prompt)
            parsed = json.loads(raw) if raw.startswith("[") else json.loads(
                re.search(r"\[.*\]", raw, re.DOTALL).group()  # type: ignore[union-attr]
            )
            segments = []
            for item in parsed[:count]:
                s, e = float(item["start"]), float(item["end"])
                if e - s >= min_duration and s >= 0 and e <= duration + 1:
                    segments.append((round(s, 2), round(min(e, duration), 2)))
            if len(segments) == count:
                return segments
        except Exception as exc:
            logger.warning("Gemini segment detection failed: %s", exc)

        seg = duration / count
        return [(round(i * seg, 2), round(min((i + 1) * seg, duration), 2)) for i in range(count)]
