"""Transcription routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import DEFAULT_CONFIG, TranscriptionConfig
from ...models import Transcript
from ...pipeline import transcriber
from ...project_store import ProjectStore
from ..jobs import registry

router = APIRouter(prefix="/projects/{project_id}/transcript", tags=["transcript"])


class TranscribeRequest(BaseModel):
    model: str | None = None
    language: str | None = None


@router.post("")
def start_transcribe(project_id: str, body: TranscribeRequest) -> dict:
    store = ProjectStore(project_id)
    if not store.source_path.exists():
        raise HTTPException(status_code=400, detail="Source video missing")

    cfg = TranscriptionConfig(
        model=body.model or DEFAULT_CONFIG.transcription.model,
        quantization=DEFAULT_CONFIG.transcription.quantization,
        device=DEFAULT_CONFIG.transcription.device,
        language=body.language,
    )
    job = registry.create("transcribe")

    def _run(progress):
        transcript = transcriber.transcribe(store.source_path, cfg, on_progress=progress)
        store.save_transcript(transcript)

    registry.run(job.job_id, _run)
    return {"job_id": job.job_id}


@router.get("")
def get_transcript(project_id: str) -> Transcript:
    store = ProjectStore(project_id)
    transcript = store.load_transcript()
    if transcript is None:
        raise HTTPException(status_code=404, detail="No transcript yet")
    return transcript


class TranscriptUpdate(BaseModel):
    transcript: Transcript


@router.put("")
def update_transcript(project_id: str, body: TranscriptUpdate) -> dict:
    store = ProjectStore(project_id)
    store.save_transcript(body.transcript)
    return {"ok": True}
