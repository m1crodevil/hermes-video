#!/usr/bin/env python3
"""Auto-apply corrections to transcript based on vision verification.

Reads verified moments with corrections and applies them to the transcript.
Generates a corrected transcript and a diff of changes.

Usage:
    # Apply corrections and generate corrected transcript
    python3 apply_corrections.py --transcript transcript.json --moments key_moments.json --output corrected_transcript.json

    # Generate diff of changes
    python3 apply_corrections.py --transcript transcript.json --moments key_moments.json --diff
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ── Core Logic ───────────────────────────────────────────────────────────

def extract_corrections_from_moments(moments: list[dict]) -> dict[str, str]:
    """Extract corrections mapping from verified moments.
    
    Returns:
        Dict mapping original word -> corrected word
    """
    corrections = {}
    for moment in moments:
        if not moment.get("verified"):
            continue
        
        word = moment.get("word", "")
        correction = moment.get("correction")
        
        if correction and correction != word:
            corrections[word] = correction
    
    return corrections


def apply_corrections_to_segments(
    segments: list[dict],
    corrections: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    """Apply corrections to transcript segments.
    
    Args:
        segments: List of transcript segments
        corrections: Dict mapping original -> corrected
    
    Returns:
        Tuple of (corrected_segments, changes)
    """
    corrected_segments = []
    changes = []
    
    for seg in segments:
        original_text = seg.get("text", "")
        words = original_text.split()
        
        corrected_words = []
        seg_changed = False
        
        for word in words:
            # Strip punctuation for matching
            stripped = word.strip(".,!?;:\"'()[]{}")
            prefix = word[:len(word) - len(word.lstrip(".,!?;:\"'()[]{}"))]
            suffix = word[len(word.rstrip(".,!?;:\"'()[]{}")):]
            
            if stripped in corrections:
                corrected = corrections[stripped]
                # Preserve case of first letter
                if stripped and stripped[0].isupper() and corrected:
                    corrected = corrected[0].upper() + corrected[1:]
                
                corrected_words.append(prefix + corrected + suffix)
                changes.append({
                    "segment_start": seg.get("start", 0),
                    "original": stripped,
                    "corrected": corrected,
                })
                seg_changed = True
            else:
                corrected_words.append(word)
        
        corrected_seg = seg.copy()
        corrected_seg["text"] = " ".join(corrected_words)
        
        if seg_changed:
            corrected_seg["original_text"] = original_text
            corrected_seg["corrected"] = True
        
        corrected_segments.append(corrected_seg)
    
    return corrected_segments, changes


def generate_corrected_transcript_text(segments: list[dict]) -> str:
    """Generate human-readable corrected transcript."""
    lines = []
    for seg in segments:
        start = seg.get("start", 0)
        mins = int(start // 60)
        secs = int(start % 60)
        text = seg.get("text", "")
        lines.append(f"[{mins:02d}:{secs:02d}] {text}")
    return "\n".join(lines)


def generate_diff(changes: list[dict]) -> str:
    """Generate human-readable diff of changes."""
    if not changes:
        return "No changes made."
    
    lines = [f"Applied {len(changes)} corrections:"]
    for change in changes:
        ts = change["segment_start"]
        mins = int(ts // 60)
        secs = int(ts % 60)
        lines.append(f"  [{mins:02d}:{secs:02d}] {change['original']} → {change['corrected']}")
    
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        prog="apply_corrections",
        description="Auto-apply corrections to transcript based on vision verification.",
    )
    ap.add_argument("--transcript", type=str, required=True, help="Path to transcript JSON")
    ap.add_argument("--moments", type=str, required=True, help="Path to key_moments.json")
    ap.add_argument("--output", type=str, default=None, help="Output path for corrected transcript JSON")
    ap.add_argument("--diff", action="store_true", help="Show diff of changes")
    ap.add_argument("--text", action="store_true", help="Output corrected transcript as text")
    
    args = ap.parse_args()
    
    # Load transcript
    transcript_data = json.loads(Path(args.transcript).read_text())
    if isinstance(transcript_data, dict):
        segments = transcript_data.get("transcript_segments", [])
    else:
        segments = transcript_data
    
    # Load moments
    moments = json.loads(Path(args.moments).read_text())
    
    # Extract corrections
    corrections = extract_corrections_from_moments(moments)
    
    if not corrections:
        print("No corrections found in verified moments.", file=sys.stderr)
        print("Make sure moments have 'verified': true and 'correction' fields.", file=sys.stderr)
        return 0
    
    print(f"Found {len(corrections)} corrections:", file=sys.stderr)
    for orig, corrected in corrections.items():
        print(f"  {orig} → {corrected}", file=sys.stderr)
    
    # Apply corrections
    corrected_segments, changes = apply_corrections_to_segments(segments, corrections)
    
    # Output results
    if args.diff:
        print(generate_diff(changes))
    
    if args.text:
        print(generate_corrected_transcript_text(corrected_segments))
    
    # Save corrected transcript
    if args.output:
        output_data = {
            "original_segments": segments,
            "corrected_segments": corrected_segments,
            "corrections": corrections,
            "changes": changes,
        }
        Path(args.output).write_text(json.dumps(output_data, indent=2))
        print(f"\nSaved corrected transcript to: {args.output}", file=sys.stderr)
    else:
        # Print corrected segments to stdout
        print(json.dumps(corrected_segments, indent=2))
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
