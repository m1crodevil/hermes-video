---
name: watch
version: "3.0.0"
description: Watch a video (URL or local path). Downloads with yt-dlp, extracts frames with ffmpeg, pulls the transcript from captions (or Whisper fallback), and hands the result to your agent.
argument-hint: "<video-url-or-path> [--timestamps T1,T2,...]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/m1crodevil/hermes-video
repository: https://github.com/m1crodevil/hermes-video
author: m1crodevil
license: MIT
user-invocable: true
platforms: [macos, linux]
metadata:
  hermes:
    tags: [video, analysis, multimodal]
    category: content-creation
    requires_toolsets: [terminal]
---

# /watch (Python)

**Version:** 3.0.0  
**Implementation:** Python (`hermes-video`)  
**Not `/watch2`:** `/watch2` is the Rust implementation from `hermes-video-rs`. They are functionally equivalent but written in different languages.

Downloads a video, pulls its transcript, detects scenes, and extracts frames only when the agent asks for specific timestamps.

## When to use /watch

- User shares a video URL (YouTube, TikTok, Vimeo, etc.)
- User shares a local video file path (.mp4, .mov, .mkv, .webm)
- User asks about video content ("what happens in this video?")

## Usage

**Always invoke the Python `/watch` skill through the skill's own `cli.py`. Never call `watch2` or any other binary directly.**

```bash
python3 "${SKILL_DIR}/scripts/cli.py" <url-or-path> [--timestamps 0:30,1:45] [--resolution 512] [--output json|markdown|both]
```

- If `--timestamps` is provided, frames are extracted at those timestamps.
- If `--timestamps` is omitted, no frames are extracted. The agent must run a second pass with `--timestamps`.

## Setup preflight

```bash
python3 "${SKILL_DIR}/scripts/setup.py" --json
```

Branch on JSON fields:

- `can_proceed: true` → binaries present, config exists. Proceed.
- `first_run: true` → run installer, scaffold `.env`, write `SETUP_COMPLETE=true`.
- `can_proceed: false` → environment regressed. Run installer.

## Pipeline

1. Download video + captions in a single yt-dlp pass (JSON3/VTT)
2. Parse transcript
3. Whisper fallback if no captions and API key available
4. Detect scene boundaries with `ffmpeg scdet`
5. Extract frames at `--timestamps` with `ffmpeg`
6. Emit `report.json` + Markdown

## CLI flags

| Flag | Description |
|------|-------------|
| `--timestamps` | Comma-separated timestamps for frame extraction |
| `--resolution` | Frame width in pixels (default: 512) |
| `--out-dir` | Working directory (default: tmp) |
| `--keep-video` | Keep downloaded video |
| `--cookies` | Use Chrome cookies |
| `--cookies-file` | Path to cookies file |
| `--no-whisper` | Disable Whisper fallback |
| `--whisper` | Whisper backend: `groq` or `openai` |
| `--output` | Output format: `json`, `markdown`, or `both` |

## Requirements

- Python 3.11+
- ffmpeg
- yt-dlp
- Deno, Node, QuickJS, or Bun (for YouTube video downloads; captions work without it)
- Groq or OpenAI API key (optional, for Whisper fallback)

> **Note:** yt-dlp requires an external JavaScript runtime to download YouTube video streams. Install [Deno](https://deno.com/) (recommended) to enable frame extraction. Captions still work without it.
