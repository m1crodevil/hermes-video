# /watch — Comprehensive Video Analysis for AI Agents

> **Transcript-driven, agent-selected, full-coverage video analysis.** Paste a URL, get a thorough article-quality review.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Hermes Agent](https://img.shields.io/badge/Hermes-Agent-purple)](https://hermes-agent.nousresearch.com)
[![GitHub stars](https://img.shields.io/github/stars/m1crodevil/hermes-video)](https://github.com/m1crodevil/hermes-video/stargazers)
[![Version](https://img.shields.io/badge/version-2.1.0-blue)](https://github.com/m1crodevil/hermes-video/releases)

**Works with:** Hermes Agent · Claude Code · Codex · Cursor · Any AI agent that reads files

`/watch` delivers **comprehensive analysis** — not just frames and transcript, but a thorough review like reading a detailed article. The agent reads the full transcript, selects 21+ key moments using 8 selection criteria, extracts frames at those timestamps, and analyzes every single frame. The result: specific data, key arguments, important quotes, and clear conclusions.

Zero config to start. `yt-dlp` and `ffmpeg` install on first run. Captions cover most public videos for free. Whisper API key is only needed when a video has no captions.

---

## Quick Install

```
hermes skill install watch
```

Or manually:

```bash
git clone https://github.com/m1crodevil/hermes-video.git
ln -s "$(pwd)/hermes-video/skills/watch" ~/.hermes/skills/content-creation/watch
```

**First run** auto-installs everything — no manual setup required:

- **macOS** — `brew install ffmpeg yt-dlp`
- **Linux** — `apt install ffmpeg`, yt-dlp + deno via installer
- **Windows** — `winget` / `pip` commands printed

---

## What People Use It For

**Deep-dive analysis.** `/watch https://youtu.be/abc analyze this comprehensively`

**Research someone's arguments.** `/watch https://youtu.be/abc what are their main points and conclusions?`

**Fact-check claims.** `/watch https://youtu.be/abc what statistics and data do they cite?`

**Understand context.** `/watch https://youtu.be/abc what's the historical/political background?`

---

## How It Works

`/watch` runs a **two-pass workflow** — transcript first, then targeted frame extraction:

```
Video URL / local path
    ↓
Pass 1: Transcript + Metadata (no video download)
    ├── Fetch captions via yt-dlp (JSON3 preferred)
    ├── Parse transcript with word-level timing
    ├── Whisper fallback (if no captions, API key available)
    └── Write report.json with full transcript
    ↓
Pass 2: Agent-Driven Moment Selection
    ├── Agent reads FULL transcript (mandatory)
    ├── Selects 21+ key moments using 8 criteria
    ├── Writes key_moments.json
    └── Re-run with --timestamps → extract frames
    ↓
Pass 3: Comprehensive Analysis
    ├── Vision analyze EVERY frame (no skipping)
    ├── Cross-reference transcript × visuals × metadata
    ├── Identify ASR errors, speaker identity, visual context
    └── Generate article-quality analysis
    ↓
Cleanup video file (save disk space)
```

**Why two passes?** Pass 1 provides the full transcript for intelligent moment selection. Pass 2 extracts frames only at agent-selected moments — targeted at proper nouns, claims, deictic references, and topic changes. No wasted frames, no blind spots.

---

## Moment Selection Criteria

The agent selects key moments using **8 mandatory criteria**:

| # | Criteria | What to look for |
|---|----------|------------------|
| 1 | **Proper nouns** | Names, brands, titles that might be misspelled in auto-captions |
| 2 | **Claims/statistics** | Numbers, prices, dates, percentages that need fact-checking |
| 3 | **Deictic references** | "ini", "itu", "lihat", "this", "that", "look at this" |
| 4 | **Topic transitions** | Moments where conversation shifts to a new subject |
| 5 | **Key arguments** | Important conclusions, controversial statements, strong opinions |
| 6 | **Visual context** | Moments where visuals change interpretation |
| 7 | **Speaker identity** | Speaker changes or identity matters (multi-speaker videos) |
| 8 | **Entity recognition** | Brand names, product names, on-screen text, logos |

**Minimum 21 moments, no maximum** — scale with video duration and content density.

---

## Key Features

| Feature | Detail |
|---------|--------|
| **Agent-driven moments** | Agent selects 21+ key moments using 8 criteria — no hardcoded logic |
| **Full frame coverage** | Analyze EVERY extracted frame — never skip to "save API calls" |
| **Transcript-first** | JSON3 captions with word-level timing — fast, no video download needed |
| **Comprehensive output** | Article-quality analysis with specific data, quotes, conclusions |
| **Zero config** | Auto-installs yt-dlp + ffmpeg on first run — no manual setup |
| **50+ platforms** | YouTube, TikTok, Vimeo, Instagram, Loom, + hundreds more via yt-dlp |
| **Focus mode** | `--start/--end` for dense extraction on specific sections |
| **Whisper fallback** | Groq ($0.004/min) or OpenAI when no captions available |
| **Optional stats** | `--stats` shows processing time, frame count, token estimate |

---

## Output Format

The output focuses on **analysis content**, not process:

```
🎬 **[Video Title]**
Channel: [Uploader] · Duration: [time]

---

[Comprehensive analysis — key findings, main arguments, conclusions, important quotes]

---
```

**What's included:**
- All main points from transcript
- Specific data (numbers, names, dates, statistics)
- Historical/political context (if relevant)
- Key quotes from speakers
- Clear conclusions and recommendations

**What's NOT included:**
- Process artifacts (cross-reference tables, correction sections)
- Stats block (only when user specifically requests)
- Frame-by-frame notes

---

## Analysis Quality Checklist

Before delivering, the agent verifies:

- [ ] All main points from transcript are covered
- [ ] Specific data (numbers, names, dates) are included
- [ ] Historical/political context is explained (if relevant)
- [ ] Key quotes from speakers are included
- [ ] Conclusions and recommendations are clear
- [ ] Output language matches transcript language
- [ ] NO process artifacts in the output

---

## CLI Reference

```
/watch https://youtu.be/dQw4w9WgXcQ what happens at 30 seconds?
/watch ~/Movies/screen-recording.mp4 what's going wrong?
/watch https://youtu.be/abc --timestamps 1:30,2:45,10
/watch https://youtu.be/abc --start 2:15 --end 2:45
```

| Flag | Description | Default |
|------|-------------|---------|
| `--detail` | Mode: `transcript-moments`, `screenshot-first`, `transcript`, `efficient`, `balanced`, `token-burner` | `transcript-moments` |
| `--timestamps T` | Comma-separated timestamps for frame extraction | none |
| `--min-moments N` | Minimum key moments to select (agent-driven) | 21 |
| `--resolution W` | Frame width in pixels (128–4096) | 512 |
| `--start T` / `--end T` | Focus on a specific section (SS, MM:SS, HH:MM:SS) | full video |
| `--max-frames N` | Override frame cap | mode default |
| `--fps F` | Override auto-fps (max 2.0) | auto |
| `--out-dir DIR` | Custom working directory | temp dir |
| `--keep-video` | Retain downloaded video after processing | false |
| `--cookies` | Use Chrome cookies for yt-dlp (age-restricted videos) | false |
| `--no-whisper` | Disable Whisper fallback transcription | false |
| `--output markdown\|json\|both` | Output format | both |
| `--stats` | Include analysis stats in output | false |

---

## Detail Modes

| Mode | Speed | Data | Best for |
|------|-------|------|----------|
| `transcript-moments` | ~15s + frames | Minimal | **DEFAULT** — comprehensive analysis |
| `screenshot-first` | ~35s | ~10MB | Long videos (>20 min) with captions |
| `transcript` | ~5s | 0MB | Dialogue-heavy, transcript-first |
| `efficient` | ~10-20s | 413MB | Quick overview, hard cuts |
| `balanced` | ~300s | 413MB | Most content, thorough |
| `token-burner` | ~500s+ | 413MB | Max fidelity, short videos |

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

## Skill Architecture

The skill uses **progressive disclosure** — the agent loads only what it needs:

```
Tier 1: skill_view('watch') → Core workflow + moment selection criteria
Tier 2: skill_view('watch', file_path) → Reference files on-demand
```

**Core** (`SKILL.md`): Workflow steps, moment selection criteria, output format, CLI options
**References** (`references/`): Detailed workflows, pitfalls, visual verification rules

This keeps token cost minimal while providing full context when needed.

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

- [bradautomates/claude-video](https://github.com/bradautomates/claude-video) — Original inspiration (7.6k stars)

---

## License

MIT. Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org). Whisper transcription via [Groq](https://groq.com) or [OpenAI](https://openai.com).

Original: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)
