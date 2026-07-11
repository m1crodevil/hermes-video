#!/usr/bin/env python3
"""Download a video via yt-dlp, or resolve a local file path.

Also fetches subtitles (manual first, then auto-generated) in JSON3 format
(with VTT fallback) so transcribe.py can parse them without needing Whisper.

Subtitle download anti-429 strategy:
  1. fetch_captions() downloads subtitles once (--skip-download)
  2. download_url() receives existing subtitle_path and SKIPS re-downloading
  3. Falls back to --cookies-from-browser for authenticated sessions
  4. Uses --sleep-subtitles as rate-limit safety net
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}

# Rate-limit safety: sleep seconds between subtitle requests
SLEEP_SUBTITLES = "3"


def is_url(source: str) -> bool:
    if source.startswith("-"):
        return False
    parsed = urlparse(source)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _has_chrome_cookies() -> bool:
    """Check if Chrome has cookies we could use."""
    for path in [
        Path.home() / ".config/google-chrome/Default/Cookies",
        Path.home() / ".config/chromium/Default/Cookies",
        Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies",
    ]:
        if path.exists():
            return True
    return False


def _common_yt_dlp_opts(lang: str = "en.*") -> list[str]:
    """Shared yt-dlp flags for subtitle downloads."""
    return [
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", lang,
        "--no-playlist",
        "--ignore-errors",
        "--sleep-subtitles", SLEEP_SUBTITLES,
    ]


def _cookie_opts() -> list[str]:
    """Return cookie flags if Chrome cookies are available and deno is installed.

    Chrome cookies + no JS runtime = YouTube blocks format extraction.
    Only use cookies when deno (or another JS runtime) is available.
    """
    if not _has_chrome_cookies():
        return []
    # Only use cookies if deno is available for n-signature solving
    if shutil.which("deno"):
        return ["--cookies-from-browser", "chrome"]
    return []


def resolve_local(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"File not found: {p}")
    if p.suffix.lower() not in VIDEO_EXTS:
        print(
            f"[watch] warning: {p.suffix} is not a known video extension, proceeding anyway",
            file=sys.stderr,
        )
    return {
        "video_path": str(p),
        "subtitle_path": None,
        "info": {"title": p.name, "url": str(p)},
        "downloaded": False,
    }


def _pick_subtitle(out_dir: Path, preferred_lang: str = "en") -> Path | None:
    """Pick best subtitle file, preferring the video's language."""
    for ext in ("json3", "vtt"):
        candidates = sorted(out_dir.glob(f"video*.{ext}"))
        if not candidates:
            continue
        # Prefer files matching the video language
        lang_match = [
            c for c in candidates
            if f".{preferred_lang}." in c.name or f".{preferred_lang}-" in c.name
        ]
        if lang_match:
            return lang_match[0]
        # Fallback to any available
        return candidates[0]
    return None


def _pick_video(out_dir: Path) -> Path | None:
    for ext in (".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".opus"):
        for candidate in out_dir.glob(f"video*{ext}"):
            return candidate
    for candidate in out_dir.glob("video.*"):
        if candidate.suffix.lower() in VIDEO_EXTS:
            return candidate
    return None


def fetch_metadata_only(url: str, out_dir: Path) -> dict:
    """Fetch ONLY metadata (title, description, language) — no subtitle download."""
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")

    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-info-json",
        "--no-write-subs",
        "--no-playlist",
        "-o", output_template,
        "--", url,
    ]

    # Use cookies if available
    cmd[1:1] = _cookie_opts()

    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    return _read_info(out_dir / "video.info.json", url)


def list_available_subtitles(url: str) -> dict:
    """List available subtitle languages for a video.

    Returns: {"manual": ["id", "en"], "auto": ["id", "en", "ms", ...]}
    """
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--list-subs",
        "--no-playlist",
        "--", url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr

    manual = []
    auto = []

    for line in output.splitlines():
        line = line.strip()
        # Parse manual subtitles line like: "id Indonesian" or "en English"
        if "Available subtitles" in line or "manual" in line.lower():
            continue
        if "Available automatic" in line or "auto" in line.lower():
            continue

        # Try to extract language code (first column)
        parts = line.split()
        if parts and len(parts[0]) == 2 and parts[0].isalpha():
            lang_code = parts[0]
            # Determine if manual or auto based on context
            # Simple heuristic: if we've seen "Available automatic" header, it's auto
            pass

    # Simpler approach: parse the structured output
    in_auto = False
    for line in output.splitlines():
        if "Available automatic" in line:
            in_auto = True
            continue
        if "Available manual" in line or "Available subtitles" in line:
            in_auto = False
            continue

        parts = line.split()
        if parts and len(parts[0]) >= 2 and parts[0].isalpha():
            lang_code = parts[0]
            if in_auto:
                auto.append(lang_code)
            else:
                manual.append(lang_code)

    return {"manual": manual, "auto": auto}


def fetch_captions(url: str, out_dir: Path) -> dict:
    """Fetch metadata and best available captions with smart language detection.
    
    Phase 1: Fetch metadata + list available subtitles
    Phase 2: Detect best language from video metadata
    Phase 3: Download subtitles in detected language
    """
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Phase 1: Fetch metadata only (no subtitles yet)
    print("[watch] fetching video metadata...", file=sys.stderr)
    info = fetch_metadata_only(url, out_dir)
    
    # Phase 2: List available subtitles
    print("[watch] listing available subtitles...", file=sys.stderr)
    available = list_available_subtitles(url)
    
    # Phase 3: Detect best language
    from language import suggest_subtitle_language, get_language_name
    best_lang = suggest_subtitle_language(info, available)
    lang_name = get_language_name(best_lang)
    print(f"[watch] detected language: {lang_name} ({best_lang})", file=sys.stderr)
    print(f"[watch] available: manual={available.get('manual', [])}, auto={available.get('auto', [])[:10]}...", file=sys.stderr)
    
    # Phase 4: Download subtitles in detected language
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
        "--", url,
    ]
    
    # Use cookies if available
    cmd[1:1] = _cookie_opts()
    
    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    subtitle = _pick_subtitle(out_dir, best_lang)
    
    return {
        "video_path": None,
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "detected_language": best_lang,
        "downloaded": False,
    }


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


def download_url(
    url: str,
    out_dir: Path,
    audio_only: bool = False,
    existing_subtitle: str | None = None,
) -> dict:
    """Download video via yt-dlp.

    Args:
        existing_subtitle: If set, skip subtitle re-download (prevents 429).
            Pass the subtitle_path from fetch_captions() to avoid redundant requests.
    """
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")

    fmt = "ba/bestaudio" if audio_only else "bv*[height<=720]+ba/b[height<=720]/bv+ba/b"
    cmd = [
        "yt-dlp",
        "-N", "4",
        "-f", fmt,
        "--merge-output-format", "mp4",
        "--write-info-json",
        "-o", output_template,
        "--",
        url,
    ]

    # Only download subtitles if we don't already have them from fetch_captions()
    if existing_subtitle:
        print("[watch] subtitle already fetched, skipping re-download", file=sys.stderr)
    else:
        print("[watch] downloading subtitles with video (first time)", file=sys.stderr)
        cmd[1:1] = _common_yt_dlp_opts()
        cmd[1:1] = ["--sub-format", "json3/best"]

    # NOTE: cookies NOT used for video download — they cause 403 Forbidden
    # because YouTube gives authenticated format URLs that expire quickly.
    # Cookies are only useful for subtitle downloads (handled in fetch_captions).

    # yt-dlp may exit non-zero if a subtitle variant fails (e.g. 429) even when
    # the video itself downloaded fine. Treat "video file present" as success.
    result = subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    video = _pick_video(out_dir)
    if video is None:
        raise SystemExit(
            f"yt-dlp did not produce a video file in {out_dir} (exit {result.returncode})"
        )

    subtitle = _pick_subtitle(out_dir)
    info = _read_info(out_dir / "video.info.json", url)

    return {
        "video_path": str(video),
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "downloaded": True,
    }


def download(
    source: str,
    out_dir: Path,
    audio_only: bool = False,
    existing_subtitle: str | None = None,
) -> dict:
    if is_url(source):
        return download_url(
            source, out_dir,
            audio_only=audio_only,
            existing_subtitle=existing_subtitle,
        )
    return resolve_local(source)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: download.py <url-or-path> <out-dir>", file=sys.stderr)
        raise SystemExit(2)
    result = download(sys.argv[1], Path(sys.argv[2]))
    print(json.dumps(result, indent=2))
