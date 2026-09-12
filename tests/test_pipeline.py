"""Integration tests for the simplified watch pipeline."""
from __future__ import annotations

import io
import contextlib
import sys
from pathlib import Path

from watch.cli import main as watch_main


def _run(clip: Path, *args: str) -> str:
    old_argv = sys.argv
    try:
        sys.argv = ["watch", str(clip), "--no-whisper", *args]
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            try:
                watch_main()
            except SystemExit as e:
                if e.code != 0:
                    raise
        return f.getvalue()
    finally:
        sys.argv = old_argv


def test_timestamps_extract_cue_frames(cut_clip: Path):
    out = _run(cut_clip, "--timestamps", "0.5")
    assert "frames" in out.lower()


def test_no_timestamps_auto_extracts_frames(cut_clip: Path):
    out = _run(cut_clip)
    assert "frames" in out.lower()


def test_multiple_timestamps_extract_multiple_frames(cut_clip: Path):
    out = _run(cut_clip, "--timestamps", "0.5,1.0,1.5")
    assert "frames" in out.lower()
