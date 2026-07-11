# /watch

> 🎬 Video analysis skill for Hermes Agent — download, extract frames, get transcript, answer questions.

[![Hermes](https://img.shields.io/badge/Agent-Hermes-blue)](https://hermes-agent.nousresearch.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Hermes skill that watches videos for you. Downloads with yt-dlp, extracts scene-aware frames with ffmpeg, pulls the transcript from native captions (JSON3/VTT) with Whisper API fallback, and hands the result to your agent so it can answer questions about what's in the video.

## ✨ Features

- 🎬 **Frame extraction** — scene-aware or keyframe-only, with deduplication
- 📝 **Transcript** — JSON3 captions (free, word-level timing) → Whisper API fallback
- 🔍 **Detail modes** — `transcript` | `efficient` | `balanced` | `token-burner`
- 🎯 **Focus mode** — `--start`/`--end` for dense frames on a specific section
- ⏱️ **Transcript-cue frames** — `--timestamps` for moments the speaker flags
- 🧹 **Auto-cleanup** — downloaded video deleted after processing (saves 200MB–1GB)
- 🍪 **Auto cookies** — detects Chrome/Chromium for YouTube auth
- 📊 **Structured output** — Pydantic models, JSON + markdown reports

## 📦 Prerequisites

> **Good news:** `setup.py` now **auto-installs everything on Linux** (with sudo) and macOS (via brew). Just run the setup script and you're done — no manual steps needed on Ubuntu/Debian.

| Platform | Auto-install | Notes |
|----------|-------------|-------|
| **macOS** | ✅ via `brew install` | Requires Homebrew |
| **Linux (Debian/Ubuntu)** | ✅ via `apt` + standalone binaries | `sudo` required for ffmpeg only |
| **Linux (no sudo)** | ⚠️ partial | yt-dlp + deno install to `~/.local/bin` and `~/.deno/bin`; ffmpeg needs manual install |
| **Windows** | ❌ hints only | winget/pip commands printed |

### Required (video download + frame extraction)

| Dependency | Purpose | Install |
|------------|---------|---------|
| **Python 3.10+** | Script runtime | System default |
| **ffmpeg** + **ffprobe** | Frame extraction, audio processing | `sudo apt install ffmpeg` / `brew install ffmpeg` |
| **yt-dlp** | Video + subtitle download | `pipx install yt-dlp` / `brew install yt-dlp` |
| **pydantic** | Structured output models | `pip install pydantic` |

### Required for YouTube 2026+ (video download, not just transcripts)

YouTube now requires a JavaScript runtime and browser impersonation to download video streams. **Without these, transcripts still work but video downloads return HTTP 403.**

| Dependency | Purpose | Install |
|------------|---------|---------|
| **[Deno](https://deno.land)** | JS runtime for YouTube challenge solving | `curl -fsSL https://deno.land/install.sh \| sh` |
| **[curl_cffi](https://github.com/lexiforest/curl_cffi)** | Browser impersonation (bypasses bot detection) | `pip install --break-system-packages curl-cffi` |

After installing Deno, add it to your PATH:
```bash
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Optional (Whisper transcription fallback)

Only needed when videos have **no native captions** (rare for YouTube). Most YouTube videos have auto-generated captions — Whisper is rarely triggered.

| Dependency | Purpose | Get key at |
|------------|---------|------------|
| **Groq API key** | Whisper large-v3 (preferred, cheaper) | [console.groq.com/keys](https://console.groq.com/keys) |
| **OpenAI API key** | Whisper-1 (fallback) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |

### Optional (browser cookies)

Improves subtitle download reliability for age-restricted or private videos:
- Install Chrome/Chromium
- Log in to YouTube in the browser
- The script auto-detects cookies — no configuration needed

## 🚀 Installation

### Hermes CLI (Recommended)

```bash
hermes skill install watch
```

### Manual

```bash
# Clone into skills directory
git clone https://github.com/m1crodevil/hermes-video.git ~/.hermes/skills/content-creation/watch

# Run setup (auto-installs all deps on macOS + Linux, scaffolds config)
python3 ~/.hermes/skills/content-creation/watch/scripts/setup.py
```

## ⚙️ Post-Install Setup

After installation, run the setup script to verify everything:

```bash
python3 ~/.hermes/skills/content-creation/watch/scripts/setup.py --json
```

This checks:
- ✅ `ffmpeg` / `ffprobe` / `yt-dlp` installed
- ✅ `deno` available (for YouTube video downloads)
- ✅ `curl_cffi` importable (for browser impersonation)
- ✅ `~/.config/watch/.env` created (Whisper API keys go here)
- ✅ `~/.config/yt-dlp/config` created (YouTube 2026 flags)

### Configure Whisper (optional)

Edit `~/.config/watch/.env`:

```bash
# Add your API key (only needed for videos without captions)
GROQ_API_KEY=gsk_your_key_here
# or
OPENAI_API_KEY=sk-your_key_here
```

### Configure default detail mode (optional)

```bash
# In ~/.config/watch/.env
WATCH_DETAIL=balanced   # transcript | efficient | balanced | token-burner
```

## 📖 Usage

### As a Hermes skill

```
/watch https://youtu.be/abc123
/watch https://youtu.be/abc123 what language is this in?
/watch https://youtu.be/abc123 summarize the key points
```

### Direct script invocation

```bash
SKILL_DIR=~/.hermes/skills/content-creation/watch

# Full analysis (balanced detail, scene-aware frames)
python3 "${SKILL_DIR}/scripts/watch.py" "https://youtu.be/abc123"

# Transcript only (no frames, no video download)
python3 "${SKILL_DIR}/scripts/watch.py" "https://youtu.be/abc123" --detail transcript

# Focus on a section (denser frames)
python3 "${SKILL_DIR}/scripts/watch.py" "https://youtu.be/abc123" --start 2:00 --end 5:00

# With specific timestamps for speaker-flagged moments
python3 "${SKILL_DIR}/scripts/watch.py" "https://youtu.be/abc123" --timestamps 1:30,4:15,7:20

# Local file
python3 "${SKILL_DIR}/scripts/watch.py" /path/to/video.mp4
```

## 📊 Detail Modes

| Mode | Frames | Best for | Token cost |
|------|--------|----------|------------|
| `transcript` | 0 (transcript only) | Long videos, quick answers | ~5K |
| `efficient` | ≤50 keyframes | Fast overview | ~30K |
| `balanced` | ≤100 scene-aware | Most use cases (default) | ~60K |
| `token-burner` | uncapped | Maximum fidelity | ~100K+ |

## 🔧 Troubleshooting

### Video download fails with 403 Forbidden

YouTube 2026 requires Deno + curl_cffi. Check:

```bash
# Verify deno is installed and in PATH
which deno

# Verify curl_cffi is importable
python3 -c "import curl_cffi; print(curl_cffi.__version__)"

# Verify yt-dlp config exists
cat ~/.config/yt-dlp/config
```

### Subtitle download fails with 429

YouTube rate-limits subtitle requests. Wait a few minutes, or:

```bash
# Use browser cookies (requires Chrome logged into YouTube)
yt-dlp --cookies-from-browser chrome --write-auto-subs --skip-download URL
```

### No transcript available

Captions missing AND no Whisper key. Options:
1. Set up a Groq/OpenAI API key in `~/.config/watch/.env`
2. Run with `--detail balanced` for frames-only analysis
3. Run with `--no-whisper` to skip transcription entirely

## 📁 Directory Structure

```
skills/watch/
├── SKILL.md              # Skill definition (loaded by Hermes)
├── assets/
│   ├── README.md         # This file
│   └── CHANGELOG.md      # Version history
├── references/           # Detailed guides and pitfall docs
├── scripts/
│   ├── watch.py          # Entry point
│   ├── download.py       # yt-dlp wrapper (subs + video)
│   ├── frames.py         # ffmpeg frame extraction
│   ├── transcribe.py     # Caption selection + Whisper orchestration
│   ├── whisper.py        # Groq / OpenAI Whisper clients
│   ├── language.py       # Auto-detect video language for subs
│   ├── config.py         # Config reader (~/.config/watch/.env)
│   ├── models.py         # Pydantic output models
│   └── setup.py          # Preflight + installer
├── templates/            # Report templates
└── tests/                # pytest suite
```

## 🔒 Security

- **No video upload** — only extracted audio goes to Whisper API (and only when captions are missing)
- **No credentials stored** — API keys stay in `~/.config/watch/.env` (mode 0600)
- **Browser cookies read-only** — uses `--cookies-from-browser`, never writes to cookie store
- **Auto-cleanup** — downloaded video deleted after processing (unless `--keep-video`)

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 🙏 Credits

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — video + subtitle download
- **[ffmpeg](https://ffmpeg.org)** — frame extraction
- **[Groq](https://console.groq.com)** — Whisper API (preferred)
- **[OpenAI](https://platform.openai.com)** — Whisper API (fallback)
- **[Deno](https://deno.land)** — JS runtime for YouTube challenge solving
- **[curl_cffi](https://github.com/lexiforest/curl_cffi)** — browser impersonation
- **[Hermes Agent](https://hermes-agent.nousresearch.com)** — AI agent framework

---

**Built with ❤️ for the Hermes community**
