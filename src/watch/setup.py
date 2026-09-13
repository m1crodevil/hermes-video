#!/usr/bin/env python3
"""Setup / preflight for /watch (Rust parity).

Modes:
  setup.py --check      Silent preflight. Exit 0 if ready, 2/3/4 on failure.
  setup.py --json       Machine-readable status for the skill.
  setup.py              Installer. Scaffolds .env and marks SETUP_COMPLETE.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from watch.config import CONFIG_DIR, CONFIG_FILE, read_env_key


REQUIRED_BINARIES = ["ffmpeg", "ffprobe", "yt-dlp"]
# yt-dlp needs an external JS runtime to download YouTube video streams.
# Captions still work without it, but frames require it. Deno is recommended.
JS_RUNTIMES = ["deno", "node", "qjs", "bun"]

ENV_TEMPLATE = """# /watch API configuration
#
# Whisper transcription fallback — used only when yt-dlp cannot get captions.
# Groq is preferred: https://console.groq.com/keys
# OpenAI fallback: https://platform.openai.com/api-keys
#
# Leave both blank to disable Whisper — /watch will still work, but videos
# without native captions will come back frames-only.

GROQ_API_KEY=
OPENAI_API_KEY=
"""


# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------

def _have_api_key() -> tuple[bool, str | None]:
    if read_env_key("GROQ_API_KEY"):
        return True, "groq"
    if read_env_key("OPENAI_API_KEY"):
        return True, "openai"
    return False, None


def is_first_run() -> bool:
    return read_env_key("SETUP_COMPLETE") != "true"


# ---------------------------------------------------------------------------
# Binary checks
# ---------------------------------------------------------------------------

def _check_binaries() -> list[str]:
    return [b for b in REQUIRED_BINARIES if shutil.which(b) is None]


def _detect_js_runtime() -> str | None:
    """Return the first JS runtime found on PATH that yt-dlp can use."""
    for name in JS_RUNTIMES:
        if shutil.which(name) is not None:
            return name
    return None


# ---------------------------------------------------------------------------
# Env scaffolding
# ---------------------------------------------------------------------------

def _scaffold_env() -> bool:
    if CONFIG_FILE.exists():
        return False
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(CONFIG_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(ENV_TEMPLATE)
    return True


def _write_setup_complete() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = ""
    if CONFIG_FILE.exists():
        existing = CONFIG_FILE.read_text(encoding="utf-8")
        if any(line.strip().startswith("SETUP_COMPLETE=") for line in existing.splitlines()):
            return
    content = (existing.rstrip() + "\nSETUP_COMPLETE=true\n") if existing else ENV_TEMPLATE + "SETUP_COMPLETE=true\n"
    fd = os.open(str(CONFIG_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Status / check / install
# ---------------------------------------------------------------------------

def _status() -> dict:
    missing = _check_binaries()
    has_key, backend = _have_api_key()
    setup_complete = not is_first_run()
    js_runtime = _detect_js_runtime()
    status: str
    if not missing and has_key:
        status = "ready"
    elif missing and not has_key:
        status = "needs_install_and_key"
    elif missing:
        status = "needs_install"
    else:
        status = "needs_key"

    return {
        "status": status,
        "can_proceed": (not missing) and (has_key or setup_complete),
        "first_run": not setup_complete,
        "setup_complete": setup_complete,
        "missing_binaries": missing,
        "js_runtime_available": js_runtime is not None,
        "js_runtime": js_runtime,
        "whisper_backend": backend,
        "has_api_key": has_key,
        "config_file": str(CONFIG_FILE),
        "platform": platform.system(),
    }


def cmd_check() -> int:
    missing = _check_binaries()
    if not missing:
        return 0
    installer = Path(__file__).resolve()
    sys.stderr.write(f"[watch] missing binaries: {', '.join(missing)}. Run: python3 {installer}\n")
    sys.stderr.flush()
    return 2


def cmd_json() -> int:
    json.dump(_status(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_install() -> int:
    missing = _check_binaries()
    js_runtime = _detect_js_runtime()
    if missing:
        print(f"[setup] missing binaries: {', '.join(missing)}", file=sys.stderr)
        print("[setup] install manually (e.g. `apt install ffmpeg`, `pip install yt-dlp`)", file=sys.stderr)
        return 2

    _scaffold_env()
    _write_setup_complete()
    has_key, backend = _have_api_key()
    if js_runtime:
        print(f"[setup] js runtime: {js_runtime}")
    else:
        print("[setup] warning: no js runtime (deno/node/qjs/bun) — YouTube frame extraction may fail")
    if has_key:
        print(f"[setup] ready. whisper backend: {backend}")
    else:
        print("[setup] ready. no whisper key — captions-only mode")
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--check":
            return cmd_check()
        if arg == "--json":
            return cmd_json()
    return cmd_install()


if __name__ == "__main__":
    raise SystemExit(main())
