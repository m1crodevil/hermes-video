# /watch — Video Analysis for AI Agents

> **Agent-driven video analysis for Hermes Agent.** Paste any URL, get grounded answers from frames + transcript.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Hermes Agent](https://img.shields.io/badge/Hermes-Agent-purple)](https://hermes-agent.nousresearch.com)
[![GitHub stars](https://img.shields.io/github/stars/m1crodevil/hermes-video)](https://github.com/m1crodevil/hermes-video/stargazers)
[![Version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/m1crodevil/hermes-video/releases)

**Works with:** Hermes Agent · Claude Code · Codex · Any AI agent that reads files

Paste a URL or a local path. `/watch` fetches captions, downloads the video, extracts frames at agent-selected timestamps, and delivers a structured report. The agent reads `report.json`, selects key moments, and analyzes what's actually on screen and in the audio.

Zero config to start. `yt-dlp` and `ffmpeg` install on first run. Captions cover most public videos for free. Whisper API key is only needed when a video has no captions.

---

## Quick Install

**Hermes Agent (recommended):**

```
hermes skill install watch
```

**Manual:**

```bash
git clone https://github.com/m1crodevil/hermes-video.git
ln -s "$(pwd)/hermes-video/skills/watch" ~/.hermes/skills/content-creation/watch
```

**First run** auto-installs dependencies:

- **macOS** — `brew install ffmpeg yt-dlp`
- **Linux** — `apt install ffmpeg`, yt-dlp + deno via installer
- **Windows** — `winget` / `pip` commands printed

---

## What People Use It For

**Analyze someone else's content.** `/watch https://youtu.be/abc what hook did they open with?`

**Diagnose a bug from a video.** `/watch bug-repro.mov what's going wrong?`

**Summarize a video.** `/watch https://youtu.be/abc summarize this`

**Catch what captions get wrong.** `/watch https://youtu.be/abc are any names misspelled in the captions?`

---

## How It Works

`/watch` runs a **single linear pipeline** — no mode branching, no configuration trees:

```
Video URL / local path
    ↓
1. Fetch captions via yt-dlp (JSON3 preferred)
    ↓
2. Download video (720p) if frames needed
    ↓
3. Parse transcript from best-matching subtitle
    ↓
4. Whisper fallback (if no captions, API key available)
    ↓
5. Agent reads report.json → selects key moments
    ↓
6. Re-run with --timestamps → extract frames at those moments
    ↓
7. Agent vision-analyzes frames, cross-references transcript
    ↓
8. Cleanup video file (save disk space)
```

The binary handles data extraction only. All intelligence (moment selection, analysis, cross-referencing) is handled by the agent. No `moments_prompt.txt`, no `key_moments.json` — the agent reads `report.json` and decides what to analyze.

---

## Cross-Reference Methodology

Every vision finding is classified:

- ✅ **confirmed** — vision matches transcript
- 🔧 **corrected** — vision shows different spelling/entity
- ❓ **fabrication** — claim has no visual evidence
- ⚠️ **unverified** — cannot determine from visual alone
- 🔸 **partial** — partially shown on screen

---

## Skill Architecture

The skill uses **progressive disclosure** — the agent loads only what it needs:

```
Tier 1: skill_view('watch') → 203-line core (~800 tokens)
Tier 2: skill_view('watch', file_path) → reference files on-demand
```

**Core** (`SKILL.md`): Quick reference, output format, CLI options, configuration
**References** (`references/`): Detailed workflows, pitfalls, visual verification rules

This keeps token cost minimal (~800 tokens per invocation) while providing full context when needed.

---

## Key Features

| Feature | Detail |
|---------|--------|
| Transcript-first | JSON3 captions with word-level timing |
| Agent-driven | Agent selects key moments, no hardcoded logic |
| Timestamp extraction | Frames at agent-selected timestamps only |
| Multi-platform | YouTube, TikTok, Vimeo, local files, any URL yt-dlp supports |
| Whisper fallback | Groq ($0.004/min) or OpenAI — only when no captions |
| Zero config | Auto-installs yt-dlp + ffmpeg on first run |

---

## CLI Reference

```
/watch https://youtu.be/dQw4w9WgXcQ what happens at 30 seconds?
/watch ~/Movies/screen-recording.mp4 what's going wrong?
/watch https://youtu.be/abc --timestamps 1:30,2:45,10
```

| Flag | Description | Default |
|------|-------------|---------|
| `--timestamps T` | Comma-separated timestamps for frame extraction | none |
| `--detail transcript\|frames` | Transcript-only or frames mode | frames |
| `--resolution W` | Frame width in pixels (128–4096) | 512 |
| `--out-dir DIR` | Custom working directory | temp dir |
| `--keep-video` | Retain downloaded video after processing | false |
| `--cookies` | Use Chrome cookies for yt-dlp (age-restricted videos) | false |
| `--no-whisper` | Disable Whisper fallback transcription | false |
| `--output markdown\|json\|both` | Output format | both |
| `--start T` / `--end T` | Focus on a specific section | full video |

---

## Output Formats

| Format | Command | Use When |
|--------|---------|----------|
| Both (default) | `/watch URL question` | Agent reads markdown + JSON backup |
| JSON only | `/watch URL question --output json` | Programmatic processing |
| Markdown only | `/watch URL question --output markdown` | Direct reading |

The `WatchReport` includes: video metadata, extracted frames with timestamps, full transcript with word-level timing (when available from JSON3 captions), and warnings for missing transcript.

---

## API Keys & Configuration

Captions cover the majority of public videos for free. The Whisper fallback only kicks in when a video has no caption track.

| Capability | Requirement | Cost |
|------------|-------------|------|
| Download + native captions | `yt-dlp` + `ffmpeg` | Free |
| Agent-side moment selection | Agent LLM (via Hermes) | Included |
| Whisper fallback (preferred) | [Groq API key](https://console.groq.com/keys) | ~$0.004/min |
| Whisper fallback (alt) | [OpenAI API key](https://platform.openai.com/api-keys) | Standard pricing |
| Disable Whisper | `--no-whisper` | Free, frames-only |

Config file: `~/.config/watch/.env`

---

## Why Python?

| | Python (hermes-video) | Rust (hermes-video-rs) |
|---|----------------------|----------------------|
| **Startup** | ~500ms (Python import) | ~5ms |
| **Memory** | ~50-100MB | ~5-15MB |
| **Binary** | 0 (needs Python runtime) | ~6MB self-contained |
| **Install** | pip + yt-dlp + ffmpeg | Single binary + yt-dlp + ffmpeg + av-scenechange |
| **Hosts** | **50+ agent platforms** | Hermes Agent only |
| **Setup** | **Zero — auto-installs** | Manual cargo build |

**Choose Python when:** You need broad agent platform support (Claude Code, Codex, Cursor, 50+ others). No Rust toolchain required.

**Choose Rust when:** You need minimal footprint, fastest startup, or single-binary deployment.

---

## Architecture

```
skills/watch/
├── SKILL.md              # Core skill (203 lines, ~800 tokens)
├── references/           # On-demand reference files
│   ├── pitfalls.md
│   └── ...
└── scripts/
    ├── watch.py          # Entry point — pipeline orchestrator
    ├── download.py       # yt-dlp wrapper with retry
    ├── frames.py         # Timestamp-only frame extraction
    ├── transcribe.py     # Caption selection + Whisper orchestration
    ├── whisper.py        # Groq/OpenAI Whisper API
    ├── setup.py          # Preflight + auto-installer
    ├── config.py         # Configuration from .env
    ├── models.py         # Pydantic WatchReport model
    ├── language.py       # Language detection
    ├── errors.py         # Custom exception hierarchy
    └── stats_collector.py # Analysis statistics
```

---

## Development

```bash
# Run tests
python3 -m pytest tests/ -v

# Build skill bundle
bash skills/watch/scripts/build-skill.sh
```

---

## Related Projects

- [m1crodevil/hermes-video-rs](https://github.com/m1crodevil/hermes-video-rs) — Rust rewrite (faster startup, single binary)
- [bradautomates/claude-video](https://github.com/bradautomates/claude-video) — Original inspiration (7.6k stars)

---

## License

MIT. Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org). Whisper transcription via [Groq](https://groq.com) or [OpenAI](https://openai.com).

Original: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)
