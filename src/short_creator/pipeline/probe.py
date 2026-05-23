"""Probe a video file for width/height/duration/fps via ffprobe."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import VideoMeta
from ..platform_compat.ffmpeg_locator import ffprobe_path
from ..platform_compat.proc import run


def probe(video_path: Path | str) -> VideoMeta:
    path = str(video_path)
    cmd = [
        ffprobe_path(),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    result = run(cmd, capture=True)
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise ValueError("No video stream found")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    width = int(video_stream["width"])
    height = int(video_stream["height"])
    duration = float(data.get("format", {}).get("duration", 0.0))

    fps_raw = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1"
    try:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    return VideoMeta(
        width=width,
        height=height,
        duration=duration,
        fps=round(fps, 3),
        has_audio=has_audio,
        title=data.get("format", {}).get("tags", {}).get("title"),
    )
