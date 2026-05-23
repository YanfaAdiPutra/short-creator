"""Best-effort GPU detection without forcing a CUDA install at import time."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from .proc import no_window_flags


@dataclass
class GPUInfo:
    name: str
    vram_gb: float

    def profile(self) -> str:
        if self.vram_gb >= 12:
            return "high"
        if self.vram_gb >= 6:
            return "mid"
        return "low"


def detect_nvidia_gpu() -> GPUInfo | None:
    """Return GPU info via nvidia-smi if available."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            creationflags=no_window_flags(),
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    line = result.stdout.strip().splitlines()
    if not line:
        return None
    parts = [p.strip() for p in line[0].split(",")]
    if len(parts) < 2:
        return None
    try:
        vram_mb = float(parts[1])
    except ValueError:
        return None
    return GPUInfo(name=parts[0], vram_gb=round(vram_mb / 1024, 1))


def recommended_whisper_model(gpu: GPUInfo | None) -> str:
    if gpu is None:
        return "base"
    if gpu.profile() == "high":
        return "large-v3"
    if gpu.profile() == "mid":
        return "medium"
    return "small"
