# Developing short-creator

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer (for the frontend)
- `ffmpeg` and `ffprobe` on PATH (Windows: `winget install ffmpeg`)
- Optional but recommended: NVIDIA GPU with NVENC support

## First-time setup

```bash
# Python (creates a venv and installs the package in editable mode)
python -m venv .venv
.venv\Scripts\activate              # PowerShell:  .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Frontend
cd frontend
npm install
```

## Configure an LLM provider

The recommender reads API keys from environment variables. Copy `.env.example`
to `.env` and set whichever provider you have a key for. The app loads `.env`
automatically on startup.

```
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENAI_API_KEY=sk-...
# or
OLLAMA_HOST=http://localhost:11434
```

## Running in dev mode

Open two terminals.

**Terminal 1 — backend (FastAPI on :8765):**
```bash
short serve --reload
```

**Terminal 2 — frontend (Vite on :5173):**
```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` — the Vite dev server proxies `/api/*` to the
FastAPI server. Hot-module reload works for both layers.

## Production-style run

After running `npm run build` in `frontend/`, the FastAPI server will serve
the built bundle at `/` and you only need one process:

```bash
cd frontend && npm run build && cd ..
short serve
```

## Running tests

```bash
pytest
```

The headline pipeline modules (subtitle builder, composer math) have unit
tests that run without GPU/network/ffmpeg.

## CLI overview

```bash
short download <url>                             # yt-dlp wrapper
short transcribe <video> --model medium          # faster-whisper → transcript.json
short recommend transcript.json --provider auto  # LLM → recommendations.json
short compose video.mp4 --crop crop.json --transcript transcript.json
short serve --port 8765
short env                                        # dump runtime detection (GPU/NVENC/providers)
```

## Project layout

```
src/short_creator/
├── cli.py                          click commands
├── config.py                       AppConfig dataclasses (defaults — Path A stack)
├── models.py                       Pydantic shared schemas
├── project_store.py                per-project folder under user data dir
├── pipeline/
│   ├── downloader.py               yt_dlp
│   ├── probe.py                    ffprobe → VideoMeta
│   ├── transcriber.py              faster-whisper
│   ├── recommender.py              Anthropic / OpenAI / Ollama providers
│   ├── subtitle_builder.py         ASS karaoke with rolling 3-5 word window
│   └── composer.py                 segment-then-concat + NVENC subtitle burn
├── platform_compat/
│   ├── ffmpeg_locator.py           find ffmpeg.exe + has_nvenc()
│   ├── gpu.py                      nvidia-smi parsing
│   └── proc.py                     subprocess.run wrapper, suppresses console flash
└── server/
    ├── app.py                      FastAPI app, SPA fallback for the built frontend
    ├── jobs.py                     thread-based job registry with progress callbacks
    ├── video_response.py           HTTP range-request support for browser scrubbing
    └── routes/                     projects, transcription, recommend, crop, style, render, jobs, settings

frontend/src/
├── App.tsx                         BrowserRouter; nested project routes
├── api.ts                          typed API client
├── store.ts                        Zustand store
├── components/
│   ├── Sidebar.tsx                 step nav + env badge
│   ├── TopBar.tsx                  active job indicator
│   ├── CropCanvas.tsx              source-video canvas + draggable 9:16 box
│   ├── PreviewPane.tsx             live 9:16 output preview
│   └── Timeline.tsx                scrubber with segment bands
└── pages/
    ├── Home.tsx                    create / pick a project
    ├── Input.tsx                   source video preview
    ├── Transcript.tsx              Whisper run + edit
    ├── Recommend.tsx               LLM clip suggestions
    ├── CropEditor.tsx              the headline screen
    ├── Style.tsx                   subtitle controls
    └── Export.tsx                  render + download
```
