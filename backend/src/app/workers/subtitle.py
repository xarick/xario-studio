"""
Generate viral-style ASS subtitles from word timestamps.

Two styles:
  * "karaoke" — words light up one-by-one exactly in sync with the speech
                (ASS \\k tags). Upcoming words are dimmed, spoken words pop to
                solid white. This is the modern "TikTok caption" look.
  * "plain"   — a static line shown for its whole duration.

Optimised for 9:16 portrait (1080 × 1920). Subtitles sit in the lower third,
big and bold with a heavy outline so they stay readable over any footage.
"""
import logging
import os
import shutil
import subprocess
import tempfile

from app.workers.transcriber import WordTimestamp

logger = logging.getLogger(__name__)

WORDS_PER_LINE = 4

# ASS colours are &HAABBGGRR (alpha, blue, green, red).
_PRIMARY = "&H00FFFFFF"   # spoken / past words  → solid white
_SECONDARY = "&H64FFFFFF"  # upcoming words        → ~40% transparent white
_OUTLINE = "&H00101010"   # near-black outline
_SHADOW = "&H80000000"    # soft shadow

def _make_header(play_w: int = 1080, play_h: int = 1920) -> str:
    """ASS header with style scaled to the target frame (1920px tall = baseline)."""
    s = play_h / 1920.0
    font = max(22, round(88 * s))
    outline = max(2, round(5 * s))
    shadow = max(1, round(3 * s))
    margin_v = round(330 * s)
    margin_lr = round(80 * s)
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        f"PlayResX: {play_w}\n"
        f"PlayResY: {play_h}\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{font},{_PRIMARY},{_SECONDARY},{_OUTLINE},{_SHADOW},"
        f"-1,0,0,0,100,100,1,0,1,{outline},{shadow},2,{margin_lr},{margin_lr},{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _ts(seconds: float) -> str:
    """Format seconds → ASS timestamp H:MM:SS.cc"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    if cs == 100:  # rounding overflow
        s, cs = s + 1, 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(word: str) -> str:
    """Strip ASS control characters from a word."""
    return word.replace("{", "").replace("}", "").replace("\\", "").strip()


def _collect_words(
    word_timestamps: list[WordTimestamp],
    clips: list[tuple[float, float]],
) -> list[tuple[float, float, str]]:
    """
    Map words that fall inside `clips` onto the output (concatenated) timeline.
    Clips are concatenated in order, so each clip's words are shifted by the
    cumulative duration of the clips before it.
    """
    out: list[tuple[float, float, str]] = []
    offset = 0.0
    for clip_start, clip_end in clips:
        for w in word_timestamps:
            if w.start >= clip_start and w.end <= clip_end + 0.05:
                text = _clean(w.word)
                if text:
                    out.append((
                        offset + (w.start - clip_start),
                        offset + (w.end - clip_start),
                        text,
                    ))
        offset += clip_end - clip_start
    return out


def _karaoke_line(group: list[tuple[float, float, str]]) -> str:
    """Build a karaoke-timed Dialogue body for one line of words."""
    line_start = group[0][0]
    body = ""
    prev_end = line_start
    for ws, we, word in group:
        gap_cs = int(round((ws - prev_end) * 100))
        if gap_cs > 0:
            body += f"{{\\k{gap_cs}}} "          # silence spacer
        dur_cs = max(1, int(round((we - ws) * 100)))
        body += f"{{\\k{dur_cs}}}{word} "
        prev_end = we
    return body.strip()


def build_ass_for_clips(
    word_timestamps: list[WordTimestamp],
    clips: list[tuple[float, float]],
    words_per_line: int = WORDS_PER_LINE,
    style: str = "karaoke",
    play_w: int = 1080,
    play_h: int = 1920,
) -> str:
    """
    Build ASS subtitle content for a short composed of `clips`.
    `play_w`/`play_h` size the style to the target frame (default 9:16 short).
    Returns "" if no words fall inside the clips.
    """
    words = _collect_words(word_timestamps, clips)
    if not words:
        return ""

    events = ""
    for i in range(0, len(words), words_per_line):
        group = words[i : i + words_per_line]
        line_start = group[0][0]
        line_end = group[-1][1]
        # Avoid overlapping the next line.
        if i + words_per_line < len(words):
            line_end = min(line_end, words[i + words_per_line][0] - 0.02)
        if line_end <= line_start:
            line_end = line_start + 0.4

        if style == "karaoke":
            text = _karaoke_line(group)
        else:
            text = " ".join(w for _, _, w in group)

        if text:
            events += f"Dialogue: 0,{_ts(line_start)},{_ts(line_end)},Default,,0,0,0,,{text}\n"

    return (_make_header(play_w, play_h) + events) if events else ""


_TEXT_ALIGN = {"top": 8, "center": 5, "bottom": 2}


def _hex_to_ass_colour(hex_colour: str) -> str:
    """Convert a #RRGGBB (or RRGGBB) hex string to an opaque ASS &H00BBGGRR
    colour. Returns "" for empty/invalid input so the caller keeps its default."""
    if not hex_colour:
        return ""
    h = hex_colour.strip().lstrip("#")
    if len(h) != 6:
        return ""
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return ""
    return f"&H00{b:02X}{g:02X}{r:02X}"


def build_static_text_ass(
    text: str,
    duration: float,
    position: str = "bottom",
    play_w: int = 1080,
    play_h: int = 1920,
    color: str = "",
    font_scale: float = 1.0,
) -> str:
    """
    Build ASS for a single static text overlay shown for the whole clip.
    Used by the manual editor (montage) to burn a caption/title at the chosen
    position. `color` (#RRGGBB) and `font_scale` (0.5–2.0) style the text;
    defaults reproduce the original white caption. Returns "" when there's
    nothing to draw.
    """
    text = _clean(text)
    if not text or duration <= 0:
        return ""
    text = text.replace("\n", "\\N")  # honour user line breaks
    align = _TEXT_ALIGN.get(position, 2)
    primary = _hex_to_ass_colour(color) or _PRIMARY
    font_scale = max(0.5, min(2.0, float(font_scale)))

    s = (play_h / 1920.0) * font_scale
    font = max(20, round(72 * s))
    outline = max(2, round(5 * s))
    shadow = max(1, round(3 * s))
    margin_v = round(120 * s)
    margin_lr = round(70 * s)

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        f"PlayResX: {play_w}\n"
        f"PlayResY: {play_h}\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{font},{primary},{_SECONDARY},{_OUTLINE},{_SHADOW},"
        f"-1,0,0,0,100,100,1,0,1,{outline},{shadow},{align},{margin_lr},{margin_lr},{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    body = f"Dialogue: 0,{_ts(0.0)},{_ts(duration)},Default,,0,0,0,,{text}\n"
    return header + body


def build_multi_text_ass(
    texts: list[dict],
    play_w: int = 1080,
    play_h: int = 1920,
) -> str:
    """
    Build ASS for several independent text overlays, each shown over its own
    [start, end] window with its own position / colour / size. Used by the pro
    editor where the user adds captions at specific moments of the montage.

    Each item: {text, start, end, position(top|center|bottom), color(#RRGGBB),
    scale(0.5–2.0)}. Returns "" when nothing is drawable.
    """
    items = []
    for it in texts or []:
        txt = _clean(str(it.get("text", "")))
        if not txt:
            continue
        try:
            start = float(it.get("start", 0.0))
            end = float(it.get("end", 0.0))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        items.append({
            "text": txt.replace("\n", "\\N"),
            "start": start,
            "end": end,
            "position": it.get("position", "bottom"),
            "color": it.get("color", ""),
            "scale": it.get("scale", 1.0),
        })
    if not items:
        return ""

    s = play_h / 1920.0
    base_font = 72 * s
    outline = max(2, round(5 * s))
    shadow = max(1, round(3 * s))
    margin_v = round(120 * s)
    margin_lr = round(70 * s)

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        f"PlayResX: {play_w}\n"
        f"PlayResY: {play_h}\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{round(base_font)},{_PRIMARY},{_SECONDARY},{_OUTLINE},{_SHADOW},"
        f"-1,0,0,0,100,100,1,0,1,{outline},{shadow},2,{margin_lr},{margin_lr},{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    body = ""
    for it in items:
        align = _TEXT_ALIGN.get(it["position"], 2)
        try:
            scale = max(0.5, min(2.0, float(it["scale"])))
        except (TypeError, ValueError):
            scale = 1.0
        fs = max(20, round(base_font * scale))
        override = f"\\an{align}\\fs{fs}"
        colour = _hex_to_ass_colour(it["color"])
        if colour:
            override += f"\\c{colour}"
        body += (
            f"Dialogue: 0,{_ts(it['start'])},{_ts(it['end'])},Default,,0,0,0,,"
            f"{{{override}}}{it['text']}\n"
        )
    return header + body


def write_temp_ass(ass_content: str) -> str:
    """Write ASS content to a temp .ass file and return its path."""
    with tempfile.NamedTemporaryFile(
        suffix=".ass", mode="w", encoding="utf-8", delete=False
    ) as tf:
        tf.write(ass_content)
        return tf.name


def burn_subtitles(input_path: str, output_path: str, ass_content: str) -> None:
    """
    Standalone re-encode that burns ASS subtitles into an existing video.
    Kept as a fallback; the main pipeline burns subtitles in the cutting pass.
    If ass_content is empty the file is copied unchanged.
    """
    if not ass_content.strip():
        if input_path != output_path:
            shutil.copy2(input_path, output_path)
        return

    ass_file = ""
    tmp_out = output_path + ".subtmp.mp4"
    try:
        ass_file = write_temp_ass(ass_content)
        escaped = ass_file.replace("\\", "/")
        if ":" in escaped:
            drive, rest = escaped.split(":", 1)
            escaped = drive + "\\:" + rest

        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", input_path,
                "-vf", f"ass={escaped}",
                "-c:v", "libx264", "-preset", "fast",
                "-c:a", "copy", "-movflags", "+faststart",
                tmp_out,
            ],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            logger.warning("Subtitle burn failed: %s", result.stderr[-500:])
            if input_path != output_path:
                shutil.copy2(input_path, output_path)
        else:
            os.replace(tmp_out, output_path)
    except Exception as exc:
        logger.warning("burn_subtitles error: %s", exc)
        if input_path != output_path and not os.path.exists(output_path):
            try:
                shutil.copy2(input_path, output_path)
            except OSError:
                pass
    finally:
        for p in (ass_file, tmp_out):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
