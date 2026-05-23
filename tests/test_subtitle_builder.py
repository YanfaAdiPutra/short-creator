"""Tests for the subtitle builder."""

from __future__ import annotations

from short_creator.config import SubtitleStyle
from short_creator.models import Transcript, TranscriptSegment, Word
from short_creator.pipeline.subtitle_builder import build_ass


def _sample_transcript() -> Transcript:
    words = [
        Word(word="hello", start=0.0, end=0.5),
        Word(word="world", start=0.5, end=1.0),
        Word(word="this", start=1.0, end=1.3),
        Word(word="is", start=1.3, end=1.5),
        Word(word="a", start=1.5, end=1.7),
        Word(word="test", start=1.7, end=2.2),
    ]
    return Transcript(
        language="en",
        duration=2.2,
        segments=[
            TranscriptSegment(start=0.0, end=2.2, text="hello world this is a test", words=words),
        ],
    )


def test_ass_contains_header_and_one_dialogue_per_word():
    style = SubtitleStyle(window_size=3)
    ass = build_ass(_sample_transcript(), style, output_width=1080, output_height=1920)
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass
    dialogues = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogues) == 6  # one per word


def test_window_size_limits_words_per_line():
    style = SubtitleStyle(window_size=3)
    ass = build_ass(_sample_transcript(), style, output_width=1080, output_height=1920)
    dialogues = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    # Each dialogue text should contain at most 3 visible words (ignoring tags)
    for line in dialogues:
        text = line.split(",,", 1)[-1]
        # strip ASS overrides {...}
        import re

        stripped = re.sub(r"\{[^}]*\}", "", text).strip()
        words = [w for w in stripped.split(" ") if w]
        assert len(words) <= 3


def test_clip_range_normalizes_timestamps_to_zero():
    style = SubtitleStyle(window_size=4)
    ass = build_ass(
        _sample_transcript(),
        style,
        output_width=1080,
        output_height=1920,
        clip_start=1.0,
        clip_end=2.2,
    )
    # First dialogue line should start at or after t=0 (since we shift by clip_start)
    dialogues = [line for line in ass.splitlines() if line.startswith("Dialogue:")]
    assert dialogues
    first = dialogues[0]
    # Format: Dialogue: 0,H:MM:SS.cc,H:MM:SS.cc,...
    start_field = first.split(",")[1]
    h, m, s = start_field.split(":")
    seconds = int(h) * 3600 + int(m) * 60 + float(s)
    assert seconds < 0.1  # first word starts close to t=0 after the shift
