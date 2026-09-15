"""CLI entry point for /watch (parity with hermes-video-rs)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from watch.core import run_watch


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
    parser.add_argument("--cookies-file", type=str, default=None, help="Path to cookies file")
    parser.add_argument("--no-whisper", action="store_true", help="Disable Whisper fallback")
    parser.add_argument("--whisper", choices=["groq", "openai"], default=None, help="Whisper backend")
    parser.add_argument("--output", choices=["markdown", "json", "both"], default="both", help="Output format")
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else None

    report = run_watch(
        source=args.source,
        out_dir=out_dir,
        timestamps_str=args.timestamps,
        use_cookies=args.cookies,
        cookies_file=args.cookies_file,
        no_whisper=args.no_whisper,
        output_format=args.output,
        keep_video=args.keep_video,
        resolution=args.resolution,
    )

    print(f"[watch] report written to {report.working_dir}/report.json", file=sys.stderr)
    print(f"[watch] extracted {len(report.frames)} frames", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
