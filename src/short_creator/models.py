"""Pydantic data models shared across pipeline + server."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Word(BaseModel):
    word: str
    start: float
    end: float


class TranscriptSegment(BaseModel):
    """A sentence-or-phrase-level chunk produced by Whisper, containing words."""
    start: float
    end: float
    text: str
    words: list[Word] = Field(default_factory=list)


class Transcript(BaseModel):
    language: str | None = None
    duration: float
    segments: list[TranscriptSegment]

    @property
    def words(self) -> list[Word]:
        return [w for s in self.segments for w in s.words]

    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments)


class ClipSuggestion(BaseModel):
    id: str
    start: float
    end: float
    title: str
    hook: str
    reason: str
    score: int

    @property
    def duration(self) -> float:
        return self.end - self.start


class Recommendations(BaseModel):
    generated_at_transcript_hash: str
    clips: list[ClipSuggestion]


class CropSegment(BaseModel):
    """A static crop window from `start` to `end` in source-video time."""
    start: float
    end: float
    x: int
    y: int


class CropPlan(BaseModel):
    source_width: int
    source_height: int
    output_width: int = 1080
    output_height: int = 1920
    segments: list[CropSegment]


class VideoMeta(BaseModel):
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool = True
    title: str | None = None
    source_url: str | None = None


class ProjectStep(str, Enum):
    INPUT = "input"
    TRANSCRIBE = "transcribe"
    RECOMMEND = "recommend"
    CROP = "crop"
    STYLE = "style"
    EXPORT = "export"


class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class JobStatus(BaseModel):
    job_id: str
    kind: Literal["download", "transcribe", "recommend", "render"]
    state: JobState = JobState.PENDING
    progress: float = 0.0
    message: str = ""
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Project(BaseModel):
    id: str
    title: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    current_step: ProjectStep = ProjectStep.INPUT
    source_url: str | None = None
    video_meta: VideoMeta | None = None
    selected_clip_id: str | None = None
    selected_range: tuple[float, float] | None = None
