"""
AI provider protocol.
Swap providers by changing AI_PROVIDER in .env — no code changes needed.
"""
import json
from typing import Protocol, runtime_checkable

_LANG_NAMES = {
    "uz": "Uzbek", "ru": "Russian", "en": "English", "tr": "Turkish",
    "de": "German", "es": "Spanish", "fr": "French", "it": "Italian",
    "pt": "Portuguese", "ar": "Arabic",
}


def lang_name(code: str | None) -> str:
    return _LANG_NAMES.get((code or "").lower(), code or "the target language")


def build_translate_prompt(texts: list[str], target_lang: str, source_lang: str | None = None) -> str:
    """A numbered-lines → JSON-array translation prompt, order/count preserved."""
    src = f" from {lang_name(source_lang)}" if source_lang else ""
    lines = json.dumps(texts, ensure_ascii=False)
    return (
        f"Translate each line{src} into {lang_name(target_lang)}.\n"
        f"You are given a JSON array of {len(texts)} strings.\n"
        f"Return ONLY a JSON array of exactly {len(texts)} strings — the translations "
        f"in the SAME order. Do not merge, split, reorder, or add lines. Keep it natural "
        f"and spoken; translate names phonetically only if natural.\n\n"
        f"Input:\n{lines}"
    )


def coerce_translations(parsed, texts: list[str]) -> list[str]:
    """Force the model output into a same-length list of strings (fallback: original)."""
    if not isinstance(parsed, list):
        return list(texts)
    out = [str(x).strip() if x is not None else "" for x in parsed]
    if len(out) < len(texts):
        out += texts[len(out):]
    elif len(out) > len(texts):
        out = out[:len(texts)]
    # Replace empties with the original line so a segment is never silently dropped.
    return [o or t for o, t in zip(out, texts)]


@runtime_checkable
class AIProvider(Protocol):
    def find_key_segments(
        self,
        duration: float,
        count: int,
        min_duration: int,
        max_duration: int,
        context: str,
    ) -> list[list[tuple[float, float]]]:
        """
        Return a list of `count` compilations.
        Each compilation is a list of (start_sec, end_sec) clips from different timestamps.
        Total duration of clips in each compilation must be between min_duration and max_duration.
        """
        ...

    def suggest_shorts_count(self, duration: float, context: str) -> tuple[int, str]:
        """
        Suggest how many shorts to create from this video.
        Returns (count, reason_string).
        """
        ...

    def translate_batch(
        self,
        texts: list[str],
        target_lang: str,
        source_lang: str | None = None,
    ) -> list[str]:
        """
        Translate `texts` into `target_lang`, preserving order and count.
        Returns a list of the same length (falls back to the original on failure).
        """
        ...
