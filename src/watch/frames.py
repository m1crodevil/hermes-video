"""Frame extraction and scene detection via ffmpeg."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable


SCDET_THRESHOLD = 10


def _run_ffmpeg(args: list[str], timeout: int = 600, loglevel: str = "error") -> tuple[int, str, str]:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", loglevel, "-y"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def detect_scenes(video_path: str | Path, duration: float | None = None) -> list[dict]:
    """Detect scene boundaries using ffmpeg scdet."""
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is not installed")

    cmd = [
        "-i", str(video_path),
        "-vf", f"scdet=t={SCDET_THRESHOLD},metadata=print",
        "-an", "-f", "null", "-",
    ]
    returncode, _, stderr = _run_ffmpeg(cmd, loglevel="info")
    if returncode != 0:
        # Fallback to select filter if scdet is unavailable (older ffmpeg)
        return _detect_scenes_select(video_path)

    boundaries = []
    last_end = 0.0
    for line in stderr.splitlines():
        if "lavfi.scd.time" in line:
            match = re.search(r"lavfi\.scd\.time=(\d+(?:\.\d+)?)", line)
            if match:
                start = float(match.group(1))
                if start > last_end:
                    boundaries.append({"start": last_end, "end": start, "duration": start - last_end})
                    last_end = start

    if boundaries and duration and last_end < duration:
        boundaries.append({"start": last_end, "end": duration, "duration": duration - last_end})
    return boundaries


def _detect_scenes_select(video_path: str | Path, threshold: float = 0.35) -> list[dict]:
    """Fallback scene detection using ffmpeg select filter."""
    cmd = [
        "-i", str(video_path),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-an", "-f", "null", "-",
    ]
    returncode, _, stderr = _run_ffmpeg(cmd)
    if returncode != 0:
        return []

    timestamps = [0.0]
    for line in stderr.splitlines():
        match = re.search(r"pts_time:(\d+(?:\.\d+)?)", line)
        if match:
            timestamps.append(float(match.group(1)))

    boundaries = []
    for i in range(len(timestamps) - 1):
        boundaries.append({
            "start": timestamps[i],
            "end": timestamps[i + 1],
            "duration": timestamps[i + 1] - timestamps[i],
        })
    return boundaries


def extract_frame(video_path: str | Path, timestamp: float, out_path: Path, width: int = 512) -> Path:
    """Extract a single frame at timestamp (seconds)."""
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is not installed")

    cmd = [
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        "-vf", f"scale='min({width},iw)':-1",
        "-an",
        str(out_path),
    ]
    returncode, _, stderr = _run_ffmpeg(cmd)
    if returncode != 0:
        raise SystemExit(f"frame extraction failed: {stderr.strip()}")
    return out_path


def extract_frames(
    video_path: str | Path,
    timestamps: Iterable[float],
    out_dir: Path,
    width: int = 512,
) -> list[dict]:
    """Extract frames at given timestamps. Returns list of frame metadata."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, ts in enumerate(sorted(timestamps)):
        out_path = out_dir / f"frame_{i:04d}.jpg"
        extract_frame(video_path, ts, out_path, width=width)
        frames.append({
            "path": str(out_path),
            "timestamp": round(ts, 3),
            "filename": out_path.name,
        })
    return frames
