"""Subtitle style routes."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from ...config import DEFAULT_CONFIG
from ...project_store import ProjectStore

router = APIRouter(prefix="/projects/{project_id}/style", tags=["style"])


@router.get("")
def get_style(project_id: str) -> dict:
    store = ProjectStore(project_id)
    style = store.load_style()
    if style is None:
        style = asdict(DEFAULT_CONFIG.subtitle_style)
    return style


@router.put("")
def put_style(project_id: str, style: dict) -> dict:
    store = ProjectStore(project_id)
    # Filter to known fields to avoid leaking arbitrary keys to disk
    allowed = set(asdict(DEFAULT_CONFIG.subtitle_style).keys())
    sanitized = {k: v for k, v in style.items() if k in allowed}
    store.save_style(sanitized)
    return {"ok": True}
