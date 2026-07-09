#!/usr/bin/env python3
"""Probe video metadata and extract frames at an auto-scaled fps.

Auto-fps targets a frame budget, not a fixed rate. Token cost scales with frame
count, so budget-by-duration keeps short videos dense and long videos capped.
When a user-specified range is passed, focused-mode budgets denser (they are
zooming in for detail).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import dataclasses
from pathlib import Path

from .errors import ExtractionError, WatchError
from .types import Frame, FrameMetadata, VideoMetadata, Seconds


MAX_FPS = 2.0
SCENE_THRESHOLD = 0.20
# Keep scene-detection results once we have at least this many distinct shots.
# Below this the video is effectively static (screen recording, talking head),
# so we fall back to uniform sampling. Matching the reference fork's behaviour,
# this is a low floor — NOT the frame budget — so normal videos with cuts use
# the (single-pass) scene engine instead of paying for a wasted second decode.
SCENE_MIN_FRAMES = 8
# Below this many decoded keyframes a clip is too sparse for keyframe coverage
# (very short or oddly encoded), so the cheap tier falls back to uniform.
KEYFRAME_MIN = 4
MAX_READ_DIMENSION = 1998
# Frame-delta dedup: downscale each frame to a DEDUP_THUMB x DEDUP_THUMB
# grayscale thumbnail and treat two frames as near-identical when their mean
# per-pixel difference (0-255) is at or below DEDUP_THRESHOLD. Conservative on
# purpose: only collapses frames that are visually the same shot, so a code diff
# / scrolling terminal / slide-gaining-a-bullet survives. Unlike a within-frame
# perceptual hash, this distinguishes flat frames (solid slides, fades) by luma.
DEDUP_THUMB = 16
DEDUP_THRESHOLD = 2.0
SHOWINFO_TS_RE = re.compile(r"pts_time:([0-9.]+)")


def _scale_filter(resolution: int) -> str:  # noqa: D401
    return (
        f"scale=w='min({resolution},iw)':h='min({MAX_READ_DIMENSION},ih)':"
        "force_original_aspect_ratio=decrease:force_divisible_by=2"
    )


def _clamp_fps(fps: float, duration_seconds: Seconds, max_frames: int) -> tuple[float, int]:
    fps = min(fps, MAX_FPS)
    target = min(max_frames, max(1, int(round(fps * duration_seconds))))
    return fps, target


def parse_time(value: str | float | int | None) -> Seconds | None:
    """Parse a time value into seconds.

    Accepts multiple formats commonly used for video timestamps:
    ``SS`` (plain seconds), ``MM:SS``, or ``HH:MM:SS`` (with optional
    fractional ``.ms`` component).

    Args:
        value: Time string, numeric seconds, or ``None``.

    Returns:
        Time in seconds as a float, or ``None`` when *value* is ``None``
        or an empty string.

    Raises:
        WatchError: If the string cannot be parsed as a valid time format.

    Example:
        >>> parse_time("90.5")
        90.5
        >>> parse_time("1:30")
        90.0
        >>> parse_time("1:02:30.5")
        3750.5
        >>> parse_time(None) is None
        True
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    parts = s.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        pass
    raise WatchError(f"Cannot parse time value: {value!r} (expected SS, MM:SS, or HH:MM:SS)")


def format_time(seconds: Seconds) -> str:
    """Format a time value in seconds as a human-readable timestamp.

    Returns ``HH:MM:SS`` when the duration exceeds one hour, otherwise
    ``MM:SS``.  Fractional seconds are rounded to the nearest integer.

    Args:
        seconds: Time duration in seconds.

    Returns:
        Formatted timestamp string.

    Example:
        >>> format_time(125)
        '02:05'
        >>> format_time(3661)
        '1:01:01'
    """
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, sec = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def get_metadata(video_path: str) -> VideoMetadata:
    """Probe video file via ffprobe and return typed metadata.

    Runs ``ffprobe`` to extract duration, resolution, codec, file size,
    and audio presence.  The video file is **not** modified.

    Security:
        - Only reads metadata; no content is uploaded or transmitted
        - ``ffprobe`` is invoked via subprocess with no shell expansion

    Args:
        video_path: Path to the video file.

    Returns:
        A :class:`VideoMetadata` dataclass with ``duration_seconds``,
        ``width``, ``height``, ``codec``, ``size_bytes``, and ``has_audio``.

    Raises:
        ExtractionError: If ``ffprobe`` is not installed or fails on the
            given file.

    Example:
        >>> meta = get_metadata("/tmp/video.mp4")
        >>> print(meta.duration_seconds)
        142.5
    """
    if shutil.which("ffprobe") is None:
        raise ExtractionError(
            "ffprobe is not installed — install with: brew install ffmpeg",
            video_path=Path(video_path),
        )

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(Path(video_path).resolve()),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ExtractionError(
            f"ffprobe failed: {result.stderr.strip()}",
            video_path=Path(video_path),
            return_code=result.returncode,
            stderr=result.stderr,
        )

    data = json.loads(result.stdout or "{}")
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(fmt.get("duration") or video_stream.get("duration") or 0)
    return VideoMetadata(
        duration_seconds=duration,
        width=video_stream.get("width"),
        height=video_stream.get("height"),
        codec=video_stream.get("codec_name"),
        size_bytes=int(fmt.get("size") or 0),
        has_audio=audio_stream is not None,
    )


def auto_fps(duration_seconds: Seconds, max_frames: int = 100) -> tuple[float, int]:
    """Pick fps that targets a sensible frame budget for full-video scans.

    Short videos get denser sampling (up to 1 frame/sec for sub-30s clips)
    while long videos are capped at *max_frames* total.  The result is
    clamped to :data:`MAX_FPS` and always yields at least 1 frame.

    Args:
        duration_seconds: Total duration of the video (or segment).
        max_frames: Hard cap on total frame count (default: 100).

    Returns:
        A ``(fps, target_frames)`` tuple where *target_frames* is the
        expected output count.

    Example:
        >>> fps, n = auto_fps(10.0, max_frames=50)
        >>> fps
        1.0
    """
    if duration_seconds <= 0:
        return 1.0, 1

    if duration_seconds <= 30:
        target = min(max_frames, max(12, int(round(duration_seconds))))
    elif duration_seconds <= 60:
        target = min(max_frames, 40)
    elif duration_seconds <= 180:  # 3 min
        target = min(max_frames, 60)
    elif duration_seconds <= 600:  # 10 min
        target = min(max_frames, 80)
    else:
        target = max_frames

    return _clamp_fps(target / duration_seconds, duration_seconds, max_frames)


def auto_fps_focus(duration_seconds: Seconds, max_frames: int = 100) -> tuple[float, int]:
    """Denser fps budget for user-specified ranges — they are zooming in for detail.

    When the user specifies a start/end window (e.g. ``--start 1:00 --end 2:00``),
    this function produces a tighter fps so every second of the short segment
    gets more frames than a full-video scan would.

    Args:
        duration_seconds: Duration of the focused segment.
        max_frames: Hard cap on total frame count (default: 100).

    Returns:
        A ``(fps, target_frames)`` tuple.

    Example:
        >>> fps, n = auto_fps_focus(5.0, max_frames=50)
        >>> n >= 10
        True
    """
    if duration_seconds <= 0:
        return min(MAX_FPS, 2.0), 2

    if duration_seconds <= 5:
        target = min(max_frames, max(10, int(round(duration_seconds * 6))))
    elif duration_seconds <= 15:
        target = min(max_frames, max(30, int(round(duration_seconds * 4))))
    elif duration_seconds <= 30:
        target = min(max_frames, 60)
    elif duration_seconds <= 60:
        target = min(max_frames, 80)
    elif duration_seconds <= 180:
        target = max_frames
    else:
        target = max_frames

    return _clamp_fps(target / duration_seconds, duration_seconds, max_frames)


def extract(
    video_path: str,
    out_dir: Path,
    fps: float,
    resolution: int = 512,
    max_frames: int = 100,
    start_seconds: Seconds | None = None,
    end_seconds: Seconds | None = None,
) -> list[Frame]:
    """Extract frames at uniform fps via ffmpeg.

    Generates JPEG thumbnails at the specified frame rate, scaled to
    *resolution* pixels wide.  Existing ``frame_*.jpg`` files in *out_dir*
    are removed before extraction.

    Security:
        - Only local file reads; no network calls
        - ``ffmpeg`` is invoked via subprocess with no shell expansion

    Args:
        video_path: Path to the video file.
        out_dir: Output directory for frame JPEGs.
        fps: Frames per second to extract.
        resolution: Target width in pixels (height auto-scaled to maintain
            aspect ratio, default: 512).
        max_frames: Maximum frames to extract (default: 100).
        start_seconds: Seek offset in seconds. When set, ``-ss`` is placed
            before ``-i`` for fast keyframe-based seeking.
        end_seconds: Stop time in seconds.

    Returns:
        A list of :class:`Frame` dataclass instances sorted by timestamp.

    Raises:
        ExtractionError: If ``ffmpeg`` is not installed or extraction fails.

    Example:
        >>> frames = extract("video.mp4", Path("/tmp/frames"), fps=1.0)
        >>> len(frames)
        142
    """
    if shutil.which("ffmpeg") is None:
        raise ExtractionError(
            "ffmpeg is not installed — install with: brew install ffmpeg",
            video_path=Path(video_path),
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    for existing in out_dir.glob("frame_*.jpg"):
        existing.unlink()

    output_pattern = str(out_dir / "frame_%04d.jpg")
    cmd: list[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
    ]

    # -ss before -i = fast seek (keyframe-snap, good enough for preview frames).
    if start_seconds is not None:
        cmd += ["-ss", f"{start_seconds:.3f}"]
    if end_seconds is not None:
        cmd += ["-to", f"{end_seconds:.3f}"]

    cmd += [
        "-i", str(Path(video_path).resolve()),
        "-vf", f"fps={fps},{_scale_filter(resolution)}",
        "-frames:v", str(max_frames),
        "-q:v", "4",
        output_pattern,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ExtractionError(
            f"ffmpeg frame extraction failed: {result.stderr.strip()}",
            video_path=Path(video_path),
            command=cmd,
            return_code=result.returncode,
            stderr=result.stderr,
        )

    offset = start_seconds or 0.0
    frames = sorted(out_dir.glob("frame_*.jpg"))
    return [
        Frame(
            index=i,
            timestamp_seconds=round(offset + (i / fps if fps > 0 else 0.0), 2),
            path=str(p),
            reason="uniform",
        )
        for i, p in enumerate(frames)
    ]


def extract_scene_candidates(
    video_path: str,
    out_dir: Path,
    resolution: int = 512,
    max_frames: int | None = 100,
    start_seconds: Seconds | None = None,
    end_seconds: Seconds | None = None,
    threshold: float = SCENE_THRESHOLD,
) -> list[Frame]:
    """Extract first frame plus ffmpeg scene-change frames.

    Uses ffmpeg's ``select`` filter with a scene-change threshold to detect
    visual cuts.  The first frame is always included.  When ``max_frames`` is
    set, ``-frames:v`` lets ffmpeg stop decoding once it has emitted that many
    frames (early exit) and avoids writing extras that would only be deleted
    afterwards.  ``None`` (uncapped "complete" detail) keeps every detected
    shot, as the user explicitly opted in.

    Security:
        - Only local file reads; no network calls

    Args:
        video_path: Path to the video file.
        out_dir: Output directory for frame JPEGs.
        resolution: Target width in pixels (default: 512).
        max_frames: Maximum frames to extract, or ``None`` for unbounded
            (default: 100).
        start_seconds: Seek offset in seconds.
        end_seconds: Stop time in seconds.
        threshold: Scene-change sensitivity 0–1 (default: :data:`SCENE_THRESHOLD`).
            Lower values detect more cuts.

    Returns:
        A list of :class:`Frame` dataclass instances.  The first frame has
        ``reason="first-frame"``; subsequent frames have ``reason="scene-change"``.

    Raises:
        ExtractionError: If ``ffmpeg`` is not installed or extraction fails.

    Example:
        >>> frames = extract_scene_candidates("video.mp4", Path("/tmp/shots"))
        >>> frames[0].reason
        'first-frame'
    """
    if shutil.which("ffmpeg") is None:
        raise ExtractionError(
            "ffmpeg is not installed — install with: brew install ffmpeg",
            video_path=Path(video_path),
        )

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

    vf = f"select='eq(n\\\\,0)+gt(scene\\\\,{threshold})',{_scale_filter(resolution)},showinfo"
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ExtractionError(
            f"ffmpeg scene extraction failed: {result.stderr.strip()}",
            video_path=Path(video_path),
            command=cmd,
            return_code=result.returncode,
            stderr=result.stderr,
        )

    offset = start_seconds or 0.0
    timestamps = [round(offset + float(match.group(1)), 2) for match in SHOWINFO_TS_RE.finditer(result.stderr)]
    frames = sorted(out_dir.glob("frame_*.jpg"))
    out: list[Frame] = []
    for i, path in enumerate(frames):
        ts = timestamps[i] if i < len(timestamps) else offset
        out.append(Frame(
            index=i,
            timestamp_seconds=ts,
            path=str(path),
            reason="first-frame" if i == 0 else "scene-change",
        ))
    return out


def _even_indices(count: int, n: int) -> list[int]:
    """Indices of ``n`` evenly-spaced items out of ``count`` (first + last kept).

    ``n >= count`` returns every index; ``n == 1`` returns just the first.
    """
    if n >= count:
        return list(range(count))
    if n <= 1:
        return [0]
    return [round(i * (count - 1) / (n - 1)) for i in range(n)]


def parse_timestamps(value: str | None) -> list[Seconds]:
    """Parse a comma-separated list of timestamps into seconds.

    Each token is parsed via :func:`parse_time` (supports ``SS``, ``MM:SS``,
    ``HH:MM:SS``).  Empty tokens are skipped; duplicates are removed.  The
    result is always sorted ascending.

    Args:
        value: Comma-separated time string (e.g. ``"0:30, 2:15, 1:00:00"``),
            or ``None``.

    Returns:
        Sorted, de-duplicated list of seconds.

    Raises:
        WatchError: If any non-empty token cannot be parsed.

    Example:
        >>> parse_timestamps("1:30, 0:45, 1:30")
        [45.0, 90.0]
        >>> parse_timestamps(None)
        []
    """
    if not value:
        return []
    out: list[float] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        seconds = parse_time(token)
        if seconds is not None:
            out.append(float(seconds))
    return sorted(set(out))


def merge_frames(primary: list[Frame], pinned: list[Frame]) -> list[Frame]:
    """Combine two frame lists into one chronological list and reindex 0..n-1.

    ``pinned`` frames (typically transcript cue frames) are never dropped —
    this is a plain union, so the frame budget cap must be enforced upstream
    by reserving budget for the cues.

    Args:
        primary: Main list of extracted frames.
        pinned: Pinned frames (e.g. transcript cues) that must always
            appear in the final output.

    Returns:
        A merged, sorted (by ``timestamp_seconds``) list with sequential
        ``index`` values starting from 0.

    Example:
        >>> from scripts.types import Frame
        >>> a = [Frame(0, 1.0, "a.jpg", "uniform")]
        >>> b = [Frame(0, 0.5, "b.jpg", "transcript-cue")]
        >>> merged = merge_frames(a, b)
        >>> len(merged)
        2
    """
    merged = sorted([*primary, *pinned], key=lambda f: f.timestamp_seconds)
    result = [
        dataclasses.replace(frame, index=i)
        for i, frame in enumerate(merged)
    ]
    return result


def extract_at_timestamps(
    video_path: str,
    out_dir: Path,
    timestamps: list[Seconds],
    resolution: int = 512,
    max_frames: int | None = None,
    start_seconds: Seconds | None = None,
    end_seconds: Seconds | None = None,
) -> tuple[list[Frame], FrameMetadata]:
    """Grab exactly one frame at each requested timestamp (transcript cues).

    Timestamps are absolute source seconds.  Any falling outside an active
    ``[start, end]`` focus window are dropped.  Files use a ``cue_*.jpg``
    prefix so they sit alongside detail-engine ``frame_*.jpg`` output without
    either clobbering the other.  When more cues than ``max_frames`` survive,
    they are even-sampled (first + last kept) before extraction.

    Security:
        - Only local file reads; no network calls

    Args:
        video_path: Path to the video file.
        out_dir: Output directory for cue JPEG files.
        timestamps: List of absolute timestamps in seconds to extract.
        resolution: Target width in pixels (default: 512).
        max_frames: Maximum cues to extract, or ``None`` for all (default: ``None``).
        start_seconds: Focus window start — cues before this are dropped.
        end_seconds: Focus window end — cues after this are dropped.

    Returns:
        A tuple of ``(frames, metadata)`` where *frames* is a list of
        :class:`Frame` instances with ``reason="transcript-cue"`` and
        *metadata* is a :class:`FrameMetadata` summarising extraction stats.

    Raises:
        ExtractionError: If ``ffmpeg`` is not installed.

    Example:
        >>> frames, meta = extract_at_timestamps(
        ...     "video.mp4", Path("/tmp/cues"), [10.0, 30.5, 60.0]
        ... )
        >>> meta.engine
        'timestamps'
    """
    if shutil.which("ffmpeg") is None:
        raise ExtractionError(
            "ffmpeg is not installed — install with: brew install ffmpeg",
            video_path=Path(video_path),
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    for existing in out_dir.glob("cue_*.jpg"):
        existing.unlink()

    lo = start_seconds or 0.0
    hi = end_seconds if end_seconds is not None else float("inf")
    requested = sorted(set(round(float(t), 2) for t in timestamps))
    in_window = [t for t in requested if lo <= t <= hi]
    dropped = len(requested) - len(in_window)

    if max_frames is not None and len(in_window) > max_frames:
        points = [in_window[i] for i in _even_indices(len(in_window), max_frames)]
    else:
        points = in_window

    out: list[Frame] = []
    for t in points:
        path = out_dir / f"cue_{len(out):04d}.jpg"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", f"{t:.3f}",
            "-i", str(Path(video_path).resolve()),
            "-frames:v", "1",
            "-vf", _scale_filter(resolution),
            "-q:v", "4",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and path.exists():
            out.append(Frame(
                index=len(out),
                timestamp_seconds=t,
                path=str(path),
                reason="transcript-cue",
            ))

    meta = FrameMetadata(
        engine="timestamps",
        candidate_count=len(requested),
        selected_count=len(out),
        dropped_out_of_window=dropped,
        fallback=False,
    )
    return out, meta


def _even_sample(candidates: list[Frame], n: int) -> list[Frame]:
    """Pick ``n`` evenly-spaced candidates (always including first and last),
    delete the JPEGs we drop, and reindex the survivors 0..len-1.

    Shared by every capped engine so all detail modes sample the same way:
    detect all candidates across the full range, then thin down to the cap.
    ``n >= len(candidates)`` keeps everything (the uncapped / under-cap case).
    """
    selected = [candidates[i] for i in _even_indices(len(candidates), n)]

    keep_paths = {sel.path for sel in selected}
    for cand in candidates:
        if cand.path not in keep_paths:
            try:
                Path(cand.path).unlink()
            except OSError:
                pass
    return [
        dataclasses.replace(frame, index=i)
        for i, frame in enumerate(selected)
    ]


def _frame_delta(a: bytes, b: bytes) -> float:
    """Mean absolute per-pixel difference (0-255) between two grayscale
    thumbnails. Mismatched lengths are treated as maximally different so a
    decode hiccup never collapses distinct frames."""
    if not a or len(a) != len(b):
        return float("inf")
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _thumb_frames(paths: list[Path]) -> list[bytes]:
    """Decode every frame in ``paths`` to a small grayscale thumbnail via one
    ffmpeg pass over the JPEG sequence.

    ffmpeg does the pixel decode (keeps us pure-stdlib); we slice the raw
    grayscale stream into one ``DEDUP_THUMB``-square thumbnail per frame.
    Fail-open: any ffmpeg error, an unrecognized name, or a byte-count mismatch
    returns ``[]`` so the caller skips dedup rather than breaking extraction.
    """
    if not paths:
        return []
    paths = [Path(p) for p in paths]
    m = re.match(r"(.*?)(\d+)(\.[A-Za-z0-9]+)$", paths[0].name)
    if m is None:
        return []
    prefix, digits, ext = m.group(1), m.group(2), m.group(3)
    pattern = str(paths[0].parent / f"{prefix}%0{len(digits)}d{ext}")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-start_number", str(int(digits)),
        "-i", pattern,
        "-vf", f"scale={DEDUP_THUMB}:{DEDUP_THUMB},format=gray",
        "-f", "rawvideo",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        return []

    chunk = DEDUP_THUMB * DEDUP_THUMB
    data = result.stdout
    if len(data) != chunk * len(paths):
        return []
    return [data[i * chunk:(i + 1) * chunk] for i in range(len(paths))]


def dedupe_perceptual(
    candidates: list[Frame], threshold: float = DEDUP_THRESHOLD
) -> tuple[list[Frame], int]:
    """Drop near-identical frames from a chronological candidate list.

    Thumbnails the extracted JPEGs and greedily removes frames whose mean
    per-pixel difference from the last kept one is within *threshold*.  This
    collapses visually identical shots (e.g. a static slide held for several
    seconds) while preserving genuine content changes.

    Security:
        - Only reads local JPEG files; no network calls

    Args:
        candidates: Chronologically sorted list of :class:`Frame` instances.
        threshold: Mean per-pixel difference (0–255) below which two frames
            are considered identical (default: :data:`DEDUP_THRESHOLD`).

    Returns:
        A ``(survivors, dropped_count)`` tuple.  When thumbnails are
        unavailable (ffmpeg error) or there are fewer than two candidates,
        the input list is returned unchanged with ``dropped_count=0``.

    Example:
        >>> survivors, n = dedupe_perceptual(frames, threshold=2.0)
        >>> print(f"dropped {n} identical frames")
    """
    if len(candidates) <= 1:
        return candidates, 0
    thumbs = _thumb_frames([Path(c.path) for c in candidates])
    return _dedupe_by_deltas(candidates, thumbs, threshold)


def _dedupe_by_deltas(
    candidates: list[Frame], thumbs: list[bytes], threshold: float = DEDUP_THRESHOLD
) -> tuple[list[Frame], int]:
    """Greedily drop frames within ``threshold`` mean per-pixel difference of the
    last *kept* frame. Deletes dropped JPEGs and reindexes survivors 0..n-1 (same
    cleanup contract as :func:`_even_sample`). Fail-open: if ``thumbs`` does not
    line up 1:1 with ``candidates``, return them unchanged.
    """
    if len(thumbs) != len(candidates) or len(candidates) <= 1:
        return candidates, 0

    kept = [candidates[0]]
    last = thumbs[0]
    dropped: list[Frame] = []
    for cand, thumb in zip(candidates[1:], thumbs[1:]):
        if _frame_delta(thumb, last) <= threshold:
            dropped.append(cand)
        else:
            kept.append(cand)
            last = thumb

    for cand in dropped:
        try:
            Path(cand.path).unlink()
        except OSError:
            pass
    result = [
        dataclasses.replace(frame, index=i)
        for i, frame in enumerate(kept)
    ]
    return result, len(dropped)


def extract_scene_or_uniform(
    video_path: str,
    out_dir: Path,
    fps: float,
    target_frames: int,
    resolution: int = 512,
    max_frames: int | None = 100,
    start_seconds: Seconds | None = None,
    end_seconds: Seconds | None = None,
    dedup: bool = True,
) -> tuple[list[Frame], FrameMetadata]:
    """Prefer scene selection, falling back to uniform when the video is static.

    Scene cuts are detected across the *whole* range (uncapped), near-identical
    frames are dropped (:func:`dedupe_perceptual`, unless ``dedup`` is False),
    and the survivors are even-sampled down to ``max_frames`` via
    :func:`_even_sample`.  When fewer than ``SCENE_MIN_FRAMES`` distinct shots
    are detected (e.g. a screen recording or talking-head video), falls back to
    uniform fps extraction.

    This costs a full decode but guarantees coverage spans the entire clip —
    capping detection with ``-frames:v`` instead would keep only the first
    cuts and drop the tail of long videos.

    Security:
        - Only local file reads; no network calls

    Args:
        video_path: Path to the video file.
        out_dir: Output directory for frame JPEGs.
        fps: Fps used for the uniform fallback path.
        target_frames: Target frame count for the uniform fallback.
        resolution: Target width in pixels (default: 512).
        max_frames: Hard cap on output frames, or ``None`` for uncapped
            (default: 100).
        start_seconds: Seek offset in seconds.
        end_seconds: Stop time in seconds.
        dedup: Enable perceptual deduplication (default: ``True``).

    Returns:
        A ``(frames, metadata)`` tuple.  *metadata.engine* is ``"scene"``
        when scene detection succeeded or ``"uniform"`` as a fallback.

    Raises:
        ExtractionError: If ``ffmpeg`` is not installed or extraction fails.

    Example:
        >>> frames, meta = extract_scene_or_uniform(
        ...     "video.mp4", Path("/tmp/out"), fps=1.0, target_frames=60
        ... )
        >>> meta.engine in ("scene", "uniform")
        True
    """
    scene_frames = extract_scene_candidates(
        video_path,
        out_dir,
        resolution=resolution,
        max_frames=None,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )
    scene_count = len(scene_frames)
    if scene_count >= SCENE_MIN_FRAMES:
        deduped, n_dropped = dedupe_perceptual(scene_frames) if dedup else (scene_frames, 0)
        cap = len(deduped) if max_frames is None else max_frames
        selected = _even_sample(deduped, cap)
        return selected, FrameMetadata(
            engine="scene",
            candidate_count=scene_count,
            deduped_count=n_dropped,
            selected_count=len(selected),
            fallback=False,
        )

    fallback_cap = target_frames if max_frames is None else min(max_frames, target_frames)
    frames = extract(
        video_path,
        out_dir,
        fps=fps,
        resolution=resolution,
        max_frames=fallback_cap,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
    )
    n_dropped = 0
    if dedup:
        frames, n_dropped = dedupe_perceptual(frames)
    return frames, FrameMetadata(
        engine="uniform",
        candidate_count=scene_count,
        deduped_count=n_dropped,
        selected_count=len(frames),
        fallback=True,
    )


def extract_keyframes(
    video_path: str,
    out_dir: Path,
    resolution: int = 512,
    max_frames: int | None = 50,
    start_seconds: Seconds | None = None,
    end_seconds: Seconds | None = None,
    dedup: bool = True,
) -> tuple[list[Frame], FrameMetadata]:
    """Decode only keyframes (I-frames) — the cheap, near-instant tier.

    ``-skip_frame nokey`` makes ffmpeg reconstruct only keyframes, skipping
    all P/B frames.  Encoders emit keyframes at scene cuts, so these already
    approximate "distinct moments" at a fraction of the decode cost.

    Near-identical frames are dropped (:func:`dedupe_perceptual`, unless
    ``dedup`` is False); over-cap → even-sample first→last; too few
    keyframes (< :data:`KEYFRAME_MIN`) → uniform fallback.

    Security:
        - Only local file reads; no network calls

    Args:
        video_path: Path to the video file.
        out_dir: Output directory for frame JPEGs.
        resolution: Target width in pixels (default: 512).
        max_frames: Maximum frames to output, or ``None`` for uncapped
            (default: 50).
        start_seconds: Seek offset in seconds.
        end_seconds: Stop time in seconds.
        dedup: Enable perceptual deduplication (default: ``True``).

    Returns:
        A ``(frames, metadata)`` tuple.  *metadata.engine* is ``"keyframe"``
        when keyframe extraction succeeded or ``"uniform"`` as a fallback.

    Raises:
        ExtractionError: If ``ffmpeg`` is not installed or extraction fails.

    Example:
        >>> frames, meta = extract_keyframes(
        ...     "video.mp4", Path("/tmp/keys"), max_frames=30
        ... )
        >>> meta.engine
        'keyframe'
    """
    if shutil.which("ffmpeg") is None:
        raise ExtractionError(
            "ffmpeg is not installed — install with: brew install ffmpeg",
            video_path=Path(video_path),
        )

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
    cmd += [
        "-skip_frame", "nokey",
        "-i", str(Path(video_path).resolve()),
        "-vf", f"{_scale_filter(resolution)},showinfo",
        "-vsync", "vfr",
        "-q:v", "4",
        output_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ExtractionError(
            f"ffmpeg keyframe extraction failed: {result.stderr.strip()}",
            video_path=Path(video_path),
            command=cmd,
            return_code=result.returncode,
            stderr=result.stderr,
        )

    offset = start_seconds or 0.0
    timestamps = [round(offset + float(m.group(1)), 2) for m in SHOWINFO_TS_RE.finditer(result.stderr)]
    files = sorted(out_dir.glob("frame_*.jpg"))
    candidates: list[Frame] = []
    for i, path in enumerate(files):
        ts = timestamps[i] if i < len(timestamps) else offset
        candidates.append(Frame(
            index=i,
            timestamp_seconds=ts,
            path=str(path),
            reason="keyframe",
        ))

    # Too few keyframes → uniform fallback over the same range.
    if len(candidates) < KEYFRAME_MIN:
        for cand in candidates:
            try:
                Path(cand.path).unlink()
            except OSError:
                pass
        meta = get_metadata(video_path)
        full_duration = meta.duration_seconds
        eff_start = start_seconds or 0.0
        eff_end = end_seconds if end_seconds is not None else full_duration
        eff_duration = max(0.0, eff_end - eff_start)
        budget = max_frames if max_frames is not None else 100
        fps, _ = auto_fps(eff_duration, max_frames=budget)
        frames_out = extract(
            video_path,
            out_dir,
            fps=fps,
            resolution=resolution,
            max_frames=budget,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )
        n_dropped = 0
        if dedup:
            frames_out, n_dropped = dedupe_perceptual(frames_out)
        return frames_out, FrameMetadata(
            engine="uniform",
            candidate_count=len(candidates),
            deduped_count=n_dropped,
            selected_count=len(frames_out),
            fallback=True,
        )

    # Detect-all, drop near-duplicates, then even-sample down to the cap (first +
    # last always kept). ``max_frames is None`` (uncapped) keeps every keyframe.
    candidate_count = len(candidates)
    deduped, n_dropped = dedupe_perceptual(candidates) if dedup else (candidates, 0)
    cap = len(deduped) if max_frames is None else max_frames
    selected = _even_sample(deduped, cap)
    return selected, FrameMetadata(
        engine="keyframe",
        candidate_count=candidate_count,
        deduped_count=n_dropped,
        selected_count=len(selected),
        fallback=False,
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "usage: frames.py <video-path> <out-dir> [--fps F] [--resolution W] "
            "[--max-frames N] [--start T] [--end T] [--no-dedup]",
            file=sys.stderr,
        )
        raise SystemExit(2)

    video = sys.argv[1]
    out = Path(sys.argv[2])
    args = sys.argv[3:]

    fps_override = None
    resolution = 512
    max_frames = 100
    start_arg = None
    end_arg = None
    dedup = True
    i = 0
    while i < len(args):
        if args[i] == "--fps":
            fps_override = float(args[i + 1]); i += 2
        elif args[i] == "--resolution":
            resolution = int(args[i + 1]); i += 2
        elif args[i] == "--max-frames":
            max_frames = int(args[i + 1]); i += 2
        elif args[i] == "--start":
            start_arg = args[i + 1]; i += 2
        elif args[i] == "--end":
            end_arg = args[i + 1]; i += 2
        elif args[i] == "--no-dedup":
            dedup = False; i += 1
        else:
            i += 1

    meta = get_metadata(video)
    start_sec = parse_time(start_arg)
    end_sec = parse_time(end_arg)
    full_duration = meta.duration_seconds

    effective_start = start_sec if start_sec is not None else 0.0
    effective_end = end_sec if end_sec is not None else full_duration
    effective_duration = max(0.0, effective_end - effective_start)

    focused = start_sec is not None or end_sec is not None
    if focused:
        fps, target = auto_fps_focus(effective_duration, max_frames=max_frames)
    else:
        fps, target = auto_fps(effective_duration, max_frames=max_frames)
    if fps_override is not None:
        fps = fps_override
        target = max(1, int(round(fps * effective_duration)))

    frames = extract(
        video, out,
        fps=fps,
        resolution=resolution,
        max_frames=max_frames,
        start_seconds=start_sec,
        end_seconds=end_sec,
    )
    deduped_count = 0
    if dedup:
        frames, deduped_count = dedupe_perceptual(frames)
    print(json.dumps(
        {
            "meta": meta, "fps": fps, "target": target, "focused": focused,
            "deduped_count": deduped_count, "frames": frames,
        },
        indent=2,
    ))
