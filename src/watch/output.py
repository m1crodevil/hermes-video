"""Simplified output models (feature-parity with hermes-video-rs)."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[dict] | None = None

    def to_dict(self):
        return {"start": self.start, "end": self.end, "text": self.text, "words": self.words}


@dataclass
class FrameInfo:
    path: str
    timestamp: float
    timestamp_fmt: str

    def to_dict(self):
        return {"path": self.path, "timestamp": self.timestamp, "timestamp_fmt": self.timestamp_fmt}


@dataclass
class AnalysisCapabilities:
    transcript: bool = True
    scene_detection: bool = False
    frame_extraction: bool = False
    visual_verification: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class WatchReport:
    title: str
    source: str
    uploader: str | None
    language: str | None
    frames: list[FrameInfo]
    transcript: list[TranscriptSegment]
    transcript_source: str
    video_access: str
    analysis_capabilities: AnalysisCapabilities
    duration: float
    working_dir: str
    warnings: list[str]
    scene_boundaries: list[float] | None
    scene_count: int | None

    def to_dict(self):
        return {
            "title": self.title,
            "source": self.source,
            "uploader": self.uploader,
            "language": self.language,
            "frames": [f.to_dict() for f in self.frames],
            "transcript": [t.to_dict() for t in self.transcript],
            "transcript_source": self.transcript_source,
            "video_access": self.video_access,
            "analysis_capabilities": self.analysis_capabilities.to_dict(),
            "duration": self.duration,
            "working_dir": self.working_dir,
            "warnings": self.warnings,
            "scene_boundaries": self.scene_boundaries,
            "scene_count": self.scene_count,
        }

    def to_json_file(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title or 'Video Analysis'}",
            f"**Source:** {self.source}",
            f"**Duration:** {self.duration:.1f}s",
        ]
        if self.uploader:
            lines.append(f"**Uploader:** {self.uploader}")
        if self.language:
            lines.append(f"**Language:** {self.language}")
        lines.append(f"**Transcript source:** {self.transcript_source}")
        lines.append(f"**Video access:** {self.video_access}")
        lines.append("## Frames")
        if self.frames:
            for f in self.frames:
                lines.append(f"- [{f.timestamp_fmt}] `{f.path}`")
        else:
            lines.append("_No frames extracted._")
        lines.append("## Transcript")
        if self.transcript:
            for seg in self.transcript:
                lines.append(f"[{seg.start:.1f}s] {seg.text}")
        else:
            lines.append("_No transcript._")
        if self.warnings:
            lines.append("## Warnings")
            lines.extend(f"- {w}" for w in self.warnings)
        return "\n".join(lines)
