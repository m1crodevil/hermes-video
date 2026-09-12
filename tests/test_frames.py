"""Tests for frames metadata probe."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from watch.frames import metadata as frames


class TestGetMetadata:
    def test_missing_ffprobe(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda x: None)
        with pytest.raises(SystemExit):
            frames.get_metadata("/nonexistent.mp4")
