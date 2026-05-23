"""Final compose: segment-then-concat crop + subtitle burn-in."""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable
from pathlib import Path

from ..config import ComposeConfig
from ..models import CropPlan, Transcript
from ..platform_compat.ffmpeg_locator import ffmpeg_path, pick_encoder
from ..platform_compat.proc import run, stream

ProgressCallback = Callable[[float, str], None]


def _encoder_args(encoder: str, cfg: ComposeConfig) -> list[str]:
    if encoder == "h264_nvenc":
        return [
            "-c:v", "h264_nvenc",
            "-preset", cfg.nvenc_preset,
            "-rc", "vbr",
            "-cq", str(cfg.nvenc_cq),
            "-b:v", "0",
        ]
    return [
        "-c:v", "libx264",
        "-preset", cfg.libx264_preset,
        "-crf", str(cfg.libx264_crf),
    ]


def _ffmpeg_path_escape_for_filter(p: Path) -> str:
    """Escape a path for use inside an ffmpeg filter argument.

    On Windows, ffmpeg filters require backslashes escaped and the colon after
    a drive letter (``C:``) to be escaped as ``C\\:``.
    """
    s = str(p).replace("\\", "/")
    # Escape Windows-style ``C:`` so ffmpeg doesn't treat it as a filter delimiter
    s = re.sub(r"^([A-Za-z]):", r"\1\\:", s)
    s = s.replace("'", r"\'")
    return s


def _normalize_segments(plan: CropPlan, video_duration: float) -> list[tuple[float, float, int, int]]:
    out: list[tuple[float, float, int, int]] = []
    for seg in plan.segments:
        start = max(0.0, seg.start)
        end = min(video_duration, seg.end) if video_duration > 0 else seg.end
        if end <= start:
            continue
        out.append((start, end, seg.x, seg.y))
    return out


def crop_concat(
    source: Path,
    plan: CropPlan,
    out_path: Path,
    cfg: ComposeConfig,
    video_duration: float,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Cut each segment, apply its static crop, then concat all segments."""
    encoder = pick_encoder(cfg.encoder)
    segments = _normalize_segments(plan, video_duration)
    if not segments:
        raise ValueError("Crop plan has no usable segments")

    work_dir = out_path.parent / "_segments"
    work_dir.mkdir(parents=True, exist_ok=True)
    segment_files: list[Path] = []

    for i, (start, end, x, y) in enumerate(segments):
        seg_path = work_dir / f"seg_{i:03d}.mp4"
        segment_files.append(seg_path)
        if on_progress:
            on_progress(i / len(segments) * 50, f"Cropping segment {i + 1}/{len(segments)}")
        cmd = [
            ffmpeg_path(),
            "-y",
            "-hide_banner",
            "-loglevel", "warning",
            "-ss", f"{start:.3f}",
            "-to", f"{end:.3f}",
            "-i", str(source),
            "-vf",
            f"crop={plan.output_width}:{plan.output_height}:{x}:{y},"
            f"scale={cfg.output_width}:{cfg.output_height}:flags=lanczos,setsar=1",
            *_encoder_args(encoder, cfg),
            "-c:a", cfg.audio_codec, "-b:a", cfg.audio_bitrate,
            "-movflags", "+faststart",
            str(seg_path),
        ]
        run(cmd)

    # Build concat list file
    list_path = work_dir / "concat.txt"
    with list_path.open("w", encoding="utf-8") as f:
        for seg in segment_files:
            seg_str = str(seg).replace("\\", "/").replace("'", r"'\''")
            f.write(f"file '{seg_str}'\n")

    if on_progress:
        on_progress(55, "Concatenating segments…")

    concat_path = work_dir / "concat.mp4"
    run([
        ffmpeg_path(),
        "-y", "-hide_banner", "-loglevel", "warning",
        "-f", "concat", "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        str(concat_path),
    ])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    concat_path.replace(out_path)

    # Cleanup
    for seg in segment_files:
        seg.unlink(missing_ok=True)
    list_path.unlink(missing_ok=True)
    try:
        work_dir.rmdir()
    except OSError:
        pass

    if on_progress:
        on_progress(60, "Crop concat complete")
    return out_path


def burn_subtitles(
    cropped: Path,
    ass_path: Path,
    out_path: Path,
    cfg: ComposeConfig,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Burn an ASS subtitle file into the cropped video."""
    encoder = pick_encoder(cfg.encoder)
    if on_progress:
        on_progress(70, "Burning subtitles…")

    ass_arg = _ffmpeg_path_escape_for_filter(ass_path)

    cmd = [
        ffmpeg_path(),
        "-y", "-hide_banner", "-loglevel", "warning",
        "-i", str(cropped),
        "-vf", f"ass={ass_arg}",
        *_encoder_args(encoder, cfg),
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(out_path),
    ]
    run(cmd)
    if on_progress:
        on_progress(100, "Render complete")
    return out_path


def compose(
    source: Path,
    plan: CropPlan,
    ass_path: Path | None,
    out_path: Path,
    cfg: ComposeConfig,
    video_duration: float,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Full pipeline: crop+concat then optional subtitle burn-in."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cropped = Path(tmp) / "cropped.mp4"
        crop_concat(source, plan, cropped, cfg, video_duration, on_progress)
        if ass_path is None:
            cropped.replace(out_path)
        else:
            burn_subtitles(cropped, ass_path, out_path, cfg, on_progress)
    return out_path


def center_crop_plan(meta_width: int, meta_height: int, duration: float) -> CropPlan:
    """Build a single-segment, center-aligned 9:16 crop covering the whole video."""
    target_ratio = 9 / 16
    src_ratio = meta_width / meta_height
    if src_ratio > target_ratio:
        out_h = meta_height
        out_w = int(out_h * target_ratio)
    else:
        out_w = meta_width
        out_h = int(out_w / target_ratio)
    x = (meta_width - out_w) // 2
    y = (meta_height - out_h) // 2
    from ..models import CropSegment
    return CropPlan(
        source_width=meta_width,
        source_height=meta_height,
        output_width=out_w,
        output_height=out_h,
        segments=[CropSegment(start=0.0, end=duration, x=x, y=y)],
    )


# Keep ffmpeg streaming export for future use (line-by-line progress parsing).
__all__ = [
    "compose",
    "crop_concat",
    "burn_subtitles",
    "center_crop_plan",
    "stream",          # re-export so consumers don't have to import platform_compat
    "Transcript",      # re-export type hint
]
