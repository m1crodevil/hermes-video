#!/usr/bin/env python3
"""Fetch captions/metadata via yt-dlp, or resolve a local file path."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}
VALID_LANG_CODES = {
    "en", "id", "ms", "jv", "su", "ar", "zh", "ja", "ko", "es", "pt",
    "fr", "de", "it", "ru", "hi", "th", "vi", "tl", "tr", "pl", "nl",
    "sv", "da", "no", "fi",
}
SLEEP_SUBTITLES = "3"


def _sanitize_url(url: str) -> str:
    return ''.join(c for c in url if c.isprintable())


def is_url(source: str) -> bool:
    if source.startswith("-"):
        return False
    parsed = urlparse(source)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def resolve_local(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"File not found: {p}")
    return {
        "video_path": str(p),
        "subtitle_path": None,
        "info": {"title": p.name, "url": str(p)},
        "downloaded": False,
    }


def _pick_subtitle(out_dir: Path, preferred_lang: str = "en") -> Path | None:
    for ext in ("json3", "vtt"):
        candidates = sorted(out_dir.glob(f"video*.{ext}"))
        if not candidates:
            continue
        lang_match = [
            c for c in candidates
            if f".{preferred_lang}." in c.name or f".{preferred_lang}-" in c.name
        ]
        if lang_match:
            return lang_match[0]
        return candidates[0]
    return None


def _read_info(info_path: Path, url: str) -> dict:
    info: dict = {}
    if info_path.exists():
        try:
            raw = json.loads(info_path.read_text(encoding="utf-8"))
            info = {
                "title": raw.get("title"),
                "uploader": raw.get("uploader") or raw.get("channel"),
                "duration": raw.get("duration"),
                "language": raw.get("language", "en"),
                "description": (raw.get("description") or "")[:500],
                "url": raw.get("webpage_url") or url,
            }
        except Exception as exc:
            print(f"[watch] info.json parse failed: {exc}", file=sys.stderr)
            info = {"url": url}
    return info


def fetch_metadata_only(url: str, out_dir: Path, js_runtimes: str | None = None) -> dict:
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed")
    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")
    cmd = [
        "yt-dlp", "--skip-download", "--write-info-json", "--no-write-subs",
        "--no-playlist", "-o", output_template, "--", _sanitize_url(url),
    ]
    if js_runtimes:
        cmd.insert(1, "--js-runtimes")
        cmd.insert(2, js_runtimes)
    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr, timeout=300)
    return _read_info(out_dir / "video.info.json", url)


def fetch_captions(url: str, out_dir: Path, js_runtimes: str | None = None) -> dict:
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed")
    out_dir.mkdir(parents=True, exist_ok=True)

    info = fetch_metadata_only(url, out_dir, js_runtimes=js_runtimes)
    best_lang = info.get("language", "en") or "en"
    if best_lang not in VALID_LANG_CODES:
        best_lang = "en"

    lang_pattern = f"{best_lang}.*" if best_lang != "en" else "en.*"
    output_template = str(out_dir / "video.%(ext)s")

    cmd = [
        "yt-dlp",
        "--skip-download",
        "-N", "4",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", lang_pattern,
        "--sub-format", "json3/best",
        "--no-playlist",
        "--ignore-errors",
        "--sleep-subtitles", SLEEP_SUBTITLES,
        "-o", output_template,
        "--", _sanitize_url(url),
    ]
    if js_runtimes:
        cmd.insert(1, "--js-runtimes")
        cmd.insert(2, js_runtimes)
    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr, timeout=300)
    subtitle = _pick_subtitle(out_dir, best_lang)

    return {
        "video_path": None,
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "detected_language": best_lang,
        "downloaded": False,
    }


def fetch_video(url: str, out_dir: Path, js_runtimes: str | None = None) -> dict:
    """Download the actual video file. Requires a JS runtime for YouTube."""
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed")
    out_dir.mkdir(parents=True, exist_ok=True)

    output_template = str(out_dir / "video.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--ignore-errors",
        "-o", output_template,
        "--", _sanitize_url(url),
    ]
    if js_runtimes:
        cmd.insert(1, "--js-runtimes")
        cmd.insert(2, js_runtimes)
    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr, timeout=300)

    # Find the downloaded video file
    video_path = None
    for ext in VIDEO_EXTS:
        candidates = list(out_dir.glob(f"video*{ext}"))
        if candidates:
            video_path = str(candidates[0])
            break

    return {
        "video_path": video_path,
        "subtitle_path": None,
        "info": {"url": url},
        "downloaded": video_path is not None,
    }
