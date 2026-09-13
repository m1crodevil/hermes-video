"""CLI entry point for /watch (parity with hermes-video-rs)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure package imports work when executed directly or via symlink
_src = Path(__file__).resolve().parent.parent
_pkg = Path(__file__).resolve().parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
if str(_pkg) in sys.path:
    sys.path.remove(str(_pkg))


def main() -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(
        prog="watch",
        description="Download a video, extract frames, and surface the transcript.",
    )
    parser.add_argument("source", help="Video URL or local file path")
    parser.add_argument("--resolution", type=int, default=512, help="Frame width in pixels (default 512)")
    parser.add_argument("--timestamps", type=str, default=None, help="Comma-separated timestamps (SS, MM:SS, HH:MM:SS)")
    parser.add_argument("--out-dir", type=str, default=None, help="Working directory (default: tmp)")
    parser.add_argument("--keep-video", action="store_true", help="Keep downloaded video")
    parser.add_argument("--cookies", action="store_true", help="Use Chrome cookies")
    parser.add_argument("--no-whisper", action="store_true", help="Disable Whisper fallback")
    parser.add_argument("--whisper", choices=["groq", "openai"], default=None, help="Whisper backend")
    parser.add_argument("--output", choices=["markdown", "json", "both"], default="both", help="Output format")
    args = parser.parse_args()

    # Identity banner: make it unambiguous which skill binary is running.
    print("[watch] Python /watch skill (hermes-video v2.3.0)", file=sys.stderr)

    from watch.core import run
    return run(args.source, args)


if __name__ == "__main__":
    raise SystemExit(main())
