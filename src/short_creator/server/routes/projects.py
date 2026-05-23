"""Project lifecycle routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ...models import Project, ProjectStep
from ...pipeline import downloader, probe
from ...project_store import ProjectStore, list_projects
from ..jobs import registry
from ..video_response import video_response

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateFromUrlRequest(BaseModel):
    url: str
    title: str | None = None


class ProjectListItem(BaseModel):
    id: str
    title: str | None
    created_at: str
    current_step: ProjectStep


@router.get("")
def all_projects() -> list[ProjectListItem]:
    return [
        ProjectListItem(
            id=p.id,
            title=p.title,
            created_at=p.created_at.isoformat(),
            current_step=p.current_step,
        )
        for p in list_projects()
    ]


@router.post("/from-url")
def create_from_url(req: CreateFromUrlRequest) -> dict:
    """Create a project and kick off a YouTube download in the background."""
    try:
        meta = downloader.get_metadata(req.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {exc}") from exc

    store = ProjectStore.create(title=req.title or meta.get("title"), source_url=req.url)
    project = store.load_project()

    job = registry.create("download")

    def _run(progress):
        downloader.download(req.url, store.source_path, on_progress=progress)
        meta_info = probe.probe(store.source_path)
        store.save_video_meta(meta_info)
        store.set_step(ProjectStep.TRANSCRIBE)

    registry.run(job.job_id, _run)
    return {"project_id": project.id, "job_id": job.job_id}


@router.post("/from-upload")
async def create_from_upload(file: UploadFile) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    store = ProjectStore.create(title=file.filename)
    with store.source_path.open("wb") as fh:
        while chunk := await file.read(1024 * 1024 * 4):
            fh.write(chunk)
    meta_info = probe.probe(store.source_path)
    store.save_video_meta(meta_info)
    store.set_step(ProjectStep.TRANSCRIBE)
    return {"project_id": store.id}


@router.get("/{project_id}")
def get_project(project_id: str) -> Project:
    try:
        return ProjectStore(project_id).load_project()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


class StepUpdate(BaseModel):
    step: ProjectStep


@router.put("/{project_id}/step")
def set_step(project_id: str, body: StepUpdate) -> dict:
    store = ProjectStore(project_id)
    store.set_step(body.step)
    return {"ok": True}


class RangeSelection(BaseModel):
    clip_id: str | None = None
    start: float
    end: float


@router.put("/{project_id}/selection")
def set_selection(project_id: str, body: RangeSelection) -> dict:
    store = ProjectStore(project_id)
    project = store.load_project()
    project.selected_clip_id = body.clip_id
    project.selected_range = (body.start, body.end)
    store.save_project(project)
    return {"ok": True}


@router.get("/{project_id}/source")
def get_source(project_id: str, request: Request):
    store = ProjectStore(project_id)
    return video_response(store.source_path, request)


@router.get("/{project_id}/output")
def get_output(project_id: str, request: Request):
    store = ProjectStore(project_id)
    out = store.output_path
    if not out.exists():
        raise HTTPException(status_code=404, detail="Output not rendered yet")
    return video_response(out, request)
