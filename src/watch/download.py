#!/usr/bin/env python3
"""Fetch video + subtitles via yt-dlp in a single pass."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from watch.config import ytdlp_network_opts

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}
SLEEP_SUBTITLES = "3"


def _sanitize_url(url: str) -> str:
    return "".join(c for c in url if c.isprintable())


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
    import json
    info: dict = {}
    if info_path.exists():
        try:
            raw = json.loads(info_path.read_text(encoding="utf-8"))
            info = {
                "title": raw.get("title"),
                "uploader": raw.get("uploader") or raw.get("channel"),
                "duration": raw.get("duration"),
                "language": raw.get("language"),
                "description": (raw.get("description") or "")[:500],
                "url": raw.get("webpage_url") or url,
            }
        except Exception as exc:
            print(f"[watch] info.json parse failed: {exc}", file=sys.stderr)
            info = {"url": url}
    return info


def _base_ytdlp_cmd(output_template: str, url: str, extra_args: list[str] | None = None) -> list[str]:
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--ignore-errors",
        "--sleep-subtitles", SLEEP_SUBTITLES,
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend([
        "-o", output_template,
        "--", _sanitize_url(url),
    ])
    return cmd


def _run_ytdlp(cmd: list[str], timeout: int = 300) -> None:
    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr, timeout=timeout)


def _detect_language(info: dict, subtitle_path: str | None = None) -> str:
    """Return best language code from info.json or existing subtitle file."""
    # Prefer yt-dlp reported language first
    lang = info.get("language") or "en"
    if "-" in lang:
        lang = lang.split("-")[0]

    # If no language in info.json, try to infer from subtitle filename
    if not subtitle_path:
        return lang

    name = Path(subtitle_path).name.lower()
    for code in ("id", "ms", "jv", "su", "ar", "zh", "ja", "ko", "es", "pt",
                 "fr", "de", "it", "ru", "hi", "th", "vi", "tl", "tr", "pl",
                 "nl", "sv", "da", "no", "fi"):
        if f".{code}." in name or f".{code}-" in name:
            return code
    return lang


def download_video(
    url: str,
    out_dir: Path,
    use_cookies: bool = False,
    cookies_file: str | None = None,
) -> dict:
    """Download video + subtitles in one yt-dlp pass."""
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")

    network_opts = ytdlp_network_opts(use_cookies, cookies_file)

    extra = [
        "-f", "bv*[height<=720]+ba/b[height<=720]/bv+ba/b",
        "--merge-output-format", "mp4",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", "en.*,id.*,ms.*,jv.*,su.*,ar.*,zh.*,ja.*,ko.*,es.*,pt.*,fr.*,de.*,it.*,ru.*,hi.*,th.*,vi.*,tl.*,tr.*,pl.*,nl.*,sv.*,da.*,no.*,fi.*",
        "--sub-format", "json3/best",
    ]

    cmd = _base_ytdlp_cmd(output_template, url, extra_args=network_opts + extra)
    _run_ytdlp(cmd)

    info = _read_info(out_dir / "video.info.json", url)
    best_lang = _detect_language(info)
    subtitle = _pick_subtitle(out_dir, best_lang)

    # Fallback: if detected language failed, try any available subtitle
    if not subtitle:
        subtitle = _pick_subtitle(out_dir, "en")

    # If language wasn't in info.json, infer from the actual subtitle file
    best_lang = _detect_language(info, str(subtitle) if subtitle else None)

    video_path = None
    for ext in VIDEO_EXTS:
        candidates = list(out_dir.glob(f"video*{ext}"))
        if candidates:
            video_path = str(candidates[0])
            break

    info = info or {"url": url}
    return {
        "video_path": video_path,
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info,
        "detected_language": best_lang,
        "downloaded": video_path is not None,
        "source": info.get("url") or url,
        "uploader": info.get("uploader"),
        "title": info.get("title"),
    }
