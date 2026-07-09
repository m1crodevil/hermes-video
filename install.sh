#!/bin/bash
# hermes-video installer
# Installs the watch skill into ~/.hermes/skills/video/
# Usage: ./install.sh [--repo-path /path/to/repo]
#
# Run from the repo root, or pass --repo-path to specify the source repo.

set -e

REPO_DIR=""
CONFIG_DIR="$HOME/.config/watch"
SKILL_DIR="$HOME/.hermes/skills/video"

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --repo-path)
            REPO_DIR="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--repo-path /path/to/repo]"
            echo ""
            echo "Options:"
            echo "  --repo-path PATH   Path to the claude-video repo (default: script location)"
            echo "  -h, --help         Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--repo-path /path/to/repo]"
            exit 1
            ;;
    esac
done

# Resolve repo directory (follow symlinks to find actual script location)
if [ -z "$REPO_DIR" ]; then
    # Get the real directory where this script lives
    REPO_DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
fi

# Validate repo directory has expected files
if [ ! -d "$REPO_DIR/skills/watch" ]; then
    echo "❌ Could not find skills/watch/ in: $REPO_DIR"
    echo "   Make sure you're running this script from the repo root,"
    echo "   or pass --repo-path /path/to/claude-video"
    exit 1
fi

echo "🎬 Installing hermes-video..."
echo "   Source: $REPO_DIR"
echo "   Target: $SKILL_DIR"
echo ""

# ─── Check dependencies ───────────────────────────────────────────────
echo "Checking dependencies..."

MISSING=0

command -v ffmpeg >/dev/null 2>&1 || {
    echo "  ❌ ffmpeg not installed (required for video processing)"
    echo "     Install: sudo apt install ffmpeg  (Debian/Ubuntu)"
    MISSING=1
}

command -v yt-dlp >/dev/null 2>&1 || {
    echo "  ❌ yt-dlp not installed (required for video download)"
    echo "     Install: pip install yt-dlp  or  sudo apt install yt-dlp"
    MISSING=1
}

command -v python3 >/dev/null 2>&1 || {
    echo "  ❌ python3 not installed (required for skill scripts)"
    MISSING=1
}

if [ "$MISSING" -ne 0 ]; then
    echo ""
    echo "Please install missing dependencies and re-run."
    exit 1
fi

echo "  ✅ ffmpeg found: $(ffmpeg -version 2>&1 | head -1)"
echo "  ✅ yt-dlp found: $(yt-dlp --version 2>/dev/null)"
echo "  ✅ python3 found: $(python3 --version 2>&1)"
echo ""

# ─── Create skill directory structure ─────────────────────────────────
echo "Creating skill directory structure..."
mkdir -p "$SKILL_DIR"/{scripts,references,templates,assets}
echo "  ✅ $SKILL_DIR"
echo ""

# ─── Copy files ───────────────────────────────────────────────────────
echo "Installing skill files..."

# Skill definition
cp "$REPO_DIR/skills/watch/SKILL.md" "$SKILL_DIR/"
echo "  ✅ SKILL.md"

# Python scripts (skip __pycache__)
for script in "$REPO_DIR"/skills/watch/scripts/*.py; do
    [ -f "$script" ] || continue
    cp "$script" "$SKILL_DIR/scripts/"
    echo "  ✅ scripts/$(basename "$script")"
done

# Reference docs
for doc in "$REPO_DIR"/docs/*.md; do
    [ -f "$doc" ] || continue
    cp "$doc" "$SKILL_DIR/references/"
    echo "  ✅ references/$(basename "$doc")"
done

# Config templates
if [ -f "$REPO_DIR/.env.example" ]; then
    cp "$REPO_DIR/.env.example" "$SKILL_DIR/templates/"
    echo "  ✅ templates/.env.example"
fi

# Documentation assets
if [ -f "$REPO_DIR/README.md" ]; then
    cp "$REPO_DIR/README.md" "$SKILL_DIR/assets/"
    echo "  ✅ assets/README.md"
fi
if [ -f "$REPO_DIR/CHANGELOG.md" ]; then
    cp "$REPO_DIR/CHANGELOG.md" "$SKILL_DIR/assets/"
    echo "  ✅ assets/CHANGELOG.md"
fi
echo ""

# ─── Set permissions ──────────────────────────────────────────────────
echo "Setting permissions..."
chmod +x "$SKILL_DIR/scripts/"*.py 2>/dev/null || true
echo "  ✅ Executable permissions set"
echo ""

# ─── Create config directory ──────────────────────────────────────────
echo "Creating config directory..."
mkdir -p "$CONFIG_DIR"

# Create .env from template if it doesn't exist
if [ ! -f "$CONFIG_DIR/.env" ] && [ -f "$SKILL_DIR/templates/.env.example" ]; then
    cp "$SKILL_DIR/templates/.env.example" "$CONFIG_DIR/.env"
    echo "  ✅ Created $CONFIG_DIR/.env from template"
else
    echo "  ⏭  $CONFIG_DIR/.env already exists, skipping"
fi
echo ""

# ─── Check for API keys ──────────────────────────────────────────────
echo "Checking API configuration..."

if [ -z "$OPENCODE_API_KEY" ] && [ ! -f "$CONFIG_DIR/.env" ]; then
    echo "  ⚠️  No OPENCODE_API_KEY found"
    echo "     Set in $CONFIG_DIR/.env or export OPENCODE_API_KEY=..."
elif [ -f "$CONFIG_DIR/.env" ]; then
    if grep -q "your_opencode_api_key_here" "$CONFIG_DIR/.env" 2>/dev/null; then
        echo "  ⚠️  OPENCODE_API_KEY needs to be configured"
        echo "     Edit: $CONFIG_DIR/.env"
    else
        echo "  ✅ Config file found"
    fi
fi

# Check optional Whisper keys
if [ -z "$GROQ_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "  ℹ️  No Whisper API key set (optional, for videos without captions)"
    echo "     Set GROQ_API_KEY or OPENAI_API_KEY in $CONFIG_DIR/.env"
fi
echo ""

# ─── Verify setup ─────────────────────────────────────────────────────
echo "Verifying installation..."

PASS=0
FAIL=0

for f in \
    "$SKILL_DIR/SKILL.md" \
    "$SKILL_DIR/scripts/watch.py" \
    "$SKILL_DIR/scripts/config.py" \
    "$SKILL_DIR/scripts/download.py" \
    "$SKILL_DIR/scripts/frames.py" \
    "$SKILL_DIR/scripts/transcribe.py" \
    "$SKILL_DIR/scripts/opencode_client.py" \
    "$SKILL_DIR/scripts/env.py" \
    "$SKILL_DIR/templates/.env.example"; do
    if [ -f "$f" ]; then
        PASS=$((PASS + 1))
    else
        echo "  ❌ Missing: $f"
        FAIL=$((FAIL + 1))
    fi
done

echo "  Files verified: $PASS ok, $FAIL missing"
echo ""

# ─── Python dependency check (informational) ─────────────────────────
echo "Checking Python packages..."
for pkg in requests aiohttp; do
    if python3 -c "import $pkg" 2>/dev/null; then
        echo "  ✅ $pkg"
    else
        echo "  ⚠️  $pkg not installed (may be needed by some scripts)"
    fi
done
echo ""

# ─── Done ─────────────────────────────────────────────────────────────
if [ "$FAIL" -eq 0 ]; then
    echo "✅ hermes-video installed successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Edit $CONFIG_DIR/.env with your API key"
    echo "  2. In Hermes, use the 'watch' skill to analyze videos"
    echo ""
else
    echo "⚠️  Installation completed with $FAIL missing file(s)"
    echo "   Check the output above for details."
fi
