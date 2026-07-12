#!/usr/bin/env python3
"""Extract frames at key moment timestamps.

Automatically extracts frames at timestamps identified by LLM moment detection.
Integrates with the existing extract_at_timestamps() function.

Usage:
    # Extract frames for all moments
    python3 extract_moment_frames.py --video video.mp4 --moments key_moments.json --out-dir frames/

    # Extract frames for high-priority moments only
    python3 extract_moment_frames.py --video video.mp4 --moments key_moments.json --out-dir frames/ --priority 1

    # Extract and update moments with frame paths
    python3 extract_moment_frames.py --video video.mp4 --moments key_moments.json --out-dir frames/ --update
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from frames import extract_at_timestamps, parse_time  # noqa: E402


def get_timestamps_from_moments(
    moments: list[dict],
    max_priority: int | None = None,
) -> list[float]:
    """Extract timestamps from key moments.
    
    Args:
        moments: List of moment dicts
        max_priority: If set, only include moments with priority <= max_priority
    
    Returns:
        Sorted list of unique timestamps in seconds
    """
    timestamps = []
    
    for moment in moments:
        priority = moment.get("priority", 3)
        if max_priority is not None and priority > max_priority:
            continue
        
        ts = moment.get("timestamp", 0)
        if isinstance(ts, str):
            # Parse MM:SS or HH:MM:SS
            parts = ts.strip().split(":")
            if len(parts) == 2:
                ts = int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                ts = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            else:
                ts = float(parts[0])
        
        timestamps.append(float(ts))
    
    # Sort and deduplicate (within 1 second tolerance)
    timestamps.sort()
    deduped = []
    for ts in timestamps:
        if not deduped or abs(ts - deduped[-1]) >= 1.0:
            deduped.append(ts)
    
    return deduped


def update_moments_with_frames(
    moments: list[dict],
    frames: list[dict],
) -> list[dict]:
    """Update moments with extracted frame paths.
    
    Args:
        moments: List of moment dicts
        frames: List of frame dicts from extract_at_timestamps
    
    Returns:
        Updated moments with frame_path added
    """
    # Build timestamp -> frame path mapping
    frame_map = {}
    for frame in frames:
        ts = frame.get("timestamp_seconds", 0)
        path = frame.get("path", "")
        frame_map[ts] = path
    
    # Match moments to frames (within 2 second tolerance)
    for moment in moments:
        ts = moment.get("timestamp", 0)
        # Parse timestamp to seconds for matching
        ts_seconds = _parse_timestamp(ts) if isinstance(ts, str) else float(ts)
        
        # Find closest frame
        best_path = None
        best_diff = float("inf")
        for frame_ts, frame_path in frame_map.items():
            diff = abs(frame_ts - ts_seconds)
            if diff < best_diff and diff <= 2.0:
                best_diff = diff
                best_path = frame_path
        
        if best_path:
            moment["frame_path"] = best_path
    
    return moments


def _parse_timestamp(ts) -> float:
    """Parse timestamp to seconds."""
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        parts = ts.strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            return float(parts[0])
    return 0.0
def main() -> int:
    ap = argparse.ArgumentParser(
        prog="extract_moment_frames",
        description="Extract frames at key moment timestamps.",
    )
    ap.add_argument("--video", type=str, required=True, help="Path to video file")
    ap.add_argument("--moments", type=str, required=True, help="Path to key_moments.json")
    ap.add_argument("--out-dir", type=str, required=True, help="Output directory for frames")
    ap.add_argument("--resolution", type=int, default=512, help="Frame width in pixels (default 512)")
    ap.add_argument("--priority", type=int, default=None, help="Max priority level to extract (1=critical only)")
    ap.add_argument("--update", action="store_true", help="Update moments JSON with frame paths")
    ap.add_argument("--max-frames", type=int, default=30, help="Maximum frames to extract (default 30)")
    
    args = ap.parse_args()
    
    # Load moments
    moments_path = Path(args.moments)
    if not moments_path.exists():
        print(f"Error: {moments_path} not found", file=sys.stderr)
        return 1
    
    moments = json.loads(moments_path.read_text())
    print(f"Loaded {len(moments)} moments", file=sys.stderr)
    
    # Get timestamps to extract
    timestamps = get_timestamps_from_moments(moments, max_priority=args.priority)
    print(f"Extracting {len(timestamps)} frames at timestamps: {[f'{t:.1f}s' for t in timestamps]}", file=sys.stderr)
    
    # Extract frames
    out_dir = Path(args.out_dir)
    frames, meta = extract_at_timestamps(
        args.video,
        out_dir,
        timestamps,
        resolution=args.resolution,
        max_frames=args.max_frames,
    )
    
    print(f"Extracted {len(frames)} frames (engine: {meta.get('engine', 'unknown')})", file=sys.stderr)
    
    # Update moments with frame paths
    if args.update:
        updated_moments = update_moments_with_frames(moments, frames)
        
        # Count how many moments got frames
        with_frames = sum(1 for m in updated_moments if m.get("frame_path"))
        print(f"Updated {with_frames}/{len(updated_moments)} moments with frame paths", file=sys.stderr)
        
        # Write updated moments
        moments_path.write_text(json.dumps(updated_moments, indent=2))
        print(f"Updated {moments_path}", file=sys.stderr)
    
    # Output frame info
    output = {
        "extracted": len(frames),
        "total_moments": len(moments),
        "timestamps": timestamps,
        "frames": frames,
        "meta": meta,
    }
    
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
