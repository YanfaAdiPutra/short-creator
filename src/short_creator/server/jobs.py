"""In-process background-job registry with progress reporting."""

from __future__ import annotations

import secrets
import threading
import traceback
from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..models import JobState, JobStatus

JobFn = Callable[[Callable[[float, str], None]], Any]


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobStatus] = {}
        self._lock = threading.Lock()

    def create(self, kind: str) -> JobStatus:
        job_id = secrets.token_hex(8)
        status = JobStatus(job_id=job_id, kind=kind)  # type: ignore[arg-type]
        with self._lock:
            self._jobs[job_id] = status
        return status

    def get(self, job_id: str) -> JobStatus | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[JobStatus]:
        with self._lock:
            return list(self._jobs.values())

    def _update(self, job_id: str, **kwargs: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            updated = job.model_copy(update=kwargs)
            self._jobs[job_id] = updated

    def run(self, job_id: str, fn: JobFn) -> None:
        """Run `fn` in a thread, feeding it a progress callback bound to this job."""
        def _progress(pct: float, msg: str) -> None:
            self._update(job_id, progress=max(0.0, min(100.0, pct)), message=msg)

        def _worker() -> None:
            self._update(
                job_id,
                state=JobState.RUNNING,
                started_at=datetime.utcnow(),
                progress=0.0,
            )
            try:
                fn(_progress)
                self._update(
                    job_id,
                    state=JobState.DONE,
                    progress=100.0,
                    finished_at=datetime.utcnow(),
                )
            except Exception as exc:
                self._update(
                    job_id,
                    state=JobState.ERROR,
                    error=f"{type(exc).__name__}: {exc}",
                    message=traceback.format_exc(limit=2),
                    finished_at=datetime.utcnow(),
                )

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()


registry = JobRegistry()
