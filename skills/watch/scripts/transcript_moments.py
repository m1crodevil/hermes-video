#!/usr/bin/env python3
"""Extract key moments from transcript for visual verification.

Uses LLM-driven analysis to identify moments that need visual verification
from video frames. Zero hardcoding — all detection is context-aware and
works across languages and content types.

Usage:
    # Generate analysis prompt (agent processes this)
    python3 transcript_moments.py prompt --transcript transcript.txt --title "Video Title"

    # Parse LLM response into structured moments
    python3 transcript_moments.py parse --response response.json --transcript transcript.txt

    # Full pipeline (standalone, calls LLM directly)
    python3 transcript_moments.py detect --transcript transcript.txt --title "Video Title"
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


# ── Data Models ──────────────────────────────────────────────────────────

@dataclass
class KeyMoment:
    """A moment in the transcript that needs visual verification."""
    timestamp: float          # seconds from video start
    timestamp_fmt: str        # "MM:SS" format
    word: str                 # triggering word/phrase
    context: str              # surrounding text (for LLM context)
    reason: str               # why this needs verification
    question: str             # what to ask vision model
    priority: int             # 1=critical, 5=nice-to-have

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> KeyMoment:
        return cls(
            timestamp=data["timestamp"],
            timestamp_fmt=data.get("timestamp_fmt", ""),
            word=data["word"],
            context=data.get("context", ""),
            reason=data.get("reason", "unknown"),
            question=data.get("question", "What is shown in this frame?"),
            priority=data.get("priority", 3),
        )


# ── Prompt Generation ────────────────────────────────────────────────────

MOMENT_DETECTION_PROMPT = """You are analyzing a video transcript to identify moments that need visual verification from video frames.

Video Title: {title}
Uploader: {uploader}
Duration: {duration}s

Transcript (timestamped):
{transcript}

Your task: Identify up to {max_moments} key moments where visual verification would improve accuracy.

Focus on moments where:
1. **Proper nouns** — names, brands, game titles, tool names that might be misspelled in auto-captions
2. **Claims/statistics** — numbers, prices, dates that need fact-checking
3. **Deictic references** — "this", "that", "here", "look at this" where speaker points at something
4. **Speaker identity** — moments where it's unclear who is speaking
5. **Visual context** — moments where understanding the visual context changes interpretation
6. **Entity validation** — game names, software names, product names that could be transcribed incorrectly

For EACH moment, provide:
- timestamp: MM:SS format (from the transcript timestamps)
- word: the specific word/phrase that triggered this
- context: 1-2 sentences around this moment
- reason: one of [proper_noun, claim, deictic, speaker_id, visual_context, entity]
- question: specific question to ask a vision model about this frame
- priority: 1 (critical) to 5 (nice-to-have)

Return ONLY a valid JSON array. No markdown, no explanation.

Example:
[
  {{
    "timestamp": "0:54",
    "word": "Raknarok",
    "context": "Ya kan Ragnarok. Tahu Raknarok? Raknarok tahu tahu.",
    "reason": "proper_noun",
    "question": "What game name is displayed on screen? Correct any misspellings.",
    "priority": 1
  }},
  {{
    "timestamp": "9:28",
    "word": "1 juta dolar",
    "context": "1 juta dolar berarti kalau rupiah sekarang 18 M",
    "reason": "claim",
    "question": "What prize amount or monetary figure is mentioned or shown?",
    "priority": 1
  }}
]

Be selective — only include moments where visual verification would ACTUALLY improve accuracy. Quality over quantity."""


def generate_prompt(
    transcript_text: str,
    video_metadata: dict,
    max_moments: int = 15,
) -> str:
    """Generate LLM prompt for moment detection."""
    return MOMENT_DETECTION_PROMPT.format(
        title=video_metadata.get("title", "Unknown"),
        uploader=video_metadata.get("uploader", "Unknown"),
        duration=video_metadata.get("duration", 0),
        transcript=transcript_text,
        max_moments=max_moments,
    )


# ── Response Parsing ─────────────────────────────────────────────────────

def parse_moments_response(
    response: str,
    transcript_segments: list[dict],
) -> list[KeyMoment]:
    """Parse LLM response into KeyMoment objects.
    
    Handles various response formats:
    - Pure JSON array
    - JSON wrapped in markdown code block
    - JSON with explanation text before/after
    """
    # Extract JSON from response (handle markdown code blocks)
    json_str = response.strip()
    
    # Remove markdown code block if present
    if "```json" in json_str:
        start = json_str.index("```json") + 7
        end = json_str.index("```", start)
        json_str = json_str[start:end].strip()
    elif "```" in json_str:
        start = json_str.index("```") + 3
        end = json_str.index("```", start)
        json_str = json_str[start:end].strip()
    
    # Try to find JSON array
    try:
        moments_raw = json.loads(json_str)
    except json.JSONDecodeError:
        # Try to find array in text
        import re
        match = re.search(r'\[.*\]', json_str, re.DOTALL)
        if match:
            moments_raw = json.loads(match.group())
        else:
            print("[transcript_moments] Failed to parse LLM response", file=sys.stderr)
            return []
    
    if not isinstance(moments_raw, list):
        print("[transcript_moments] Response is not a JSON array", file=sys.stderr)
        return []
    
    # Build timestamp lookup for context
    timestamp_map = _build_timestamp_map(transcript_segments)
    
    # Convert to KeyMoment objects
    moments = []
    for m in moments_raw:
        try:
            timestamp_str = m.get("timestamp", "0:00")
            timestamp = _parse_timestamp(timestamp_str)
            
            # Get context from transcript if not provided
            context = m.get("context", "")
            if not context and timestamp in timestamp_map:
                context = timestamp_map[timestamp]
            
            moments.append(KeyMoment(
                timestamp=timestamp,
                timestamp_fmt=timestamp_str,
                word=m.get("word", ""),
                context=context,
                reason=m.get("reason", "unknown"),
                question=m.get("question", "What is shown in this frame?"),
                priority=m.get("priority", 3),
            ))
        except (KeyError, ValueError) as e:
            print(f"[transcript_moments] Skipping invalid moment: {e}", file=sys.stderr)
            continue
    
    # Sort by priority (ascending), then timestamp
    moments.sort(key=lambda x: (x.priority, x.timestamp))
    
    # Deduplicate nearby timestamps (within 2 seconds)
    moments = _deduplicate_moments(moments, min_gap_seconds=2.0)
    
    return moments


def _build_timestamp_map(segments: list[dict]) -> dict[float, str]:
    """Build lookup from timestamp to surrounding text."""
    result = {}
    for seg in segments:
        start = seg.get("start", 0)
        text = seg.get("text", "")
        # Store first 100 chars of text at this timestamp
        result[start] = text[:100]
    return result


def _parse_timestamp(ts: str) -> float:
    """Parse MM:SS or HH:MM:SS timestamp to seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    else:
        return float(parts[0])


def _deduplicate_moments(
    moments: list[KeyMoment],
    min_gap_seconds: float = 2.0,
) -> list[KeyMoment]:
    """Remove duplicate moments within min_gap_seconds, keeping higher priority."""
    if not moments:
        return []
    
    result = [moments[0]]
    for m in moments[1:]:
        last = result[-1]
        if abs(m.timestamp - last.timestamp) >= min_gap_seconds:
            result.append(m)
        elif m.priority < last.priority:
            # Replace with higher priority (lower number)
            result[-1] = m
    
    return result


# ── Transcript Formatting ────────────────────────────────────────────────

def format_transcript_for_analysis(segments: list[dict]) -> str:
    """Format transcript segments for LLM analysis."""
    lines = []
    for seg in segments:
        start = seg.get("start", 0)
        text = seg.get("text", "")
        mins = int(start // 60)
        secs = int(start % 60)
        lines.append(f"[{mins:02d}:{secs:02d}] {text}")
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        prog="transcript_moments",
        description="Extract key moments from transcript for visual verification.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    # Prompt command
    prompt_cmd = sub.add_parser("prompt", help="Generate LLM prompt for moment detection")
    prompt_cmd.add_argument("--transcript", type=str, required=True, help="Path to transcript file or JSON")
    prompt_cmd.add_argument("--title", type=str, default="Unknown", help="Video title")
    prompt_cmd.add_argument("--uploader", type=str, default="Unknown", help="Video uploader")
    prompt_cmd.add_argument("--duration", type=float, default=0, help="Video duration in seconds")
    prompt_cmd.add_argument("--max-moments", type=int, default=15, help="Maximum moments to identify")

    # Parse command
    parse_cmd = sub.add_parser("parse", help="Parse LLM response into structured moments")
    parse_cmd.add_argument("--response", type=str, required=True, help="LLM response (JSON or text)")
    parse_cmd.add_argument("--transcript", type=str, required=True, help="Path to transcript file or JSON")

    # Info command
    info_cmd = sub.add_parser("info", help="Show moment statistics")

    args = ap.parse_args()

    if args.command == "prompt":
        # Load transcript
        transcript_path = Path(args.transcript)
        if transcript_path.suffix == ".json":
            segments = json.loads(transcript_path.read_text())
        else:
            # Assume timestamped text format
            segments = _parse_text_transcript(transcript_path.read_text())
        
        transcript_text = format_transcript_for_analysis(segments)
        
        metadata = {
            "title": args.title,
            "uploader": args.uploader,
            "duration": args.duration,
        }
        
        prompt = generate_prompt(transcript_text, metadata, args.max_moments)
        print(prompt)
        return 0

    elif args.command == "parse":
        # Load transcript
        transcript_path = Path(args.transcript)
        if transcript_path.suffix == ".json":
            segments = json.loads(transcript_path.read_text())
        else:
            segments = _parse_text_transcript(transcript_path.read_text())
        
        # Load response
        response_path = Path(args.response)
        if response_path.exists():
            response = response_path.read_text()
        else:
            # Assume inline response
            response = args.response
        
        moments = parse_moments_response(response, segments)
        
        # Output as JSON
        output = [m.to_dict() for m in moments]
        print(json.dumps(output, indent=2))
        return 0

    elif args.command == "info":
        # Read moments from stdin
        data = json.load(sys.stdin)
        moments = [KeyMoment.from_dict(m) for m in data]
        
        print(f"Total moments: {len(moments)}")
        print(f"Priority distribution:")
        for p in range(1, 6):
            count = sum(1 for m in moments if m.priority == p)
            if count > 0:
                print(f"  Priority {p}: {count}")
        
        print(f"\nReason distribution:")
        reasons = {}
        for m in moments:
            reasons[m.reason] = reasons.get(m.reason, 0) + 1
        for reason, count in sorted(reasons.items()):
            print(f"  {reason}: {count}")
        
        return 0

    return 1


def _parse_text_transcript(text: str) -> list[dict]:
    """Parse timestamped text transcript into segments."""
    import re
    segments = []
    pattern = re.compile(r'\[(\d{2}):(\d{2})\]\s*(.*)')
    
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if match:
            mins, secs, text = match.groups()
            start = int(mins) * 60 + int(secs)
            segments.append({"start": start, "text": text})
    
    return segments


if __name__ == "__main__":
    raise SystemExit(main())
