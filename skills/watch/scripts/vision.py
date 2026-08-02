#!/usr/bin/env python3
"""Vision verification for key moments.

Handles the workflow of verifying key moments using visual analysis.
Designed to work with the agent's vision_analyze tool.

Usage:
    # List frames needed for verification
    python3 vision_verify.py frames --moments key_moments.json --frames-dir frames/

    # Generate vision questions for each moment
    python3 vision_verify.py questions --moments key_moments.json

    # Process vision results and extract corrections
    python3 vision_verify.py process --moments key_moments.json --results results.json

    # Update moments with verification results
    python3 vision_verify.py update --moments key_moments.json --verified verified.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


# ── Data Models ──────────────────────────────────────────────────────────

@dataclass
class VisionRequest:
    """A request for vision analysis on a frame."""
    moment_index: int
    timestamp: float
    timestamp_fmt: str
    frame_path: str
    word: str
    question: str
    reason: str
    priority: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VisionResult:
    """Result from vision analysis."""
    moment_index: int
    timestamp: float
    frame_path: str
    raw_answer: str
    correction: str | None = None
    corrected_word: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VerifiedMoment:
    """A moment with verification results."""
    timestamp: float
    timestamp_fmt: str
    word: str
    context: str
    reason: str
    question: str
    priority: int
    vision_result: str | None = None
    correction: str | None = None
    verified: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ── Frame Matching ───────────────────────────────────────────────────────

def find_frame_at_timestamp(
    timestamp: float,
    frames_dir: Path,
    tolerance: float = 2.0,
) -> str | None:
    """Find a frame file closest to the given timestamp.
    
    Args:
        timestamp: Target timestamp in seconds
        frames_dir: Directory containing frame files
        tolerance: Maximum time difference in seconds
    
    Returns:
        Path to frame file, or None if not found
    """
    best_match = None
    best_diff = float("inf")
    
    # Check for both frame_*.jpg and cue_*.jpg
    for pattern in ("frame_*.jpg", "cue_*.jpg", "fill_*.jpg"):
        for frame_path in frames_dir.glob(pattern):
            # Extract timestamp from filename
            # frame_0001.jpg -> we need to check the actual timestamp
            # For now, we'll use the frame index and metadata
            pass
    
    # If we have report.json, use its frame metadata
    report_path = frames_dir.parent / "report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text())
            frames = report.get("frames", [])
            for frame in frames:
                frame_ts = frame.get("timestamp", 0)
                frame_path = frame.get("path", "")
                diff = abs(frame_ts - timestamp)
                if diff < best_diff and diff <= tolerance:
                    best_diff = diff
                    best_match = frame_path
        except Exception:
            pass
    
    # Fallback: look for frames by naming pattern
    if not best_match:
        # Try to find frame by approximate timestamp
        # This is a heuristic - assumes 1 frame per second for scene-detected
        for frame_path in frames_dir.glob("frame_*.jpg"):
            # Extract index from filename
            try:
                idx = int(frame_path.stem.split("_")[1])
                # Rough estimate: assume 30fps video
                # This is imprecise but works as fallback
                pass
            except (ValueError, IndexError):
                continue
    
    return best_match


def list_frames_needed(
    moments: list[dict],
    frames_dir: Path,
) -> list[dict]:
    """List frames needed for verification, checking which already exist."""
    result = []
    
    for i, moment in enumerate(moments):
        timestamp = moment.get("timestamp", 0)
        if isinstance(timestamp, str):
            # Parse MM:SS
            parts = timestamp.split(":")
            if len(parts) == 2:
                timestamp = int(parts[0]) * 60 + float(parts[1])
            else:
                timestamp = float(parts[0])
        
        frame_path = find_frame_at_timestamp(timestamp, frames_dir)
        
        result.append({
            "moment_index": i,
            "timestamp": timestamp,
            "timestamp_fmt": moment.get("timestamp_fmt", ""),
            "word": moment.get("word", ""),
            "question": moment.get("question", ""),
            "frame_path": frame_path,
            "frame_exists": frame_path is not None,
            "priority": moment.get("priority", 3),
        })
    
    return result


# ── Vision Questions ─────────────────────────────────────────────────────

def generate_vision_questions(moments: list[dict]) -> list[VisionRequest]:
    """Generate vision analysis requests for each moment."""
    requests = []
    
    for i, moment in enumerate(moments):
        timestamp = moment.get("timestamp", 0)
        if isinstance(timestamp, str):
            parts = timestamp.split(":")
            if len(parts) == 2:
                timestamp = int(parts[0]) * 60 + float(parts[1])
            else:
                timestamp = float(parts[0])
        
        # Skip if vision_result already exists
        if moment.get("vision_result"):
            continue
        
        requests.append(VisionRequest(
            moment_index=i,
            timestamp=timestamp,
            timestamp_fmt=moment.get("timestamp_fmt", ""),
            frame_path=moment.get("frame_path", ""),
            word=moment.get("word", ""),
            question=moment.get("question", "What is shown in this frame?"),
            reason=moment.get("reason", "unknown"),
            priority=moment.get("priority", 3),
        ))
    
    # Sort by priority
    requests.sort(key=lambda x: x.priority)
    
    return requests


# ── Result Processing ────────────────────────────────────────────────────

def process_vision_results(
    moments: list[dict],
    results: list[dict],
) -> list[VerifiedMoment]:
    """Process vision results and extract corrections."""
    
    # Index results by moment_index
    results_by_index = {}
    for r in results:
        idx = r.get("moment_index")
        if idx is not None:
            results_by_index[idx] = r
    
    verified = []
    
    for i, moment in enumerate(moments):
        timestamp = moment.get("timestamp", 0)
        if isinstance(timestamp, str):
            parts = timestamp.split(":")
            if len(parts) == 2:
                timestamp = int(parts[0]) * 60 + float(parts[1])
            else:
                timestamp = float(parts[0])
        
        result = results_by_index.get(i)
        
        if result:
            verified.append(VerifiedMoment(
                timestamp=timestamp,
                timestamp_fmt=moment.get("timestamp_fmt", ""),
                word=moment.get("word", ""),
                context=moment.get("context", ""),
                reason=moment.get("reason", ""),
                question=moment.get("question", ""),
                priority=moment.get("priority", 3),
                vision_result=result.get("raw_answer", ""),
                correction=result.get("correction"),
                verified=True,
            ))
        else:
            verified.append(VerifiedMoment(
                timestamp=timestamp,
                timestamp_fmt=moment.get("timestamp_fmt", ""),
                word=moment.get("word", ""),
                context=moment.get("context", ""),
                reason=moment.get("reason", ""),
                question=moment.get("question", ""),
                priority=moment.get("priority", 3),
                verified=False,
            ))
    
    return verified


def extract_corrections(verified: list[VerifiedMoment]) -> dict[str, str]:
    """Extract word corrections from verified moments."""
    corrections = {}
    for v in verified:
        if v.correction and v.correction != v.word:
            corrections[v.word] = v.correction
    return corrections


# ── CLI ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        prog="vision_verify",
        description="Vision verification for key moments.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    # Frames command
    frames_cmd = sub.add_parser("frames", help="List frames needed for verification")
    frames_cmd.add_argument("--moments", type=str, required=True, help="Path to key_moments.json")
    frames_cmd.add_argument("--frames-dir", type=str, required=True, help="Path to frames directory")

    # Questions command
    questions_cmd = sub.add_parser("questions", help="Generate vision questions for each moment")
    questions_cmd.add_argument("--moments", type=str, required=True, help="Path to key_moments.json")

    # Process command
    process_cmd = sub.add_parser("process", help="Process vision results and extract corrections")
    process_cmd.add_argument("--moments", type=str, required=True, help="Path to key_moments.json")
    process_cmd.add_argument("--results", type=str, required=True, help="Path to results JSON")

    # Update command
    update_cmd = sub.add_parser("update", help="Update moments with verification results")
    update_cmd.add_argument("--moments", type=str, required=True, help="Path to key_moments.json")
    update_cmd.add_argument("--verified", type=str, required=True, help="Path to verified JSON")

    args = ap.parse_args()

    if args.command == "frames":
        moments = json.loads(Path(args.moments).read_text())
        frames_dir = Path(args.frames_dir)
        result = list_frames_needed(moments, frames_dir)
        print(json.dumps(result, indent=2))
        return 0

    elif args.command == "questions":
        moments = json.loads(Path(args.moments).read_text())
        requests = generate_vision_questions(moments)
        print(json.dumps([r.to_dict() for r in requests], indent=2))
        return 0

    elif args.command == "process":
        moments = json.loads(Path(args.moments).read_text())
        results = json.loads(Path(args.results).read_text())
        verified = process_vision_results(moments, results)
        print(json.dumps([v.to_dict() for v in verified], indent=2))
        return 0

    elif args.command == "update":
        moments = json.loads(Path(args.moments).read_text())
        verified_data = json.loads(Path(args.verified).read_text())
        
        # Convert to VerifiedMoment objects
        verified = [VerifiedMoment(**v) for v in verified_data]
        
        # Extract corrections
        corrections = extract_corrections(verified)
        
        # Update moments with corrections
        for moment in moments:
            word = moment.get("word", "")
            if word in corrections:
                moment["correction"] = corrections[word]
        
        # Output updated moments
        print(json.dumps(moments, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
