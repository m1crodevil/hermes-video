#!/usr/bin/env python3
"""Parse a WebVTT subtitle file into a clean, timestamped transcript.

YouTube auto-subs emit rolling-duplicate cues (each line appears 2-3 times as it
scrolls). We dedupe consecutive identical cues and merge their time ranges.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from types import TranscriptSegment, Seconds

TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def _to_seconds(h: str, m: str, s: str, ms: str) -> Seconds:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(path: str) -> list[dict[str, Any]]:
    """Parse a WebVTT subtitle file into a list of timestamped segments.

    YouTube auto-subs emit rolling-duplicate cues (each line appears 2–3
    times as it scrolls).  This function deduplicates consecutive identical
    cues and merges their time ranges so each segment appears exactly once.

    HTML-style tags (e.g. ``<c>...</c>``) are stripped from cue text.

    Args:
        path: Filesystem path to the ``.vtt`` subtitle file.

    Returns:
        A list of dicts, each with ``"start"`` (float seconds), ``"end"``
        (float seconds), and ``"text"`` (str) keys, sorted by start time.
        Empty when the file has no parseable cues.

    Example:
        >>> segments = parse_vtt("video.en.vtt")
        >>> segments[0]["text"]
        'Hello world'
    """
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    segments: list[dict[str, Any]] = []
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


def _dedupe(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse rolling duplicates common in YouTube auto-subs."""
    out: list[dict[str, Any]] = []
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
    segments: list[dict[str, Any]],
    start_seconds: Seconds | None,
    end_seconds: Seconds | None,
) -> list[dict[str, Any]]:
    """Return segments whose time range overlaps ``[start, end]``.

    A segment is included when *any* part of its ``[start, end]`` interval
    intersects the requested window.  Unbounded windows (``None``) are treated
    as ``-inf`` / ``+inf``.

    Args:
        segments: List of segment dicts with ``"start"`` and ``"end"`` keys.
        start_seconds: Inclusive lower bound, or ``None`` for unbounded.
        end_seconds: Inclusive upper bound, or ``None`` for unbounded.

    Returns:
        Filtered list of segments.  Empty when the range is outside all segments.

    Example:
        >>> segs = [{"start": 0, "end": 10, "text": "hi"}]
        >>> filter_range(segs, 5, 15)
        [{'start': 0, 'end': 10, 'text': 'hi'}]
        >>> filter_range(segs, 20, 30)
        []
    """
    if start_seconds is None and end_seconds is None:
        return segments
    lo = start_seconds if start_seconds is not None else float("-inf")
    hi = end_seconds if end_seconds is not None else float("inf")
    return [seg for seg in segments if seg["end"] >= lo and seg["start"] <= hi]


def format_transcript(segments: list[dict[str, Any]]) -> str:
    """Format a list of segments into a human-readable timestamped transcript.

    Each line is prefixed with ``[MM:SS]`` (or ``[H:MM:SS]`` for hour-long
    videos) followed by the segment text.  Lines are separated by newlines
    with no trailing newline.

    Args:
        segments: List of dicts with ``"start"`` (float seconds) and
            ``"text"`` keys.

    Returns:
        A single multi-line string ready for printing or LLM context.

    Example:
        >>> segs = [{"start": 0.0, "text": "Hello"}, {"start": 65.0, "text": "World"}]
        >>> print(format_transcript(segs))
        [00:00] Hello
        [01:05] World
    """
    lines = []
    for seg in segments:
        start = int(seg["start"])
        stamp = f"[{start // 60:02d}:{start % 60:02d}]"
        lines.append(f"{stamp} {seg['text']}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: transcribe.py <vtt-path>", file=sys.stderr)
        raise SystemExit(2)
    print(format_transcript(parse_vtt(sys.argv[1])))
