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

Downloads a video, pulls its transcript, extracts frames at agent-provided timestamps, and hands everything to the agent.

## When to use /watch

- User shares a video URL (YouTube, TikTok, Vimeo, etc.)
- User shares a local video file path (.mp4, .mov, .mkv, .webm)
- User asks about video content ("what happens in this video?")

## Usage

```bash
python3 "${SKILL_DIR}/scripts/cli.py" <url-or-path> --timestamps 0:30,1:45 [--resolution 512] [--output json|markdown|both]
```

## Setup

Run setup once:

```bash
python3 "${SKILL_DIR}/scripts/setup.py" --json
```

## Pipeline

1. Download captions + metadata via `yt-dlp`
2. Parse JSON3/VTT transcript
3. Whisper fallback if no captions and API key available
4. Extract frames at `--timestamps`
5. Emit `report.json` + Markdown
