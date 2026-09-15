"""Frame/video metadata helpers."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def get_metadata(video_path: str | Path) -> dict:
    """Probe video metadata with ffprobe."""
    if shutil.which("ffprobe") is None:
        raise SystemExit("ffprobe is not installed")
    proc = subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-loglevel", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"ffprobe failed: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    format_info = data.get("format", {})
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = float(format_info.get("duration") or video_stream.get("duration") or 0)
    width = video_stream.get("width")
    height = video_stream.get("height")
    return {
        "duration": duration,
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "codec": video_stream.get("codec_name"),
        "has_audio": audio_stream is not None,
    }
