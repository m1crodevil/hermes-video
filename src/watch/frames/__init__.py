"""Frame extraction sub-package — re-exports public API."""
from __future__ import annotations

from watch.frames.extract import extract_at_timestamps
from watch.frames.metadata import get_metadata

__all__ = ["extract_at_timestamps", "get_metadata"]
