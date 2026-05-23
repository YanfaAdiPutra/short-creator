# short-creator

Turn long YouTube videos into 9:16 shorts with auto subtitles, smart clip recommendations, and a visual crop editor.

## Features

- YouTube URL or local video file as input
- Local Whisper transcription with word-level timestamps
- LLM-powered "best clips" recommender (Claude / GPT / Ollama)
- Visual crop editor with static-segment, jump-cut crop windows (9:16 output)
- Rolling-window karaoke subtitles burned into the final video
- Hardware-accelerated H.264 encoding via NVENC where available

See [FEATURES.md](./FEATURES.md) and [IDEATION.md](./IDEATION.md) for the full design.

## Quick start

```bash
pip install -e .
short serve
```

Then open `http://localhost:8765` in your browser.

## Configuration

API keys are read from environment variables — the app never stores them on disk:

```bash
# Pick one
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export OLLAMA_HOST=http://localhost:11434
```

A `.env` file in the project folder works too (loaded via `python-dotenv`).

## Requirements

- Python 3.10+
- `ffmpeg` on PATH (or bundled — see installer)
- NVIDIA GPU recommended (Whisper transcription + NVENC encoding)

## CLI

```bash
short download <url>                     # download a YouTube video
short transcribe <video>                 # run Whisper on a local file
short recommend <video>                  # LLM clip suggestions
short edit <video>                       # open the crop editor in browser
short compose <video> --crop crop.json   # render the final short
short serve                              # launch the full web UI
```

## License

MIT
