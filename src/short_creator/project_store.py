"""Disk persistence for projects — each project is a folder of JSON + media."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime
from pathlib import Path

from .config import projects_dir
from .models import (
    CropPlan,
    Project,
    ProjectStep,
    Recommendations,
    Transcript,
    VideoMeta,
)


def _safe_load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _safe_dump(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


class ProjectStore:
    """Reads and writes a single project's files on disk."""

    def __init__(self, project_id: str) -> None:
        self.id = project_id
        self.root = projects_dir() / project_id
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create(cls, title: str | None = None, source_url: str | None = None) -> "ProjectStore":
        pid = datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
        store = cls(pid)
        project = Project(id=pid, title=title, source_url=source_url)
        store.save_project(project)
        return store

    # ---------- file path helpers ----------

    @property
    def project_path(self) -> Path:
        return self.root / "project.json"

    @property
    def source_path(self) -> Path:
        return self.root / "source.mp4"

    @property
    def transcript_path(self) -> Path:
        return self.root / "transcript.json"

    @property
    def recommendations_path(self) -> Path:
        return self.root / "recommendations.json"

    @property
    def crop_path(self) -> Path:
        return self.root / "crop.json"

    @property
    def style_path(self) -> Path:
        return self.root / "style.json"

    @property
    def output_path(self) -> Path:
        out = self.root / "output"
        out.mkdir(parents=True, exist_ok=True)
        return out / "short.mp4"

    # ---------- read/write ----------

    def load_project(self) -> Project:
        data = _safe_load(self.project_path)
        if data is None:
            raise FileNotFoundError(f"project.json missing for {self.id}")
        return Project.model_validate(data)

    def save_project(self, project: Project) -> None:
        _safe_dump(self.project_path, project)

    def save_video_meta(self, meta: VideoMeta) -> None:
        project = self.load_project()
        project.video_meta = meta
        self.save_project(project)

    def set_step(self, step: ProjectStep) -> None:
        project = self.load_project()
        project.current_step = step
        self.save_project(project)

    def load_transcript(self) -> Transcript | None:
        data = _safe_load(self.transcript_path)
        return Transcript.model_validate(data) if data else None

    def save_transcript(self, transcript: Transcript) -> None:
        _safe_dump(self.transcript_path, transcript)

    def load_recommendations(self) -> Recommendations | None:
        data = _safe_load(self.recommendations_path)
        return Recommendations.model_validate(data) if data else None

    def save_recommendations(self, recs: Recommendations) -> None:
        _safe_dump(self.recommendations_path, recs)

    def load_crop(self) -> CropPlan | None:
        data = _safe_load(self.crop_path)
        return CropPlan.model_validate(data) if data else None

    def save_crop(self, crop: CropPlan) -> None:
        _safe_dump(self.crop_path, crop)

    def load_style(self) -> dict | None:
        return _safe_load(self.style_path)

    def save_style(self, style: dict) -> None:
        _safe_dump(self.style_path, style)

    # ---------- bookkeeping ----------

    def transcript_hash(self) -> str:
        """Stable hash of the transcript text, used to detect staleness."""
        t = self.load_transcript()
        if t is None:
            return ""
        return hashlib.sha256(t.text().encode("utf-8")).hexdigest()[:16]


def list_projects() -> list[Project]:
    projects = []
    for p in projects_dir().iterdir():
        if not p.is_dir():
            continue
        data = _safe_load(p / "project.json")
        if data:
            try:
                projects.append(Project.model_validate(data))
            except Exception:
                continue
    projects.sort(key=lambda x: x.created_at, reverse=True)
    return projects
