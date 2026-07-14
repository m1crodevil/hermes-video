"""Scene-change detection and gap-filling for frame extraction."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from watch.frames.metadata import (
    MAX_FPS, SCENE_MIN_FRAMES, MAX_READ_DIMENSION,
    SHOWINFO_TS_RE, _scale_filter, get_metadata,
)
from watch.frames.dedup import dedupe_perceptual

def adaptive_scene_threshold(duration_seconds: float, fps: float = 30.0) -> float:
    """Return optimal scene-change threshold based on video duration.

    Long videos with gradual transitions (documentaries, vlogs) need lower
    thresholds to catch more scene changes. Short fast-cut videos (music,
    trailers) need higher thresholds to avoid false positives.

    Reference: ffmpeg-cookbook.com recommends 0.35 for hard cuts,
    0.25-0.3 for fast-cut content. GDELT project uses 0.20 for news.
    Our default 0.20 was too high for long-form documentary content.

    Args:
        duration_seconds: Total video duration
        fps: Video frame rate (used for minimum scene interval)

    Returns:
        Threshold value between 0.12 and 0.30
    """
    # Minimum interval between scenes (avoid duplicate frames from rapid cuts)
    min_scene_interval = max(1.0, 0.5)  # At least 0.5 seconds between scenes

    if duration_seconds <= 60:        # ≤1 min (shorts, clips)
        return 0.25  # Higher threshold for short content
    elif duration_seconds <= 300:     # ≤5 min
        return 0.22  # Moderate
    elif duration_seconds <= 600:     # ≤10 min
        return 0.20  # Current default (works well here)
    elif duration_seconds <= 1800:    # ≤30 min
        return 0.17  # Lower for longer content
    elif duration_seconds <= 3600:    # ≤60 min
        return 0.15  # Even lower for long-form
    else:                             # >60 min
        return 0.12  # Most sensitive for very long videos


def extract_scene_candidates(
    video_path: str,
    out_dir: Path,
    resolution: int = 512,
    max_frames: int | None = 100,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
    threshold: float | None = None,
) -> list[dict]:
    """Extract first frame plus ffmpeg scene-change frames.

    When ``max_frames`` is set, ``-frames:v`` lets ffmpeg stop decoding once it
    has emitted that many frames (early exit) and avoids writing extras that we
    would only delete afterwards. ``None`` (uncapped "complete" detail) keeps
    every detected shot, as the user explicitly opted in.

    When ``threshold`` is ``None``, the optimal threshold is auto-selected
    based on video duration via :func:`adaptive_scene_threshold`.
    """
    # Auto-select threshold if not provided
    if threshold is None:
        meta = get_metadata(video_path)
        duration = meta["duration_seconds"]
        if start_seconds is not None and end_seconds is not None:
            duration = end_seconds - start_seconds
        threshold = adaptive_scene_threshold(duration)
        print(f"[watch] scene threshold: {threshold:.2f} (duration: {duration:.0f}s)",
              file=sys.stderr)
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is not installed. Install with: brew install ffmpeg")

    out_dir.mkdir(parents=True, exist_ok=True)
    for existing in out_dir.glob("frame_*.jpg"):
        existing.unlink()

    output_pattern = str(out_dir / "frame_%04d.jpg")
    cmd: list[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "info",
        "-y",
    ]
    if start_seconds is not None:
        cmd += ["-ss", f"{start_seconds:.3f}"]
    if end_seconds is not None:
        cmd += ["-to", f"{end_seconds:.3f}"]

    vf = f"select='eq(n\\,0)+gt(scene\\,{threshold})',{_scale_filter(resolution)},showinfo"
    cmd += [
        "-i", str(Path(video_path).resolve()),
        "-vf", vf,
        "-vsync", "vfr",
    ]
    if max_frames is not None:
        cmd += ["-frames:v", str(max_frames)]
    cmd += [
        "-q:v", "4",
        output_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg scene extraction failed: {result.stderr.strip()}")

    offset = start_seconds or 0.0
    timestamps = [round(offset + float(match.group(1)), 2) for match in SHOWINFO_TS_RE.finditer(result.stderr)]
    frames = sorted(out_dir.glob("frame_*.jpg"))
    out: list[dict] = []
    for i, path in enumerate(frames):
        ts = timestamps[i] if i < len(timestamps) else offset
        out.append({
            "index": i,
            "timestamp_seconds": ts,
            "path": str(path),
            "reason": "first-frame" if i == 0 else "scene-change",
        })
    return out

def fill_gaps_with_uniform(
    scene_frames: list[dict],
    video_path: str,
    out_dir: Path,
    resolution: int = 512,
    max_gap_seconds: float = 120.0,
    target_frames: int = 100,
) -> list[dict]:
    """Insert uniform frames in large gaps between scene-detected frames.

    After scene detection, some gaps may be too large (>2 minutes) because
    the video has gradual transitions that don't cross the threshold.
    This function fills those gaps with uniformly-sampled frames.

    Args:
        scene_frames: Frames from scene detection (sorted by timestamp)
        video_path: Path to video file
        out_dir: Output directory for frames
        resolution: Frame width in pixels
        max_gap_seconds: Maximum acceptable gap before filling
        target_frames: Total frame budget (scene + fill)

    Returns:
        Merged list of scene + fill frames, sorted by timestamp
    """
    if not scene_frames or len(scene_frames) < 2:
        return scene_frames

    # Calculate expected interval based on target
    video_meta = get_metadata(video_path)
    duration = video_meta["duration_seconds"]
    expected_interval = duration / target_frames if target_frames > 0 else 60.0

    # Use 2x expected interval or max_gap_seconds, whichever is smaller
    fill_threshold = min(max_gap_seconds, expected_interval * 2)

    fill_frames = []
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, len(scene_frames)):
        prev_ts = scene_frames[i-1]["timestamp_seconds"]
        curr_ts = scene_frames[i]["timestamp_seconds"]
        gap = curr_ts - prev_ts

        if gap > fill_threshold:
            # Calculate how many fill frames needed
            num_fill = int(gap / fill_threshold) - 1
            num_fill = min(num_fill, 5)  # Cap at 5 fill frames per gap

            for j in range(1, num_fill + 1):
                fill_ts = prev_ts + (gap * j / (num_fill + 1))
                fill_path = out_dir / f"fill_{len(fill_frames):04d}.jpg"

                # Extract frame at fill timestamp
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "error",
                    "-y",
                    "-ss", f"{fill_ts:.3f}",
                    "-i", str(Path(video_path).resolve()),
                    "-frames:v", "1",
                    "-vf", _scale_filter(resolution),
                    "-q:v", "4",
                    str(fill_path),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0 and fill_path.exists():
                    fill_frames.append({
                        "index": 0,  # Will be reindexed
                        "timestamp_seconds": fill_ts,
                        "path": str(fill_path),
                        "reason": "gap-fill",
                    })

    # Merge scene + fill frames and reindex
    all_frames = sorted(scene_frames + fill_frames, key=lambda f: f["timestamp_seconds"])
    for i, frame in enumerate(all_frames):
        frame["index"] = i

    return all_frames

