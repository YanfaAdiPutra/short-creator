"""HTTP range-request support for streaming video to the browser."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse


_CHUNK = 1024 * 1024  # 1 MiB


def video_response(path: Path, request: Request, media_type: str = "video/mp4"):
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header is None:
        return FileResponse(path, media_type=media_type)

    # Parse "bytes=START-END"
    if not range_header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="Invalid range header")
    raw = range_header[len("bytes="):]
    try:
        start_s, end_s = raw.split("-", 1)
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Malformed range") from exc

    start = max(0, start)
    end = min(end, file_size - 1)
    if start > end:
        raise HTTPException(status_code=416, detail="Range out of bounds")

    length = end - start + 1

    def _iter():
        with path.open("rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(_CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Cache-Control": "no-cache",
    }
    return StreamingResponse(_iter(), status_code=206, media_type=media_type, headers=headers)


def serve_static_file(path: Path) -> FileResponse:
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


def safe_join(root: Path, *parts: str) -> Path:
    """Join under `root`, refusing path-traversal attempts."""
    candidate = (root / Path(*parts)).resolve()
    root_resolved = root.resolve()
    if os.path.commonpath([str(candidate), str(root_resolved)]) != str(root_resolved):
        raise HTTPException(status_code=400, detail="Invalid path")
    return candidate
