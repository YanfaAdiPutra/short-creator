# YouTube-to-Short Converter — Feature List

## Modular Input Pipeline

The pipeline has discrete stages that cache their outputs. Re-running the app on the same project skips already-completed stages:

| Entry Point | What you provide |
|-------------|-----------------|
| Stage 1 | YouTube URL — app downloads, transcribes, recommends clips, edits, and composes |
| Stage 2 | Local video file — same flow, skipping the download |

External subtitle files (SRT/VTT) are **not** accepted as input — the app always generates its own transcript locally using Whisper. This guarantees precise word-level timing needed for the karaoke subtitle effect and reliable clip boundaries for the LLM recommender.

## Core Input Options
- YouTube URL → auto-download at highest available quality
- Local video file (MP4, MKV, MOV, etc.)

## Output Format
- 9:16 aspect ratio (vertical/portrait)
- Resolution targets: 1080×1920 (or scaled down proportionally)
- Output preserves original video bitrate and quality as closely as possible

## Crop Editor (Interactive UI)

The user manually defines the crop window in a visual editor before composing. The crop is built from **static segments with hard cuts** — no smooth panning.

### Static segment model
- The clip is divided into one or more segments along the timeline
- Each segment has a single fixed crop position (a static 9:16 window) that doesn't move within that segment
- Between segments the crop **jump-cuts** to the next position — no interpolation
- Example: 0–5 sec the crop sits at one spot, 5–12 sec it cuts to another spot, 12–30 sec it cuts to a third spot
- Simple, predictable, and easy for users to reason about

### Editor features:
- Displays the original video in a timeline-aware preview
- Overlays a draggable 9:16 bounding box on the source frame (like the reference screenshot — blue/white rectangle showing the active crop region)
- User drags the box to frame the subject for the currently-selected segment
- Timeline shows segment boundaries as vertical divider lines
- "+ Cut here" button at the current playhead position creates a new segment boundary
- Each segment is independently selectable; selecting one updates the editor to that segment's crop position
- Crop data is saved as a `.crop.json` file (list of `{start, end, x, y}` segments) so the user can reload and tweak later
- Live 9:16 preview on the side renders what the final output will look like

### Crop editor controls:
- Drag box to reposition (snaps to source-pixel coordinates)
- Scrub / playback to preview
- "+ Cut here" — add a new segment boundary at the current time
- Delete segment boundary (merges two adjacent segments)
- Reset to center-crop default
- "Preview output" button to see the final 9:16 with subtitles burned in

## Subtitles
- Auto-transcribe audio using local Whisper (word-level timestamps) — always runs
- Render subtitles on video using a **rolling 3–5 word window**:
  - At any moment, 3–5 words are visible on screen
  - The currently-spoken word is highlighted (active color), surrounding words appear muted for reading context
  - Window scrolls forward word by word in sync with speech
  - Window size configurable (3, 4, or 5 words; default 4)
- Burn subtitles directly into the video (no external subtitle file needed in final output)

## Subtitle Styling Options
- Font family (default: bold sans-serif)
- Font size scaling
- Active word color (highlighted) vs. inactive word color (muted)
- Window size (3 / 4 / 5 words visible at a time)
- Background box / drop shadow toggle
- Vertical position (top / middle / bottom)

## Smart Short Recommender (LLM-powered)

After transcription, the app uses an LLM to analyze the full transcript and recommend which parts of the long video would make the best shorts.

### Recommender output (per suggested clip):
- Start/end timestamps (constrained to 15-90 seconds)
- A "hook" — what grabs attention in the first 3 seconds
- A suggested title (under 60 characters)
- A reason explaining why this segment works as a short
- A virality score (0-100) so clips can be ranked

### How the user interacts:
- Recommendations appear as ranked cards (thumbnail + title + score) on a dedicated screen between Transcription and Crop Editor
- Clicking a card jumps to the Crop Editor with that clip's time range pre-loaded
- Multiple clips can be batch-selected to render several shorts in one run
- User can ignore recommendations entirely and pick a custom range

### LLM provider options:
- Anthropic Claude Haiku 4.5 (default, best quality-per-dollar)
- OpenAI GPT-4o-mini (cheapest cloud option)
- Local Ollama models (free, private, requires Ollama installed locally)

### API key handling:
- API keys are read **only from environment variables** — the app never stores them on disk
  - `ANTHROPIC_API_KEY` for Claude
  - `OPENAI_API_KEY` for GPT
  - `OLLAMA_HOST` for Ollama (defaults to `http://localhost:11434`)
- `.env` files in the project folder are supported (loaded automatically)
- Results cached in `recommendations.json` so re-opening a project doesn't re-pay

### Stale recommendations:
- If the user edits the transcript after recommendations were generated, old recommendations are preserved
- A yellow "stale" banner appears with a manual **"Re-analyze"** button — no automatic re-runs (avoids surprise API charges)

## Clip Selection
- **Smart mode (default):** use LLM recommendations to find compelling segments
- **Full video mode:** convert entire video to one short (or chunked into segments)
- **Segment mode:** specify a time range (start → end) to extract manually
- **Silence-detection fallback:** when no LLM is configured, split on natural pause points

## Quality Preservation
- No unnecessary re-encoding passes
- Use lossless intermediate when compositing subtitles, then encode final at target quality
- Configurable CRF / bitrate ceiling

## Output
- Single MP4 file (H.264 + AAC) ready for upload to YouTube Shorts, TikTok, Instagram Reels
- Optional: sidecar SRT/VTT subtitle file
- Saved `.crop.json` for re-use and future edits

## User Interface

The app is primarily a **web-based UI** that walks the user through the full pipeline. Layout follows a step/wizard pattern with a persistent left sidebar showing pipeline progress.

### UI Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Logo        Project: my_short_01            [Save] [Export]     │
├──────────┬───────────────────────────────────────────────────────┤
│ Sidebar  │                                                       │
│          │                                                       │
│ ① Input  │           ── Main workspace area ──                   │
│ ② Trans  │     (changes based on current step)                   │
│ ③ Recmd  │                                                       │
│ ④ Crop   │                                                       │
│ ⑤ Style  │                                                       │
│ ⑥ Export │                                                       │
│          │                                                       │
└──────────┴───────────────────────────────────────────────────────┘
```

### Step 1 — Input Screen
- Tabs: **"From YouTube"** | **"Upload Video"**
- YouTube tab: URL field, "Fetch video" button, progress bar during download
- Upload tab: drag-drop area + file picker
- After input is ready, "Continue" advances to transcription

### Step 2 — Transcription Screen
- Shows transcription progress in real time (model status, % done)
- After completion: editable transcript view with timestamps
- User can:
  - Correct misrecognized words inline
  - Re-split sentence boundaries
  - Skip this step if a valid SRT was provided
- "Continue" advances to the recommender

### Step 3 — Smart Recommender Screen
- Triggers an LLM call against the transcript to suggest 3–10 candidate short clips
- Displays results as ranked cards: thumbnail (frame at midpoint), title suggestion, time range, hook, virality score
- Each card has an expandable "Why this clip?" explanation
- Clicking a card jumps to the crop editor with that clip's time range pre-loaded
- Batch select multiple clips → render multiple shorts in one export
- "Skip & pick manually" button → goes straight to crop editor with full video range
- Settings link to pick LLM provider (Anthropic / OpenAI / Ollama) and enter API keys

### Step 4 — Crop Editor Screen (the screenshot reference)
- Main canvas: original video preview with overlaid **draggable 9:16 crop box** (blue/white outline)
- Right side: small 9:16 preview showing what the cropped output looks like in real time for the currently-selected segment
- Top controls: segment selector dropdown, undo/redo, device preview toggle, prev/next segment arrows (matching screenshot)
- Bottom: timeline with:
  - Scrubber + play/pause
  - **Segment dividers** drawn as vertical lines on the timeline
  - "+ Cut here" button at current playhead — creates a new segment boundary at this time
  - Click on a segment to select it; the crop box on the main canvas reflects that segment's position
- Side panel: list of all segments with their `start–end` times and `x` positions, editable numerically

### Step 5 — Subtitle Style Screen
- Live 9:16 preview with subtitles burned in
- Right panel of controls:
  - Font family dropdown (preset list of bold sans-serif fonts)
  - Font size slider
  - Active word color picker
  - Inactive word color picker
  - Background style: none / box / drop shadow
  - Vertical position: top / middle / bottom slider
  - Animation style: pop, slide, fade
- Changes reflected in preview within ~1 second

### Step 6 — Export Screen
- Output settings:
  - Resolution (1080×1920 default, options for 720×1280)
  - Quality (CRF slider or preset: high / medium / fast)
  - Save subtitle sidecar file (toggle)
  - Save crop.json (toggle)
- "Start render" button
- Render progress bar with ETA
- When done: download button + preview player + "Open in folder" link

### Cross-cutting UI elements
- **Project autosave** — every step saves state to disk so the user can close and reopen
- **Top-right Save / Export** — accessible from any step
- **Toast notifications** for completion / errors
- **Keyboard shortcuts**:
  - Space: play/pause in editor
  - C: cut — add a segment boundary at current playhead
  - ←/→: nudge crop box by 1px (shift for 10px)
  - Cmd/Ctrl+Z: undo

### CLI Fallback
For scripted / headless use, a CLI mirrors every stage:
- `short download <url>`
- `short transcribe <video>`
- `short recommend <video> --srt subs.srt` (LLM-based clip suggestions)
- `short edit <video>` (opens the editor in the browser)
- `short compose <video> --crop crop.json --srt subs.srt`
- `short serve` (launches the full web UI)

## Platform Support

The app is designed to run on **Windows 10 / 11** as the primary target, with macOS and Linux support as a side effect of using cross-platform tools.

### Windows-specific requirements:
- Works on Windows 10 and 11 (tested on Windows 11 Pro)
- Standard Windows install paths: project data stored under `%APPDATA%\short\`
- All paths handled via `pathlib` so spaces and non-ASCII characters in folder names work
- No reliance on cmd.exe shell features — subprocesses called directly with argument lists
- Handles Windows file path quirks: long paths (>260 chars), drive letters, UNC paths

### Installation options on Windows:
- **Pip install:** `pip install short-app` then `short serve` (requires Python 3.10+)
- **Standalone installer:** double-click `.exe` installer that bundles Python and dependencies (for non-technical users)
- **Bundled ffmpeg:** the installer ships with a working `ffmpeg.exe` so users don't need a separate install

### Cross-platform compatibility:
- macOS 12+ and recent Linux distros also work — the codebase doesn't use Windows-only APIs
- CI runs tests on all three platforms to prevent regressions
