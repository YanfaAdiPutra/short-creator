"""Job status route."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...models import JobStatus
from ..jobs import registry

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: str) -> JobStatus:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
