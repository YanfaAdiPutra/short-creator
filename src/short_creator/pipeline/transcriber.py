"""Transcription via faster-whisper with word-level timestamps."""

from __future__ import annotations

import gc
from collections.abc import Callable
from pathlib import Path

from ..config import TranscriptionConfig
from ..models import Transcript, TranscriptSegment, Word

ProgressCallback = Callable[[float, str], None]


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def transcribe(
    audio_or_video: Path,
    cfg: TranscriptionConfig,
    on_progress: ProgressCallback | None = None,
) -> Transcript:
    """Run faster-whisper on the given file and return a Transcript."""
    from faster_whisper import WhisperModel  # heavy import; lazy

    device = _resolve_device(cfg.device)
    compute_type = cfg.quantization

    if on_progress:
        on_progress(0.0, f"Loading Whisper {cfg.model} ({compute_type}, {device})")

    model = WhisperModel(cfg.model, device=device, compute_type=compute_type)

    if on_progress:
        on_progress(5.0, "Transcribing audio…")

    segments_iter, info = model.transcribe(
        str(audio_or_video),
        language=cfg.language,
        word_timestamps=True,
        vad_filter=True,
    )

    duration = info.duration or 0.0
    segments: list[TranscriptSegment] = []
    for seg in segments_iter:
        words: list[Word] = []
        for w in (seg.words or []):
            if w.start is None or w.end is None or not (w.word or "").strip():
                continue
            words.append(Word(word=w.word.strip(), start=float(w.start), end=float(w.end)))
        segments.append(
            TranscriptSegment(
                start=float(seg.start),
                end=float(seg.end),
                text=seg.text.strip(),
                words=words,
            )
        )
        if on_progress and duration > 0:
            pct = min(99.0, 5.0 + (seg.end / duration) * 94.0)
            on_progress(pct, f"Transcribed up to {seg.end:.1f}s / {duration:.1f}s")

    # Free VRAM aggressively so later stages (NVENC compose) can use it.
    del model
    gc.collect()
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    if on_progress:
        on_progress(100.0, "Transcription complete")

    return Transcript(
        language=info.language,
        duration=duration,
        segments=segments,
    )
