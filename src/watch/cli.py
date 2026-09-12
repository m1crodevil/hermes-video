"""CLI entry point for /watch (parity with hermes-video-rs)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="watch",
        description="Download a video, extract frames, and surface the transcript.",
    )
    ap.add_argument("source", help="Video URL or local file path")
    ap.add_argument("--resolution", type=int, default=512, help="Frame width in pixels (default 512)")
    ap.add_argument("--timestamps", type=str, default=None, help="Comma-separated timestamps (SS, MM:SS, HH:MM:SS)")
    ap.add_argument("--out-dir", type=str, default=None, help="Working directory (default: tmp)")
    ap.add_argument("--keep-video", action="store_true", help="Keep downloaded video")
    ap.add_argument("--cookies", action="store_true", help="Use Chrome cookies")
    ap.add_argument("--no-whisper", action="store_true", help="Disable Whisper fallback")
    ap.add_argument("--whisper", choices=["groq", "openai"], default=None, help="Whisper backend")
    ap.add_argument("--output", choices=["markdown", "json", "both"], default="both", help="Output format")
    ap.add_argument("--js-runtimes", type=str, default=None, help="yt-dlp JS runtimes (e.g. deno,node)")
    return ap


def main() -> int:
    import os
    os.umask(0o077)
    parser = _build_parser()
    args = parser.parse_args()

    # Lazy import so module-level failures in old pipeline do not block new CLI
    from watch.core import run
    return run(args.source, args)


if __name__ == "__main__":
    raise SystemExit(main())
