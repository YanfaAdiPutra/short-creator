"""Read-only settings/environment endpoint."""

from __future__ import annotations

import os

from fastapi import APIRouter

from ... import __version__
from ...platform_compat.ffmpeg_locator import has_nvenc
from ...platform_compat.gpu import detect_nvidia_gpu, recommended_whisper_model

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/env")
def env() -> dict:
    gpu = detect_nvidia_gpu()
    return {
        "version": __version__,
        "providers": {
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "ollama": bool(os.environ.get("OLLAMA_HOST")),
        },
        "gpu": (
            {"name": gpu.name, "vram_gb": gpu.vram_gb, "profile": gpu.profile()}
            if gpu else None
        ),
        "ffmpeg": {"nvenc": has_nvenc()},
        "recommended_whisper_model": recommended_whisper_model(gpu),
    }
