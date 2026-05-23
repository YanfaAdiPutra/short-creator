"""Build an ASS subtitle file with rolling-window karaoke highlights."""

from __future__ import annotations

from pathlib import Path

from ..config import SubtitleStyle
from ..models import Transcript, Word


def _format_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _ass_header(style: SubtitleStyle, output_width: int, output_height: int) -> str:
    margin_v = {
        "top": output_height - 200,
        "middle": output_height // 2,
        "bottom": 200,
    }.get(style.vertical_position, 200)

    alignment = {"top": 8, "middle": 5, "bottom": 2}.get(style.vertical_position, 2)

    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {output_width}\n"
        f"PlayResY: {output_height}\n"
        "ScaledBorderAndShadow: yes\n"
        "WrapStyle: 2\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{style.font_family},{style.font_size},{style.inactive_color},"
        f"{style.inactive_color},{style.outline_color},&H00000000,-1,0,0,0,100,100,0,0,1,"
        f"{style.outline_thickness},0,{alignment},80,80,{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _build_window_text(
    words: list[Word], active_index: int, active_color: str
) -> str:
    parts: list[str] = []
    for i, w in enumerate(words):
        clean = w.word.replace("{", "(").replace("}", ")")
        if i == active_index:
            parts.append(f"{{\\c{active_color}}}{clean}{{\\r}}")
        else:
            parts.append(clean)
    return " ".join(parts)


def _dialogue(start: float, end: float, text: str) -> str:
    return f"Dialogue: 0,{_format_time(start)},{_format_time(end)},Default,,0,0,0,,{text}\n"


def build_ass(
    transcript: Transcript,
    style: SubtitleStyle,
    *,
    output_width: int,
    output_height: int,
    clip_start: float = 0.0,
    clip_end: float | None = None,
) -> str:
    """Render the full ASS file as a string.

    Generates one Dialogue event per spoken word. Each event shows a rolling
    window of `style.window_size` words centered (lopsided right) on the active
    word, with the active word highlighted via inline color override.

    Times are normalized so that `clip_start` becomes t=0 in the output.
    """
    all_words = [w for w in transcript.words if w.word.strip()]
    if not all_words:
        return _ass_header(style, output_width, output_height)

    if clip_end is None:
        clip_end = transcript.duration

    # Restrict to words within the requested clip range
    words = [w for w in all_words if w.end > clip_start and w.start < clip_end]
    if not words:
        return _ass_header(style, output_width, output_height)

    window = max(1, style.window_size)
    body_lines: list[str] = []

    for i, active in enumerate(words):
        half = window // 2
        lo = max(0, i - half)
        hi = min(len(words), lo + window)
        lo = max(0, hi - window)
        window_words = words[lo:hi]
        active_index = i - lo

        line_start = max(clip_start, active.start) - clip_start
        line_end = max(clip_start, active.end) - clip_start
        if line_end <= line_start:
            continue

        text = _build_window_text(window_words, active_index, style.active_color)
        body_lines.append(_dialogue(line_start, line_end, text))

    return _ass_header(style, output_width, output_height) + "".join(body_lines)


def write_ass(
    transcript: Transcript,
    style: SubtitleStyle,
    out_path: Path,
    *,
    output_width: int,
    output_height: int,
    clip_start: float = 0.0,
    clip_end: float | None = None,
) -> Path:
    content = build_ass(
        transcript,
        style,
        output_width=output_width,
        output_height=output_height,
        clip_start=clip_start,
        clip_end=clip_end,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path
