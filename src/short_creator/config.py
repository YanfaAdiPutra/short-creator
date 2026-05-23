"""Application configuration and default settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "short"
APP_AUTHOR = "short-creator"


def data_root() -> Path:
    """Return the cross-platform data directory for project storage."""
    override = os.environ.get("SHORT_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def projects_dir() -> Path:
    p = data_root() / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class TranscriptionConfig:
    model: str = "medium"
    quantization: str = "int8"
    device: str = "auto"          # auto | cuda | cpu
    language: str | None = None   # None → auto-detect


@dataclass
class RecommenderConfig:
    provider: str = "anthropic"   # anthropic | openai | ollama
    model: str = "claude-haiku-4-5-20251001"
    min_clip_seconds: int = 15
    max_clip_seconds: int = 90
    max_clips: int = 10


@dataclass
class ComposeConfig:
    encoder: str = "auto"         # auto | h264_nvenc | libx264
    nvenc_preset: str = "p5"
    nvenc_cq: int = 20
    libx264_crf: int = 18
    libx264_preset: str = "fast"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    output_width: int = 1080
    output_height: int = 1920


@dataclass
class SubtitleStyle:
    font_family: str = "Arial Black"
    font_size: int = 72
    window_size: int = 4                # words visible at once
    active_color: str = "&H0000FFFF&"   # ASS color (yellow, BGR + alpha)
    inactive_color: str = "&H00FFFFFF&" # white
    outline_color: str = "&H00000000&"  # black
    outline_thickness: int = 4
    vertical_position: str = "bottom"   # top | middle | bottom


@dataclass
class AppConfig:
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    recommender: RecommenderConfig = field(default_factory=RecommenderConfig)
    compose: ComposeConfig = field(default_factory=ComposeConfig)
    subtitle_style: SubtitleStyle = field(default_factory=SubtitleStyle)


DEFAULT_CONFIG = AppConfig()
