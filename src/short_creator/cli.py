"""Command-line entrypoints."""

from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

import click
from dotenv import load_dotenv

from . import __version__
from .config import DEFAULT_CONFIG
from .pipeline import composer, downloader, probe, recommender, subtitle_builder, transcriber
from .project_store import ProjectStore


def _progress_printer(pct: float, msg: str) -> None:
    click.echo(f"[{pct:6.2f}%] {msg}")


@click.group()
@click.version_option(__version__)
def main() -> None:
    """short-creator — turn long videos into 9:16 shorts."""
    load_dotenv()


@main.command()
@click.argument("url")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=Path("source.mp4"))
def download(url: str, out_path: Path) -> None:
    """Download a YouTube video at the best available quality."""
    downloader.download(url, out_path, on_progress=_progress_printer)
    click.echo(f"Saved -> {out_path}")


@main.command()
@click.argument("video", type=click.Path(exists=True, path_type=Path))
@click.option("--model", default=None, help="faster-whisper model (default: medium)")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=Path("transcript.json"))
def transcribe(video: Path, model: str | None, out_path: Path) -> None:
    """Transcribe a local video using faster-whisper."""
    cfg = DEFAULT_CONFIG.transcription
    if model:
        cfg.model = model
    transcript = transcriber.transcribe(video, cfg, on_progress=_progress_printer)
    out_path.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
    click.echo(f"Saved -> {out_path}")


@main.command()
@click.argument("transcript_file", type=click.Path(exists=True, path_type=Path))
@click.option("--provider", default=None, help="anthropic | openai | ollama")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=Path("recommendations.json"))
def recommend(transcript_file: Path, provider: str | None, out_path: Path) -> None:
    """Ask an LLM to suggest the best short clips from a transcript."""
    from .models import Transcript
    transcript = Transcript.model_validate_json(transcript_file.read_text(encoding="utf-8"))

    cfg = DEFAULT_CONFIG.recommender
    if provider:
        cfg.provider = provider
    recs = recommender.recommend(transcript, cfg)
    out_path.write_text(recs.model_dump_json(indent=2), encoding="utf-8")
    click.echo(f"Found {len(recs.clips)} clips, saved -> {out_path}")
    for c in recs.clips:
        click.echo(f"  [{c.score:3d}] {c.start:6.1f}s-{c.end:6.1f}s  {c.title}")


@main.command()
@click.argument("video", type=click.Path(exists=True, path_type=Path))
@click.option("--crop", "crop_file", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--transcript", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=Path("output.mp4"))
def compose(video: Path, crop_file: Path, transcript: Path | None, out_path: Path) -> None:
    """Render the final 9:16 short with crop + subtitles."""
    from .models import CropPlan, Transcript

    plan = CropPlan.model_validate_json(crop_file.read_text(encoding="utf-8"))
    meta = probe.probe(video)

    ass_path: Path | None = None
    if transcript:
        t = Transcript.model_validate_json(transcript.read_text(encoding="utf-8"))
        ass_path = out_path.with_suffix(".ass")
        subtitle_builder.write_ass(
            t,
            DEFAULT_CONFIG.subtitle_style,
            ass_path,
            output_width=DEFAULT_CONFIG.compose.output_width,
            output_height=DEFAULT_CONFIG.compose.output_height,
        )

    composer.compose(
        video, plan, ass_path, out_path,
        DEFAULT_CONFIG.compose,
        video_duration=meta.duration,
        on_progress=_progress_printer,
    )
    click.echo(f"Rendered -> {out_path}")


@main.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", type=int, default=8765)
@click.option("--no-browser", is_flag=True, default=False, help="Don't open a browser tab")
@click.option("--reload", is_flag=True, default=False, help="Auto-reload on code changes (dev)")
def serve(host: str, port: int, no_browser: bool, reload: bool) -> None:
    """Launch the full web UI (FastAPI + bundled frontend)."""
    import uvicorn

    url = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"
    click.echo(f"short-creator UI -> {url}")

    if not no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run(
        "short_creator.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@main.command()
def env() -> None:
    """Show runtime environment (GPU, providers, ffmpeg encoders)."""
    from .platform_compat.ffmpeg_locator import has_nvenc
    from .platform_compat.gpu import detect_nvidia_gpu, recommended_whisper_model
    import os

    gpu = detect_nvidia_gpu()
    info = {
        "version": __version__,
        "gpu": (
            {"name": gpu.name, "vram_gb": gpu.vram_gb, "profile": gpu.profile()}
            if gpu else "none"
        ),
        "nvenc": has_nvenc(),
        "recommended_whisper_model": recommended_whisper_model(gpu),
        "providers": {
            "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "openai": bool(os.environ.get("OPENAI_API_KEY")),
            "ollama": bool(os.environ.get("OLLAMA_HOST")),
        },
    }
    click.echo(json.dumps(info, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
