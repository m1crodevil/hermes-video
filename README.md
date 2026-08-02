# /watch — Video Analysis for AI Agents

> **It reads. It selects. It verifies.**
> Python-powered video analysis skill for Hermes Agent — transcript-first with auto-generated moment selection. Cross-references frames against captions to catch what either one misses.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Hermes Agent](https://img.shields.io/badge/Hermes-Agent-purple)](https://hermes-agent.nousresearch.com)
[![GitHub stars](https://img.shields.io/github/stars/m1crodevil/hermes-video)](https://github.com/m1crodevil/hermes-video/stargazers)
[![Version](https://img.shields.io/badge/version-2.2.0-blue)](https://github.com/m1crodevil/hermes-video/releases)

**Works with:** Hermes Agent · Claude Code · Codex · Cursor · Any AI agent that reads files

Paste a URL or a local path. Hermes fetches captions, downloads only the video sections it needs, extracts frames at key-moment timestamps, and cross-references the transcript against what's actually on screen. Auto-captions misspell names? It catches that. A claim doesn't match the visual? It flags that.

Zero config to start. `yt-dlp` and `ffmpeg` install on first run. Captions cover most public videos for free. Whisper API key is only needed when a video has no captions.

---

## Quick Install

```bash
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

**Analyze someone else's content.**
```bash
/watch https://youtu.be/abc what hook did they open with?
```

**Diagnose a bug from a video.**
```bash
/watch bug-repro.mov what's going wrong?
```

**Summarize a video.**
```bash
/watch https://youtu.be/abc summarize this
```

**Catch what captions get wrong.**
```bash
/watch https://youtu.be/abc are any names or terms misspelled in the captions?
```

---

## How It Works

`/watch` runs a **single-pass pipeline** — transcript first, then targeted frame extraction. No agent round-trip required:

```
Video URL / local path
    ↓
Step 1: Transcript + Metadata (no video download)
    ├── Fetch captions via yt-dlp (JSON3 preferred)
    ├── Parse transcript with word-level timing
    ├── Whisper fallback (if no captions, API key available)
    └── Write report.json + transcript.json (deduped — prompts reference the file)
    ↓
Step 2: Auto-Generated Key Moments (single-pass)
    ├── Evenly-spaced transcript segments (or ffmpeg scene detection)
    ├── Writes key_moments.json + moments_prompt.txt
    └── Agent MAY refine the JSON and re-run — the pipeline doesn't block on it
    ↓
Step 3: Frame Extraction (targeted)
    ├── 2-second sections per moment — NOT the full video
    ├── Fallback: full video download (cached in ~/.cache/watch)
    └── One frame per LLM-selected timestamp
    ↓
Step 4: Batch Vision Verification
    ├── All frames verified in ONE batch vision call (vision_batch.json)
    ├── Cross-reference transcript × visuals × metadata
    ├── Identify ASR errors, speaker identity, visual context
    └── Generate article-quality analysis
    ↓
Cleanup video file (save disk space)
```

**Why single-pass?** Moment selection used to block on an agent writing `key_moments.json` between runs. The pipeline now auto-generates heuristic moments (evenly spaced transcript segments, or ffmpeg scene changes when there's no transcript), so a run completes end-to-end in one invocation. Re-runs with an edited `key_moments.json` download only 2-second sections at the selected timestamps instead of the full video.

### Cross-Reference Methodology

Every vision finding is classified:

- ✅ **confirmed** — vision matches transcript
- 🔧 **corrected** — vision shows different spelling/entity
- ❓ **fabrication** — claim has no visual evidence
- ⚠️ **unverified** — cannot determine from visual alone
- 🔸 **partial** — partially shown on screen

---

## Moment Selection Criteria

Key moments are selected using **8 criteria** (agent-guided when refining, heuristic when auto-generated):

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

**Default 50 moments, no maximum** — scale with video duration and content density (`--min-moments` to adjust).

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

## Key Features

| Feature | Detail |
|---------|--------|
| **Single-pass pipeline** | Auto-generates key moments — no blocking agent round-trip |
| **Section downloads** | 2s sections per moment instead of the full video on re-runs |
| **Video cache** | SHA-256 keyed, 10GB LRU cache in `~/.cache/watch/` |
| **Batch vision** | ALL frames in one vision call — not N serial calls |
| **Transcript-first** | JSON3 captions with word-level timing |
| **Cross-reference** | Frames vs transcript — catches errors |
| **Comprehensive output** | Article-quality analysis |
| **Zero config** | Auto-installs on first run |
| **50+ platforms** | YouTube, TikTok, Vimeo, + more |
| **Focus mode** | `--start/--end` for specific sections |
| **Whisper fallback** | Groq ($0.004/min) or OpenAI |

---

## CLI Reference

```bash
# Basic usage
/watch https://youtu.be/dQw4w9WgXcQ what happens at the 30 second mark?
/watch https://www.tiktok.com/@user/video/123 summarize this
/watch ~/Movies/screen-recording.mp4 when does the UI break?
/watch https://vimeo.com/123 what tools does she mention?
```

| Flag | Description | Default |
|------|-------------|---------|
| `--detail` | Mode: `transcript-moments`, `screenshot-first`, `transcript`, `efficient`, `balanced`, `token-burner` | `transcript-moments` |
| `--timestamps T` | Comma-separated timestamps for frame extraction | none |
| `--min-moments N` | Minimum key moments to generate/select | 50 |
| `--max-moments N` | Maximum key moments for the analysis prompt | 15 |
| `--resolution W` | Frame width in pixels (128–4096) | 512 |
| `--start T` / `--end T` | Focus on a specific section (SS, MM:SS, HH:MM:SS) | full video |
| `--max-frames N` | Override frame cap | mode default |
| `--fps F` | Override auto-fps (max 2.0) | auto |
| `--out-dir DIR` | Custom working directory | temp dir |
| `--keep-video` | Retain downloaded video after processing | false |
| `--cookies` | Use Chrome cookies for yt-dlp (age-restricted videos) | false |
| `--no-cache` | Bypass the on-disk video cache, always download fresh | false |
| `--no-whisper` | Disable Whisper fallback transcription | false |
| `--whisper {groq,openai}` | Force a specific Whisper backend | groq→openai |
| `--auto-moments` | Write the moments prompt for agent refinement | false |
| `--output markdown\|json\|both` | Output format | both |
| `--stats` | Include analysis stats in output | false |
| `--stats-format telegram\|compact` | Stats formatting | telegram |

---

## Output Formats

| Format | Command | Use When |
|--------|---------|----------|
| Both (default) | `/watch URL question` | Agent reads markdown + JSON backup |
| JSON only | `/watch URL question --output json` | Programmatic processing |
| Markdown only | `/watch URL question --output markdown` | Direct reading |

The `WatchReport` includes: video metadata, extracted frames with timestamps, full transcript with word-level timing (when available from JSON3 captions), key moment metadata (auto-generated or LLM-selected moments with reasons), and warnings for missing transcript.

---

## Detail Modes

| Mode | Speed | Download | Best for |
|------|-------|----------|----------|
| `transcript-moments` | ~15s + frames | 2s sections | **DEFAULT** — comprehensive analysis |
| `screenshot-first` | ~35s | ~10MB | Long videos (>20 min) with captions |
| `transcript` | ~5s | 0MB | Dialogue-heavy, transcript-first |
| `efficient` | ~10-20s | full video | Quick overview, hard cuts |
| `balanced` | ~300s | full video | Most content, thorough |
| `token-burner` | ~500s+ | full video | Max fidelity, short videos |

Full-video downloads are cached (`~/.cache/watch/`, 10GB LRU), so repeat runs of any mode skip the network transfer entirely.

---

## API Keys & Configuration

Captions cover the majority of public videos for free. The Whisper fallback only kicks in when a video has no caption track.

| Capability | Requirement | Cost |
|------------|-------------|------|
| Download + native captions | `yt-dlp` + `ffmpeg` | Free |
| Auto-generated moment selection | Built into the pipeline | Free |
| Agent-driven moment refinement | Agent LLM (via Hermes) | Included |
| Whisper fallback (preferred) | [Groq API key](https://console.groq.com/keys) | ~$0.004/min |
| Whisper fallback (alt) | [OpenAI API key](https://platform.openai.com/api-keys) | Standard pricing |
| Disable Whisper | `--no-whisper` | Free, frames-only |

Config file: `~/.config/watch/.env`

```bash
GROQ_API_KEY=gsk_...        # Optional — for Whisper fallback
OPENAI_API_KEY=sk-...        # Optional — alternative Whisper provider
SETUP_COMPLETE=true
```

---

## Architecture

```
hermes-video/
├── src/watch/                # Modular package (source of truth)
│   ├── pipeline.py           # CLI entry + orchestration
│   ├── cache.py              # SHA-256 keyed video cache (10GB LRU)
│   ├── download.py           # yt-dlp wrapper + 2s section downloads
│   ├── moments.py            # Moment prompt generation + parsing
│   ├── vision_batch.py       # Batch vision verification payloads
│   ├── frames/               # Frame extraction (extract/metadata/scene/dedup)
│   └── ...
├── skills/watch/             # Installed skill (flat mirror of src/watch)
│   ├── SKILL.md              # Core skill (workflow + criteria)
│   ├── scripts/              # Flattened bundle — watch.py entry point
│   └── references/           # On-demand reference files
├── tests/
└── dist/watch.skill          # Built skill archive (gitignored)
```

`skills/watch/scripts/` is a flat mirror of `src/watch/` — regenerate it with `build-skill.sh` whenever the package changes, so the installed skill stays in sync.

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
- [m1crodevil/hermes-video-rs](https://github.com/m1crodevil/hermes-video-rs) — Rust version (faster startup, single binary)

---

## License

MIT. Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org). Whisper transcription via [Groq](https://groq.com) or [OpenAI](https://openai.com).

Original: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)
