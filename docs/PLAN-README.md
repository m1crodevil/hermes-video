# README.md Rewrite Plan

> **Goal:** Rewrite README.md to be accurate, comprehensive, and reflect the actual codebase

**Current Issues:** See review below

---

## Current Issues

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | Repo name `claude-video` in URLs | 🔴 | Change to `hermes-video` |
| 2 | Description mentions features not in codebase | 🔴 | Remove inaccurate claims |
| 3 | Directory structure wrong | 🔴 | Use actual file tree |
| 4 | Installation commands wrong | 🟡 | Fix to actual commands |
| 5 | Usage commands don't exist | 🔴 | Fix to actual usage |
| 6 | Hermes config format wrong | 🟡 | Fix to correct format |
| 7 | References to non-existent files | 🟡 | Remove or fix |
| 8 | Testing commands wrong | 🟡 | Fix to actual commands |

---

## Plan: Comprehensive README.md

### Section 1: Header & Badges

**Current:**
```markdown
# hermes-video
> 🎬 Video analysis for Hermes Agent powered by MiMo V2.5
[![Hermes](https://img.shields.io/badge/Agent-Hermes-blue)](...)
[![MiMo](https://img.shields.io/badge/Model-MiMo_V2.5-green)](...)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](...)
```

**New:**
```markdown
# hermes-video

> 🎬 Video analysis skill for Hermes Agent powered by MiMo V2.5

[![Hermes](https://img.shields.io/badge/Agent-Hermes-blue)](https://hermes-agent.nousresearch.com)
[![MiMo](https://img.shields.io/badge/Model-MiMo_V2.5-green)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-218%20passing-brightgreen)](#testing)
```

---

### Section 2: Description

**Current:**
> A Hermes skill for video analysis using Xiaomi's MiMo V2.5 multimodal model via OpenCode Zen. Analyzes videos frame-by-frame to find viral moments, engagement scoring, and TikTok clipping potential.

**New:**
> A Hermes skill for video analysis using Xiaomi's MiMo V2.5 multimodal model via OpenCode Zen. Downloads videos, extracts frames, transcribes audio, and analyzes content using MiMo's vision capabilities.

---

### Section 3: Features

**Current:**
- Full multimodal analysis — MiMo sees frames + reads transcript
- $0 cost — OpenCode Zen free tier
- 1M context window
- Hermes native
- Zero dependencies (optional: openai)
- Memory integration
- Cron support
- Structured output — Zod-validated JSON with TypeScript ❌
- Keyframe extraction — PySceneDetect ❌
- SRT integration ❌

**New:**
```markdown
## ✨ Features

- 🎬 **Full multimodal analysis** — MiMo sees frames + reads transcript
- 💰 **$0 cost** — OpenCode Zen free tier
- 🧠 **1M context window** — analyze long videos without splitting
- 🔧 **Hermes native** — works as Hermes skill
- 📦 **Zero dependencies** — stdlib Python only
- 🧠 **Memory integration** — saves analyses for future reference
- ⏰ **Cron support** — schedule regular video analysis
- 🎯 **Scene-aware frames** — smart frame extraction
- 📝 **Transcript support** — captions or Whisper fallback
```

---

### Section 4: Installation

**Current:**
```bash
# Wrong: references claude-video
git clone https://github.com/m1crodevil/claude-video.git ~/.hermes/skills/hermes-video
pip install openai  # Not needed
npm install  # Not needed
```

**New:**
```markdown
## 🚀 Installation

### Option 1: Hermes CLI (Recommended)

```bash
hermes skill add m1crodevil/hermes-video
```

### Option 2: Install Script

```bash
git clone https://github.com/m1crodevil/hermes-video.git
cd hermes-video
./install.sh
```

### Option 3: Manual

```bash
git clone https://github.com/m1crodevil/hermes-video.git
cd hermes-video
mkdir -p ~/.hermes/skills/video/{scripts,references,templates,assets}
cp skills/watch/SKILL.md ~/.hermes/skills/video/
cp skills/watch/scripts/*.py ~/.hermes/skills/video/scripts/
```

### Dependencies

Required:
- Python 3.11+
- ffmpeg (for frame extraction)
- yt-dlp (for video download)

Optional:
- Groq API key (for Whisper transcription)
- OpenAI API key (alternative Whisper backend)
```

---

### Section 5: Configuration

**Current:**
```yaml
# Wrong format
skills:
  - video-analysis-mimo
env:
  OPENCODE_ZEN_API_KEY: "your-api-key"
```

**New:**
```markdown
## ⚙️ Configuration

### 1. Set API Key

```bash
# Option A: Environment variable
export OPENCODE_API_KEY="your-api-key"

# Option B: Config file
mkdir -p ~/.config/watch
cat > ~/.config/watch/.env << 'EOF'
OPENCODE_API_KEY=your-api-key
OPENCODE_MODEL=mimo-v2.5-free
EOF
```

### 2. Optional: Whisper (for videos without captions)

```bash
# Get free Groq API key at https://console.groq.com/keys
echo "GROQ_API_KEY=your-groq-key" >> ~/.config/watch/.env
```

### 3. Verify Setup

```bash
python3 ~/.hermes/skills/video/scripts/setup.py --check
```
```

---

### Section 6: Usage

**Current:**
```bash
# Wrong: commands don't exist
python3 scripts/mimo_video_pipeline.py /path/to/video.mp4
python3 mimo-video-analyzer/analyze.py video.mp4 --fps 0.25
npx tsx mimo-video-analyzer/analyze-zod.ts keyframes_dir/ video_url
```

**New:**
```markdown
## 📖 Usage

### Via Hermes Chat

```
/watch https://youtu.be/VIDEO_ID summarize this
```

### Via CLI

```bash
# Basic analysis
python3 ~/.hermes/skills/video/scripts/watch.py https://youtu.be/VIDEO_ID

# With question
python3 ~/.hermes/skills/video/scripts/watch.py https://youtu.be/VIDEO_ID --engine opencode --question "summarize this"

# Focused analysis
python3 ~/.hermes/skills/video/scripts/watch.py https://youtu.be/VIDEO_ID --start 1:00 --end 2:00

# Transcript only (cheapest)
python3 ~/.hermes/skills/video/scripts/watch.py https://youtu.be/VIDEO_ID --detail transcript
```

### Engine Options

```bash
# Claude mode (default) - prints markdown report
/watch https://youtu.be/VIDEO_ID

# MiMo mode - analyzes via API
/watch --engine opencode --question "what happens at 2:30?" https://youtu.be/VIDEO_ID
```
```

---

### Section 7: Detail Modes

**Current:**
```markdown
| Mode | FPS | Tokens/min | Best For |
|------|-----|------------|----------|
| Quick scan | 0.125 | 1,050 | Long videos, overview |
| Balanced | 0.25 | 2,100 | Most use cases |
| Detailed | 0.5 | 4,200 | Short videos, deep analysis |
| Maximum | 1.0 | 8,400 | Critical moments, max detail |
```

**New:**
```markdown
## 📊 Detail Modes

| Mode | Frames | Speed | Best For |
|------|--------|-------|----------|
| `transcript` | 0 | ~4.5s | Cheapest, text-only |
| `efficient` | 50 | ~0.5s | Fast scan |
| `balanced` | 100 | ~21s | Default, good balance |
| `token-burner` | uncapped | ~21s | Full coverage |

### Frame Budget by Duration

| Duration | Default Frames | Coverage |
|----------|----------------|----------|
| ≤30s | ~30 | Dense |
| 30s - 1min | ~40 | Dense |
| 1 - 3min | ~60 | Comfortable |
| 3 - 10min | ~80 | Sparse |
| >10min | 100 (capped) | Use `--start`/`--end` |
```

---

### Section 8: Hermes Integration

**Current:**
```python
# Wrong paths and formats
results automatically saved to ~/.hermes/memories/video_analysis/
```

**New:**
```markdown
## 🔗 Hermes Integration

### Memory

Video analyses are automatically saved to Hermes memory:

```python
# Recall previous analyses
hermes chat "What videos have I analyzed about Python?"
```

### Cron Jobs

Schedule regular video analysis:

```bash
# Create via Hermes
hermes cron create daily-tech-news \
  --schedule "0 9 * * *" \
  --prompt "Analyze https://youtu.be/NEWS_VIDEO and summarize key points"
```

### Skill Bundles

Combine with other skills:

```bash
# Use the video-research bundle
/video-research https://youtu.be/VIDEO_ID analyze this thoroughly
```
```

---

### Section 9: Directory Structure

**Current:**
```
hermes-video/
├── scripts/
│   ├── mimo_video_pipeline.py      # ❌ Doesn't exist
│   └── mimo_video_test.py          # ❌ Doesn't exist
├── mimo-video-analyzer/            # ❌ Doesn't exist
│   ├── analyze.py                  # ❌ Doesn't exist
│   ├── analyze-zod.ts              # ❌ Doesn't exist
│   └── test_limit.py               # ❌ Doesn't exist
├── clipping-pipeline/              # ❌ Doesn't exist
│   └── schema.py                   # ❌ Doesn't exist
├── skills/
│   └── watch/                      # ✅ Exists
├── docs/                           # ✅ Exists
└── README.md
```

**New:**
```
hermes-video/
├── skills/watch/
│   ├── SKILL.md                    # Hermes skill contract
│   └── scripts/
│       ├── watch.py                # Entry point
│       ├── download.py             # yt-dlp wrapper
│       ├── frames.py               # ffmpeg frame extraction
│       ├── transcribe.py           # VTT parser
│       ├── whisper.py              # Groq/OpenAI client
│       ├── config.py               # Configuration
│       ├── env.py                  # Environment loading
│       ├── errors.py               # Custom exceptions
│       ├── types.py                # Type definitions
│       ├── opencode_client.py      # MiMo V2.5 client
│       ├── hermes_memory.py        # Memory integration
│       └── hermes_cron.py          # Cron integration
├── tests/
│   ├── conftest.py                 # Test fixtures
│   ├── test_types.py               # Type tests
│   ├── test_env.py                 # Env tests
│   ├── test_config.py              # Config tests
│   └── test_opencode_client.py     # Client tests
├── docs/
│   ├── PLAN-MIMO.md                # MiMo integration plan
│   ├── PLAN-REFACTOR.md            # Refactoring plan
│   └── PLAN-REBRAND.md             # Rebranding plan
├── skill-bundles/
│   └── video-research.yaml         # Skill bundle
├── .env.example                    # Environment template
├── manifest.json                   # Skill manifest
├── install.sh                      # Install script
├── SECURITY.md                     # Security policy
├── LICENSE                         # MIT License
└── README.md                       # This file
```

---

### Section 10: Testing

**Current:**
```bash
# Wrong
python3 -m pytest tests/
npm test  # Doesn't exist
python3 mimo-video-analyzer/test_limit.py  # Doesn't exist
```

**New:**
```markdown
## 🧪 Testing

### Run Tests

```bash
# Run all tests (218 tests)
python3 -m pytest tests/ -v

# Run specific test files
python3 -m pytest tests/test_types.py -v
python3 -m pytest tests/test_env.py -v
python3 -m pytest tests/test_opencode_client.py -v
```

### Test Coverage

- `test_types.py` — 110 tests (dataclasses, exceptions, protocols)
- `test_env.py` — 35 tests (environment loading)
- `test_opencode_client.py` — 61 tests (API client)
- `test_config.py` — 12 tests (configuration)
```

---

### Section 11: Documentation

**Current:**
```markdown
- **[SKILL.md](.hermes/skills/video-processing/video-analysis-mimo/SKILL.md)** — ❌ Wrong path
- **[references/](.hermes/skills/video-processing/video-analysis-mimo/references/)** — ❌ Wrong path
  - `clipping-pipeline-schema.md` — ❌ Doesn't exist
  - `pyscenedetect-quickref.md` — ❌ Doesn't exist
  - `keyframe-analysis-benchmarks.md` — ❌ Doesn't exist
  - `claude-video-reference.md` — ❌ Doesn't exist
```

**New:**
```markdown
## 📚 Documentation

- **[SKILL.md](skills/watch/SKILL.md)** — Full skill documentation
- **[PLAN-MIMO.md](docs/PLAN-MIMO.md)** — MiMo integration plan
- **[PLAN-REFACTOR.md](docs/PLAN-REFACTOR.md)** — Refactoring plan
- **[PLAN-REBRAND.md](docs/PLAN-REBRAND.md)** — Rebranding plan
- **[SECURITY.md](SECURITY.md)** — Security policy
- **[Hermes Docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)** — Hermes skills guide
```

---

### Section 12: Security

**Current:** Mostly correct

**New:**
```markdown
## 🔒 Security

### API Key Protection

- **Never commit** API keys to git
- Store in `~/.config/watch/.env` (gitignored)
- Use environment variables in CI/CD
- Rotate keys periodically

### Video Privacy

- Videos are processed locally
- Only frames are sent to MiMo API (if using opencode engine)
- No video data stored on external servers
- Delete local copies after analysis if needed

### Best Practices

- Use `--detail transcript` for sensitive content
- Review analysis results before sharing
- Use `--no-whisper` to avoid audio upload
```

---

### Section 13: Contributing

**Current:**
```bash
# Wrong URLs
git clone https://github.com/your-username/claude-video.git
```

**New:**
```markdown
## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** changes (`git commit -m 'Add amazing feature'`)
4. **Push** to branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/hermes-video.git
cd hermes-video

# Run tests
python3 -m pytest tests/ -v
```

### Code Style

- Python: PEP 8, type hints, docstrings
- Follow existing patterns in the codebase
- Add tests for new features
```

---

### Section 14: License & Credits

**Current:** Mostly correct

**New:**
```markdown
## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 🙏 Credits

- Original: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)
- MiMo integration: [m1crodevil](https://github.com/m1crodevil)
- Model: [Xiaomi MiMo V2.5](https://huggingface.co/XiaomiMiMo/MiMo-V2.5)
- Agent: [Hermes Agent](https://hermes-agent.nousresearch.com)
- API: [OpenCode Zen](https://opencode.ai)

---

**Built with ❤️ for the Hermes community**
```

---

## Summary of Changes

| Section | Current | New |
|---------|---------|-----|
| Header | 3 badges | 5 badges |
| Description | Misleading | Accurate |
| Features | 10 (3 wrong) | 9 (all accurate) |
| Installation | Wrong commands | Correct commands |
| Configuration | Wrong format | Correct format |
| Usage | Wrong commands | Correct commands |
| Detail Modes | Wrong table | Correct table |
| Directory Structure | Wrong paths | Correct paths |
| Testing | Wrong commands | Correct commands |
| Documentation | Wrong paths | Correct paths |
| Security | Mostly correct | Enhanced |
| Contributing | Wrong URLs | Correct URLs |
| Credits | Incomplete | Complete |

---

## Execution

1. **Rewrite README.md** with all corrections
2. **Commit** with message: `docs: rewrite README with accurate information`
3. **Push** to GitHub

**Ready to execute?** 🚀
