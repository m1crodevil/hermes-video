#!/usr/bin/env python3
"""Transcribe a video via Groq or OpenAI Whisper API.

Strategy: extract audio (mono 16kHz mp3, tiny payload), upload to whichever
API has a key. Returns segments in the same shape as transcribe.parse_vtt so
the rest of the pipeline (filter_range, format_transcript) doesn't care where
the transcript came from.

Pure stdlib — no `pip install groq` or `pip install openai` needed.
"""
from __future__ import annotations

import io
import json
import math
import mimetypes
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from typing import Any, Callable

from errors import ConfigError, TranscriptionError
from types import TranscriptSegment, Seconds, WhisperBackend


GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"

OPENAI_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_MODEL = "whisper-1"

# Both Groq's free tier and OpenAI whisper-1 cap uploads at 25 MB. We target a
# margin under that so multipart framing overhead never pushes a chunk over.
MAX_UPLOAD_BYTES = 24 * 1024 * 1024


def plan_chunks(
    total_seconds: Seconds,
    total_bytes: int,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> list[tuple[Seconds, Seconds]]:
    """Split a duration into contiguous (offset, duration) chunks under max_bytes.

    Size scales linearly with duration (constant-bitrate mono mp3), so an even
    time split yields evenly-sized chunks.  Returns a single full-length chunk
    when the audio already fits within *max_bytes*.

    Args:
        total_seconds: Total audio duration in seconds.
        total_bytes: Total file size in bytes.
        max_bytes: Maximum bytes per chunk (default: :data:`MAX_UPLOAD_BYTES`).

    Returns:
        A list of ``(offset_seconds, duration_seconds)`` tuples that
        partition the full duration without gaps or overlaps.

    Example:
        >>> plan_chunks(300.0, 50 * 1024 * 1024)  # fits in one chunk
        [(0.0, 300.0)]
    """
    if total_bytes <= max_bytes or total_seconds <= 0:
        return [(0.0, total_seconds)]

    n = math.ceil(total_bytes / max_bytes)
    chunk = total_seconds / n
    plan: list[tuple[float, float]] = []
    for i in range(n):
        offset = i * chunk
        # The last chunk absorbs any rounding remainder so durations sum exactly.
        duration = (total_seconds - offset) if i == n - 1 else chunk
        plan.append((round(offset, 3), round(duration, 3)))
    return plan


def load_api_key(preferred: str | None = None) -> tuple[str, str] | tuple[None, None]:
    """Return ``(backend, api_key)`` for Whisper transcription.

    Searches environment variables and ``~/.config/watch/.env`` for
    ``GROQ_API_KEY`` (preferred) or ``OPENAI_API_KEY``.  Groq is checked
    first because it offers a free tier with no upload size limit.

    Security:
        - API keys are never logged or returned in error messages
        - Keys are loaded from environment only; never hardcoded

    Args:
        preferred: Force a specific backend (``"groq"`` or ``"openai"``).
            When ``None`` (default), Groq is preferred with OpenAI fallback.

    Returns:
        A ``(backend_name, api_key)`` tuple, or ``(None, None)`` when no
        valid key is found.

    Example:
        >>> backend, key = load_api_key("groq")
        >>> backend
        'groq'
    """
    def _from_env(name: str) -> str | None:
        value = os.environ.get(name)
        return value.strip() if value else None

    def _from_dotenv(path: Path, name: str) -> str | None:
        if not path.exists():
            return None
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() != name:
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                return value or None
        except OSError:
            return None
        return None

    dotenv_paths = [
        Path.home() / ".config" / "watch" / ".env",
        Path.cwd() / ".env",
    ]

    candidates = (("GROQ_API_KEY", "groq"), ("OPENAI_API_KEY", "openai"))
    if preferred is not None:
        candidates = tuple(c for c in candidates if c[1] == preferred)

    for key_name, backend in candidates:
        value = _from_env(key_name)
        if not value:
            for candidate in dotenv_paths:
                value = _from_dotenv(candidate, key_name)
                if value:
                    break
        if value:
            return backend, value

    return None, None


def extract_audio(video_path: str, out_path: Path) -> Path:
    """Extract mono 16kHz 64kbps mp3 from a video file.

    Produces a tiny audio file (~480 kB/min) suitable for upload to any
    Whisper-compatible transcription API.

    Security:
        - Only reads the local video file; no network calls
        - Output is written only to *out_path*

    Args:
        video_path: Path to the source video file.
        out_path: Destination path for the extracted ``.mp3``.

    Returns:
        The resolved *out_path* on success.

    Raises:
        TranscriptionError: If ``ffmpeg`` is not installed, the extraction
            fails, or the video has no audio track.

    Example:
        >>> extract_audio("video.mp4", Path("audio.mp3"))
        PosixPath('audio.mp3')
    """
    if shutil.which("ffmpeg") is None:
        raise TranscriptionError(
            "ffmpeg is not installed — install with: brew install ffmpeg",
            backend="unknown",
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", str(Path(video_path).resolve()),
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "64k",
        str(out_path.resolve()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise TranscriptionError(
            f"ffmpeg audio extraction failed: {result.stderr.strip()}",
            backend="unknown",
            api_error=result.stderr,
        )
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise TranscriptionError(
            "ffmpeg produced no audio — video may have no audio track",
            backend="unknown",
        )
    return out_path


def audio_duration(audio_path: Path) -> Seconds:
    """Return the duration of an audio file in seconds via ffprobe.

    Args:
        audio_path: Path to the audio file (mp3, wav, etc.).

    Returns:
        Duration in seconds as a float.

    Raises:
        TranscriptionError: If ``ffprobe`` is not installed or fails on the
            given file.

    Example:
        >>> audio_duration(Path("audio.mp3"))
        142.5
    """
    if shutil.which("ffprobe") is None:
        raise TranscriptionError(
            "ffprobe is not installed — install with: brew install ffmpeg",
            backend="unknown",
        )

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(audio_path.resolve()),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TranscriptionError(
            f"ffprobe failed: {result.stderr.strip()}",
            backend="unknown",
            api_error=result.stderr,
        )
    fmt = json.loads(result.stdout or "{}").get("format", {})
    return float(fmt.get("duration") or 0.0)


def split_audio(
    full_audio: Path,
    work_dir: Path,
    plan: list[tuple[float, float]],
) -> list[tuple[Path, float]]:
    """Slice full_audio into per-plan chunk files, returning ``(path, offset)`` pairs.

    Uses stream copy (``-c copy``) so there is no re-encode and no quality
    loss; mp3 frame boundaries are close enough for transcription purposes.
    Each chunk is written as ``chunk_NNN.mp3`` in *work_dir*.

    Security:
        - Only reads *full_audio*; writes only to *work_dir*

    Args:
        full_audio: Path to the source mp3 file.
        work_dir: Directory for chunk files.  Created if needed.
        plan: Chunk plan from :func:`plan_chunks` — list of
            ``(offset_seconds, duration_seconds)`` tuples.

    Returns:
        A list of ``(chunk_path, offset_seconds)`` tuples in plan order.

    Raises:
        TranscriptionError: If ``ffmpeg`` is not installed or any chunk
            fails to produce output.

    Example:
        >>> chunks = split_audio(Path("audio.mp3"), Path("/tmp/chunks"),
        ...     [(0.0, 120.0), (120.0, 120.0)])
        >>> len(chunks)
        2
    """
    if shutil.which("ffmpeg") is None:
        raise TranscriptionError(
            "ffmpeg is not installed — install with: brew install ffmpeg",
            backend="unknown",
        )

    work_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[tuple[Path, float]] = []
    for index, (offset, duration) in enumerate(plan):
        out_path = work_dir / f"chunk_{index:03d}.mp3"
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", f"{offset:.3f}",
            "-i", str(full_audio.resolve()),
            "-t", f"{duration:.3f}",
            "-c", "copy",
            str(out_path.resolve()),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            raise TranscriptionError(
                f"ffmpeg failed to split audio chunk {index + 1}: {result.stderr.strip()}",
                backend="unknown",
                api_error=result.stderr,
                chunk_index=index,
            )
        chunks.append((out_path, offset))
    return chunks


def _build_multipart(fields: dict[str, str], file_path: Path) -> tuple[bytes, str]:
    """Assemble a multipart/form-data body the Whisper APIs accept.

    Whisper's multipart upload is small and predictable — doing it by hand
    keeps us on pure stdlib instead of pulling requests/groq/openai SDKs.
    """
    boundary = f"----WatchBoundary{uuid.uuid4().hex}"
    eol = b"\r\n"
    buf = io.BytesIO()

    for name, value in fields.items():
        buf.write(f"--{boundary}".encode()); buf.write(eol)
        buf.write(f'Content-Disposition: form-data; name="{name}"'.encode()); buf.write(eol)
        buf.write(eol)
        buf.write(str(value).encode()); buf.write(eol)

    mimetype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    buf.write(f"--{boundary}".encode()); buf.write(eol)
    buf.write(
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"'.encode()
    )
    buf.write(eol)
    buf.write(f"Content-Type: {mimetype}".encode()); buf.write(eol)
    buf.write(eol)
    buf.write(file_path.read_bytes())
    buf.write(eol)
    buf.write(f"--{boundary}--".encode()); buf.write(eol)

    return buf.getvalue(), boundary

MAX_ATTEMPTS = 4       # initial + 3 retries
MAX_429_RETRIES = 2
RETRY_BASE_DELAY = 2.0


def _post_whisper(
    endpoint: str,
    api_key: str,
    model: str,
    audio_path: Path,
    backend: str = "unknown",
) -> dict[str, Any]:
    fields = {
        "model": model,
        "response_format": "verbose_json",
        "temperature": "0",
    }
    body, boundary = _build_multipart(fields, audio_path)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        # Groq sits behind Cloudflare — the default `Python-urllib/3.x` UA
        # trips WAF rule 1010 (403) before auth even runs. Any non-default
        # UA clears it; we identify honestly.
        "User-Agent": "watch-skill/1.0 (+claude-code; python-urllib)",
    }

    context = ssl.create_default_context()
    rate_limit_hits = 0
    last_exc: Exception | None = None
    last_detail = ""

    for attempt in range(MAX_ATTEMPTS):
        request = Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=300, context=context) as response:
                payload = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = _read_error_body(exc)
            last_exc, last_detail = exc, detail

            # 4xx other than 429 are client errors — no retry will fix them.
            if 400 <= exc.code < 500 and exc.code != 429:
                raise TranscriptionError(
                    f"Whisper request failed: {exc}{detail}",
                    backend=backend,
                    api_error=str(exc),
                )

            if exc.code == 429:
                rate_limit_hits += 1
                if rate_limit_hits >= MAX_429_RETRIES:
                    raise TranscriptionError(
                        f"Whisper request failed: {exc}{detail}",
                        backend=backend,
                        api_error=str(exc),
                    )
                delay = _retry_after(exc) or RETRY_BASE_DELAY * (2 ** attempt) + 1
            else:
                delay = RETRY_BASE_DELAY * (2 ** attempt)

            if attempt < MAX_ATTEMPTS - 1:
                print(
                    f"[watch] whisper HTTP {exc.code} — retrying in {delay:.1f}s "
                    f"(attempt {attempt + 2}/{MAX_ATTEMPTS})",
                    file=sys.stderr,
                )
                time.sleep(delay)
            continue
        except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as exc:
            last_exc, last_detail = exc, ""
            if attempt < MAX_ATTEMPTS - 1:
                delay = RETRY_BASE_DELAY * (attempt + 1)
                print(
                    f"[watch] whisper network error ({type(exc).__name__}: {exc}) — "
                    f"retrying in {delay:.1f}s (attempt {attempt + 2}/{MAX_ATTEMPTS})",
                    file=sys.stderr,
                )
                time.sleep(delay)
            continue

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise TranscriptionError(
                f"Whisper returned non-JSON response: {exc}: {payload[:200]}",
                backend=backend,
                api_error=payload[:200],
            )

    raise TranscriptionError(
        f"Whisper request failed after {MAX_ATTEMPTS} attempts: {last_exc}{last_detail}",
        backend=backend,
        api_error=str(last_exc),
    )


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read()
    except Exception:
        return ""
    if not body:
        return ""
    try:
        return f" — {body.decode('utf-8', errors='replace')[:400]}"
    except Exception:
        return ""


def _retry_after(exc: urllib.error.HTTPError) -> Seconds | None:
    header = exc.headers.get("Retry-After") if getattr(exc, "headers", None) else None
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None


def shift_segments(segments: list[dict[str, Any]], offset_seconds: Seconds) -> list[dict[str, Any]]:
    """Return a copy of segments with start/end shifted by *offset_seconds*.

    Each chunk is transcribed in isolation, so Whisper returns 0-based
    timestamps per chunk; shifting by the chunk's offset stitches them into
    source time.  A no-op when *offset_seconds* is zero.

    Args:
        segments: List of dicts with ``"start"``, ``"end"``, and ``"text"``
            keys (0-based within the chunk).
        offset_seconds: Seconds to add to every timestamp.

    Returns:
        A new list of shifted segments (originals are not mutated).

    Example:
        >>> segs = [{"start": 0, "end": 5, "text": "hi"}]
        >>> shifted = shift_segments(segs, 120.0)
        >>> shifted[0]["start"]
        120.0
    """
    if offset_seconds == 0:
        return segments
    return [
        {
            "start": round(seg["start"] + offset_seconds, 2),
            "end": round(seg["end"] + offset_seconds, 2),
            "text": seg["text"],
        }
        for seg in segments
    ]


def _segments_from_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Whisper verbose_json into our {start, end, text} segment format."""
    out: list[dict[str, Any]] = []
    for seg in data.get("segments") or []:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        out.append({
            "start": round(float(seg.get("start") or 0.0), 2),
            "end": round(float(seg.get("end") or 0.0), 2),
            "text": text,
        })

    if not out:
        full = (data.get("text") or "").strip()
        if full:
            out.append({"start": 0.0, "end": 0.0, "text": full})

    return out


def transcribe_chunks(
    chunks: list[tuple[Path, Seconds]],
    transcribe_one: Callable[[Path], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Transcribe each chunk, shift its segments by the chunk offset, concatenate.

    A chunk that fails after its own retries is logged and skipped so one bad
    slice doesn't discard the whole transcript.  Raises only if *every* chunk
    fails.

    Security:
        - API keys are not logged; only backend name is printed

    Args:
        chunks: List of ``(chunk_path, offset_seconds)`` tuples from
            :func:`split_audio`.
        transcribe_one: Callable that takes a chunk path and returns its
            0-based segments (typically wraps :func:`_transcribe_file`).

    Returns:
        A merged list of segment dicts with source-relative timestamps.

    Raises:
        TranscriptionError: If every chunk fails transcription.

    Example:
        >>> chunks = [(Path("chunk_000.mp3"), 0.0), (Path("chunk_001.mp3"), 120.0)]
        >>> segments = transcribe_chunks(chunks, my_transcriber)
    """
    segments: list[dict[str, Any]] = []
    failures = 0
    for index, (path, offset) in enumerate(chunks):
        try:
            chunk_segments = transcribe_one(path)
        except TranscriptionError as exc:
            failures += 1
            print(
                f"[watch] chunk {index + 1}/{len(chunks)} failed — skipping ({exc})",
                file=sys.stderr,
            )
            continue
        segments.extend(shift_segments(chunk_segments, offset))
        print(
            f"[watch] chunk {index + 1}/{len(chunks)} → {len(chunk_segments)} segments",
            file=sys.stderr,
        )

    if failures == len(chunks):
        raise TranscriptionError(
            "Whisper failed on every audio chunk",
            backend="unknown",
        )
    return segments


def _transcribe_file(backend: str, api_key: str, audio_path: Path) -> list[dict[str, Any]]:
    """Upload one audio file and return its 0-based segments."""
    if backend == "groq":
        response = _post_whisper(GROQ_ENDPOINT, api_key, GROQ_MODEL, audio_path, backend=backend)
    elif backend == "openai":
        response = _post_whisper(OPENAI_ENDPOINT, api_key, OPENAI_MODEL, audio_path, backend=backend)
    else:
        raise TranscriptionError(
            f"Unknown whisper backend: {backend}",
            backend=backend,
        )
    return _segments_from_response(response)


def transcribe_video(
    video_path: str,
    audio_out: Path,
    backend: WhisperBackend | None = None,
    api_key: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Run the full transcription flow: extract audio → upload → parse segments.

    This is the high-level entry point.  It auto-detects the backend/key if
    not provided, extracts mono mp3 audio, uploads to the Whisper-compatible
    API (with automatic chunking for files exceeding 24 MB), and returns
    segments in the same shape as :func:`transcribe.parse_vtt`.

    Security:
        - API keys are loaded from environment or ``~/.config/watch/.env``
        - Keys are never logged in output or error messages
        - HTTPS is used for all API calls

    Args:
        video_path: Path to the source video file.
        audio_out: Destination path for the extracted audio file.
        backend: Whisper backend (``"groq"`` or ``"openai"``), or ``None``
            for auto-detection via :func:`load_api_key`.
        api_key: API key for the backend, or ``None`` for auto-detection.

    Returns:
        A ``(segments, backend_used)`` tuple where *segments* is a list of
        dicts with ``"start"``, ``"end"``, and ``"text"`` keys.

    Raises:
        ConfigError: If no API key is available for either backend.
        TranscriptionError: If audio extraction, upload, or parsing fails.

    Example:
        >>> segments, backend = transcribe_video(
        ...     "video.mp4", Path("audio.mp3"), backend="groq"
        ... )
        >>> print(f"Transcribed {len(segments)} segments via {backend}")
    """
    if backend is None or api_key is None:
        detected_backend, detected_key = load_api_key()
        backend = backend or detected_backend
        api_key = api_key or detected_key

    if not backend or not api_key:
        setup_py = Path(__file__).resolve().parent / "setup.py"
        raise ConfigError(
            "No Whisper API key available. Set GROQ_API_KEY (preferred) or OPENAI_API_KEY "
            "in the environment or in ~/.config/watch/.env. "
            f"Run `python3 {setup_py}` to configure.",
            config_file=Path.home() / ".config" / "watch" / ".env",
            missing_key="GROQ_API_KEY/OPENAI_API_KEY",
        )

    print(f"[watch] extracting audio for Whisper ({backend})…", file=sys.stderr)
    audio_path = extract_audio(video_path, audio_out)
    audio_bytes = audio_path.stat().st_size

    def transcribe_one(path: Path) -> list[dict]:
        return _transcribe_file(backend, api_key, path)

    if audio_bytes <= MAX_UPLOAD_BYTES:
        print(
            f"[watch] audio: {audio_bytes / 1024:.0f} kB — uploading to {backend} Whisper…",
            file=sys.stderr,
        )
        segments = transcribe_one(audio_path)
    else:
        duration = audio_duration(audio_path)
        plan = plan_chunks(duration, audio_bytes, MAX_UPLOAD_BYTES)
        print(
            f"[watch] audio: {audio_bytes / (1024 * 1024):.0f} MB exceeds "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB — splitting into {len(plan)} chunks…",
            file=sys.stderr,
        )
        chunks = split_audio(audio_path, audio_out.parent / "chunks", plan)
        segments = transcribe_chunks(chunks, transcribe_one)

    if not segments:
        raise TranscriptionError(
            "Whisper returned no transcript segments",
            backend=backend or "unknown",
        )

    print(f"[watch] transcribed {len(segments)} segments via {backend}", file=sys.stderr)
    return segments, backend


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: whisper.py <video-path> [<audio-out.mp3>] [--backend groq|openai]", file=sys.stderr)
        raise SystemExit(2)

    video = sys.argv[1]
    audio_out = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else Path("audio.mp3")
    backend_override = None
    if "--backend" in sys.argv:
        backend_override = sys.argv[sys.argv.index("--backend") + 1]

    segments, backend = transcribe_video(video, audio_out, backend=backend_override)
    print(json.dumps({"backend": backend, "segments": segments}, indent=2))
