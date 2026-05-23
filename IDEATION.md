# YouTube-to-Short Converter — Ideation & Technical Approach

## Recommended Runtime Profile (Path A — Hybrid)

This is the **default stack** the app should ship with. It assumes a typical user on a Windows machine with a mid-range NVIDIA GPU (e.g., GTX 1070 Ti / RTX 3060 / RTX 4060) and 8 GB VRAM.

### Stack at a glance

| Stage | Tool | Runs on | VRAM at peak | Cost |
|-------|------|---------|--------------|------|
| Download | `yt-dlp` | CPU + network | 0 | Free |
| Transcription | `faster-whisper` `medium` int8 | **GPU** | ~3 GB | Free |
| Recommender | Claude Haiku 4.5 (Anthropic API) | **Cloud** | 0 | ~$0.01–0.04 per video |
| Crop Editor | Browser (`<video>` element) | CPU/GPU (browser) | minimal | Free |
| Compose | `ffmpeg` with `h264_nvenc` | **GPU** | ~1 GB | Free |

### Why this stack

1. **No VRAM contention** — Whisper finishes and unloads before ffmpeg's NVENC pass starts. The recommender runs on the cloud so it doesn't touch local VRAM at all. 8 GB is enough.
2. **Cloud LLM ≪ cost of headache** — at ~$0.01–0.04 per video, the API beats wrangling local 7B models on a constrained GPU. Quality is dramatically better too.
3. **`medium` int8 is the sweet spot for Whisper** — `large-v3` only marginally improves English transcription accuracy but takes 3× longer and eats more VRAM.
4. **NVENC for compose** — Pascal-era and later NVIDIA cards have hardware H.264 encoders. The compose step becomes near-instant.

### Expected speeds on a 1070 Ti–class GPU

| Video length | Transcribe | Recommend | Compose | Total |
|--------------|-----------|-----------|---------|-------|
| 30 min | ~2 min | ~5 sec | ~10 sec | **~3 min** |
| 1 hr | ~4 min | ~10 sec | ~20 sec | **~5 min** |
| 2 hr | ~8 min | ~15 sec | ~40 sec | **~10 min** |

### Auto-detect on first launch

The app detects the user's hardware once and writes defaults to `~/.short/config.yaml`:

```python
def detect_runtime_profile():
    gpu = detect_nvidia_gpu()
    if not gpu:
        return CPU_PROFILE   # base/small Whisper, software ffmpeg
    if gpu.vram_gb >= 12:
        return HIGH_PROFILE  # large-v3 int8, NVENC
    if gpu.vram_gb >= 6:
        return MID_PROFILE   # medium int8, NVENC  ← 1070 Ti lands here
    return LOW_PROFILE       # small int8, NVENC
```

A user can override these at any time via the settings screen, but the defaults should "just work" without configuration.

### Default config file (shipped with app)

```yaml
transcription:
  model: medium
  quantization: int8
  device: auto           # uses cuda if available, else cpu

recommender:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  # API keys are read from environment variables only:
  #   ANTHROPIC_API_KEY  or  OPENAI_API_KEY  or  OLLAMA_HOST
  # The app never persists keys to disk.

compose:
  encoder: h264_nvenc    # falls back to libx264 if NVENC unavailable
  preset: p5             # balanced speed/quality for NVENC
  crf: 20                # for libx264 fallback
  audio_codec: aac
  audio_bitrate: 192k

paths:
  data_dir: auto         # %APPDATA%\short on Windows
```

### Path B (Fully Local) — opt-in fallback

For users who want zero API cost or work offline, a `--local-llm` flag swaps Anthropic for Ollama. The app then:

1. Loads Whisper, runs transcription, **explicitly frees VRAM** (`del model; torch.cuda.empty_cache()`)
2. Calls Ollama with `OLLAMA_KEEP_ALIVE=0` so it unloads after generating
3. Runs ffmpeg NVENC compose

This avoids VRAM contention by enforcing strict sequential model loading. Documented but not default — the cloud path is simpler and barely costs anything.

---

## High-Level Modular Pipeline

The pipeline is broken into discrete stages. Each stage caches its output to disk, so re-runs skip already-completed work.

```
[Optional] YouTube URL
    ↓
[Stage 1] Download          →  video.mp4         (skip if local file provided)
    ↓
[Stage 2] Transcribe        →  transcript.json   (always run, cached)
    ↓
[Stage 2.5] Recommend       →  recommendations.json (cached)
    ↓
[Stage 3] Crop Editor       →  crop.json
    ↓
[Stage 4] Compose           →  output_short.mp4
```

**Caching:** all artifacts are stored in the project folder and reused on subsequent runs. If the user edits the transcript, downstream caches (recommendations) are flagged stale but kept until manually re-analyzed. The user never re-uploads an external SRT — we always transcribe ourselves.

---

## Stage 1 — Download

**Tool:** `yt-dlp`

- Fetch best available video+audio stream, merged as MP4
- Capture metadata: duration, original resolution, fps, title
- Skip entirely if user provides a local file

```
yt-dlp -f "bestvideo+bestaudio" --merge-output-format mp4 <URL>
```

---

## Stage 2 — Transcription (Word-Level Timestamps)

**Tool:** `faster-whisper` (local) — **always runs**, regardless of input source

The app always generates transcripts itself. External SRT files are not accepted as input because:
- We need precise word-level timestamps for the karaoke subtitle effect, and most third-party SRT files only have sentence-level timing
- Generating our own transcript guarantees consistent quality and format
- The LLM recommender also needs reliable word timestamps for accurate clip boundaries

If the user has a video they want to re-process, the transcription is cached on disk, so subsequent runs skip the work.

- Run on the audio track of the video
- Output word-level timestamps: `[{ word, start, end }, ...]`
- Save as a JSON file in the project folder; SRT is generated as a sidecar at export time

**Model choice tradeoff (int8 quantization):**
| Model | Speed (RTX 3060-class) | Accuracy | VRAM (int8) |
|-------|----------------------|----------|-------------|
| `tiny` | ~100× realtime | Lower | ~0.5 GB |
| `base` | ~80× realtime | Good | ~0.7 GB |
| `small` | ~50× realtime | Better | ~1.2 GB |
| `medium` | ~25× realtime | Great | ~2.5 GB |  ← **Path A default**
| `large-v3` | ~10× realtime | Best | ~5 GB |

**Path A default:** `medium` with int8 quantization on CUDA.
- Best speed/accuracy balance for English YouTube content
- Fits comfortably in 8 GB GPUs alongside other stages
- 1-hour video transcribes in ~4 minutes on a 1070 Ti, ~2 minutes on RTX 4060

**Quantization choice:**
- `int8` — default, ~½ VRAM, small accuracy hit, supported on all NVIDIA GPUs including Pascal
- `int8_float16` — slightly better quality, requires Turing+ (RTX 20 series and later)
- `float16` — full precision, double the VRAM, mainly useful on high-end cards

**VRAM lifecycle:**
After transcription completes, explicitly free the model so later stages (NVENC compose) have full VRAM:
```python
del model
gc.collect()
torch.cuda.empty_cache()
```

---

## Stage 3 — Crop Editor (Interactive Web UI)

This replaces automatic face detection. The user manually defines the crop window visually, with optional keyframing for different time positions.

### UI concept (matches reference screenshot)
- Left panel: original video preview with a draggable **9:16 crop box** overlaid as a blue/white rectangle
- The crop box can be dragged to position the desired subject (e.g., center on the speaker)
- Right panel or bottom: timeline scrubber with keyframe markers

### Crop segment system (static segments — no interpolation)

The crop is defined as a series of **static segments**, not interpolated keyframes. Each segment has a fixed crop position that doesn't move until the next segment begins.

**Example:**
```
0s ────── 5s ────── 12s ──────── 30s
   crop A    crop B       crop C
   (static)  (static)     (static)
```
From 0–5s the crop sits at position A; at 5s it jump-cuts to position B and stays there until 12s; at 12s it jump-cuts to position C.

**Why no interpolation:**
- Simpler to implement (one ffmpeg crop per segment, then concat)
- Predictable output — no smooth pan that might miss the speaker
- Matches the "scene cut" model most users intuitively understand
- Easier to debug — what you see in the editor is exactly what you get

**User flow in the editor:**
- At any point on the timeline, click "+ Cut here" to start a new segment
- Drag the crop box to position it for that segment
- Segment boundaries appear as vertical dividers on the timeline
- Each segment can be selected independently and its crop position adjusted

### Output
- Saved as `crop.json` — reusable, editable, version-controllable
- Format: list of segments, each with its own static crop rectangle
```json
{
  "source_width": 1920,
  "source_height": 1080,
  "output_width": 608,
  "output_height": 1080,
  "segments": [
    { "start": 0.0,  "end": 5.0,  "x": 656, "y": 0 },
    { "start": 5.0,  "end": 12.0, "x": 820, "y": 0 },
    { "start": 12.0, "end": 30.0, "x": 656, "y": 0 }
  ]
}
```
Segments are contiguous: each segment's `end` equals the next segment's `start`. The final segment's `end` matches the chosen clip's end timestamp.

### Tech stack for the editor
See the **UI Architecture** section below — the crop editor is one screen inside a unified multi-step web UI that covers the whole pipeline.

---

## Stage 4 — Compose (Crop + Subtitles → Final Video)

**Tool:** `ffmpeg` via `ffmpeg-python`

### Crop pass — segment-then-concat (decision: Option B)
- Read `crop.json` segments
- For each segment: ffmpeg cuts that time range from the source and applies its static crop
- Concat all cropped segments back into a single video using the ffmpeg `concat` demuxer
- Pros: simple, predictable, one ffmpeg invocation per segment is easy to debug
- Each segment is jump-cut to the next — no interpolation between crop positions

**Pseudocode:**
```python
for i, seg in enumerate(crop.segments):
    run_ffmpeg([
        "-ss", str(seg.start), "-to", str(seg.end),
        "-i", "source.mp4",
        "-vf", f"crop={out_w}:{out_h}:{seg.x}:{seg.y}",
        "-c:v", "h264_nvenc", "-preset", "p5",
        f"seg_{i}.mp4",
    ])
run_ffmpeg(["-f", "concat", "-i", "segments.txt", "-c", "copy", "cropped.mp4"])
```

### Subtitle pass (decision: rolling 3–5 word window)
- Convert word-timestamp data to an **ASS subtitle file** with karaoke `\k` tags
- ffmpeg's `subtitles` or `ass` filter burns the ASS file directly into the cropped video

**Layout: rolling window**
At any moment, 3–5 words are visible on screen. The currently-spoken word is highlighted in the active color; the surrounding words appear in a muted color for reading context. As speech progresses, the window scrolls forward word by word.

```
Visible at t=2.3s:    "the  [quick]  brown  fox"
Visible at t=2.6s:    "quick  [brown]  fox  jumps"
Visible at t=3.0s:    "brown  [fox]  jumps  over"
```

**ASS Karaoke implementation:**
Each dialogue line in the ASS file contains a 3–5 word window with `\k` tags:
```
{\k0}the {\k30\c&H00FFFF&}quick{\r} {\k0}brown {\k0}fox
```
Where `\c&H00FFFF&` sets the active color (yellow), `\r` resets to the default style, and `\k` durations advance the highlight in sync with speech.

The window size (3, 4, or 5 words) is configurable in the Style screen; default is 4.

### Single ffmpeg command (goal)
Ideally the entire compose step is one ffmpeg invocation.

**Path A default — hardware-accelerated H.264 via NVENC:**
```
ffmpeg -hwaccel cuda -i video.mp4
  -vf "crop=608:1080:656:0, ass=subtitles.ass"
  -c:v h264_nvenc -preset p5 -rc vbr -cq 20
  -c:a aac -b:a 192k
  output.mp4
```
On a 1070 Ti, this encodes a 60-second short in 5–10 seconds. NVENC quality at `cq 20` is visually indistinguishable from `libx264 -crf 18` for short-form vertical video.

**Software fallback** (if NVENC unavailable):
```
ffmpeg -i video.mp4
  -vf "crop=608:1080:656:0, ass=subtitles.ass"
  -c:v libx264 -crf 18 -preset fast
  -c:a aac -b:a 192k
  output.mp4
```

**Encoder detection:**
```python
def pick_encoder() -> str:
    if has_nvenc():     return "h264_nvenc"
    if has_videotoolbox(): return "h264_videotoolbox"  # macOS
    if has_qsv():       return "h264_qsv"               # Intel iGPU
    return "libx264"                                     # CPU fallback
```

Because we use static-segment crops (not interpolated keyframes), the final compose is actually a two-step pipeline:
1. Per-segment crop + concat → `cropped.mp4`
2. Subtitle burn-in over the concatenated video → `output.mp4`

Both steps use NVENC where available.

---

## UI Architecture

The app ships as a **local web app**: a Python backend server that the user starts via `short serve`, which opens a browser tab on `localhost:8765`. This avoids the complexity of bundling a desktop app while giving full browser video playback (hardware accelerated).

### Why a local web app
- Browsers decode H.264 natively → smooth scrubbing in the crop editor
- HTML/CSS makes the draggable crop box and timeline trivial to build
- Same UI can later be deployed as a hosted SaaS if desired
- No Electron / Tauri bundling overhead in v1

### Frontend stack
- **React + Vite** for the UI (component-based, fast dev iteration)
  - Alternatively vanilla JS for a smaller footprint if React feels heavy
- **TailwindCSS** for styling — matches the clean look in the reference screenshot
- **Zustand** for state management (simpler than Redux, perfect for project state)
- **HTML5 `<video>`** for playback in the crop editor
- **Canvas overlay** for the draggable crop box (handles drag/resize math precisely)
- **WaveSurfer.js** (optional) for audio waveform in the timeline, useful for finding pause points

### Backend stack
- **FastAPI** server, single process
- Serves the React build as static files
- REST endpoints:
  - `POST /api/project` — create new project from URL or upload
  - `GET /api/project/:id` — fetch project state
  - `POST /api/project/:id/transcribe` — kick off transcription (returns job id)
  - `GET /api/project/:id/status` — poll job progress
  - `PUT /api/project/:id/crop` — save crop.json
  - `PUT /api/project/:id/style` — save subtitle style
  - `POST /api/project/:id/render` — start final compose
  - `GET /api/project/:id/download` — stream final MP4
- Video files served via FastAPI's `FileResponse` with HTTP range support (so the browser can seek)
- Long-running jobs (download, transcribe, render) run as background tasks; UI polls for status

### Project state on disk
Each project is a folder:
```
~/.short/projects/<project_id>/
├── source.mp4
├── subtitles.srt          (auto or user-provided)
├── crop.json              (from crop editor)
├── style.json             (subtitle styling choices)
├── project.json           (current step, metadata)
└── output/
    └── short.mp4
```

The frontend never holds canonical state — everything is persisted to JSON on disk so refresh/reopen always restores the project.

### Screen-by-screen implementation notes

**Step 1 — Input**
- Tabbed component, one tab per input type
- YouTube URL → `POST /api/project` with `{ source: "url", url: "..." }`
- File upload → `POST /api/project` with multipart form (browser uploads to backend)
- Backend immediately returns `project_id`, frontend navigates to step 2

**Step 2 — Transcription**
- On entry, if no SRT exists, fire `POST /api/project/:id/transcribe`
- Poll `/status` every 1s until done
- Render transcript as editable text segments mapped to timestamps
- Edits write back to the SRT via `PUT /api/project/:id/subtitles`

**Step 3 — Crop Editor**
- React component composed of:
  - `<VideoCanvas>` — `<video>` element + absolutely-positioned crop box `<div>` with drag handles
  - `<Timeline>` — current time, keyframe markers, play controls
  - `<KeyframeList>` — table of keyframes with edit/delete
- Crop box math: convert mouse position in screen pixels → video pixel coordinates using the video element's `naturalWidth/Height` vs. rendered size
- Drag uses `requestAnimationFrame` for smooth updates
- Keyframes stored in Zustand state, debounced save to backend (`PUT /api/project/:id/crop`) every 500ms after last change
- Live preview canvas on the right re-renders by drawing the current video frame into a 9:16 canvas using the interpolated crop coords

**Step 4 — Subtitle Style**
- Render a small preview by spawning a quick ffmpeg job that processes ~3 seconds of video at low resolution → returns a preview MP4
- Backend caches the preview; re-renders when style changes
- For instant feedback on text-only changes (color, font), can do CSS overlay on top of the raw video as an approximation, then trust the ffmpeg render at export time

**Step 5 — Export**
- `POST /api/project/:id/render` with final settings
- Backend runs the ffmpeg compose pipeline
- WebSocket or SSE pushes progress percentage to the UI
- On completion, frontend shows download button (linking to `/api/project/:id/download`)

### Launch flow
```
$ short serve
[short] Starting server on http://localhost:8765
[short] Opening browser...
```
The CLI sub-commands (`short download`, `short transcribe`, etc.) still exist for scripted use and share the same pipeline modules under the hood.

---

## Technology Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Download | `yt-dlp` | Best YouTube support |
| Transcription | `faster-whisper` | Fast, word timestamps, local |
| UI backend | `FastAPI` + `uvicorn` | Lightweight, async, serves video with HTTP range |
| UI frontend | `React` + `Vite` + `TailwindCSS` | Fast dev loop, component reuse, clean styling |
| Frontend state | `Zustand` | Minimal boilerplate vs. Redux |
| Background jobs | FastAPI `BackgroundTasks` | Simple, no Celery needed for single-user app |
| Video processing | `ffmpeg` + `ffmpeg-python` | Industry standard, GPU support |
| Subtitle format | ASS with `\k` karaoke tags | Native ffmpeg per-word highlight |
| Language | Python 3.10+ (backend), TypeScript (frontend) | Best ecosystems for the respective layers |
| CLI | `click` | Clean argument handling for pipeline flags |

---

## Rough File Structure

```
short/
├── pyproject.toml              # Python package config (works on Windows + *nix)
├── main.py                     # CLI entrypoint, stage orchestration
├── pipeline/
│   ├── downloader.py           # yt-dlp wrapper
│   ├── transcriber.py          # faster-whisper, returns word timestamps
│   ├── recommender.py          # LLM-based short-clip recommender
│   ├── subtitle_builder.py     # word timestamps → ASS file with \k tags
│   └── composer.py             # ffmpeg: applies crop.json + ASS → output MP4
├── server/
│   ├── app.py                  # FastAPI app
│   ├── routes/
│   │   ├── project.py
│   │   ├── transcribe.py
│   │   ├── recommend.py
│   │   ├── crop.py
│   │   ├── style.py
│   │   └── render.py
│   ├── jobs.py                 # background task runner
│   └── project_store.py        # disk persistence for projects
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       ├── store.ts            # Zustand store
│       ├── pages/
│       │   ├── Input.tsx
│       │   ├── Transcript.tsx
│       │   ├── Recommend.tsx   # LLM short suggestions
│       │   ├── CropEditor.tsx
│       │   ├── Style.tsx
│       │   └── Export.tsx
│       └── components/
│           ├── VideoCanvas.tsx
│           ├── Timeline.tsx
│           └── KeyframeList.tsx
├── config.py                   # defaults (font, colors, resolution, model)
└── platform/
    ├── ffmpeg_locator.py       # finds ffmpeg.exe on Windows, ffmpeg on *nix
    └── paths.py                # platform-safe path handling (pathlib everywhere)
```

---

## Smart Short Recommender (LLM-powered)

A new pipeline stage that analyzes the full transcript and recommends which segments of a long video would make compelling shorts. Runs after transcription, before the crop editor.

### How it works

```
Full transcript (with timestamps)
    ↓
[Chunk transcript into ~3-5 minute windows]
    ↓
[For each chunk] LLM analyzes for "viral potential"
    ↓
[LLM returns] List of recommended clips with:
    - start_time, end_time
    - reason (why this clip is interesting)
    - hook (what grabs attention)
    - suggested_title
    - virality_score (0-100)
    ↓
UI displays ranked recommendations
```

### LLM prompt design
The LLM receives the transcript with timestamps and is asked to identify segments that:
- Contain a complete thought (don't start/end mid-sentence)
- Are between 15-90 seconds long (ideal for shorts)
- Have a hook in the first 3 seconds (question, surprising statement, strong claim)
- Contain emotional, controversial, educational, or surprising content
- Could stand alone without the surrounding context

**Example prompt structure:**
```
You are a viral video editor. Given this transcript with timestamps,
identify 3-10 segments that would make compelling YouTube Shorts.

For each segment, return:
- start: float (seconds)
- end: float (seconds)  (must be 15-90 seconds long)
- hook: string (what grabs attention in first 3 seconds)
- title_suggestion: string (under 60 characters)
- reason: string (why this works as a short)
- score: integer 0-100 (viral potential)

Transcript:
[0.0-3.2] So I was talking to my friend last week...
[3.2-7.8] and she told me something that completely changed...
...

Return as JSON array.
```

### LLM choice

**Path A default: Claude Haiku 4.5 (Anthropic API)**
- ~$0.015 per 30-min video, ~$0.04 per 2-hour video
- Quality dramatically better than any 7B local model
- Zero VRAM footprint — frees the GPU for Whisper + ffmpeg
- Setup: paste API key in settings screen, done

**Provider hierarchy:**
1. **Anthropic Claude Haiku 4.5** — default if `ANTHROPIC_API_KEY` env var or saved key exists
2. **OpenAI GPT-4o-mini** — alternative cloud, even cheaper (~$0.002/video) but slightly lower quality
3. **Ollama (local)** — fallback for offline / zero-cost use, requires sequential VRAM management (Path B)

**Provider abstraction:**
A common interface in `pipeline/recommender.py`:
```python
class Recommender(Protocol):
    def recommend(self, transcript: Transcript) -> list[ClipSuggestion]: ...

class AnthropicRecommender:    ...
class OpenAIRecommender:       ...
class OllamaRecommender:       ...
```
Switching providers is a config change, not a code change.

### API key handling (decision: environment variables only)

API keys are read **exclusively from environment variables** — the app never stores keys on disk.

| Provider | Env var |
|----------|---------|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Ollama | `OLLAMA_HOST` (defaults to `http://localhost:11434`) |

**Why env vars only:**
- No risk of accidentally committing a `config.yaml` with secrets
- No risk of leaking keys via screenshots of settings screens
- Works cleanly with `.env` files (loaded via `python-dotenv`)
- Works on shared machines without per-user encrypted storage
- Cross-platform with zero extra dependencies

**Setup options on Windows:**
- System-wide: `setx ANTHROPIC_API_KEY "sk-ant-..."` then restart the shell
- Per-session: `$env:ANTHROPIC_API_KEY = "sk-ant-..."` in PowerShell
- Project-local: create a `.env` file in the project folder; the app loads it on launch via `python-dotenv`

**First-run flow:**
- If no API key env var is detected on launch, the Recommend screen shows a setup card:
  - Instructions to set the env var (with copy-paste commands per OS)
  - A "Re-check" button to scan env vars again after the user sets them
  - A "Use Ollama instead" link (requires only `OLLAMA_HOST`, defaults to localhost)
  - A "Skip — pick clips manually" link

### Token / cost management
- Long videos can have 10k+ tokens of transcript — chunk by ~3-5 minute windows with small overlaps to avoid splitting clips
- LLM call is async; show progress in UI
- Cache results in `recommendations.json` so user can re-open without re-paying

### Recommend screen (Step 2.5 in the UI)
Inserted between transcription and crop editor:
- Lists all LLM-recommended clips as cards, ranked by score
- Each card shows: thumbnail (frame at midpoint), title suggestion, time range, hook, score, "why" expandable
- User clicks a clip → jumps directly to the crop editor pre-populated with that clip's start/end as the export range
- "Skip recommendations" button → user picks the range manually

### Stale recommendation handling (decision: explicit re-analyze)

If the user goes back and edits the transcript after recommendations were generated:
- Existing recommendations remain visible on the Recommend screen
- A yellow banner appears: **"Transcript has changed since these recommendations were generated. They may no longer reflect the current content."**
- A **"Re-analyze"** button is shown — clicking it re-runs the LLM call (and re-incurs API cost)
- No automatic re-run; the user controls when to spend the next API call

Stale state is tracked by storing a hash of the transcript at recommendation time:
```json
{
  "generated_at_transcript_hash": "sha256:abc123...",
  "clips": [ ... ]
}
```
On load, compare to the current transcript hash; if mismatched, set the stale flag.
- Can also bulk-select multiple clips to generate multiple shorts in one batch

### Output
Saved as `recommendations.json` in the project folder:
```json
{
  "clips": [
    {
      "id": "c1",
      "start": 142.5,
      "end": 205.8,
      "title": "The one mistake every beginner makes",
      "hook": "If you've ever tried to learn X, you've probably done this...",
      "reason": "Strong hook, concrete payoff, clear takeaway",
      "score": 87
    },
    ...
  ]
}
```

---

## Windows Compatibility

The app must run cleanly on Windows 10/11 (primary target — user's environment is Windows 11). All design choices below ensure this:

### Path & filesystem handling
- Use `pathlib.Path` exclusively — never raw string concatenation with `/` or `\\`
- Project data stored at `%APPDATA%\short\projects\<id>\` on Windows, `~/.short/projects/<id>/` on macOS/Linux — resolved via `platformdirs` library
- All ffmpeg / yt-dlp calls pass paths as quoted strings to handle spaces in user folder names (e.g., `C:\Users\Yan Fa\Videos\`)

### Dependencies that need Windows care
| Tool | Windows handling |
|------|-----------------|
| `ffmpeg` | Bundle a static `ffmpeg.exe` in the package OR detect existing install via PATH; if missing, prompt user with download instructions |
| `yt-dlp` | Installs as a Python package — no native build needed, works out of the box |
| `faster-whisper` | Has prebuilt Windows wheels via PyPI; CUDA support via `ctranslate2` works on Windows with NVIDIA GPUs |
| `mediapipe` | Not needed anymore (manual crop editor replaces face detection) |
| `Node.js` (for frontend build) | Required only at dev time; end users get the prebuilt static bundle |

### ffmpeg installation strategy
Option A (recommended): bundle ffmpeg
- Ship a `ffmpeg.exe` alongside the Python package (or download on first launch from a known mirror)
- Use `platform/ffmpeg_locator.py` to resolve the path: bundled binary first, then PATH, then error with download instructions

Option B: require user install
- Document a one-line PowerShell install: `winget install ffmpeg`
- Detect at startup and show a friendly error if missing

### Subprocess calls
- Always use `subprocess.run([...])` with list args, never `shell=True` — avoids cmd.exe quoting hell
- Set `creationflags=subprocess.CREATE_NO_WINDOW` on Windows to suppress console flashes when ffmpeg runs

### Line endings & encoding
- Open all text files with `encoding="utf-8"` explicitly — Windows defaults to cp1252 and will break with non-ASCII characters in transcripts
- Write SRT and ASS files with `\n` line endings (works on both platforms)

### Installation methods on Windows
1. **`pip install short-app`** then `short serve` — simplest, requires Python 3.10+
2. **Standalone installer** — PyInstaller-bundled `.exe` that includes Python runtime; user just double-clicks. Slightly bigger but more user-friendly
3. **Winget package** (long-term) — `winget install short`

### Testing
- CI runs on Windows, macOS, and Linux (GitHub Actions has all three) to catch path / subprocess regressions early

---

## Decisions Made

All v1 decisions, locked in:

**Stack (Path A — Hybrid):**
- **Whisper model:** `medium` with `int8` quantization, CUDA when available
- **GPU acceleration:** auto-detect NVIDIA; CPU fallback with smaller default model
- **LLM provider:** Anthropic Claude Haiku 4.5 as default; OpenAI GPT-4o-mini and Ollama as alternates
- **ffmpeg encoder:** `h264_nvenc` when available, `libx264` otherwise
- **ffmpeg bundling on Windows:** ship `ffmpeg.exe` with installer (~100 MB)

**Pipeline behavior:**
- **No SRT input:** transcription always runs locally — external SRT files are not accepted. Guarantees word-level timing and consistent format.
- **Crop model:** static segments with hard cuts between them. No interpolation. Each segment has a fixed crop window (e.g., 0–5s static at position A, 5–12s static at position B).
- **Crop compose:** segment-then-concat. One ffmpeg invocation per segment, then concat demuxer. Simple and debuggable.
- **Subtitle layout:** rolling window of 3–5 words with the currently-spoken word highlighted. Window size configurable (default 4).
- **Long-video chunking:** LLM recommender + manual range selection. No silence-detection fallback.
- **Stale recommendations:** preserve old recommendations; show a yellow "stale" banner with a manual "Re-analyze" button. Track via transcript hash.
- **API key storage:** environment variables only (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OLLAMA_HOST`). App never writes keys to disk. `.env` files supported via `python-dotenv`.

## Remaining Open Questions

None for v1 — all blocking decisions resolved. Items below are future enhancements, not v1 blockers:

- **Smooth crop interpolation** — if users request panning between crop positions instead of hard cuts, add as an optional toggle per segment boundary
- **Forced alignment for imported transcripts** — currently not needed since we don't accept external SRT, but could be useful if we ever add a "use a transcript I already paid for" workflow
- **Multi-language UI** — currently English-only; add i18n if user demand emerges
