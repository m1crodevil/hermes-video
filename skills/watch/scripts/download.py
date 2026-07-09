#!/usr/bin/env python3
"""Download a video via yt-dlp, or resolve a local file path.

Also fetches subtitles (manual first, then auto-generated) in VTT format so
transcribe.py can parse them without needing Whisper.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from .errors import DownloadError
from .types import DownloadResult

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}


def is_url(source: str) -> bool:
    """Determine whether *source* looks like an HTTP(S) URL.

    Strings starting with ``-`` are treated as CLI flags, not URLs (avoids
    confusion when building ``yt-dlp`` commands).

    Args:
        source: Raw input string from the user.

    Returns:
        ``True`` when the string parses as a valid HTTP/HTTPS URL with a
        network location component.

    Example:
        >>> is_url("https://youtu.be/dQw4w9WgXcQ")
        True
        >>> is_url("/home/user/video.mp4")
        False
    """
    if source.startswith("-"):
        return False
    parsed = urlparse(source)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def resolve_local(path: str) -> DownloadResult:
    """Resolve a local file path to a :class:`DownloadResult`.

    Validates that the file exists and warns (but does not fail) when the
    extension is not a recognised video format.  No download is performed.

    Security:
        - Expands ``~`` and resolves symlinks via ``Path.expanduser().resolve()``
        - Only files that physically exist on disk are returned

    Args:
        path: Local file path (may include ``~`` or relative components).

    Returns:
        A :class:`DownloadResult` with ``video_path`` set to the resolved
        absolute path and ``downloaded=False``.

    Raises:
        DownloadError: If the file does not exist.

    Example:
        >>> result = resolve_local("~/Downloads/lecture.mp4")
        >>> print(result.video_path)
        /home/user/Downloads/lecture.mp4
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise DownloadError(f"File not found: {p}", source=str(p))
    if p.suffix.lower() not in VIDEO_EXTS:
        print(
            f"[watch] warning: {p.suffix} is not a known video extension, proceeding anyway",
            file=sys.stderr,
        )
    return DownloadResult(
        video_path=str(p),
        subtitle_path=None,
        info={"title": p.name, "url": str(p)},
        downloaded=False,
    )


def _pick_subtitle(out_dir: Path) -> Path | None:
    candidates = sorted(out_dir.glob("video*.vtt"))
    if not candidates:
        return None
    preferred = [
        c for c in candidates
        if any(marker in c.name for marker in (".en.", ".en-US.", ".en-GB.", ".en-orig."))
    ]
    return preferred[0] if preferred else candidates[0]


def _pick_video(out_dir: Path) -> Path | None:
    for ext in (".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".opus"):
        for candidate in out_dir.glob(f"video*{ext}"):
            return candidate
    for candidate in out_dir.glob("video.*"):
        if candidate.suffix.lower() in VIDEO_EXTS:
            return candidate
    return None


def fetch_captions(url: str, out_dir: Path) -> DownloadResult:
    """Fetch metadata and best available VTT captions without downloading video.

    Calls ``yt-dlp --skip-download`` to retrieve video metadata (title,
    uploader, duration) and subtitles (manual first, then auto-generated).
    The downloaded subtitle files are written to *out_dir* so that
    :func:`transcribe.parse_vtt` can parse them without needing Whisper.

    Security:
        - No credentials are stored or transmitted
        - Only public URLs are supported by yt-dlp without cookies

    Args:
        url: Video URL to fetch captions for (YouTube, Vimeo, etc.).
        out_dir: Output directory for subtitle and metadata files. Created
            if it does not exist.

    Returns:
        A :class:`DownloadResult` with ``subtitle_path`` pointing to the best
        VTT file (or ``None`` if none found) and ``info`` dict populated with
        title/uploader/duration.

    Raises:
        DownloadError: If ``yt-dlp`` is not installed on the system.

    Example:
        >>> result = fetch_captions("https://youtu.be/abc", Path("/tmp/caps"))
        >>> print(result.subtitle_path)
        /tmp/caps/video.en.vtt
    """
    if shutil.which("yt-dlp") is None:
        raise DownloadError(
            "yt-dlp is not installed — install with: brew install yt-dlp",
            source=url,
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", "en.*",
        "--sub-format", "vtt",
        "--convert-subs", "vtt",
        "--no-playlist",
        "--ignore-errors",
        "-o", output_template,
        "--",
        url,
    ]
    subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    subtitle = _pick_subtitle(out_dir)
    info = _read_info(out_dir / "video.info.json", url)
    return DownloadResult(
        video_path=None,
        subtitle_path=str(subtitle) if subtitle else None,
        info=info or {"url": url},
        downloaded=False,
    )


def _read_info(info_path: Path, url: str) -> dict[str, str]:
    info: dict = {}
    if info_path.exists():
        try:
            raw = json.loads(info_path.read_text(encoding="utf-8"))
            info = {
                "title": raw.get("title"),
                "uploader": raw.get("uploader") or raw.get("channel"),
                "duration": raw.get("duration"),
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
) -> DownloadResult:
    """Download video via yt-dlp.

    Downloads the video at the given URL into *out_dir*, fetching the best
    available resolution up to 720p. Subtitles (manual then auto-generated,
    English) are also downloaded in VTT format.  A ``video.info.json`` file
    containing metadata (title, uploader, duration) is saved alongside.

    Security:
        - No credentials are stored or transmitted
        - Only public URLs are supported without cookies
        - yt-dlp validates URLs before download

    Args:
        url: Video URL (YouTube, Vimeo, TikTok, etc.).
        out_dir: Output directory for downloaded files. Created if needed.
        audio_only: Download audio track only (default: ``False``).

    Returns:
        A :class:`DownloadResult` with ``video_path`` pointing to the
        downloaded file, ``subtitle_path`` to the best VTT (or ``None``),
        and ``downloaded=True``.

    Raises:
        DownloadError: If ``yt-dlp`` is not installed, produces no video file,
            or the download fails.

    Example:
        >>> result = download_url("https://youtu.be/abc", Path("/tmp/output"))
        >>> print(result.video_path)
        /tmp/output/video.mp4
    """
    if shutil.which("yt-dlp") is None:
        raise DownloadError(
            "yt-dlp is not installed — install with: brew install yt-dlp",
            source=url,
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")

    fmt = "ba/bestaudio" if audio_only else "bv*[height<=720]+ba/b[height<=720]/bv+ba/b"
    cmd = [
        "yt-dlp",
        "-N", "8",
        "-f", fmt,
        "--merge-output-format", "mp4",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", "en.*",
        "--sub-format", "vtt",
        "--convert-subs", "vtt",
        "--no-playlist",
        "--ignore-errors",
        "-o", output_template,
        "--",
        url,
    ]

    # yt-dlp may exit non-zero if a subtitle variant fails (e.g. 429) even when
    # the video itself downloaded fine. Treat "video file present" as success.
    result = subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    video = _pick_video(out_dir)
    if video is None:
        raise DownloadError(
            f"yt-dlp did not produce a video file in {out_dir} (exit {result.returncode})",
            source=url,
            return_code=result.returncode,
        )

    subtitle = _pick_subtitle(out_dir)
    info = _read_info(out_dir / "video.info.json", url)

    return DownloadResult(
        video_path=str(video),
        subtitle_path=str(subtitle) if subtitle else None,
        info=info or {"url": url},
        downloaded=True,
    )


def download(
    source: str,
    out_dir: Path,
    audio_only: bool = False,
) -> DownloadResult:
    """Download video or resolve local file path.

    This is the top-level entry point that automatically chooses between
    :func:`download_url` (for HTTP/HTTPS URLs) and :func:`resolve_local`
    (for local file paths).

    Security:
        - No credentials are stored or transmitted
        - Local paths are resolved and checked for existence

    Args:
        source: Video URL or local file path. URLs must use ``http://`` or
            ``https://`` scheme; everything else is treated as a local path.
        out_dir: Output directory for downloaded files.
        audio_only: Download audio track only (default: ``False``).

    Returns:
        A :class:`DownloadResult` with ``video_path``, ``subtitle_path``,
        ``info`` metadata, and ``downloaded`` flag.

    Raises:
        DownloadError: If the URL download fails or the local file does not
            exist.

    Example:
        >>> result = download("https://youtu.be/abc", Path("/tmp/output"))
        >>> result = download("~/videos/lecture.mp4", Path("/tmp/output"))
    """
    if is_url(source):
        return download_url(source, out_dir, audio_only=audio_only)
    return resolve_local(source)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: download.py <url-or-path> <out-dir>", file=sys.stderr)
        raise SystemExit(2)
    result = download(sys.argv[1], Path(sys.argv[2]))
    print(json.dumps(result, indent=2))
