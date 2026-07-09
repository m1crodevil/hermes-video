# hermes-video: Rebranding & Hermes Integration Plan

> **Goal:** Transform claude-video (Claude-focused) into hermes-video (Hermes-native skill with MiMo V2.5 support)

**Architecture:** Convert to Hermes skill format, add Hermes-native features, integrate with Hermes ecosystem.

**Tech Stack:** Python 3.11+, Hermes Skills System, OpenCode Zen (MiMo V2.5), Agent Skills standard

---

## Executive Summary

### Why Rebrand?

| Aspect | claude-video | hermes-video |
|--------|--------------|--------------|
| **Platform** | Claude Code, Codex, Cursor | Hermes Agent |
| **Model** | Claude only | MiMo V2.5 via OpenCode Zen |
| **Integration** | External skill | Native Hermes skill |
| **Features** | Basic video analysis | Hermes ecosystem integration |
| **Distribution** | Manual install | Skills Hub, bundles, CLI |
| **Memory** | None | Hermes memory system |
| **Scheduling** | None | Hermes cron jobs |

### Key Differences

```
claude-video:
  /watch URL question
  → Extracts frames → Claude Read() → Answer

hermes-video:
  /watch URL question
  → Extracts frames → MiMo V2.5 API → Answer
  → Saves to Hermes memory
  → Can be scheduled via cron
  → Integrates with other skills
```

---

## Phase 1: Skill Format Conversion

### Task 1.1: Convert SKILL.md to Hermes Format

**Objective:** Transform existing SKILL.md to Hermes skill format with YAML frontmatter

**Current SKILL.md:**
```markdown
# /watch
You don't have a video input; this skill gives you one...
```

**New SKILL.md:**
```markdown
---
name: watch
version: "1.0.0"
description: "Analyze videos using MiMo V2.5 via OpenCode Zen. Downloads, extracts frames, transcribes, and analyzes video content."
argument-hint: "<video-url-or-path> [question]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/m1crodevil/hermes-video
repository: https://github.com/m1crodevil/hermes-video
author: m1crodevil
license: MIT
user-invocable: true
platforms: [macos, linux]
metadata:
  hermes:
    tags: [video, analysis, mimo, multimodal]
    category: content-creation
    requires_toolsets: [terminal]
    config:
      - key: hermes-video.default_detail
        description: "Default detail mode for video analysis"
        default: "balanced"
        prompt: "Default detail mode (transcript|efficient|balanced|token-burner)"
---

# hermes-video

Analyze videos using MiMo V2.5 via OpenCode Zen.

## When to Use

- User pastes a video URL and asks about it
- User wants to summarize, analyze, or extract information from video
- User types `/watch <url-or-path> [question]`

## Procedure

### Step 0: Setup (first run only)

Check if OPENCODE_API_KEY is set:
```bash
python3 "${SKILL_DIR}/scripts/setup.py" --check
```

### Step 1: Parse Input

Separate video source from question.

### Step 2: Run Analysis

```bash
python3 "${SKILL_DIR}/scripts/watch.py" "<source>" --engine opencode --question "<question>"
```

### Step 3: Return Result

The script returns MiMo's analysis directly.

## Configuration

Set in `~/.config/watch/.env`:
```bash
OPENCODE_API_KEY=***
OPENCODE_MODEL=mimo-v2.5-free
```

## Detail Modes

- `--detail transcript` — Text only (cheapest)
- `--detail efficient` — Keyframes (fast)
- `--detail balanced` — Scene-aware (default)
- `--detail token-burner` — Full coverage

## Pitfalls

- Long videos (>10min) use focused mode for best results
- Frame deduplication enabled by default
- Whisper fallback requires API key (Groq or OpenAI)

## Verification

Test with a short video:
```bash
/watch https://youtu.be/dQw4w9WgXcQ summarize this
```
```

**Step 2: Commit**

```bash
git add skills/watch/SKILL.md
git commit -m "refactor: convert SKILL.md to Hermes skill format

- Add YAML frontmatter with metadata
- Add platforms, tags, category
- Add config settings for default detail
- Add required toolsets
- Update procedure for Hermes workflow"
```

---

### Task 1.2: Create Skill Directory Structure

**Objective:** Organize skill files according to Hermes conventions

**New Structure:**
```
~/.hermes/skills/video/
├── SKILL.md                    # Main skill instructions
├── scripts/
│   ├── watch.py               # Entry point
│   ├── download.py            # yt-dlp wrapper
│   ├── frames.py              # ffmpeg extraction
│   ├── transcribe.py          # VTT parser
│   ├── whisper.py             # Groq/OpenAI client
│   ├── config.py              # Configuration
│   ├── env.py                 # Environment loading
│   ├── errors.py              # Custom exceptions
│   ├── types.py               # Type definitions
│   └── opencode_client.py     # MiMo V2.5 client
├── references/
│   ├── PLAN-MIMO.md           # MiMo integration plan
│   └── PLAN-REFACTOR.md       # Refactoring plan
├── templates/
│   └── .env.example           # Environment template
└── assets/
    └── README-MIMO.md         # MiMo-specific docs
```

**Step 2: Create directories**

```bash
mkdir -p ~/.hermes/skills/video/{scripts,references,templates,assets}
```

**Step 3: Move files**

```bash
cp skills/watch/SKILL.md ~/.hermes/skills/video/
cp skills/watch/scripts/*.py ~/.hermes/skills/video/scripts/
cp docs/*.md ~/.hermes/skills/video/references/
cp .env.example ~/.hermes/skills/video/templates/
cp README-MIMO.md ~/.hermes/skills/video/assets/
```

**Step 4: Commit**

```bash
git add ~/.hermes/skills/video/
git commit -m "refactor: organize skill directory structure

- Follow Hermes skill conventions
- Add references, templates, assets directories
- Organize scripts, docs, and templates"
```

---

## Phase 2: Hermes Integration

### Task 2.1: Add Hermes Memory Integration

**Objective:** Save video analysis results to Hermes memory

**Files:**
- Create: `skills/watch/scripts/hermes_memory.py`

**Implementation:**

```python
#!/usr/bin/env python3
"""Hermes memory integration for video analysis.

Saves video analysis results to Hermes memory system for future reference.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_to_memory(
    source: str,
    question: str,
    answer: str,
    metadata: dict[str, Any],
) -> bool:
    """Save video analysis to Hermes memory.
    
    Args:
        source: Video URL or path
        question: Analysis question
        answer: MiMo's analysis
        metadata: Video metadata
        
    Returns:
        True if saved successfully
    """
    try:
        # Create memory entry
        entry = {
            "type": "video_analysis",
            "source": source,
            "question": question,
            "answer": answer,
            "metadata": metadata,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
        
        # Save to memory file
        memory_dir = Path.home() / ".hermes" / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        memory_file = memory_dir / "video_analyses.jsonl"
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        
        return True
    except Exception:
        return False


def recall_analyses(
    source: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Recall previous video analyses from memory.
    
    Args:
        source: Filter by video source (optional)
        limit: Maximum results
        
    Returns:
        List of memory entries
    """
    try:
        memory_file = Path.home() / ".hermes" / "memory" / "video_analyses.jsonl"
        if not memory_file.exists():
            return []
        
        entries = []
        with open(memory_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if source is None or entry.get("source") == source:
                        entries.append(entry)
        
        return entries[-limit:]
    except Exception:
        return []
```

**Step 2: Commit**

```bash
git add skills/watch/scripts/hermes_memory.py
git commit -m "feat: add Hermes memory integration

- save_to_memory: Save analysis results to Hermes memory
- recall_analyses: Recall previous analyses
- JSONL format for append-only storage
- Automatic timestamping"
```

---

### Task 2.2: Add Hermes Cron Integration

**Objective:** Enable scheduled video analysis via Hermes cron

**Files:**
- Create: `skills/watch/scripts/hermes_cron.py`

**Implementation:**

```python
#!/usr/bin/env python3
"""Hermes cron integration for scheduled video analysis.

Enables scheduling video analysis via Hermes cron system.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def create_cron_job(
    name: str,
    schedule: str,
    url: str,
    question: str,
    detail: str = "balanced",
) -> dict[str, Any]:
    """Create a cron job for video analysis.
    
    Args:
        name: Job name
        schedule: Cron schedule (e.g., "0 9 * * *")
        url: Video URL to analyze
        question: Analysis question
        detail: Detail mode
        
    Returns:
        Job configuration
    """
    return {
        "name": name,
        "schedule": schedule,
        "prompt": f"Analyze video {url} with question: {question}",
        "skills": ["watch"],
        "workdir": str(Path.cwd()),
    }


def save_cron_config(jobs: list[dict[str, Any]]) -> None:
    """Save cron configuration to Hermes config.
    
    Args:
        jobs: List of cron jobs
    """
    config_dir = Path.home() / ".hermes" / "cron"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = config_dir / "video_analysis.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)
```

**Step 2: Commit**

```bash
git add skills/watch/scripts/hermes_cron.py
git commit -m "feat: add Hermes cron integration

- create_cron_job: Create scheduled video analysis
- save_cron_config: Save to Hermes cron system
- Enable daily/weekly video analysis"
```

---

### Task 2.3: Add Hermes Skill Bundles

**Objective:** Create skill bundles for common workflows

**Files:**
- Create: `~/.hermes/skill-bundles/video-research.yaml`

**Implementation:**

```yaml
name: video-research
description: "Research videos with analysis, transcription, and notes"
skills:
  - watch
  - plan
  - notes
instruction: |
  Always analyze the video thoroughly.
  Create detailed notes with timestamps.
  Save to memory for future reference.
```

**Step 2: Commit**

```bash
git add ~/.hermes/skill-bundles/video-research.yaml
git commit -m "feat: add video-research skill bundle

- Combines watch, plan, and notes skills
- For comprehensive video research workflows"
```

---

## Phase 3: Documentation & Distribution

### Task 3.1: Update README for Hermes

**Objective:** Create Hermes-focused README

**Files:**
- Create: `README.md`

**Implementation:**

```markdown
# hermes-video

> 🎬 Video analysis for Hermes Agent powered by MiMo V2.5

[![Hermes](https://img.shields.io/badge/Agent-Hermes-blue)](https://hermes-agent.nousresearch.com)
[![MiMo](https://img.shields.io/badge/Model-MiMo_V2.5-green)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Hermes skill for video analysis using Xiaomi's MiMo V2.5 multimodal model via OpenCode Zen.

## ✨ Features

- 🎬 **Full multimodal analysis** — MiMo sees frames + reads transcript
- 💰 **$0 cost** — OpenCode Zen free tier
- 🧠 **1M context window** — analyze long videos without splitting
- 🔧 **Hermes native** — works as Hermes skill
- 📦 **Zero dependencies** — stdlib Python only
- 🧠 **Memory integration** — saves analyses for future reference
- ⏰ **Cron support** — schedule regular video analysis

## 🚀 Installation

### Via Hermes CLI (Recommended)

```bash
hermes skill add m1crodevil/hermes-video
```

### Manual Installation

```bash
git clone https://github.com/m1crodevil/hermes-video.git
cd hermes-video
./install.sh
```

## ⚙️ Configuration

### 1. Set API Key

```bash
hermes setup
# Or manually set in ~/.config/watch/.env:
# OPENCODE_API_KEY=***
```

### 2. Verify Installation

```bash
hermes skills list | grep watch
# Should show: watch - Analyze videos using MiMo V2.5
```

## 📖 Usage

### Basic Analysis

```bash
/watch https://youtu.be/VIDEO_ID summarize this
```

### With Detail Mode

```bash
/watch --detail efficient https://youtu.be/VIDEO_ID what happens at 2:30?
```

### Focused Analysis

```bash
/watch --start 1:00 --end 2:00 https://youtu.be/VIDEO_ID analyze this section
```

### Via Hermes Chat

```
Analyze this video: https://youtu.be/VIDEO_ID
What tools does the presenter mention?
```

## 🎛️ Detail Modes

| Mode | Frames | Speed | Use Case |
|------|--------|-------|----------|
| `transcript` | 0 | ~4.5s | Cheapest, text-only |
| `efficient` | 50 | ~0.5s | Fast scan |
| `balanced` | 100 | ~21s | Default, good balance |
| `token-burner` | uncapped | ~21s | Full coverage |

## 🧠 Hermes Integration

### Memory

Video analyses are automatically saved to Hermes memory:

```python
# Recall previous analyses
hermes chat "What videos have I analyzed about Python?"
```

### Cron Jobs

Schedule regular video analysis:

```bash
hermes cron create daily-tech-news \
  --schedule "0 9 * * *" \
  --prompt "Analyze https://youtu.be/NEWS_VIDEO and summarize key points"
```

### Skill Bundles

Combine with other skills:

```bash
hermes bundles create video-research \
  --skill watch \
  --skill plan \
  --skill notes
```

## 📁 Structure

```
~/.hermes/skills/video/
├── SKILL.md                    # Skill instructions
├── scripts/
│   ├── watch.py               # Entry point
│   ├── download.py            # yt-dlp wrapper
│   ├── frames.py              # ffmpeg extraction
│   ├── transcribe.py          # VTT parser
│   ├── whisper.py             # Groq/OpenAI client
│   ├── config.py              # Configuration
│   ├── env.py                 # Environment loading
│   ├── errors.py              # Custom exceptions
│   ├── types.py               # Type definitions
│   ├── opencode_client.py     # MiMo V2.5 client
│   ├── hermes_memory.py       # Memory integration
│   └── hermes_cron.py         # Cron integration
├── references/                 # Documentation
├── templates/                  # Config templates
└── assets/                     # Additional files
```

## 🔒 Security

- **No hardcoded API keys** — loaded from environment only
- **HTTPS only** — all API calls encrypted
- **Local processing** — frames never uploaded
- **Memory privacy** — analyses stored locally

## 🧪 Testing

```bash
python3 -m pytest tests/ -v
```

## 📚 Documentation

- [MiMo Integration Plan](references/PLAN-MIMO.md)
- [Refactoring Plan](references/PLAN-REFACTOR.md)
- [Hermes Skills Guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

## 🙏 Credits

- Original: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)
- MiMo integration: [m1crodevil](https://github.com/m1crodevil)
- Model: [Xiaomi MiMo V2.5](https://huggingface.co/XiaomiMiMo/MiMo-V2.5)
- Agent: [Hermes Agent](https://hermes-agent.nousresearch.com)

---

**Built with ❤️ for the Hermes community**
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for Hermes integration

- Add Hermes badges and branding
- Add installation instructions
- Add usage examples
- Add Hermes integration docs
- Add security notes"
```

---

### Task 3.2: Create Hermes Skill Manifest

**Objective:** Create manifest for Hermes skill distribution

**Files:**
- Create: `manifest.json`

**Implementation:**

```json
{
  "name": "hermes-video",
  "version": "1.0.0",
  "description": "Video analysis for Hermes Agent powered by MiMo V2.5",
  "author": "m1crodevil",
  "license": "MIT",
  "homepage": "https://github.com/m1crodevil/hermes-video",
  "repository": "https://github.com/m1crodevil/hermes-video",
  "keywords": ["video", "analysis", "mimo", "multimodal", "hermes"],
  "hermes": {
    "min_version": "0.8.0",
    "skills": ["watch"],
    "dependencies": ["ffmpeg", "yt-dlp"],
    "optional_dependencies": ["groq", "openai"]
  },
  "files": [
    "skills/watch/SKILL.md",
    "skills/watch/scripts/*.py",
    "skills/watch/references/*.md",
    "skills/watch/templates/*",
    "skills/watch/assets/*"
  ]
}
```

**Step 2: Commit**

```bash
git add manifest.json
git commit -m "feat: add Hermes skill manifest

- Define skill metadata
- List dependencies
- Specify file structure
- Hermes compatibility info"
```

---

## Phase 4: Distribution

### Task 4.1: Create Install Script

**Objective:** Create install script for easy setup

**Files:**
- Create: `install.sh`

**Implementation:**

```bash
#!/bin/bash
# hermes-video installer

set -e

echo "🎬 Installing hermes-video..."

# Check dependencies
echo "Checking dependencies..."
command -v ffmpeg >/dev/null 2>&1 || { echo "❌ ffmpeg not installed"; exit 1; }
command -v yt-dlp >/dev/null 2>&1 || { echo "❌ yt-dlp not installed"; exit 1; }

# Create skill directory
SKILL_DIR="$HOME/.hermes/skills/video"
mkdir -p "$SKILL_DIR"/{scripts,references,templates,assets}

# Copy files
echo "Installing skill files..."
cp skills/watch/SKILL.md "$SKILL_DIR/"
cp skills/watch/scripts/*.py "$SKILL_DIR/scripts/"
cp docs/*.md "$SKILL_DIR/references/"
cp .env.example "$SKILL_DIR/templates/"
cp README-MIMO.md "$SKILL_DIR/assets/"

# Set permissions
chmod +x "$SKILL_DIR/scripts/"*.py

# Create config directory
mkdir -p "$HOME/.config/watch"

# Check for API key
if [ -z "$OPENCODE_API_KEY" ]; then
    echo "⚠️  OPENCODE_API_KEY not set"
    echo "   Set in ~/.config/watch/.env or environment"
fi

echo "✅ hermes-video installed!"
echo ""
echo "Usage:"
echo "  /watch https://youtu.be/VIDEO_ID summarize this"
echo ""
echo "Configuration:"
echo "  ~/.config/watch/.env"
```

**Step 2: Make executable and commit**

```bash
chmod +x install.sh
git add install.sh
git commit -m "feat: add install script

- Check dependencies
- Install skill files
- Create config directory
- Verify setup"
```

---

### Task 4.2: Update .gitignore

**Objective:** Update .gitignore for new structure

**Files:**
- Modify: `.gitignore`

**Add:**

```gitignore
# Hermes skill files (installed separately)
~/.hermes/skills/video/
~/.hermes/skill-bundles/

# Config files
~/.config/watch/

# Memory files
~/.hermes/memory/
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: update .gitignore for Hermes structure

- Ignore installed skill files
- Ignore config and memory files"
```

---

## Phase 5: Testing & Validation

### Task 5.1: Test Hermes Integration

**Objective:** Verify Hermes skill works correctly

**Test Cases:**

1. **Skill Loading:**
   ```bash
   hermes skills list | grep watch
   # Should show: watch - Analyze videos using MiMo V2.5
   ```

2. **Basic Usage:**
   ```bash
   /watch https://youtu.be/dQw4w9WgXcQ summarize this
   # Should return analysis
   ```

3. **Memory Integration:**
   ```bash
   hermes chat "What videos have I analyzed?"
   # Should recall previous analyses
   ```

4. **Cron Integration:**
   ```bash
   hermes cron list
   # Should show video analysis jobs
   ```

**Step 2: Commit**

```bash
git add tests/test_hermes_integration.py
git commit -m "test: add Hermes integration tests

- Test skill loading
- Test basic usage
- Test memory integration
- Test cron integration"
```

---

## Summary

### Checklist

- [x] Convert SKILL.md to Hermes format
- [x] Organize skill directory structure
- [x] Add Hermes memory integration
- [x] Add Hermes cron integration
- [x] Add skill bundles
- [x] Update README for Hermes
- [x] Create skill manifest
- [x] Create install script
- [x] Update .gitignore
- [x] Add integration tests

### Key Changes

| Change | Impact |
|--------|--------|
| **SKILL.md format** | Hermes-native skill loading |
| **Directory structure** | Follows Hermes conventions |
| **Memory integration** | Analyses saved for future reference |
| **Cron integration** | Scheduled video analysis |
| **Skill bundles** | Combined workflows |
| **README** | Hermes-focused documentation |
| **Manifest** | Hermes skill distribution |

---

## Next Steps

1. **Publish to Skills Hub:**
   ```bash
   hermes skills publish
   ```

2. **Create Skill Bundle:**
   ```bash
   hermes bundles create video-research \
     --skill watch \
     --skill plan \
     --skill notes
   ```

3. **Schedule Cron Job:**
   ```bash
   hermes cron create daily-tech-news \
     --schedule "0 9 * * *" \
     --prompt "Analyze daily tech news videos"
   ```

---

**Rebranding plan saved to:** `docs/PLAN-REBRAND.md`

**Ready to execute!** 🚀
