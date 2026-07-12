#!/usr/bin/env python3
"""Custom exceptions for watch skill.

Exception hierarchy:
- WatchError (base)
  - DownloadError (video download failures)
  - ExtractionError (frame extraction failures)
  - TranscriptionError (transcription failures)
  - APIError (API request failures)
  - ConfigError (configuration errors)
"""
from __future__ import annotations

from typing import Any


class WatchError(Exception):
    """Base exception for watch skill."""
    
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DownloadError(WatchError):
    """Video download failures."""
    pass


class ExtractionError(WatchError):
    """Frame extraction failures."""
    pass


class TranscriptionError(WatchError):
    """Transcription failures."""
    pass


class APIError(WatchError):
    """API request failures."""
    pass


class ConfigError(WatchError):
    """Configuration errors."""
    pass
