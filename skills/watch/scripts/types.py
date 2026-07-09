#!/usr/bin/env python3
"""Type definitions for the /watch skill.

Provides typed dataclasses for all core data structures, Protocol classes for
swappable interfaces, TypeAlias shortcuts for common primitives, and a custom
exception hierarchy.

Targets Python 3.11+ while keeping ``from __future__ import annotations`` for
3.8+ runtime compatibility where needed.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, TypeAlias, runtime_checkable

# ---------------------------------------------------------------------------
# Type aliases — short, semantic names for primitives that appear everywhere
# ---------------------------------------------------------------------------

Seconds: TypeAlias = float
"""Duration or offset in seconds."""

Base64Image: TypeAlias = str
"""Base64-encoded image payload (no data-URI prefix)."""

Timestamp: TypeAlias = str
"""Human-readable time string (``SS``, ``MM:SS``, or ``HH:MM:SS``)."""

Detail: TypeAlias = Literal["transcript", "efficient", "balanced", "token-burner"]
"""Fidelity/speed dial that controls frame-extraction behaviour."""

WhisperBackend: TypeAlias = Literal["groq", "openai"]
"""Supported Whisper transcription backends."""


# ---------------------------------------------------------------------------
# Custom exception hierarchy
# ---------------------------------------------------------------------------

class WatchError(Exception):
    """Base exception for all /watch errors."""


class DownloadError(WatchError):
    """Video download or local-path resolution failed."""


class FrameExtractionError(WatchError):
    """Frame extraction or scene detection failed."""


class TranscriptionError(WatchError):
    """VTT parsing or Whisper API transcription failed."""


class ConfigError(WatchError):
    """Configuration file or environment variable is invalid."""


class FFmpegError(WatchError):
    """An ffmpeg / ffprobe subprocess returned non-zero."""


class APIError(WatchError):
    """A remote API call (Whisper, etc.) failed after retries."""


# ---------------------------------------------------------------------------
# Frozen, slotted dataclasses — value objects with __post_init__ validation
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Frame:
    """A single extracted video frame."""

    index: int
    timestamp_seconds: Seconds
    path: str
    reason: str  # "uniform" | "scene-change" | "first-frame" | "keyframe" | "transcript-cue"

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"Frame index must be >= 0, got {self.index}")
        if self.timestamp_seconds < 0:
            raise ValueError(
                f"Frame timestamp must be >= 0, got {self.timestamp_seconds}"
            )


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """A single time-aligned transcript segment."""

    start: Seconds
    end: Seconds
    text: str

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"Segment start must be >= 0, got {self.start}")
        if self.end < self.start:
            raise ValueError(
                f"Segment end ({self.end}) must be >= start ({self.start})"
            )
        if not self.text.strip():
            raise ValueError("Segment text must not be empty/whitespace-only")


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Probe results from ffprobe for a video file."""

    duration_seconds: Seconds
    width: int | None
    height: int | None
    codec: str | None
    size_bytes: int
    has_audio: bool

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError(
                f"Duration must be >= 0, got {self.duration_seconds}"
            )
        if self.size_bytes < 0:
            raise ValueError(f"Size must be >= 0, got {self.size_bytes}")
        if self.width is not None and self.width <= 0:
            raise ValueError(f"Width must be > 0 or None, got {self.width}")
        if self.height is not None and self.height <= 0:
            raise ValueError(f"Height must be > 0 or None, got {self.height}")

    @property
    def resolution(self) -> str:
        """Return ``WxH`` string or ``"unknown"``."""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "unknown"


@dataclass(frozen=True, slots=True)
class FrameMetadata:
    """Statistics about a frame-extraction run."""

    engine: str  # "scene" | "uniform" | "keyframe" | "timestamps" | "none"
    candidate_count: int
    selected_count: int
    deduped_count: int = 0
    fallback: bool = False
    dropped_out_of_window: int = 0

    def __post_init__(self) -> None:
        for attr in (
            "candidate_count",
            "selected_count",
            "deduped_count",
            "dropped_out_of_window",
        ):
            val = getattr(self, attr)
            if val < 0:
                raise ValueError(f"{attr} must be >= 0, got {val}")


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Outcome of a video download or local-path resolution."""

    video_path: str | None
    subtitle_path: str | None
    info: dict[str, Any]
    downloaded: bool

    def __post_init__(self) -> None:
        if self.downloaded and self.video_path is None:
            raise ValueError(
                "downloaded=True requires a video_path"
            )
        if not self.info:
            raise ValueError("info dict must not be empty")


@dataclass(frozen=True, slots=True)
class CueMeta:
    """Metadata returned alongside cue (transcript-timestamp) frames."""

    engine: str = "timestamps"
    candidate_count: int = 0
    selected_count: int = 0
    dropped_out_of_window: int = 0
    fallback: bool = False

    def __post_init__(self) -> None:
        for attr in (
            "candidate_count",
            "selected_count",
            "dropped_out_of_window",
        ):
            val = getattr(self, attr)
            if val < 0:
                raise ValueError(f"{attr} must be >= 0, got {val}")


@dataclass(frozen=True, slots=True)
class WhisperConfig:
    """Configuration for the Whisper transcription fallback."""

    backend: WhisperBackend
    api_key: str
    max_upload_bytes: int = 24 * 1024 * 1024
    max_attempts: int = 4
    max_429_retries: int = 2

    def __post_init__(self) -> None:
        if self.max_upload_bytes <= 0:
            raise ValueError(
                f"max_upload_bytes must be > 0, got {self.max_upload_bytes}"
            )
        if self.max_attempts < 1:
            raise ValueError(
                f"max_attempts must be >= 1, got {self.max_attempts}"
            )
        if not self.api_key:
            raise ValueError("api_key must not be empty")


@dataclass(frozen=True, slots=True)
class WatchConfig:
    """Unified configuration for a /watch run."""

    source: str
    detail: Detail = "balanced"
    max_frames: int | None = 100
    resolution: int = 512
    fps: float | None = None
    timestamps: str | None = None
    start: Timestamp | None = None
    end: Timestamp | None = None
    out_dir: str | None = None
    no_whisper: bool = False
    whisper_backend: WhisperBackend | None = None
    no_dedup: bool = False
    config_file: str = str(Path.home() / ".config" / "watch" / ".env")

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if self.resolution <= 0:
            raise ValueError(f"resolution must be > 0, got {self.resolution}")
        if self.max_frames is not None and self.max_frames < 1:
            raise ValueError(
                f"max_frames must be >= 1 or None, got {self.max_frames}"
            )
        if self.fps is not None and self.fps <= 0:
            raise ValueError(f"fps must be > 0 or None, got {self.fps}")

    @property
    def work_dir(self) -> Path:
        """Resolved working directory path."""
        if self.out_dir:
            return Path(self.out_dir).expanduser().resolve()
        import tempfile
        return Path(tempfile.mkdtemp(prefix="watch-"))


# ---------------------------------------------------------------------------
# Protocol classes — structural interfaces for swappable backends
# ---------------------------------------------------------------------------

@runtime_checkable
class VideoDownloader(Protocol):
    """Interface for video download implementations."""

    def download(
        self,
        source: str,
        out_dir: Path,
        audio_only: bool = False,
    ) -> DownloadResult:
        """Download a video from *source* (URL or path) into *out_dir*."""
        ...  # pragma: no cover


@runtime_checkable
class FrameExtractor(Protocol):
    """Interface for frame extraction implementations."""

    def extract_frames(
        self,
        video_path: str,
        out_dir: Path,
        fps: float,
        resolution: int = 512,
        max_frames: int | None = 100,
        start_seconds: Seconds | None = None,
        end_seconds: Seconds | None = None,
    ) -> tuple[list[Frame], FrameMetadata]:
        """Extract frames from *video_path* and return them with metadata."""
        ...  # pragma: no cover


@runtime_checkable
class Transcriber(Protocol):
    """Interface for transcription implementations (VTT parser, Whisper, etc.)."""

    def transcribe(
        self,
        video_path: str,
        audio_out: Path,
        backend: str | None = None,
        api_key: str | None = None,
    ) -> tuple[list[TranscriptSegment], str]:
        """Transcribe *video_path*; return segments and backend name."""
        ...  # pragma: no cover


@runtime_checkable
class AIClient(Protocol):
    """Interface for AI/vision clients that analyse frames."""

    def analyse_frames(
        self,
        frames: list[Frame],
        transcript: str | None = None,
        prompt: str | None = None,
    ) -> str:
        """Send frames (and optional transcript) to an AI model; return text."""
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Helpers for converting between dicts and typed dataclasses
# ---------------------------------------------------------------------------

def frame_from_dict(d: dict[str, Any]) -> Frame:
    """Create a :class:`Frame` from a legacy dict."""
    return Frame(
        index=d["index"],
        timestamp_seconds=float(d["timestamp_seconds"]),
        path=d["path"],
        reason=d.get("reason", "selected"),
    )


def segment_from_dict(d: dict[str, Any]) -> TranscriptSegment:
    """Create a :class:`TranscriptSegment` from a legacy dict."""
    return TranscriptSegment(
        start=float(d["start"]),
        end=float(d["end"]),
        text=d["text"],
    )


def metadata_from_dict(d: dict[str, Any]) -> VideoMetadata:
    """Create a :class:`VideoMetadata` from a legacy ffprobe dict."""
    return VideoMetadata(
        duration_seconds=float(d.get("duration_seconds", 0.0)),
        width=d.get("width"),
        height=d.get("height"),
        codec=d.get("codec"),
        size_bytes=int(d.get("size_bytes", 0)),
        has_audio=bool(d.get("has_audio", False)),
    )


def frame_meta_from_dict(d: dict[str, Any]) -> FrameMetadata:
    """Create a :class:`FrameMetadata` from a legacy dict."""
    return FrameMetadata(
        engine=d.get("engine", "unknown"),
        candidate_count=int(d.get("candidate_count", 0)),
        selected_count=int(d.get("selected_count", 0)),
        deduped_count=int(d.get("deduped_count", 0)),
        fallback=bool(d.get("fallback", False)),
        dropped_out_of_window=int(d.get("dropped_out_of_window", 0)),
    )


def download_result_from_dict(d: dict[str, Any]) -> DownloadResult:
    """Create a :class:`DownloadResult` from a legacy dict."""
    return DownloadResult(
        video_path=d.get("video_path"),
        subtitle_path=d.get("subtitle_path"),
        info=d.get("info", {}),
        downloaded=bool(d.get("downloaded", False)),
    )


# ---------------------------------------------------------------------------
# Convenience: report type
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class WatchReport:
    """Complete output of a /watch run, ready for markdown rendering."""

    source: str
    title: str | None
    uploader: str | None
    duration_seconds: Seconds
    focused: bool
    effective_start: Seconds
    effective_end: Seconds
    effective_duration: Seconds
    detail: Detail
    metadata: VideoMetadata
    frame_metadata: FrameMetadata
    frames: list[Frame]
    cue_frames: list[Frame]
    cue_meta: CueMeta
    transcript_segments: list[TranscriptSegment]
    transcript_text: str | None
    transcript_source: str | None
    work_dir: Path
    frame_cap_label: str = "100"
    engine_label: str = "scene-aware frames"
    range_mode: str = "full"

    @property
    def has_frames(self) -> bool:
        return bool(self.frames)

    @property
    def has_transcript(self) -> bool:
        return self.transcript_text is not None and bool(self.transcript_text.strip())

    @property
    def total_frames(self) -> int:
        return len(self.frames) + len(self.cue_frames)
