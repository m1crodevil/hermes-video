#!/usr/bin/env python3
"""Pydantic models for structured /watch output.

Provides validated, serializable data structures for the entire watch pipeline:
video metadata, frames, transcript segments, and the complete WatchReport.

Usage:
    report = WatchReport(metadata=meta, detail="balanced", frames=frames)
    print(report.to_markdown())   # human-readable
    report.to_json_file(path)     # machine-readable JSON
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, computed_field


# ── Enums ────────────────────────────────────────────────────────────────

class TranscriptSource(str, Enum):
    """Source of transcript data."""
    JSON3 = "json3"
    VTT = "vtt"
    WHISPER_GROQ = "whisper_groq"
    WHISPER_OPENAI = "whisper_openai"
    NONE = "none"


class FrameReason(str, Enum):
    """Why a frame was selected."""
    SCENE_CHANGE = "scene-change"
    KEYFRAME = "keyframe"
    FIRST_FRAME = "first-frame"
    TRANSCRIPT_CUE = "transcript-cue"
    UNIFORM = "uniform"
    SELECTED = "selected"


class DetailMode(str, Enum):
    """Fidelity/speed dial for frame extraction."""
    TRANSCRIPT = "transcript"
    EFFICIENT = "efficient"
    BALANCED = "balanced"
    TOKEN_BURNER = "token-burner"


# ── Helpers ──────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _fmt_duration(seconds: float) -> str:
    """Format duration with decimal for sub-second precision."""
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# ── Core Models ──────────────────────────────────────────────────────────

class WordTiming(BaseModel):
    """Single word with timing from JSON3 captions."""
    model_config = ConfigDict(use_enum_values=True)

    word: str
    start: float          # seconds from video start
    confidence: float     # ASR confidence 0-1 (from acAsrConf)


class TranscriptSegment(BaseModel):
    """A chunk of transcript text with timing bounds."""
    start: float          # seconds
    end: float            # seconds
    text: str
    words: list[WordTiming] = []

    @computed_field
    @property
    def start_fmt(self) -> str:
        return _fmt_time(self.start)

    @computed_field
    @property
    def end_fmt(self) -> str:
        return _fmt_time(self.end)

    @computed_field
    @property
    def duration(self) -> float:
        return round(self.end - self.start, 2)


class Frame(BaseModel):
    """A single extracted frame from the video."""
    model_config = ConfigDict(use_enum_values=True)

    path: str
    timestamp: float      # seconds from video start
    reason: FrameReason
    deduped: bool = False

    @computed_field
    @property
    def timestamp_fmt(self) -> str:
        """Human-readable timestamp (MM:SS or HH:MM:SS)."""
        return _fmt_time(self.timestamp)


class FrameStats(BaseModel):
    """Statistics about frame extraction."""
    total_candidates: int
    selected: int
    deduped: int = 0
    engine: str            # "scene" | "keyframes" | "uniform"
    fallback: bool = False

    @computed_field
    @property
    def selection_rate(self) -> str:
        """Percentage of candidates selected."""
        if self.total_candidates == 0:
            return "0%"
        pct = (self.selected / self.total_candidates) * 100
        return f"{pct:.0f}%"


class VideoMetadata(BaseModel):
    """Video source information."""
    source: str
    title: str | None = None
    uploader: str | None = None
    duration: float
    width: int | None = None
    height: int | None = None
    codec: str | None = None
    has_audio: bool = True
    detected_language: str | None = None

    @computed_field
    @property
    def duration_fmt(self) -> str:
        """Human-readable duration (MM:SS or HH:MM:SS)."""
        return _fmt_duration(self.duration)

    @computed_field
    @property
    def resolution(self) -> str | None:
        """Resolution string like '1280x720'."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return None


class FocusRange(BaseModel):
    """Optional focus range for partial video analysis."""
    start: float
    end: float

    @computed_field
    @property
    def start_fmt(self) -> str:
        return _fmt_time(self.start)

    @computed_field
    @property
    def end_fmt(self) -> str:
        return _fmt_time(self.end)

    @computed_field
    @property
    def duration(self) -> float:
        return round(self.end - self.start, 1)

    @computed_field
    @property
    def duration_fmt(self) -> str:
        return _fmt_duration(self.duration)


# ── Main Report ──────────────────────────────────────────────────────────

class WatchReport(BaseModel):
    """Complete structured output from /watch pipeline.

    This is the single source of truth for all watch output.
    Serialize to JSON for pipelines, or call to_markdown() for humans.
    """
    model_config = ConfigDict(use_enum_values=True)

    metadata: VideoMetadata
    detail: str  # DetailMode value as string
    focus_range: FocusRange | None = None

    # Frames
    frames: list[Frame] = []
    frame_stats: FrameStats | None = None

    # Transcript
    transcript_source: str = TranscriptSource.NONE.value
    transcript_segments: list[TranscriptSegment] = []
    transcript_text: str | None = None  # pre-formatted string

    # Warnings
    warnings: list[str] = []

    # ── Serialization ────────────────────────────────────────────────

    def to_json(self) -> str:
        """Serialize to JSON string with pretty formatting."""
        return self.model_dump_json(indent=2)

    def to_json_file(self, path: str | Path) -> Path:
        """Write JSON report to file. Returns the path written."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")
        return p

    def to_dict(self) -> dict:
        """Serialize to dict (Python objects, not JSON-safe)."""
        return self.model_dump()

    # ── Markdown Renderer ────────────────────────────────────────────

    def to_markdown(self) -> str:
        """Render comprehensive markdown report for human reading."""
        lines: list[str] = []

        # Header
        lines.append("# 🎬 Watch Report")
        lines.append("")

        # Metadata section
        lines.append("## 📋 Metadata")
        lines.append("")
        meta = self.metadata
        meta_rows = [
            ("Source", meta.source),
            ("Title", meta.title or "—"),
            ("Uploader", meta.uploader or "—"),
            ("Duration", f"{meta.duration_fmt} ({meta.duration:.1f}s)"),
        ]
        if meta.resolution:
            meta_rows.append(("Resolution", f"{meta.resolution} ({meta.codec or 'unknown'})"))
        if meta.detected_language:
            meta_rows.append(("Language", meta.detected_language))
        meta_rows.append(("Detail", self.detail))

        if self.focus_range:
            fr = self.focus_range
            meta_rows.append(("Focus Range", f"{fr.start_fmt} → {fr.end_fmt} ({fr.duration_fmt})"))

        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        for label, value in meta_rows:
            lines.append(f"| {label} | {value} |")
        lines.append("")

        # Frame stats section
        if self.frame_stats:
            fs = self.frame_stats
            lines.append("## 📊 Frame Analysis")
            lines.append("")
            lines.append(f"- **Engine:** {fs.engine}")
            lines.append(f"- **Candidates:** {fs.total_candidates} → **Selected:** {fs.selected} ({fs.selection_rate})")
            if fs.deduped:
                lines.append(f"- **Deduped:** {fs.deduped} near-duplicate{'s' if fs.deduped != 1 else ''} dropped")
            if fs.fallback:
                lines.append("- **Fallback:** uniform sampling (scene detection failed)")
            lines.append("")

        # Frame timeline
        if self.frames:
            lines.append("### Frame Timeline")
            lines.append("")
            lines.append("| # | Timestamp | File | Reason |")
            lines.append("|---|-----------|------|--------|")
            for i, frame in enumerate(self.frames, 1):
                fname = Path(frame.path).name
                dedup = " *(deduped)*" if frame.deduped else ""
                lines.append(f"| {i} | {frame.timestamp_fmt} | {fname} | {frame.reason}{dedup} |")
            lines.append("")

        # Transcript section
        if self.transcript_source and self.transcript_source != TranscriptSource.NONE.value:
            lines.append("## 📝 Transcript")
            lines.append("")
            lines.append(f"- **Source:** {self.transcript_source}")
            lines.append(f"- **Segments:** {len(self.transcript_segments)}")
            lines.append("")

            if self.transcript_text:
                lines.append("### Full Transcript")
                lines.append("")
                lines.append("```")
                lines.append(self.transcript_text)
                lines.append("```")
            elif self.transcript_segments:
                lines.append("### Full Transcript")
                lines.append("")
                lines.append("```")
                for seg in self.transcript_segments:
                    stamp = seg.start_fmt
                    lines.append(f"[{stamp}] {seg.text}")
                lines.append("```")
            lines.append("")
        else:
            lines.append("## 📝 Transcript")
            lines.append("")
            lines.append("_No transcript available._")
            lines.append("")

        # Warnings
        if self.warnings:
            lines.append("## ⚠️ Warnings")
            lines.append("")
            for w in self.warnings:
                lines.append(f"- {w}")
            lines.append("")

        return "\n".join(lines)


# ── Builder helpers (convenience) ────────────────────────────────────────

def build_report(
    *,
    source: str,
    title: str | None = None,
    uploader: str | None = None,
    duration: float = 0.0,
    width: int | None = None,
    height: int | None = None,
    codec: str | None = None,
    has_audio: bool = True,
    detected_language: str | None = None,
    detail: str = "balanced",
    focus_start: float | None = None,
    focus_end: float | None = None,
    frames: list[dict] | None = None,
    frame_meta: dict | None = None,
    transcript_source: str = "none",
    transcript_segments: list[dict] | None = None,
    transcript_text: str | None = None,
    warnings: list[str] | None = None,
) -> WatchReport:
    """Build a WatchReport from raw pipeline data dicts.

    This is the bridge between the existing dict-based pipeline and
    the new Pydantic models. Call this in watch.py after collecting
    all pipeline results.
    """
    meta = VideoMetadata(
        source=source,
        title=title,
        uploader=uploader,
        duration=duration,
        width=width,
        height=height,
        codec=codec,
        has_audio=has_audio,
        detected_language=detected_language,
    )

    focus = None
    if focus_start is not None and focus_end is not None:
        focus = FocusRange(start=focus_start, end=focus_end)

    frame_models = []
    if frames:
        for f in frames:
            frame_models.append(Frame(
                path=f.get("path", ""),
                timestamp=f.get("timestamp_seconds", 0.0),
                reason=f.get("reason", "selected"),
                deduped=f.get("deduped", False),
            ))

    stats = None
    if frame_meta:
        stats = FrameStats(
            total_candidates=frame_meta.get("candidate_count", 0),
            selected=frame_meta.get("selected_count", 0),
            deduped=frame_meta.get("deduped_count", 0),
            engine=frame_meta.get("engine", "unknown"),
            fallback=frame_meta.get("fallback", False),
        )

    segments = []
    if transcript_segments:
        for seg in transcript_segments:
            words = []
            for w in seg.get("words", []):
                words.append(WordTiming(
                    word=w.get("word", ""),
                    start=w.get("start", 0.0),
                    confidence=w.get("confidence", 0.0),
                ))
            segments.append(TranscriptSegment(
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
                text=seg.get("text", ""),
                words=words,
            ))

    return WatchReport(
        metadata=meta,
        detail=detail,
        focus_range=focus,
        frames=frame_models,
        frame_stats=stats,
        transcript_source=transcript_source,
        transcript_segments=segments,
        transcript_text=transcript_text,
        warnings=warnings or [],
    )
