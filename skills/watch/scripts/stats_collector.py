#!/usr/bin/env python3
"""Collect and format analysis statistics for Telegram deliverable.

Gathers metrics from the watch pipeline and formats them for display.

Usage:
    # Collect stats from work directory
    python3 stats_collector.py collect --work-dir /tmp/watch-xxx

    # Format stats for Telegram
    python3 stats_collector.py format --stats stats.json

    # Generate footer for Telegram
    python3 stats_collector.py footer --work-dir /tmp/watch-xxx
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path


# ── Data Models ──────────────────────────────────────────────────────────

@dataclass
class AnalysisStats:
    """Statistics from video analysis."""
    # Timing
    start_time: float = 0.0
    end_time: float = 0.0
    processing_time: float = 0.0
    
    # Video
    video_duration: float = 0.0
    video_duration_fmt: str = ""
    video_file_size: int = 0
    video_file_size_fmt: str = ""
    video_resolution: str = ""
    
    # Frames
    frames_extracted: int = 0
    frames_resolution: int = 512
    frames_engine: str = ""
    
    # Transcript
    transcript_segments: int = 0
    transcript_language: str = ""
    transcript_source: str = ""
    
    # Key Moments (optional)
    key_moments_detected: int = 0
    key_moments_priority_1: int = 0
    
    # Vision Verification (optional)
    vision_verifications: int = 0
    vision_corrections: int = 0
    
    # Token Usage (if available)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ── Stats Collection ─────────────────────────────────────────────────────

def collect_stats(work_dir: Path) -> AnalysisStats:
    """Collect statistics from work directory."""
    stats = AnalysisStats()

    # Load report.json
    report: dict = {}
    report_path = work_dir / "report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text())
            _extract_from_report(stats, report)
        except Exception as e:
            print(f"Warning: Failed to load report.json: {e}", file=sys.stderr)
    
    # Load key_moments.json
    moments_path = work_dir / "key_moments.json"
    if moments_path.exists():
        try:
            moments = json.loads(moments_path.read_text())
            stats.key_moments_detected = len(moments)
            stats.key_moments_priority_1 = sum(
                1 for m in moments if m.get("priority", 3) == 1
            )
        except Exception:
            pass
    
    # Check for vision results
    vision_results_path = work_dir / "vision_results.json"
    if vision_results_path.exists():
        try:
            results = json.loads(vision_results_path.read_text())
            stats.vision_verifications = len(results)
            stats.vision_corrections = sum(
                1 for r in results if r.get("correction")
            )
        except Exception:
            pass
    
    # Check video file size
    video_path = work_dir / "download" / "video.mp4"
    if video_path.exists():
        stats.video_file_size = video_path.stat().st_size
    
    # Count frames
    frames_dir = work_dir / "frames"
    if frames_dir.exists():
        stats.frames_extracted = len(list(frames_dir.glob("*.jpg")))
    
    moment_frames_dir = work_dir / "moment_frames"
    if moment_frames_dir.exists():
        stats.frames_extracted += len(list(moment_frames_dir.glob("*.jpg")))
    
    # Estimate token usage
    _estimate_tokens(stats, report)

    return stats


# ── Token Estimation ──────────────────────────────────────────────────

# Approximate image tokens per frame at each resolution bucket.
# Based on vision model pricing: ~800 tokens for 512px, scaling
# quadratically with dimension (area-based).
_TOKENS_PER_FRAME = {
    384: 450,
    448: 600,
    512: 800,
    640: 1_250,
    768: 1_800,
    1024: 3_200,
    1280: 5_000,
    1920: 11_000,
}

# Rough character-to-token ratio (≈ 4 chars per token for mixed Latin/CJK)
_CHARS_PER_TOKEN = 4


def _estimate_tokens(stats: AnalysisStats, report: dict) -> None:
    """Estimate token usage from frames + transcript."""
    # ── Frame image tokens ────────────────────────────────────────────
    # Pick the closest resolution bucket; default to 512.
    res = stats.frames_resolution or 512
    tpf = _TOKENS_PER_FRAME.get(res)
    if tpf is None:
        # Linear interpolation between nearest buckets
        buckets = sorted(_TOKENS_PER_FRAME.keys())
        lo = max((b for b in buckets if b <= res), default=buckets[0])
        hi = min((b for b in buckets if b >= res), default=buckets[-1])
        if lo == hi:
            tpf = _TOKENS_PER_FRAME[lo]
        else:
            tpf = _TOKENS_PER_FRAME[lo] + (
                (_TOKENS_PER_FRAME[hi] - _TOKENS_PER_FRAME[lo])
                * (res - lo) / (hi - lo)
            )
    frame_tokens = int(stats.frames_extracted * tpf)

    # ── Transcript text tokens ────────────────────────────────────────
    transcript_segments = report.get("transcript_segments", [])
    transcript_chars = sum(len(s.get("text", "")) for s in transcript_segments)
    transcript_tokens = transcript_chars // _CHARS_PER_TOKEN

    # ── Vision verification tokens (each call ≈ 800 image + 200 prompt) ──
    vision_tokens = stats.vision_verifications * 1_000

    # ── Totals ────────────────────────────────────────────────────────
    stats.input_tokens = frame_tokens + transcript_tokens + vision_tokens
    stats.output_tokens = 0  # agent output is external to the script
    stats.total_tokens = stats.input_tokens + stats.output_tokens


def _extract_from_report(stats: AnalysisStats, report: dict) -> None:
    """Extract stats from report.json."""
    metadata = report.get("metadata", {})
    
    # Video info
    stats.video_duration = metadata.get("duration", 0)
    stats.video_duration_fmt = _format_duration(stats.video_duration)
    stats.video_resolution = metadata.get("resolution", "")
    
    # Frames
    frames = report.get("frames", [])
    stats.frames_extracted = len(frames)
    
    frame_stats = report.get("frame_stats", {})
    if frame_stats:
        stats.frames_engine = frame_stats.get("engine", "")
    
    # Transcript
    transcript_segments = report.get("transcript_segments", [])
    stats.transcript_segments = len(transcript_segments)
    stats.transcript_source = report.get("transcript_source", "")
    stats.transcript_language = metadata.get("detected_language", "")


def _format_duration(seconds: float) -> str:
    """Format duration as MM:SS or HH:MM:SS."""
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_file_size(size_bytes: int) -> str:
    """Format file size as human-readable."""
    if size_bytes == 0:
        return "N/A"
    
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ── Stats Formatting ─────────────────────────────────────────────────────

def format_stats_telegram(stats: AnalysisStats) -> str:
    """Format stats for Telegram display."""
    lines = []
    
    # Header
    lines.append("📊 **Analysis Stats**")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Timing
    if stats.processing_time > 0:
        lines.append(f"⏱️ Processing Time: {stats.processing_time:.1f}s")
    
    # Video
    if stats.video_duration > 0:
        lines.append(f"🎬 Video Duration: {stats.video_duration_fmt}")
    if stats.video_resolution:
        lines.append(f"📐 Resolution: {stats.video_resolution}")
    if stats.video_file_size > 0:
        lines.append(f"💾 File Size: {_format_file_size(stats.video_file_size)}")
    
    # Frames
    if stats.frames_extracted > 0:
        engine = f" ({stats.frames_engine})" if stats.frames_engine else ""
        lines.append(f"🖼️ Frames Extracted: {stats.frames_extracted} @ {stats.frames_resolution}px{engine}")
    
    # Transcript
    if stats.transcript_segments > 0:
        lang = f" ({stats.transcript_language})" if stats.transcript_language else ""
        source = f" [{stats.transcript_source}]" if stats.transcript_source else ""
        lines.append(f"📝 Transcript: {stats.transcript_segments} segments{lang}{source}")
    
    # Key Moments
    if stats.key_moments_detected > 0:
        p1 = f" ({stats.key_moments_priority_1} critical)" if stats.key_moments_priority_1 > 0 else ""
        lines.append(f"🎯 Key Moments: {stats.key_moments_detected} detected{p1}")
    
    # Vision Verification
    if stats.vision_verifications > 0:
        corrections = f" ({stats.vision_corrections} corrections)" if stats.vision_corrections > 0 else ""
        lines.append(f"🔍 Vision Verifications: {stats.vision_verifications} completed{corrections}")
    
    # Token Usage
    if stats.total_tokens > 0:
        lines.append(f"🪙 Tokens: {stats.total_tokens:,} (in: {stats.input_tokens:,}, out: {stats.output_tokens:,})")
    
    # Footer
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(lines)


def format_stats_compact(stats: AnalysisStats) -> str:
    """Format stats as compact single line."""
    parts = []
    
    if stats.processing_time > 0:
        parts.append(f"⏱️ {stats.processing_time:.1f}s")
    
    if stats.frames_extracted > 0:
        parts.append(f"🖼️ {stats.frames_extracted} frames")
    
    if stats.transcript_segments > 0:
        parts.append(f"📝 {stats.transcript_segments} segs")
    
    if stats.key_moments_detected > 0:
        parts.append(f"🎯 {stats.key_moments_detected} moments")
    
    if stats.vision_verifications > 0:
        parts.append(f"🔍 {stats.vision_verifications} verified")
    
    return " · ".join(parts)


# ── Timer ────────────────────────────────────────────────────────────────

class StatsTimer:
    """Context manager for timing analysis."""
    
    def __init__(self):
        self.start_time: float = 0.0
        self.end_time: float = 0.0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
    
    @property
    def elapsed(self) -> float:
        return self.end_time - self.start_time


# ── CLI ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        prog="stats_collector",
        description="Collect and format analysis statistics.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    # Collect command
    collect_cmd = sub.add_parser("collect", help="Collect stats from work directory")
    collect_cmd.add_argument("--work-dir", type=str, required=True, help="Path to work directory")
    collect_cmd.add_argument("--start-time", type=float, default=0.0, help="Analysis start time (Unix timestamp)")
    collect_cmd.add_argument("--processing-time", type=float, default=0.0, help="Processing time in seconds")

    # Format command
    format_cmd = sub.add_parser("format", help="Format stats for display")
    format_cmd.add_argument("--stats", type=str, required=True, help="Path to stats JSON")
    format_cmd.add_argument("--format", choices=["telegram", "compact"], default="telegram", help="Output format")

    # Footer command
    footer_cmd = sub.add_parser("footer", help="Generate footer for Telegram")
    footer_cmd.add_argument("--work-dir", type=str, required=True, help="Path to work directory")
    footer_cmd.add_argument("--processing-time", type=float, default=0.0, help="Processing time in seconds")

    args = ap.parse_args()

    if args.command == "collect":
        stats = collect_stats(Path(args.work_dir))
        
        if args.start_time > 0:
            stats.start_time = args.start_time
            stats.end_time = time.time()
        
        if args.processing_time > 0:
            stats.processing_time = args.processing_time
        
        print(json.dumps(stats.to_dict(), indent=2))
        return 0

    elif args.command == "format":
        stats_data = json.loads(Path(args.stats).read_text())
        stats = AnalysisStats(**stats_data)
        
        if args.format == "telegram":
            print(format_stats_telegram(stats))
        else:
            print(format_stats_compact(stats))
        
        return 0

    elif args.command == "footer":
        stats = collect_stats(Path(args.work_dir))
        
        if args.processing_time > 0:
            stats.processing_time = args.processing_time
        
        print(format_stats_compact(stats))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
