"""Download a YouTube video via yt_dlp."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yt_dlp

ProgressCallback = Callable[[float, str], None]


def download(url: str, out_path: Path, on_progress: ProgressCallback | None = None) -> Path:
    """Download `url` to `out_path` (an .mp4) at the best available quality.

    Calls `on_progress(percent_0_to_100, message)` if provided.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _hook(d: dict[str, Any]) -> None:
        if not on_progress:
            return
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = (downloaded / total * 100) if total else 0.0
            speed = d.get("speed") or 0
            mbps = (speed / 1_000_000) if speed else 0
            on_progress(pct, f"Downloading… {mbps:.1f} MB/s")
        elif d.get("status") == "finished":
            on_progress(100.0, "Download complete, merging streams…")

    opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(out_path.with_suffix("")) + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "progress_hooks": [_hook],
        "concurrent_fragment_downloads": 4,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # yt_dlp may have produced a file with a different extension; locate it.
    base = out_path.with_suffix("")
    for ext in ("mp4", "mkv", "webm"):
        candidate = Path(str(base) + "." + ext)
        if candidate.exists():
            if candidate != out_path:
                candidate.rename(out_path)
            break
    else:
        raise FileNotFoundError(f"yt_dlp finished but no output found at {out_path}")

    return out_path


def get_metadata(url: str) -> dict[str, Any]:
    """Fetch video metadata without downloading."""
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        return ydl.extract_info(url, download=False)
