#!/usr/bin/env python3
"""Batch vision analysis for key moments.

Generates batch prompts for analyzing multiple frames at once,
and processes the results into structured corrections.

Usage:
    # Generate batch vision prompt
    python3 batch_vision.py prompt --moments key_moments.json

    # Process batch vision results
    python3 batch_vision.py process --moments key_moments.json --results results.json

    # Apply corrections to transcript
    python3 batch_vision.py apply --transcript transcript.json --results results.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


# ── Data Models ──────────────────────────────────────────────────────────

@dataclass
class BatchVisionRequest:
    """A batch request for vision analysis."""
    frames: list[dict]  # [{index, timestamp, frame_path, word, question}]
    total: int
    priority_filter: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VisionFinding:
    """A single finding from vision analysis."""
    moment_index: int
    timestamp: str
    word: str
    actual: str  # What is actually shown
    correction: str | None = None
    confidence: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Prompt Generation ────────────────────────────────────────────────────

BATCH_VISION_PROMPT = """You are analyzing multiple video frames to verify transcript accuracy.

For each frame below, examine the image and answer the verification question.

## Frames to Analyze

{frames}

## Response Format

Return a JSON array of findings, one per frame:

[
  {{
    "index": 0,
    "timestamp": "0:26",
    "word": "George andika erison",
    "actual": "What name is actually displayed on screen",
    "correction": "Corrected name if different, or null",
    "confidence": 0.95,
    "notes": "Any additional observations"
  }},
  ...
]

## Guidelines

- **Be precise.** Only state what you can actually see in the frame.
- **Check spelling.** Compare the transcript word with what's shown on screen.
- **Note corrections.** If the transcript has a misspelling, provide the correction.
- **Estimate confidence.** How confident are you in your reading? (0.0-1.0)
- **Add notes.** Any additional observations about the frame.

Return ONLY valid JSON array. No markdown, no explanation."""


def generate_batch_prompt(
    moments: list[dict],
    max_priority: int | None = None,
) -> str:
    """Generate batch vision prompt for multiple frames."""
    
    frames = []
    for i, moment in enumerate(moments):
        priority = moment.get("priority", 3)
        if max_priority is not None and priority > max_priority:
            continue
        
        frame_path = moment.get("frame_path", "")
        if not frame_path:
            continue
        
        frames.append({
            "index": i,
            "timestamp": moment.get("timestamp", "0:00"),
            "frame_path": frame_path,
            "word": moment.get("word", ""),
            "question": moment.get("question", "What is shown in this frame?"),
        })
    
    if not frames:
        return "No frames available for analysis."
    
    # Format frames section
    frames_text = ""
    for f in frames:
        frames_text += f"""
Frame {f['index']}:
- Timestamp: {f['timestamp']}
- Frame path: {f['frame_path']}
- Transcript word: "{f['word']}"
- Question: {f['question']}
"""
    
    return BATCH_VISION_PROMPT.format(frames=frames_text)


# ── Result Processing ────────────────────────────────────────────────────

def process_batch_results(
    results: list[dict],
) -> list[VisionFinding]:
    """Process batch vision results into structured findings."""
    
    findings = []
    for r in results:
        findings.append(VisionFinding(
            moment_index=r.get("index", 0),
            timestamp=r.get("timestamp", ""),
            word=r.get("word", ""),
            actual=r.get("actual", ""),
            correction=r.get("correction"),
            confidence=r.get("confidence", 0.0),
            notes=r.get("notes", ""),
        ))
    
    return findings


def apply_corrections_to_moments(
    moments: list[dict],
    findings: list[VisionFinding],
) -> list[dict]:
    """Apply corrections from vision findings to moments."""
    
    # Index findings by moment_index
    findings_by_index = {f.moment_index: f for f in findings}
    
    for i, moment in enumerate(moments):
        finding = findings_by_index.get(i)
        if finding:
            moment["vision_result"] = finding.actual
            if finding.correction:
                moment["correction"] = finding.correction
            moment["verified"] = True
        else:
            moment["verified"] = False
    
    return moments


def extract_corrections_for_transcript(findings: list[VisionFinding]) -> dict[str, str]:
    """Extract corrections mapping for transcript."""
    corrections = {}
    for f in findings:
        if f.correction and f.correction != f.word:
            corrections[f.word] = f.correction
    return corrections


def apply_corrections_to_transcript(
    transcript_segments: list[dict],
    corrections: dict[str, str],
) -> list[dict]:
    """Apply corrections to transcript segments."""
    
    corrected_segments = []
    for seg in transcript_segments:
        text = seg.get("text", "")
        words = text.split()
        
        corrected_words = []
        for word in words:
            clean_word = word.strip(".,!?;:")
            if clean_word in corrections:
                corrected = corrections[clean_word]
                # Preserve case
                if clean_word[0].isupper():
                    corrected = corrected[0].upper() + corrected[1:]
                word = word.replace(clean_word, corrected)
            corrected_words.append(word)
        
        corrected_seg = seg.copy()
        corrected_seg["text"] = " ".join(corrected_words)
        corrected_segments.append(corrected_seg)
    
    return corrected_segments


# ── CLI ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        prog="batch_vision",
        description="Batch vision analysis for key moments.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    # Prompt command
    prompt_cmd = sub.add_parser("prompt", help="Generate batch vision prompt")
    prompt_cmd.add_argument("--moments", type=str, required=True, help="Path to key_moments.json")
    prompt_cmd.add_argument("--priority", type=int, default=None, help="Max priority to include (1=critical only)")

    # Process command
    process_cmd = sub.add_parser("process", help="Process batch vision results")
    process_cmd.add_argument("--moments", type=str, required=True, help="Path to key_moments.json")
    process_cmd.add_argument("--results", type=str, required=True, help="Path to batch results JSON")

    # Apply command
    apply_cmd = sub.add_parser("apply", help="Apply corrections to transcript")
    apply_cmd.add_argument("--transcript", type=str, required=True, help="Path to transcript JSON")
    apply_cmd.add_argument("--results", type=str, required=True, help="Path to batch results JSON")

    args = ap.parse_args()

    if args.command == "prompt":
        moments = json.loads(Path(args.moments).read_text())
        prompt = generate_batch_prompt(moments, max_priority=args.priority)
        print(prompt)
        return 0

    elif args.command == "process":
        moments = json.loads(Path(args.moments).read_text())
        results = json.loads(Path(args.results).read_text())
        
        findings = process_batch_results(results)
        updated_moments = apply_corrections_to_moments(moments, findings)
        
        # Output updated moments
        print(json.dumps(updated_moments, indent=2))
        
        # Also output corrections
        corrections = extract_corrections_for_transcript(findings)
        if corrections:
            print("\n--- Corrections ---", file=sys.stderr)
            for orig, corrected in corrections.items():
                print(f"  {orig} → {corrected}", file=sys.stderr)
        
        return 0

    elif args.command == "apply":
        transcript = json.loads(Path(args.transcript).read_text())
        results = json.loads(Path(args.results).read_text())
        
        findings = process_batch_results(results)
        corrections = extract_corrections_for_transcript(findings)
        
        # Handle transcript format
        if isinstance(transcript, dict):
            segments = transcript.get("transcript_segments", [])
        else:
            segments = transcript
        
        corrected = apply_corrections_to_transcript(segments, corrections)
        
        print(json.dumps(corrected, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
