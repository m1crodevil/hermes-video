"""Core /watch pipeline (Rust parity)."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from watch.download import download_video, is_url, resolve_local
from watch.frames import detect_scenes, extract_frames
from watch.output import WatchReport
from watch.transcript import format_transcript, parse_json3, parse_vtt
from watch.whisper import transcribe_video


def _transcript_from_subtitle(subtitle_path: str) -> tuple[list[dict], str]:
    path = Path(subtitle_path)
    if path.suffix == ".json3":
        return parse_json3(subtitle_path), "captions"
    return parse_vtt(subtitle_path), "captions"


def _transcript_from_whisper(video_path: str, out_dir: Path) -> tuple[list[dict], str]:
    audio_out = out_dir / "audio.mp3"
    segments, _ = transcribe_video(video_path, audio_out)
    return segments, "whisper"


def _get_transcript(result: dict, out_dir: Path, no_whisper: bool = False) -> tuple[list[dict], str]:
    if result.get("subtitle_path"):
        try:
            return _transcript_from_subtitle(result["subtitle_path"])
        except Exception as exc:
            print(f"[watch] subtitle parse failed: {exc}", file=sys.stderr)
            if no_whisper:
                return [], "none"

    if result.get("video_path") and not no_whisper:
        try:
            return _transcript_from_whisper(result["video_path"], out_dir)
        except Exception as exc:
            print(f"[watch] whisper failed: {exc}", file=sys.stderr)

    return [], "none"


def _language_from_segments(segments: list[dict]) -> str | None:
    if not segments:
        return None
    # Simple heuristic: use first segment text to detect via naive check
    text = " ".join(seg.get("text", "") for seg in segments[:20]).lower()
    # Common Indonesian words heuristic
    id_markers = ["yang", "dan", "di", "ini", "itu", "dengan", "untuk", "dari", "dalam", "pada"]
    en_markers = ["the", "and", "for", "with", "you", "that", "this", "from", "have", "are"]
    id_score = sum(1 for w in id_markers if w in text)
    en_score = sum(1 for w in en_markers if w in text)
    if id_score > en_score:
        return "id"
    if en_score > id_score:
        return "en"
    return None


def _parse_timestamps(timestamps_str: str | None) -> list[float]:
    """Parse comma-separated timestamps like '00:30,01:15,02:45'."""
    if not timestamps_str:
        return []
    timestamps = []
    for part in timestamps_str.split(","):
        part = part.strip()
        if not part:
            continue
        # Try as seconds first
        try:
            timestamps.append(float(part))
            continue
        except ValueError:
            pass
        # Try as HH:MM:SS or MM:SS
        chunks = part.split(":")
        if len(chunks) == 2:
            timestamps.append(int(chunks[0]) * 60 + float(chunks[1]))
        elif len(chunks) == 3:
            timestamps.append(int(chunks[0]) * 3600 + int(chunks[1]) * 60 + float(chunks[2]))
    return timestamps


def run_watch(
    source: str,
    out_dir: Path | None = None,
    timestamps_str: str | None = None,
    use_cookies: bool = False,
    cookies_file: str | None = None,
    no_whisper: bool = False,
    output_format: str = "both",
    keep_video: bool = False,
    resolution: int = 512,
    detect_scenes_flag: bool = False,
) -> WatchReport:
    """Run the /watch pipeline."""
    if out_dir is None:
        out_dir = Path(tempfile.mkdtemp(prefix="watch-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    report = WatchReport(working_dir=str(out_dir))

    # Stage 1: resolve source
    if is_url(source):
        result = download_video(source, out_dir, use_cookies=use_cookies, cookies_file=cookies_file)
    else:
        result = resolve_local(source)

    report.title = result.get("title") or result.get("info", {}).get("title") or Path(source).name
    report.source = result.get("source") or source
    report.uploader = result.get("uploader") or result.get("info", {}).get("uploader")
    if result.get("info", {}).get("duration") is not None:
        report.duration = float(result["info"]["duration"])
    report.language = result.get("detected_language") or result.get("info", {}).get("language")

    video_path = result.get("video_path")

    # Stage 2: transcript (and scene detection if video available)
    segments, transcript_source = _get_transcript(result, out_dir, no_whisper=no_whisper)
    report.transcript = segments
    report.transcript_source = transcript_source

    if not report.language:
        report.language = _language_from_segments(segments)

    # Stage 3: scene detection (optional — not run by default to match Rust parity/performance)
    if video_path and detect_scenes_flag:
        try:
            report.scene_boundaries = detect_scenes(video_path, duration=report.duration)
        except Exception as exc:
            print(f"[watch] scene detection failed: {exc}", file=sys.stderr)
            report.warnings.append(f"scene detection failed: {exc}")

    # Stage 4: frame extraction
    timestamps = _parse_timestamps(timestamps_str)
    if video_path and not timestamps:
        # Default to start, middle, end for visual summary when video is available.
        duration = report.duration or 0.0
        if duration > 0:
            timestamps = [0.0, duration / 2, duration]
        elif duration == 0.0:
            timestamps = [0.0]

    if video_path and timestamps:
        try:
            report.frames = extract_frames(video_path, timestamps, out_dir / "frames", width=resolution)
            report.analysis_capabilities["frame_extraction"] = True
            report.analysis_capabilities["visual_verification"] = True
        except Exception as exc:
            print(f"[watch] frame extraction failed: {exc}", file=sys.stderr)
            report.warnings.append(f"frame extraction failed: {exc}")

    report.analysis_capabilities["transcript"] = bool(segments)
    report.analysis_capabilities["scene_detection"] = bool(report.scene_boundaries)

    # Write outputs
    if output_format in ("json", "both"):
        report.write_json(out_dir / "report.json")
    if output_format in ("markdown", "both"):
        report.write_markdown(out_dir / "report.md")

    # Cleanup
    if not keep_video and video_path and is_url(source):
        video_file = Path(video_path)
        if video_file.exists():
            try:
                video_file.unlink()
            except OSError:
                pass

    return report
