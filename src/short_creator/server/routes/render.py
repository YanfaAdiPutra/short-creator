"""Render routes — kicks off the full compose pipeline."""

from __future__ import annotations

import tempfile
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import DEFAULT_CONFIG, SubtitleStyle
from ...pipeline import composer, subtitle_builder
from ...project_store import ProjectStore
from ..jobs import registry

router = APIRouter(prefix="/projects/{project_id}/render", tags=["render"])


class RenderRequest(BaseModel):
    burn_subtitles: bool = True


@router.post("")
def start_render(project_id: str, body: RenderRequest) -> dict:
    store = ProjectStore(project_id)
    project = store.load_project()
    if project.video_meta is None:
        raise HTTPException(status_code=400, detail="Source not probed")
    if not store.source_path.exists():
        raise HTTPException(status_code=400, detail="Source video missing")

    crop = store.load_crop()
    if crop is None:
        raise HTTPException(status_code=400, detail="Crop plan missing")

    transcript = store.load_transcript()
    style_dict = store.load_style() or asdict(DEFAULT_CONFIG.subtitle_style)

    selected = project.selected_range
    clip_start = selected[0] if selected else 0.0
    clip_end = selected[1] if selected else project.video_meta.duration

    # Restrict the crop plan to the selected clip range so the output starts at t=0.
    from ...models import CropPlan, CropSegment
    clipped_segments: list[CropSegment] = []
    for seg in crop.segments:
        new_start = max(clip_start, seg.start) - clip_start
        new_end = min(clip_end, seg.end) - clip_start
        if new_end <= new_start:
            continue
        clipped_segments.append(
            CropSegment(start=new_start, end=new_end, x=seg.x, y=seg.y)
        )
    if not clipped_segments:
        raise HTTPException(status_code=400, detail="Crop plan does not cover selected range")
    clipped_plan = CropPlan(
        source_width=crop.source_width,
        source_height=crop.source_height,
        output_width=crop.output_width,
        output_height=crop.output_height,
        segments=clipped_segments,
    )

    job = registry.create("render")

    def _run(progress):
        with tempfile.TemporaryDirectory() as tmpd:
            tmp = Path(tmpd)
            # First, cut the selected range from the source so segments map cleanly.
            from ...platform_compat.ffmpeg_locator import ffmpeg_path
            from ...platform_compat.proc import run
            cut_path = tmp / "selected.mp4"
            progress(5, "Selecting clip range…")
            run([
                ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "warning",
                "-ss", f"{clip_start:.3f}", "-to", f"{clip_end:.3f}",
                "-i", str(store.source_path),
                "-c", "copy",
                str(cut_path),
            ])

            ass_path: Path | None = None
            if body.burn_subtitles and transcript is not None:
                progress(10, "Building subtitles…")
                ass_path = tmp / "subs.ass"
                style = SubtitleStyle(**style_dict)
                subtitle_builder.write_ass(
                    transcript,
                    style,
                    ass_path,
                    output_width=DEFAULT_CONFIG.compose.output_width,
                    output_height=DEFAULT_CONFIG.compose.output_height,
                    clip_start=clip_start,
                    clip_end=clip_end,
                )

            composer.compose(
                cut_path,
                clipped_plan,
                ass_path,
                store.output_path,
                DEFAULT_CONFIG.compose,
                video_duration=clip_end - clip_start,
                on_progress=progress,
            )

    registry.run(job.job_id, _run)
    return {"job_id": job.job_id}
