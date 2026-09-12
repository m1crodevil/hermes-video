# /watch — Video Analysis for AI Agents

> Python-powered video analysis skill for Hermes Agent — Rust-parity single-pass pipeline.
> Downloads captions, falls back to Whisper, and extracts frames only at the timestamps the agent asks for.

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
/watch <url|path> --timestamps 0:30,1:45,3:00 [--resolution 512] [--output json|markdown|both]
```

The pipeline is now single-pass and agent-driven:

1. Fetch captions via `yt-dlp` (JSON3/VTT)
2. Fallback to Whisper if no captions and API key is set
3. Extract frames at agent-provided `--timestamps`
4. Emit `report.json` + Markdown

Pass `--no-whisper` to skip transcription fallback.

## Architecture

```
Video URL / local path
    ↓
Download captions + metadata (yt-dlp)
    ↓
Whisper fallback (if needed)
    ↓
Extract frames at --timestamps (ffmpeg)
    ↓
Emit report.json + report.md
```

## Development

```bash
python3 -m pytest tests/ -q
```

## Requirements

- Python 3.11+
- ffmpeg
- yt-dlp
- Groq or OpenAI API key (optional, for Whisper fallback)
