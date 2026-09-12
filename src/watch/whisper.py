#!/usr/bin/env python3
"""Transcribe a video via Groq or OpenAI Whisper API (stdlib only)."""
from __future__ import annotations

import io
import json
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


GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"
OPENAI_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_MODEL = "whisper-1"
MAX_ATTEMPTS = 4
RETRY_DELAY = 2.0


def load_api_key(preferred: str | None = None) -> tuple[str, str] | tuple[None, None]:
    """Return (backend, api_key). Prefers Groq, falls back to OpenAI."""

    def _from_env(name: str) -> str | None:
        value = os.environ.get(name)
        return value.strip() if value else None

    def _from_dotenv(path: Path, name: str) -> str | None:
        if not path.exists():
            return None
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
        return None

    candidates = (("GROQ_API_KEY", "groq"), ("OPENAI_API_KEY", "openai"))
    if preferred is not None:
        candidates = tuple(c for c in candidates if c[1] == preferred)

    for key_name, backend in candidates:
        value = _from_env(key_name)
        if not value:
            value = _from_dotenv(Path.home() / ".config" / "watch" / ".env", key_name)
        if value:
            return backend, value

    return None, None


def extract_audio(video_path: str, out_path: Path) -> Path:
    """Extract mono 16kHz 64kbps mp3 from video."""
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is not installed. Install with: brew install ffmpeg")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(Path(video_path).resolve()),
        "-vn", "-acodec", "libmp3lame",
        "-ar", "16000", "-ac", "1", "-b:a", "64k",
        str(out_path.resolve()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg audio extraction failed: {result.stderr.strip()}")
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise SystemExit("ffmpeg produced no audio — video may have no audio track")
    return out_path


def _build_multipart(fields: dict[str, str], file_path: Path) -> tuple[bytes, str]:
    boundary = f"----WatchBoundary{uuid.uuid4().hex}"
    eol = b"\r\n"
    body = io.BytesIO()

    for name, value in fields.items():
        body.write(f"--{boundary}".encode()); body.write(eol)
        body.write(f'Content-Disposition: form-data; name="{name}"'.encode()); body.write(eol)
        body.write(eol)
        body.write(str(value).encode()); body.write(eol)

    mimetype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body.write(f"--{boundary}".encode()); body.write(eol)
    body.write(f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"'.encode())
    body.write(eol)
    body.write(f"Content-Type: {mimetype}".encode()); body.write(eol)
    body.write(eol)
    body.write(file_path.read_bytes())
    body.write(eol)
    body.write(f"--{boundary}--".encode()); body.write(eol)

    return body.getvalue(), boundary


def _post_whisper(endpoint: str, api_key: str, model: str, audio_path: Path) -> dict:
    body, boundary = _build_multipart(
        {"model": model, "response_format": "verbose_json", "temperature": "0"},
        audio_path,
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    context = ssl.create_default_context()
    request = Request(endpoint, data=body, headers=headers, method="POST")

    for attempt in range(MAX_ATTEMPTS):
        try:
            with urlopen(request, timeout=300, context=context) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:100] if hasattr(exc, "read") else ""
            if 400 <= exc.code < 500 and exc.code != 429:
                raise SystemExit(f"Whisper request failed: {exc} — {detail}")
            if attempt == MAX_ATTEMPTS - 1:
                raise SystemExit(f"Whisper request failed after {MAX_ATTEMPTS} attempts: {exc} — {detail}")
            delay = RETRY_DELAY * (2 ** attempt)
            print(f"[watch] whisper HTTP {exc.code} — retrying in {delay:.1f}s", file=sys.stderr)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as exc:
            if attempt == MAX_ATTEMPTS - 1:
                raise SystemExit(f"Whisper request failed after {MAX_ATTEMPTS} attempts: {exc}")
            delay = RETRY_DELAY * (attempt + 1)
            print(f"[watch] whisper network error ({exc}) — retrying in {delay:.1f}s", file=sys.stderr)
            time.sleep(delay)

    raise SystemExit(f"Whisper request failed after {MAX_ATTEMPTS} attempts")


def _segments_from_response(data: dict) -> list[dict]:
    """Convert Whisper verbose_json into {start, end, text} segments."""
    out = [
        {
            "start": round(float(seg.get("start") or 0.0), 2),
            "end": round(float(seg.get("end") or 0.0), 2),
            "text": (seg.get("text") or "").strip(),
        }
        for seg in (data.get("segments") or [])
        if (seg.get("text") or "").strip()
    ]
    if not out:
        full = (data.get("text") or "").strip()
        if full:
            out.append({"start": 0.0, "end": 0.0, "text": full})
    return out


def _transcribe_file(backend: str, api_key: str, audio_path: Path) -> list[dict]:
    if backend == "groq":
        response = _post_whisper(GROQ_ENDPOINT, api_key, GROQ_MODEL, audio_path)
    elif backend == "openai":
        response = _post_whisper(OPENAI_ENDPOINT, api_key, OPENAI_MODEL, audio_path)
    else:
        raise SystemExit(f"Unknown whisper backend: {backend}")
    return _segments_from_response(response)


def transcribe_video(
    video_path: str,
    audio_out: Path,
    backend: str | None = None,
    api_key: str | None = None,
) -> tuple[list[dict], str]:
    """Extract audio and transcribe with Whisper."""
    if backend is None or api_key is None:
        detected_backend, detected_key = load_api_key()
        backend = backend or detected_backend
        api_key = api_key or detected_key

    if not backend or not api_key:
        setup_py = Path(__file__).resolve().parent / "setup.py"
        raise SystemExit(
            "No Whisper API key available. Set GROQ_API_KEY (preferred) or OPENAI_API_KEY "
            "in the environment or in ~/.config/watch/.env. "
            f"Run `python3 {setup_py}` to configure."
        )

    print(f"[watch] extracting audio for Whisper ({backend})…", file=sys.stderr)
    audio_path = extract_audio(video_path, audio_out)

    print(
        f"[watch] audio: {audio_path.stat().st_size / 1024:.0f} kB — uploading to {backend} Whisper…",
        file=sys.stderr,
    )
    segments = _transcribe_file(backend, api_key, audio_path)

    if not segments:
        raise SystemExit("Whisper returned no transcript segments")

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
