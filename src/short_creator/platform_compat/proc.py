"""Subprocess helpers — Windows-safe (no shell, no console flash)."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable, Sequence


def no_window_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def run(
    cmd: Sequence[str],
    *,
    check: bool = True,
    capture: bool = False,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess as a list (no shell)."""
    return subprocess.run(
        list(cmd),
        check=check,
        capture_output=capture,
        text=True,
        cwd=cwd,
        env=env,
        creationflags=no_window_flags(),
    )


def stream(
    cmd: Sequence[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> Iterable[str]:
    """Run a process and yield combined stdout/stderr lines as they arrive."""
    proc = subprocess.Popen(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        env=env,
        creationflags=no_window_flags(),
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        yield line.rstrip("\n")
    proc.wait()
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, list(cmd))
