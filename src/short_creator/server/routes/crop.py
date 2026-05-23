"""Crop plan routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...models import CropPlan
from ...pipeline import composer
from ...project_store import ProjectStore

router = APIRouter(prefix="/projects/{project_id}/crop", tags=["crop"])


@router.get("")
def get_crop(project_id: str) -> CropPlan:
    store = ProjectStore(project_id)
    plan = store.load_crop()
    if plan is None:
        # Generate a sensible default (center-crop, single segment)
        project = store.load_project()
        if project.video_meta is None:
            raise HTTPException(status_code=400, detail="Source not probed yet")
        plan = composer.center_crop_plan(
            project.video_meta.width,
            project.video_meta.height,
            project.video_meta.duration,
        )
        store.save_crop(plan)
    return plan


@router.put("")
def put_crop(project_id: str, plan: CropPlan) -> dict:
    store = ProjectStore(project_id)
    store.save_crop(plan)
    return {"ok": True}
