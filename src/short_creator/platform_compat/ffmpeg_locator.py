"""Locate ffmpeg / ffprobe on the host system."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


def _which(name: str) -> str | None:
    found = shutil.which(name)
    return found if found else None


@lru_cache(maxsize=1)
def ffmpeg_path() -> str:
    override = os.environ.get("SHORT_FFMPEG")
    if override and Path(override).exists():
        return override
    binary = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    located = _which(binary) or _which("ffmpeg")
    if not located:
        raise FileNotFoundError(
            "ffmpeg not found. Install it (https://ffmpeg.org/download.html) "
            "and ensure it is on PATH, or set SHORT_FFMPEG to its absolute path."
        )
    return located


@lru_cache(maxsize=1)
def ffprobe_path() -> str:
    override = os.environ.get("SHORT_FFPROBE")
    if override and Path(override).exists():
        return override
    binary = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    located = _which(binary) or _which("ffprobe")
    if not located:
        raise FileNotFoundError(
            "ffprobe not found. It ships with ffmpeg — install ffmpeg or set SHORT_FFPROBE."
        )
    return located


@lru_cache(maxsize=1)
def has_nvenc() -> bool:
    """Return True if ffmpeg reports an h264_nvenc encoder."""
    try:
        result = subprocess.run(
            [ffmpeg_path(), "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=_no_window_flags(),
        )
        return "h264_nvenc" in result.stdout
    except Exception:
        return False


def _no_window_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def pick_encoder(preferred: str = "auto") -> str:
    """Resolve 'auto' to a concrete ffmpeg encoder name."""
    if preferred != "auto":
        return preferred
    if has_nvenc():
        return "h264_nvenc"
    return "libx264"
