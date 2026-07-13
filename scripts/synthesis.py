#!/usr/bin/env python3
"""Grounded synthesis from transcript + visual verification.

Generates LLM prompts for synthesizing transcript and visual evidence
into a grounded, validated summary.

Usage:
    # Generate synthesis prompt
    python3 synthesis.py prompt --transcript transcript.json --moments key_moments.json --verified verified.json --metadata metadata.json

    # Parse synthesis response
    python3 synthesis.py parse --response response.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


# ── Data Models ──────────────────────────────────────────────────────────

@dataclass
class SynthesisResult:
    """Result from grounded synthesis."""
    summary: str
    key_corrections: list[dict]
    speaker_identification: list[dict]
    visual_evidence: list[dict]
    uncertainties: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


# ── Prompt Generation ────────────────────────────────────────────────────

SYNTHESIS_PROMPT = """You are synthesizing a video analysis from multiple sources to produce a grounded, accurate summary.

Video Metadata:
{metadata}

Transcript (timestamped):
{transcript}

Visual Verifications:
{verifications}

Your task: Produce a grounded, accurate summary that:

1. **Uses corrected transcript** — Apply any corrections from visual verifications
2. **Identifies speakers** — Who said what, based on visual cues (Discord UI, facecam, etc.)
3. **Cites timestamps** — Every claim must reference when it was said/shown
4. **Notes uncertainties** — Be explicit about what you're unsure about

## Output Format

Return a JSON object with:

{{
  "summary": "Comprehensive summary of the video content",
  "key_corrections": [
    {{
      "original": "Raknarok",
      "corrected": "Ragnarok",
      "timestamp": "0:54",
      "source": "visual verification"
    }}
  ],
  "speaker_identification": [
    {{
      "speaker": "George",
      "evidence": "Discord UI shows name at 0:26",
      "quotes": ["quote 1", "quote 2"]
    }}
  ],
  "visual_evidence": [
    {{
      "timestamp": "0:54",
      "finding": "Game title screen shows 'Ragnarok Online'",
      "corrects_transcript": true
    }}
  ],
  "uncertainties": [
    "Uncertain about speaker attribution at 2:09-2:30"
  ]
}}

## Guidelines

- **Be precise.** Only state what is supported by transcript OR visual evidence.
- **Cite timestamps.** Every claim must reference when it was said/shown.
- **Cross-reference.** When transcript and visual evidence conflict, note the discrepancy.
- **Acknowledge gaps.** If something is unclear, say so explicitly.
- **Language.** Match the language of the video (Indonesian, English, etc.)

Return ONLY valid JSON. No markdown, no explanation."""


def generate_synthesis_prompt(
    transcript_text: str,
    verified_moments: list[dict],
    metadata: dict,
) -> str:
    """Generate LLM prompt for grounded synthesis."""
    
    # Format verifications
    verifications = []
    for m in verified_moments:
        if m.get("verified"):
            verifications.append({
                "timestamp": m.get("timestamp_fmt", ""),
                "word": m.get("word", ""),
                "question": m.get("question", ""),
                "vision_result": m.get("vision_result", ""),
                "correction": m.get("correction"),
            })
    
    return SYNTHESIS_PROMPT.format(
        metadata=json.dumps(metadata, indent=2),
        transcript=transcript_text,
        verifications=json.dumps(verifications, indent=2),
    )


# ── Response Parsing ─────────────────────────────────────────────────────

def parse_synthesis_response(response: str) -> SynthesisResult:
    """Parse LLM response into SynthesisResult."""
    
    # Extract JSON from response
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
    
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            return SynthesisResult(
                summary="Failed to parse synthesis response",
                key_corrections=[],
                speaker_identification=[],
                visual_evidence=[],
                uncertainties=["Response parsing failed"],
            )
    
    return SynthesisResult(
        summary=data.get("summary", ""),
        key_corrections=data.get("key_corrections", []),
        speaker_identification=data.get("speaker_identification", []),
        visual_evidence=data.get("visual_evidence", []),
        uncertainties=data.get("uncertainties", []),
    )


# ── Transcript Correction ────────────────────────────────────────────────

def apply_corrections_to_transcript(
    transcript_segments: list[dict],
    corrections: list[dict],
) -> list[dict]:
    """Apply corrections from synthesis to transcript segments."""
    
    # Build correction map
    correction_map = {}
    for c in corrections:
        original = c.get("original", "")
        corrected = c.get("corrected", "")
        if original and corrected:
            correction_map[original.lower()] = corrected
    
    # Apply corrections
    corrected_segments = []
    for seg in transcript_segments:
        text = seg.get("text", "")
        words = text.split()
        
        corrected_words = []
        for word in words:
            clean_word = word.strip(".,!?;:")
            if clean_word.lower() in correction_map:
                # Replace with corrected version, preserving case
                corrected = correction_map[clean_word.lower()]
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
        prog="synthesis",
        description="Grounded synthesis from transcript + visual verification.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    # Prompt command
    prompt_cmd = sub.add_parser("prompt", help="Generate synthesis prompt")
    prompt_cmd.add_argument("--transcript", type=str, required=True, help="Path to transcript JSON")
    prompt_cmd.add_argument("--moments", type=str, required=True, help="Path to key_moments.json")
    prompt_cmd.add_argument("--verified", type=str, required=True, help="Path to verified moments JSON")
    prompt_cmd.add_argument("--metadata", type=str, required=True, help="Path to metadata JSON")

    # Parse command
    parse_cmd = sub.add_parser("parse", help="Parse synthesis response")
    parse_cmd.add_argument("--response", type=str, required=True, help="Path to LLM response")

    # Apply command
    apply_cmd = sub.add_parser("apply", help="Apply corrections to transcript")
    apply_cmd.add_argument("--transcript", type=str, required=True, help="Path to transcript JSON")
    apply_cmd.add_argument("--synthesis", type=str, required=True, help="Path to synthesis result JSON")

    args = ap.parse_args()

    if args.command == "prompt":
        transcript_data = json.loads(Path(args.transcript).read_text())
        moments_data = json.loads(Path(args.moments).read_text())
        verified_data = json.loads(Path(args.verified).read_text())
        metadata = json.loads(Path(args.metadata).read_text())
        
        # Format transcript
        if isinstance(transcript_data, list):
            transcript_text = "\n".join(
                f"[{int(s.get('start', 0) // 60):02d}:{int(s.get('start', 0) % 60):02d}] {s.get('text', '')}"
                for s in transcript_data
            )
        else:
            transcript_text = str(transcript_data)
        
        prompt = generate_synthesis_prompt(transcript_text, verified_data, metadata)
        print(prompt)
        return 0

    elif args.command == "parse":
        response = Path(args.response).read_text()
        result = parse_synthesis_response(response)
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    elif args.command == "apply":
        transcript = json.loads(Path(args.transcript).read_text())
        synthesis = json.loads(Path(args.synthesis).read_text())
        
        corrections = synthesis.get("key_corrections", [])
        corrected = apply_corrections_to_transcript(transcript, corrections)
        
        print(json.dumps(corrected, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
