---
name: watch
version: "2.3.0"
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

# /watch

Downloads a video, pulls its transcript, extracts frames at the timestamps the agent asks for, and hands everything to the agent.

## When to use /watch

- User shares a video URL (YouTube, TikTok, Vimeo, etc.)
- User shares a local video file path (.mp4, .mov, .mkv, .webm)
- User asks about video content ("what happens in this video?")

## Usage

```bash
python3 "${SKILL_DIR}/scripts/cli.py" <url-or-path> [--timestamps 0:30,1:45] [--resolution 512] [--output json|markdown|both]
```

- If `--timestamps` is provided, frames are extracted at those timestamps.
- If `--timestamps` is omitted, the pipeline auto-selects 3 evenly-spaced timestamps (start, middle, end) when the video is available.
- If no video is available (e.g. transcript-only mode), only the transcript is returned.

### Behavior when `/watch <url>` is invoked without timestamps

The Python `/watch` skill defaults to auto-selecting start, middle, and end timestamps when the video file can be obtained. It does not wait for the user to provide timestamps before extracting frames. Captions-only output only occurs when the video stream itself is unavailable.

## Setup preflight

```bash
python3 "${SKILL_DIR}/scripts/setup.py" --json
```

Branch on JSON fields:

- `can_proceed: true` → binaries present, config exists. Proceed.
- `first_run: true` → run installer, scaffold `.env`, write `SETUP_COMPLETE=true`.
- `can_proceed: false` → environment regressed. Run installer.

## Pipeline

1. Download captions + metadata via `yt-dlp` (JSON3/VTT)
2. Parse transcript
3. Whisper fallback if no captions and API key available
4. Extract frames at `--timestamps` with `ffmpeg`
5. Emit `report.json` + Markdown

## Requirements

- Python 3.11+
- ffmpeg
- yt-dlp
- Deno, Node, QuickJS, or Bun (for YouTube video downloads; captions work without it)
- Groq or OpenAI API key (optional, for Whisper fallback)

> **Note:** yt-dlp requires an external JavaScript runtime to download YouTube video streams. Install [Deno](https://deno.com/) (recommended) to enable frame extraction. Captions still work without it.
