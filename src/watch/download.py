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
import concurrent.futures
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}

# Whitelist of valid language codes (V12: prevent injection via lang pattern)
VALID_LANG_CODES = {
    "en", "id", "ms", "jv", "su", "ar", "zh", "ja", "ko", "es", "pt",
    "fr", "de", "it", "ru", "hi", "th", "vi", "tl", "tr", "pl", "nl",
    "sv", "da", "no", "fi",
}

# Screenshot-first: parallel section download defaults
SECTION_DURATION = 2.0  # seconds per section
MAX_CONCURRENT = 8       # safe limit before YouTube rate limiting
SECTION_RETRIES = 1      # retry failed downloads once

# Rate-limit safety: sleep seconds between subtitle requests
SLEEP_SUBTITLES = "3"


def _sanitize_url(url: str) -> str:
    """Strip control characters from URL before subprocess."""
    return ''.join(c for c in url if c.isprintable())


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


def _yt_dlp_network_opts(use_cookies: bool = False) -> list[str]:
    """Network-related yt-dlp flags for YouTube 2026+ reliability.

    YouTube now requires:
      1. A JS runtime (deno) for challenge solving during extraction
      2. Browser impersonation (curl_cffi) to avoid bot detection
      3. Cookies (OPTIONAL — breaks android_vr, only use when explicitly needed)

    Without these, metadata + subtitles may still work but video downloads
    fail with HTTP 403 Forbidden.

    IMPORTANT: Do NOT pass --cookies-from-browser by default. It causes yt-dlp
    to skip android_vr (which doesn't support cookies), forcing web_creator
    which needs a GVS PO Token that we don't have. android_vr without cookies
    is the most reliable approach for YouTube 2026+.

    Install: deno (curl -fsSL https://deno.land/install.sh | sh)
    Install: curl_cffi (pip install --break-system-packages curl-cffi)
    """
    opts: list[str] = []

    # YouTube 2026+: android_vr player client bypasses JS challenge solving
    # and works reliably WITHOUT cookies. web_creator is a fallback.
    opts += ["--extractor-args", "youtube:player_client=android_vr,web_creator"]

    has_deno = shutil.which("deno") is not None
    # Fallback: check ~/.deno/bin/deno directly (may not be in PATH yet)
    if not has_deno:
        has_deno = (Path.home() / ".deno" / "bin" / "deno").is_file()

    # JS runtime for YouTube challenge solving (required since mid-2025)
    if has_deno:
        opts += ["--js-runtimes", "deno"]

    # Browser impersonation via curl_cffi (bypasses bot detection)
    try:
        import curl_cffi  # noqa: F401
        opts += ["--impersonate", "chrome"]
    except ImportError:
        pass

    # Chrome cookies: OPT-IN only. Pass use_cookies=True when needed
    # (age-restricted videos, private/unlisted). Default: OFF.
    if use_cookies and has_deno and _has_chrome_cookies():
        opts += ["--cookies-from-browser", "chrome"]

    return opts


def _common_yt_dlp_opts(lang: str = "en.*", use_cookies: bool = False) -> list[str]:
    """Shared yt-dlp flags for subtitle downloads."""
    opts = [
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", lang,
        "--no-playlist",
        "--ignore-errors",
        "--sleep-subtitles", SLEEP_SUBTITLES,
    ]
    # Only add cookies when explicitly requested (opt-in, breaks android_vr)
    if use_cookies and _has_chrome_cookies():
        opts += ["--cookies-from-browser", "chrome"]
    return opts



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
    # Check combined extensions first (e.g. .mp4.webm from yt-dlp format merge)
    for pattern in ("video*.mp4.webm", "video*.mkv.webm"):
        for candidate in out_dir.glob(pattern):
            return candidate
    # Standard single extensions
    for ext in (".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".opus"):
        for candidate in out_dir.glob(f"video*{ext}"):
            return candidate
    # Fallback: any video extension
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

    # No network opts needed: metadata works without cookies/impersonate.
    # android_vr handles YouTube 2026+ challenges automatically.

    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr, timeout=300)
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

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
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
    from watch.language import suggest_subtitle_language, get_language_name
    best_lang = suggest_subtitle_language(info, available)
    # V12: Validate against whitelist to prevent injection via lang pattern
    if best_lang not in VALID_LANG_CODES:
        best_lang = "en"
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

    # No network opts needed for subtitles: android_vr handles extraction.
    # Cookies are NOT used here — they break android_vr client selection.

    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr, timeout=300)
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
                # Channel stats
                "channel_id": raw.get("channel_id"),
                "channel_url": raw.get("channel_url"),
                "channel_follower_count": raw.get("channel_follower_count"),
                "channel_is_verified": raw.get("channel_is_verified", False),
                "uploader_id": raw.get("uploader_id"),
                "uploader_url": raw.get("uploader_url"),
                # Video stats
                "view_count": raw.get("view_count"),
                "like_count": raw.get("like_count"),
                "comment_count": raw.get("comment_count"),
                "upload_date": raw.get("upload_date"),
                "tags": raw.get("tags") or [],
                "categories": raw.get("categories") or [],
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
    use_cookies: bool = False,
) -> dict:
    """Download video via yt-dlp.

    Args:
        existing_subtitle: If set, skip subtitle re-download (prevents 429).
            Pass the subtitle_path from fetch_captions() to avoid redundant requests.
        use_cookies: If True, use Chrome cookies (opt-in, breaks android_vr).
            Only use for age-restricted or private videos.
    """
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    url = _sanitize_url(url)
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
        cmd[1:1] = _common_yt_dlp_opts(use_cookies=use_cookies)
        cmd[1:1] = ["--sub-format", "json3/best"]

    # YouTube 2026: android_vr (no cookies) is most reliable for video download
    cmd[1:1] = _yt_dlp_network_opts(use_cookies=use_cookies)

    # yt-dlp may exit non-zero if a subtitle variant fails (e.g. 429) even when
    # the video itself downloaded fine. Treat "video file present" as success.
    result = subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr, timeout=300)
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
    use_cookies: bool = False,
) -> dict:
    if is_url(source):
        return download_url(
            source, out_dir,
            audio_only=audio_only,
            existing_subtitle=existing_subtitle,
            use_cookies=use_cookies,
        )
    return resolve_local(source)


def _download_one_section(
    url: str,
    timestamp: float,
    section_dir: Path,
    section_duration: float,
    use_cookies: bool,
) -> tuple[float, str | None]:
    """Download a single video section. Returns (timestamp, video_path | None)."""
    section_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(section_dir / "video.%(ext)s")
    end_ts = timestamp + section_duration

    cmd = [
        "yt-dlp",
        "-f", "bv*[height<=720]+ba/b[height<=720]/bv+ba/b",
        "--download-sections", f"*{timestamp:.1f}-{end_ts:.1f}",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--no-write-subs",
        "--no-write-info-json",
        "-o", output_template,
        "--", url,
    ]
    cmd[1:1] = _yt_dlp_network_opts(use_cookies=use_cookies)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
        )
        video = _pick_video(section_dir)
        if video:
            return (timestamp, str(video))
        print(
            f"[watch] section {timestamp:.0f}s: no video file produced (exit {result.returncode})",
            file=sys.stderr,
        )
    except subprocess.TimeoutExpired:
        print(f"[watch] section {timestamp:.0f}s: download timed out", file=sys.stderr)
    except Exception as exc:
        print(f"[watch] section {timestamp:.0f}s: {exc}", file=sys.stderr)

    return (timestamp, None)


def download_sections_parallel(
    url: str,
    timestamps: list[float],
    work_dir: Path,
    section_duration: float = SECTION_DURATION,
    max_concurrent: int = MAX_CONCURRENT,
    use_cookies: bool = False,
) -> dict[float, str]:
    """Download short video sections at specific timestamps in parallel.

    Uses yt-dlp ``--download-sections`` to fetch only 2-second clips around
    each timestamp — much faster and lighter than downloading the full video.
    Each section goes into a separate subdirectory to avoid file conflicts
    during concurrent downloads.

    Args:
        url: Video URL (YouTube, etc.)
        timestamps: Absolute timestamps (seconds) to grab frames at.
        work_dir: Parent directory for section subdirectories.
        section_duration: Seconds to download per section (default 2.0).
        max_concurrent: Max parallel yt-dlp processes (default 8).
        use_cookies: Pass Chrome cookies to yt-dlp (opt-in, breaks android_vr).

    Returns:
        Dict mapping timestamp → video file path for successful downloads.
        Failed timestamps are omitted (caller should handle missing frames).
    """
    if not timestamps:
        return {}

    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    work_dir.mkdir(parents=True, exist_ok=True)
    ts_sorted = sorted(set(round(t, 2) for t in timestamps))
    total = len(ts_sorted)

    print(
        f"[watch] screenshot-first: downloading {total} sections "
        f"(max {max_concurrent} concurrent, {section_duration:.0f}s each)…",
        file=sys.stderr,
    )

    results: dict[float, str] = {}
    failed: list[float] = []

    def _do_download(ts: float) -> tuple[float, str | None]:
        section_dir = work_dir / f"sec_{ts:.0f}"
        # Retry once on failure
        for attempt in range(1 + SECTION_RETRIES):
            ts_result, path = _download_one_section(
                url, ts, section_dir, section_duration, use_cookies,
            )
            if path:
                return (ts_result, path)
            if attempt < SECTION_RETRIES:
                time.sleep(1)  # brief pause before retry
        return (ts, None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = {pool.submit(_do_download, ts): ts for ts in ts_sorted}
        done_count = 0
        for future in concurrent.futures.as_completed(futures):
            done_count += 1
            try:
                ts_result, path = future.result()
            except Exception as exc:
                ts_result = futures[future]
                path = None
                print(f"[watch] section {ts_result:.0f}s: {exc}", file=sys.stderr)
            if path:
                results[ts_result] = path
                status = "✅"
            else:
                failed.append(ts_result)
                status = "❌"
            if done_count % 5 == 0 or done_count == total:
                print(
                    f"[watch] sections: {done_count}/{total} done "
 f"({len(results)} ok, {len(failed)} failed)",
                    file=sys.stderr,
                )

    if failed:
        print(
 f"[watch] warning: {len(failed)} section(s) failed: "
 f"{', '.join(f'{t:.0f}s' for t in failed[:10])}",
            file=sys.stderr,
        )

    success_rate = len(results) / total if total > 0 else 0
    print(
        f"[watch] screenshot-first: {len(results)}/{total} sections downloaded "
 f"({success_rate:.0%} success)",
        file=sys.stderr,
    )

    return results


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: download.py <url-or-path> <out-dir>", file=sys.stderr)
        raise SystemExit(2)
    result = download(sys.argv[1], Path(sys.argv[2]))
    print(json.dumps(result, indent=2))
