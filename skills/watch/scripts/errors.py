"""Typed exceptions for hermes-video pipeline."""
from __future__ import annotations

from typing import Any


class WatchError(Exception):
    """Base error for watch pipeline."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DownloadError(WatchError):
    """yt-dlp or network failure."""


class FfmpegError(WatchError):
    """ffmpeg/ffprobe failure."""


class WhisperError(WatchError):
    """Whisper API failure."""


class ConfigError(WatchError):
    """Configuration issue."""


class NoCaptionsError(WatchError):
    """No captions available for video."""


# Backward compat aliases
ExtractionError = FfmpegError
TranscriptionError = WhisperError
APIError = WhisperError
