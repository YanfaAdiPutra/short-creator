"""Recommender routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import DEFAULT_CONFIG, RecommenderConfig
from ...models import Recommendations
from ...pipeline import recommender
from ...project_store import ProjectStore
from ..jobs import registry

router = APIRouter(prefix="/projects/{project_id}/recommendations", tags=["recommend"])


class RecommendRequest(BaseModel):
    provider: str | None = None
    model: str | None = None


def _detect_default_provider() -> tuple[str, str] | None:
    """Return (provider, model) for any provider whose API key env var is set."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ("anthropic", "claude-haiku-4-5-20251001")
    if os.environ.get("OPENAI_API_KEY"):
        return ("openai", "gpt-4o-mini")
    if os.environ.get("OLLAMA_HOST"):
        return ("ollama", "qwen2.5:7b")
    return None


@router.post("")
def start_recommend(project_id: str, body: RecommendRequest) -> dict:
    store = ProjectStore(project_id)
    transcript = store.load_transcript()
    if transcript is None:
        raise HTTPException(status_code=400, detail="Transcribe before recommending")

    provider = body.provider
    model = body.model
    if not provider:
        detected = _detect_default_provider()
        if detected is None:
            raise HTTPException(
                status_code=400,
                detail="No LLM provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OLLAMA_HOST.",
            )
        provider, model = detected

    cfg = RecommenderConfig(
        provider=provider,
        model=model or DEFAULT_CONFIG.recommender.model,
        min_clip_seconds=DEFAULT_CONFIG.recommender.min_clip_seconds,
        max_clip_seconds=DEFAULT_CONFIG.recommender.max_clip_seconds,
        max_clips=DEFAULT_CONFIG.recommender.max_clips,
    )
    job = registry.create("recommend")

    def _run(progress):
        progress(20.0, f"Asking {cfg.provider} {cfg.model}…")
        recs = recommender.recommend(transcript, cfg)
        store.save_recommendations(recs)
        progress(100.0, f"Got {len(recs.clips)} recommendations")

    registry.run(job.job_id, _run)
    return {"job_id": job.job_id}


class RecommendationsView(BaseModel):
    recommendations: Recommendations | None
    is_stale: bool
    current_transcript_hash: str
    available_providers: list[str]


@router.get("")
def get_recommendations(project_id: str) -> RecommendationsView:
    store = ProjectStore(project_id)
    recs = store.load_recommendations()
    current = store.transcript_hash()
    stale = bool(recs and recs.generated_at_transcript_hash != current)
    providers: list[str] = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")
    if os.environ.get("OLLAMA_HOST"):
        providers.append("ollama")
    return RecommendationsView(
        recommendations=recs,
        is_stale=stale,
        current_transcript_hash=current,
        available_providers=providers,
    )
