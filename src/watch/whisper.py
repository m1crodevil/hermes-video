"""Transcribe a video via Groq Whisper API with chunking fallback."""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

from watch.config import load_api_key


GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"
OPENAI_ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_MODEL = "whisper-1"
MAX_FILE_MB = 25  # free tier limit
CHUNK_MINUTES = 15
MAX_ATTEMPTS = 4
RETRY_DELAY = 2.0


def extract_audio(video_path: str, out_path: Path) -> Path:
    """Extract mono 16kHz mp3 from video."""
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is not installed")

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


def _post_whisper(endpoint: str, api_key: str, model: str, audio_path: Path) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {"model": model, "response_format": "verbose_json", "temperature": "0"}

    for attempt in range(MAX_ATTEMPTS):
        try:
            with audio_path.open("rb") as f:
                files = {"file": (audio_path.name, f, "audio/mpeg")}
                response = requests.post(endpoint, headers=headers, data=data, files=files, timeout=300)
            if response.status_code == 429 and attempt < MAX_ATTEMPTS - 1:
                delay = RETRY_DELAY * (2 ** attempt)
                print(f"[watch] whisper rate limited — retrying in {delay:.1f}s", file=sys.stderr)
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            if attempt == MAX_ATTEMPTS - 1:
                raise SystemExit(f"Whisper request failed after {MAX_ATTEMPTS} attempts: {exc}")
            delay = RETRY_DELAY * (attempt + 1)
            print(f"[watch] whisper network error ({exc}) — retrying in {delay:.1f}s", file=sys.stderr)
            time.sleep(delay)

    raise SystemExit(f"Whisper request failed after {MAX_ATTEMPTS} attempts")


def _segments_from_response(data: dict, offset: float = 0.0) -> list[dict]:
    out = [
        {
            "start": round(float(seg.get("start") or 0.0) + offset, 2),
            "end": round(float(seg.get("end") or 0.0) + offset, 2),
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


def _split_audio(audio_path: Path, out_dir: Path, chunk_seconds: int = CHUNK_MINUTES * 60) -> list[Path]:
    """Split audio into chunks under MAX_FILE_MB."""
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[Path] = []
    chunk_index = 0
    start = 0
    duration = chunk_seconds

    while True:
        chunk_path = out_dir / f"audio_chunk_{chunk_index:03d}.mp3"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(audio_path),
            "-ss", str(start),
            "-t", str(duration),
            "-ar", "16000", "-ac", "1", "-b:a", "64k",
            str(chunk_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            break
        if chunk_path.stat().st_size == 0:
            break
        chunks.append(chunk_path)
        chunk_index += 1
        start += duration

    return chunks


def _transcribe_file(backend: str, api_key: str, audio_path: Path, offset: float = 0.0) -> list[dict]:
    if backend == "groq":
        response = _post_whisper(GROQ_ENDPOINT, api_key, GROQ_MODEL, audio_path)
    elif backend == "openai":
        response = _post_whisper(OPENAI_ENDPOINT, api_key, OPENAI_MODEL, audio_path)
    else:
        raise SystemExit(f"Unknown whisper backend: {backend}")
    return _segments_from_response(response, offset)


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
        raise SystemExit(
            "No Whisper API key available. Set GROQ_API_KEY (preferred) or OPENAI_API_KEY "
            "in the environment or in ~/.config/watch/.env."
        )

    print(f"[watch] extracting audio for Whisper ({backend})…", file=sys.stderr)
    audio_path = extract_audio(video_path, audio_out)

    size_mb = audio_path.stat().st_size / (1024 * 1024)
    print(f"[watch] audio: {size_mb:.1f} MB", file=sys.stderr)

    segments: list[dict] = []
    if size_mb <= MAX_FILE_MB:
        segments = _transcribe_file(backend, api_key, audio_path)
    else:
        print(f"[watch] audio >{MAX_FILE_MB} MB — chunking for {backend} Whisper", file=sys.stderr)
        chunks = _split_audio(audio_path, audio_out.parent / "audio_chunks")
        for i, chunk in enumerate(chunks):
            offset = i * CHUNK_MINUTES * 60
            seg = _transcribe_file(backend, api_key, chunk, offset)
            segments.extend(seg)

    if not segments:
        raise SystemExit("Whisper returned no transcript segments")

    print(f"[watch] transcribed {len(segments)} segments via {backend}", file=sys.stderr)
    return segments, backend
