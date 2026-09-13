"""Minimal report output for /watch (Rust parity)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class WatchReport:
    title: str = ""
    source: str = ""
    uploader: str | None = None
    language: str | None = None
    duration: float | None = None
    transcript_source: str = ""
    video_access: str = "available"
    transcript: list[dict] = field(default_factory=list)
    scene_boundaries: list[dict] = field(default_factory=list)
    frames: list[dict] = field(default_factory=list)
    analysis_capabilities: dict[str, bool] = field(default_factory=dict)
    working_dir: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def write_markdown(self, path: Path) -> None:
        lines = [
            f"# {self.title or 'Video Analysis'}\n",
            f"**Source:** {self.source}\n",
            f"**Uploader:** {self.uploader or 'N/A'}\n",
            f"**Language:** {self.language or 'N/A'}\n",
            f"**Duration:** {self._fmt_duration()}\n",
            f"**Transcript source:** {self.transcript_source}\n",
            f"**Video access:** {self.video_access}\n\n",
            "## Summary\n\n",
            self._summary_text(),
            "\n\n## Transcript\n\n",
        ]
        for seg in self.transcript:
            stamp = self._fmt_time(seg.get("start", 0))
            lines.append(f"[{stamp}] {seg.get('text', '')}\n")
        path.write_text("".join(lines), encoding="utf-8")

    def _fmt_duration(self) -> str:
        if self.duration is None:
            return "N/A"
        total = int(self.duration)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        total = int(seconds)
        m, s = divmod(total, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def _summary_text(self) -> str:
        parts = [
            f"Transcript: {len(self.transcript)} segments",
            f"Scenes: {len(self.scene_boundaries)} boundaries",
        ]
        if self.warnings:
            parts.append(f"Warnings: {len(self.warnings)}")
        return "; ".join(parts)
