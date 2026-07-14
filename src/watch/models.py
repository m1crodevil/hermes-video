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
    GAP_FILL = "gap-fill"


class DetailMode(str, Enum):
    """Fidelity/speed dial for frame extraction."""
    TRANSCRIPT = "transcript"
    EFFICIENT = "efficient"
    BALANCED = "balanced"
    TOKEN_BURNER = "token-burner"


class MomentReason(str, Enum):
    """Why a moment needs visual verification."""
    PROPER_NOUN = "proper_noun"
    CLAIM = "claim"
    DEICTIC = "deictic"
    SPEAKER_ID = "speaker_id"
    VISUAL_CONTEXT = "visual_context"
    ENTITY = "entity"
    TOPIC_TRANSITION = "topic_transition"
    KEY_ARGUMENT = "key_argument"
    UNKNOWN = "unknown"


class KeyMoment(BaseModel):
    """A moment in the transcript that needs visual verification."""
    model_config = ConfigDict(use_enum_values=True)

    timestamp: float          # seconds from video start
    timestamp_fmt: str        # "MM:SS" format
    word: str                 # triggering word/phrase
    context: str              # surrounding text (for LLM context)
    reason: MomentReason      # why this needs verification
    question: str             # what to ask vision model
    priority: int             # 1=critical, 5=nice-to-have
    vision_result: str | None = None  # result from vision analysis
    correction: str | None = None     # corrected text if any

    @computed_field
    @property
    def timestamp_seconds(self) -> float:
        return self.timestamp


class KeyMomentStats(BaseModel):
    """Statistics about key moment detection."""
    total: int
    by_reason: dict[str, int] = {}
    by_priority: dict[int, int] = {}


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
def _fmt_count(n: int | float | None) -> str:
    """Format a number as human-readable (e.g. 8494167 → 8.4M)."""
    if n is None:
        return "—"
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


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
    # Channel stats (from yt-dlp, YouTube only)
    channel_id: str | None = None
    channel_url: str | None = None
    channel_follower_count: int | None = None
    channel_is_verified: bool = False
    uploader_id: str | None = None
    uploader_url: str | None = None

    # Video stats (from yt-dlp, YouTube only)
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    upload_date: str | None = None
    tags: list[str] = []
    categories: list[str] = []

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

    # Key Moments (from LLM-driven analysis)
    key_moments: list[KeyMoment] = []
    key_moment_stats: KeyMomentStats | None = None

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

    def to_markdown(self, compact: bool = False) -> str:
        """Render comprehensive markdown report for human reading.
        
        When compact=True, skips the full transcript section (useful when
        output is also written to JSON, to avoid terminal truncation).
        """
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
        # Channel stats (YouTube)
        if meta.channel_follower_count is not None:
            verified = " ✓" if meta.channel_is_verified else ""
            meta_rows.append(("Channel", f"{meta.uploader or '—'}{verified}"))
            meta_rows.append(("Subscribers", _fmt_count(meta.channel_follower_count)))
        if meta.view_count is not None:
            meta_rows.append(("Views", _fmt_count(meta.view_count)))
        if meta.like_count is not None:
            meta_rows.append(("Likes", _fmt_count(meta.like_count)))
        if meta.comment_count is not None:
            meta_rows.append(("Comments", _fmt_count(meta.comment_count)))
        if meta.upload_date:
            formatted_date = f"{meta.upload_date[:4]}-{meta.upload_date[4:6]}-{meta.upload_date[6:]}"
            meta_rows.append(("Published", formatted_date))
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
            if compact:
                lines.append("_Full transcript available in `report.json`._")
                lines.append("")
            elif self.transcript_text:
                lines.append("### Full Transcript")
                lines.append("")
                lines.append("```")
                lines.append(self.transcript_text)
                lines.append("```")
                lines.append("")
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

        # Key Moments section
        if self.key_moments:
            lines.append("## 🎯 Key Moments")
            lines.append("")
            lines.append(f"- **Total:** {len(self.key_moments)} moments identified")
            if self.key_moment_stats:
                stats = self.key_moment_stats
                if stats.by_reason:
                    reason_str = ", ".join(f"{k}: {v}" for k, v in stats.by_reason.items())
                    lines.append(f"- **By reason:** {reason_str}")
            lines.append("")
            lines.append("| # | Timestamp | Word | Reason | Priority | Question |")
            lines.append("|---|-----------|------|--------|----------|----------|")
            for i, m in enumerate(self.key_moments, 1):
                lines.append(f"| {i} | {m.timestamp_fmt} | {m.word} | {m.reason} | {m.priority} | {m.question[:50]}... |")
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
    # Channel stats
    channel_id: str | None = None,
    channel_url: str | None = None,
    channel_follower_count: int | None = None,
    channel_is_verified: bool = False,
    uploader_id: str | None = None,
    uploader_url: str | None = None,
    # Video stats
    view_count: int | None = None,
    like_count: int | None = None,
    comment_count: int | None = None,
    upload_date: str | None = None,
    tags: list[str] | None = None,
    categories: list[str] | None = None,
    detail: str = "balanced",
    focus_start: float | None = None,
    focus_end: float | None = None,
    frames: list[dict] | None = None,
    frame_meta: dict | None = None,
    transcript_source: str = "none",
    transcript_segments: list[dict] | None = None,
    transcript_text: str | None = None,
    key_moments: list[dict] | None = None,
    key_moment_stats: dict | None = None,
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
        channel_id=channel_id,
        channel_url=channel_url,
        channel_follower_count=channel_follower_count,
        channel_is_verified=channel_is_verified,
        uploader_id=uploader_id,
        uploader_url=uploader_url,
        view_count=view_count,
        like_count=like_count,
        comment_count=comment_count,
        upload_date=upload_date,
        tags=tags or [],
        categories=categories or [],
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

    # Build key moment models
    key_moment_models = []
    if key_moments:
        for m in key_moments:
            # Handle timestamp as string (MM:SS) or float (seconds)
            ts_raw = m.get("timestamp", "0:00")
            if isinstance(ts_raw, str):
                # Parse MM:SS or HH:MM:SS format
                parts = ts_raw.strip().split(":")
                if len(parts) == 2:
                    ts_seconds = int(parts[0]) * 60 + float(parts[1])
                elif len(parts) == 3:
                    ts_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                else:
                    ts_seconds = float(parts[0])
                ts_fmt = ts_raw
            else:
                ts_seconds = float(ts_raw)
                # Format as MM:SS
                mins = int(ts_seconds // 60)
                secs = int(ts_seconds % 60)
                ts_fmt = f"{mins}:{secs:02d}"

            key_moment_models.append(KeyMoment(
                timestamp=ts_seconds,
                timestamp_fmt=ts_fmt,
                word=m.get("word", ""),
                context=m.get("context", ""),
                reason=m.get("reason", "unknown"),
                question=m.get("question", ""),
                priority=m.get("priority", 3),
                vision_result=m.get("vision_result"),
                correction=m.get("correction"),
            ))

    key_stats = None
    if key_moment_stats:
        key_stats = KeyMomentStats(
            total=key_moment_stats.get("total", 0),
            by_reason=key_moment_stats.get("by_reason", {}),
            by_priority=key_moment_stats.get("by_priority", {}),
        )

    return WatchReport(
        metadata=meta,
        detail=detail,
        focus_range=focus,
        frames=frame_models,
        frame_stats=stats,
        transcript_source=transcript_source,
        transcript_segments=segments,
        transcript_text=transcript_text,
        key_moments=key_moment_models,
        key_moment_stats=key_stats,
        warnings=warnings or [],
    )
