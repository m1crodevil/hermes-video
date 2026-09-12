"""Simplified output models (feature-parity with hermes-video-rs)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[dict] | None = None


@dataclass
class FrameInfo:
    path: str
    timestamp: float
    timestamp_fmt: str


@dataclass
class AnalysisCapabilities:
    transcript: bool = True
    frame_extraction: bool = False
    visual_verification: bool = False


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

    def to_dict(self):
        return asdict(self)

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
