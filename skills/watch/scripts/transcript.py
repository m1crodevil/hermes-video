#!/usr/bin/env python3
"""Parse YouTube JSON3 subtitle files into clean, timestamped transcripts.

JSON3 (fmt=json3) is YouTube's structured caption format with word-level timing
and ASR confidence scores. Falls back to VTT parsing if a .vtt file is provided.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ── VTT fallback (kept for local .vtt files) ──────────────────────────────

TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def _to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(path: str) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    segments: list[dict] = []
    i = 0
    while i < len(lines):
        match = TS_RE.match(lines[i])
        if not match:
            i += 1
            continue

        start = _to_seconds(*match.groups()[:4])
        end = _to_seconds(*match.groups()[4:])
        i += 1

        cue_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            cleaned = TAG_RE.sub("", lines[i]).strip()
            if cleaned:
                cue_lines.append(cleaned)
            i += 1

        cue_text = " ".join(cue_lines).strip()
        if cue_text:
            segments.append({"start": round(start, 2), "end": round(end, 2), "text": cue_text})
        i += 1

    return _dedupe(segments)


# ── JSON3 parser (primary) ────────────────────────────────────────────────

def parse_json3(path: str) -> list[dict]:
    """Parse YouTube JSON3 subtitle format.

    JSON3 has word-level timing via tOffsetMs on each seg, and ASR confidence
    via acAsrConf. This parser returns segments with an optional `words` list
    for callers that want word-level granularity.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="ignore"))
    segments: list[dict] = []

    for event in data.get("events", []):
        segs = event.get("segs", [])
        if not segs:
            continue

        # Join all segs; skip pure newline events
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if not text or text == "\n":
            continue

        start_ms = event.get("tStartMs", 0)
        dur_ms = event.get("dDurationMs", 0)
        start = start_ms / 1000.0
        end = (start_ms + dur_ms) / 1000.0

        # Build word-level list from segs that have tOffsetMs
        words: list[dict] = []
        for seg in segs:
            utf8 = seg.get("utf8", "").strip()
            if not utf8:
                continue
            offset_ms = seg.get("tOffsetMs", 0)
            words.append({
                "word": utf8,
                "start": round((start_ms + offset_ms) / 1000.0, 3),
                "confidence": seg.get("acAsrConf", 0),
            })

        segments.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "text": text,
            "words": words,
        })

    return _dedupe(segments)


def _dedupe(segments: list[dict]) -> list[dict]:
    """Collapse rolling duplicates common in YouTube auto-subs."""
    out: list[dict] = []
    for seg in segments:
        if out and seg["text"] == out[-1]["text"]:
            out[-1]["end"] = seg["end"]
            continue
        if out and seg["text"].startswith(out[-1]["text"] + " "):
            out[-1]["text"] = seg["text"]
            out[-1]["end"] = seg["end"]
            continue
        out.append(seg)
    return out


def filter_range(
    segments: list[dict],
    start_seconds: float | None,
    end_seconds: float | None,
) -> list[dict]:
    """Return segments whose time range overlaps [start, end]."""
    if start_seconds is None and end_seconds is None:
        return segments
    lo = start_seconds if start_seconds is not None else float("-inf")
    hi = end_seconds if end_seconds is not None else float("inf")
    return [seg for seg in segments if seg["end"] >= lo and seg["start"] <= hi]


def format_transcript(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        start = int(seg["start"])
        stamp = f"[{start // 60:02d}:{start % 60:02d}]"
        lines.append(f"{stamp} {seg['text']}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: transcribe.py <json3-or-vtt-path>", file=sys.stderr)
        raise SystemExit(2)

    path = sys.argv[1]
    if path.endswith(".json3"):
        segments = parse_json3(path)
    else:
        segments = parse_vtt(path)
    print(format_transcript(segments))
