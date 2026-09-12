"""Core single-pass pipeline (parity with hermes-video-rs)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from watch.config import get_config
from watch.download import fetch_captions, fetch_video, is_url, resolve_local
from watch.frames import extract_at_timestamps, get_metadata
from watch.output import AnalysisCapabilities, FrameInfo, TranscriptSegment, WatchReport
from watch.transcript import format_transcript, parse_json3, parse_vtt
from watch.whisper import load_api_key, transcribe_video


def _cleanup(work: Path, video_path: str | None, keep_video: bool) -> None:
    if keep_video or not video_path:
        return
    vp = Path(video_path)
    if vp.exists() and vp.is_relative_to(work):
        try:
            mb = vp.stat().st_size / (1024 * 1024)
            vp.unlink()
            print(f"[watch] cleaned up video ({mb:.0f} MB)", file=sys.stderr)
        except OSError:
            pass


def _parse_timestamps(text: str | None) -> list[float]:
    if not text:
        return []
    timestamps: list[float] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if ":" in part:
                pieces = part.split(":")
                if len(pieces) == 2:
                    m, s = pieces
                    timestamps.append(float(m) * 60 + float(s))
                elif len(pieces) == 3:
                    h, m, s = pieces
                    timestamps.append(float(h) * 3600 + float(m) * 60 + float(s))
            else:
                timestamps.append(float(part))
        except ValueError:
            pass
    return timestamps


def _default_timestamps(duration: float, count: int = 3) -> list[float]:
    """Return evenly spaced timestamps across the video duration."""
    if duration <= 0:
        return []
    if count < 2:
        return [0.0]
    return [i * duration / (count - 1) for i in range(count)]


def _fmt_duration(seconds: float) -> str:
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def run(source: str, args: argparse.Namespace) -> int:
    work: Path = Path(args.out_dir).expanduser().resolve() if args.out_dir else Path(tempfile.mkdtemp(prefix="watch-"))
    work.mkdir(parents=True, exist_ok=True)
    print(f"[watch] working dir: {work}", file=sys.stderr)

    url_source = is_url(source)
    subtitle_path: str | None = None
    info: dict = {}
    video_path: str | None = None
    downloaded = False

    # 1. Fetch captions for URLs, or resolve local file
    if url_source:
        print("[watch] fetching metadata/captions via yt-dlp…", file=sys.stderr)
        dl = fetch_captions(source, work / "download", js_runtimes=args.js_runtimes)
        subtitle_path = dl.get("subtitle_path")
        info = dl.get("info") or {}
        video_path = dl.get("video_path")
        downloaded = dl.get("downloaded", False)

        # Ensure we have a video for frame extraction (needed for YouTube URLs)
        if not video_path:
            print("[watch] no video downloaded, attempting video fetch for frames…", file=sys.stderr)
            video_dl = fetch_video(source, work / "video", js_runtimes=args.js_runtimes)
            video_path = video_dl.get("video_path")
            downloaded = video_dl.get("downloaded", False)
    else:
        dl = resolve_local(source)
        video_path = dl["video_path"]
        info = dl.get("info") or {}

    # 2. Parse transcript
    transcript: list[TranscriptSegment] = []
    transcript_source = "none"
    if subtitle_path:
        try:
            raw = parse_json3(subtitle_path) if subtitle_path.endswith(".json3") else parse_vtt(subtitle_path)
            transcript = [TranscriptSegment(start=s["start"], end=s["end"], text=s["text"], words=s.get("words")) for s in raw]
            transcript_source = "captions"
            print(f"[watch] parsed {len(transcript)} transcript segments from {subtitle_path}", file=sys.stderr)
        except Exception as exc:
            print(f"[watch] subtitle parse failed: {exc}", file=sys.stderr)

    # 3. Get metadata
    duration = 0.0
    width = height = None
    codec = None
    has_audio = False
    meta = None
    if video_path:
        meta = get_metadata(video_path)
        duration = meta.get("duration", 0.0)
        width = meta.get("width")
        height = meta.get("height")
        codec = meta.get("codec")
        has_audio = meta.get("has_audio", False)

    # 4. Whisper fallback if no transcript
    if not transcript and not args.no_whisper and video_path and has_audio:
        backend, api_key = load_api_key(args.whisper)
        if backend and api_key:
            try:
                raw_segments, used_backend = transcribe_video(video_path, work / "audio.mp3", backend=backend, api_key=api_key)
                transcript = [TranscriptSegment(start=s["start"], end=s["end"], text=s["text"]) for s in raw_segments]
                transcript_source = f"whisper ({used_backend})"
            except Exception as exc:
                print(f"[watch] whisper fallback failed: {exc}", file=sys.stderr)

    # 5. Extract frames at timestamps
    frames: list[FrameInfo] = []
    frame_meta: dict = {"engine": "none", "selected_count": 0}
    timestamps = _parse_timestamps(args.timestamps)
    # Auto-pick default timestamps if none provided and we have a video + duration
    if not timestamps and video_path and duration > 0:
        timestamps = _default_timestamps(duration)
        print(f"[watch] auto timestamps: {timestamps}", file=sys.stderr)
    if timestamps and video_path:
        raw_frames, frame_meta = extract_at_timestamps(
            video_path,
            work / "frames",
            timestamps,
            resolution=args.resolution,
        )
        for f in raw_frames:
            ts = f["timestamp_seconds"]
            frames.append(FrameInfo(path=f["path"], timestamp=ts, timestamp_fmt=_fmt_duration(ts)))

    # 6. Build report
    title = info.get("title") or source
    has_transcript = bool(transcript)
    has_frames = bool(frames)
    video_access = "denied" if url_source and not video_path else ("available" if url_source else "local")

    report = WatchReport(
        title=title,
        source=source,
        uploader=info.get("uploader"),
        language=info.get("language"),
        frames=frames,
        transcript=transcript,
        transcript_source=transcript_source,
        video_access=video_access,
        analysis_capabilities=AnalysisCapabilities(
            transcript=has_transcript,
            frame_extraction=has_frames,
            visual_verification=has_frames,
        ),
        duration=duration,
        working_dir=str(work),
        warnings=[],
    )

    # 7. Cleanup
    _cleanup(work, video_path, args.keep_video)

    # 8. Output
    if args.output in ("markdown", "both"):
        print(report.to_markdown())
    if args.output in ("json", "both"):
        json_path = work / "report.json"
        report.to_json_file(json_path)
        if args.output == "json":
            print(f"Report written to: {json_path}")
        else:
            print(f"\nReport JSON: `{json_path}`")

    return 0
