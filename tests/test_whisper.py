"""Whisper API helpers."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from watch import whisper


class TestLoadApiKey:
    def _set_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    def test_no_key_returns_none(self, monkeypatch, tmp_path):
        self._set_home(monkeypatch, tmp_path)
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        backend, key = whisper.load_api_key()
        assert backend is None
        assert key is None

    def test_prefers_groq(self, monkeypatch, tmp_path):
        self._set_home(monkeypatch, tmp_path)
        monkeypatch.setenv("GROQ_API_KEY", "sk-groq")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        backend, key = whisper.load_api_key()
        assert backend == "groq"
        assert key == "sk-groq"

    def test_openai_fallback(self, monkeypatch, tmp_path):
        self._set_home(monkeypatch, tmp_path)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        backend, key = whisper.load_api_key()
        assert backend == "openai"
        assert key == "sk-openai"

    def test_preferred_limits_selection(self, monkeypatch, tmp_path):
        self._set_home(monkeypatch, tmp_path)
        monkeypatch.setenv("GROQ_API_KEY", "sk-groq")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        backend, key = whisper.load_api_key(preferred="openai")
        assert backend == "openai"
        assert key == "sk-openai"


def _make_mp3(path: Path, seconds: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-t", str(seconds), "-i", "sine=frequency=440:sample_rate=16000",
            "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1", "-b:a", "64k",
            str(path),
        ],
        check=True,
    )


def test_extract_audio(tmp_path: Path):
    from watch.frames.metadata import get_metadata

    video = tmp_path / "test.mp4"
    _make_mp3(tmp_path / "audio.mp3", 2.0)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=32x24:d=2.0",
            "-i", str(tmp_path / "audio.mp3"),
            "-shortest", str(video),
        ],
        check=True,
    )

    out = tmp_path / "out.mp3"
    result = whisper.extract_audio(str(video), out)
    assert result.exists()
    assert out.stat().st_size > 0
    meta = get_metadata(str(result))
    assert meta["duration_seconds"] > 0


def test_segments_from_response():
    data = {
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "hello"},
            {"start": 2.0, "end": 3.5, "text": "world"},
        ]
    }
    segs = whisper._segments_from_response(data)
    assert len(segs) == 2
    assert segs[0]["text"] == "hello"
    assert segs[1]["text"] == "world"


def test_segments_from_response_falls_back_to_full_text():
    data = {"text": "hello world"}
    segs = whisper._segments_from_response(data)
    assert len(segs) == 1
    assert segs[0]["text"] == "hello world"
