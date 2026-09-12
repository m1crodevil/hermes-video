# /watch — Video Analysis for AI Agents

> Python-powered video analysis skill for Hermes Agent — Rust-parity single-pass pipeline.
> Downloads captions, falls back to Whisper, and extracts frames at the timestamps the agent asks for.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Hermes Agent](https://img.shields.io/badge/Hermes-Agent-purple)](https://hermes-agent.nousresearch.com)
[![Version](https://img.shields.io/badge/version-2.3.0-blue)](https://github.com/m1crodevil/hermes-video/releases)

## Quick Install

```bash
hermes skill install watch
```

Or manually:

```bash
git clone https://github.com/m1crodevil/hermes-video.git
ln -s "$(pwd)/hermes-video/skills/watch" ~/.hermes/skills/content-creation/watch
```

## Usage

```bash
/watch <url|path> [--timestamps 0:30,1:45,3:00]
```

- If `--timestamps` is provided, frames are extracted at those timestamps.
- If `--timestamps` is omitted, the pipeline auto-selects 3 evenly-spaced timestamps (start, middle, end) when the video is available.
- If no video is available (e.g. transcript-only mode), only the transcript is returned.

The pipeline is single-pass and agent-driven:

1. Fetch captions + metadata via `yt-dlp` (JSON3/VTT)
2. Fallback to Whisper if no captions and a Groq/OpenAI API key is set
3. Extract frames at `--timestamps` (or auto-picked defaults) with `ffmpeg`
4. Emit `report.json` + Markdown

Pass `--no-whisper` to skip transcription fallback.

## Architecture

```
Video URL / local path
    ↓
Fetch captions + metadata (yt-dlp)
    ↓
Fetch video if needed for frame extraction
    ↓
Whisper fallback (if needed)
    ↓
Extract frames at --timestamps (ffmpeg)
    ↓
Emit report.json + report.md
```

## Development

```bash
python3 -m pytest tests/ -q   # 16 tests
```

## Requirements

- Python 3.11+
- ffmpeg
- yt-dlp
- Deno, Node, QuickJS, or Bun (for YouTube video downloads; captions work without it)
- Groq or OpenAI API key (optional, for Whisper fallback)

> **Note:** yt-dlp requires an external JavaScript runtime to download YouTube video streams. Install [Deno](https://deno.com/) (recommended) to enable frame extraction. Captions still work without it.
