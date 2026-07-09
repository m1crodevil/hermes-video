#!/usr/bin/env python3
"""Custom exceptions for claude-video.

Exception hierarchy:
- WatchError (base)
  - DownloadError (video download failures)
  - ExtractionError (frame extraction failures)
  - TranscriptionError (transcription failures)
  - APIError (API request failures)
  - ConfigError (configuration errors)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class WatchError(Exception):
    """Base exception for watch skill.
    
    Attributes:
        message: Error message
        details: Additional error details
    """
    
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        """Format exception for display."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class DownloadError(WatchError):
    """Video download failed.
    
    Attributes:
        source: Video source URL or path
        return_code: Process return code
        stderr: Process stderr output
    """
    
    def __init__(
        self,
        message: str,
        source: str,
        return_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        details: dict[str, Any] = {"source": source}
        if return_code is not None:
            details["return_code"] = return_code
        if stderr:
            details["stderr"] = stderr[:200]
        super().__init__(message, details)
        self.source = source
        self.return_code = return_code
        self.stderr = stderr


class ExtractionError(WatchError):
    """Frame extraction failed.
    
    Attributes:
        video_path: Path to video file
        command: Failed command
        return_code: Process return code
        stderr: Process stderr output
    """
    
    def __init__(
        self,
        message: str,
        video_path: Path,
        command: list[str] | None = None,
        return_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        details: dict[str, Any] = {"video_path": str(video_path)}
        if command:
            details["command"] = " ".join(command)
        if return_code is not None:
            details["return_code"] = return_code
        if stderr:
            details["stderr"] = stderr[:200]
        super().__init__(message, details)
        self.video_path = video_path
        self.command = command
        self.return_code = return_code
        self.stderr = stderr


class TranscriptionError(WatchError):
    """Transcription failed.
    
    Attributes:
        backend: Transcription backend (groq/openai)
        api_error: API error message
        chunk_index: Failed chunk index (if applicable)
    """
    
    def __init__(
        self,
        message: str,
        backend: str,
        api_error: str | None = None,
        chunk_index: int | None = None,
    ) -> None:
        details: dict[str, Any] = {"backend": backend}
        if api_error:
            details["api_error"] = api_error[:200]
        if chunk_index is not None:
            details["chunk_index"] = chunk_index
        super().__init__(message, details)
        self.backend = backend
        self.api_error = api_error
        self.chunk_index = chunk_index


class APIError(WatchError):
    """API request failed.
    
    Attributes:
        endpoint: API endpoint URL
        status_code: HTTP status code
        response_body: API response body
    """
    
    def __init__(
        self,
        message: str,
        endpoint: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        details: dict[str, Any] = {"endpoint": endpoint}
        if status_code is not None:
            details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body[:200]
        super().__init__(message, details)
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_body = response_body


class ConfigError(WatchError):
    """Configuration error.
    
    Attributes:
        config_file: Path to config file
        missing_key: Missing configuration key
    """
    
    def __init__(
        self,
        message: str,
        config_file: Path | None = None,
        missing_key: str | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if config_file:
            details["config_file"] = str(config_file)
        if missing_key:
            details["missing_key"] = missing_key
        super().__init__(message, details)
        self.config_file = config_file
        self.missing_key = missing_key
