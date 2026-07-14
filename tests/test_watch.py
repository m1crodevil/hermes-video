"""End-to-end routing of --detail through the watch pipeline on a local clip."""
from __future__ import annotations

import io
import contextlib
import os
import sys
from pathlib import Path

# src/ is added to path by conftest.py
from watch.pipeline import main as watch_main


def _run(clip: Path, *args: str, env_extra: dict | None = None) -> str:
    """Run the watch CLI by calling main() directly with overridden argv."""
    old_argv = sys.argv
    try:
        sys.argv = ["watch", str(clip), "--no-whisper", *args]
        # Capture stdout
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


def test_efficient_uses_keyframe_engine(cut_clip: Path):
    out = _run(cut_clip, "--detail", "efficient")
    assert "keyframe" in out.lower()
    assert "efficient" in out.lower()


def test_balanced_uses_scene_engine(cut_clip: Path):
    out = _run(cut_clip, "--detail", "balanced")
    assert "scene" in out.lower()
    assert "balanced" in out.lower()


def test_token_burner_uses_scene_engine(cut_clip: Path):
    out = _run(cut_clip, "--detail", "token-burner")
    assert "scene" in out.lower()


def test_transcript_skips_frames(cut_clip: Path):
    out = _run(cut_clip, "--detail", "transcript")
    assert "frame_0000.jpg" not in out


def test_flag_overrides_env(cut_clip: Path, monkeypatch):
    monkeypatch.setenv("WATCH_DETAIL", "balanced")
    out = _run(cut_clip, "--detail", "efficient")
    assert "keyframe" in out.lower()


def test_default_is_balanced(cut_clip: Path, monkeypatch):
    monkeypatch.delenv("WATCH_DETAIL", raising=False)
    out = _run(cut_clip)
    assert "balanced" in out.lower()
    assert "scene" in out.lower()


def test_timestamps_add_cue_frames_to_detail(cut_clip: Path):
    out = _run(cut_clip, "--detail", "balanced", "--timestamps", "1,3")
    assert "transcript-cue" in out
    assert "scene-change" in out  # detail frames still present (additive)


def test_timestamps_with_transcript_detail_is_cue_only(cut_clip: Path):
    out = _run(cut_clip, "--detail", "transcript", "--timestamps", "1,3")
    assert "transcript-cue" in out
    assert "scene-change" not in out
    assert "keyframe" not in out


def _frame_lines(out: str) -> int:
    return sum(1 for line in out.splitlines() if "frame_" in line and "|" in line)


def test_dedup_collapses_static_by_default(static_clip: Path):
    out = _run(static_clip)  # solid blue → identical frames collapse to one
    assert "near-duplicate" in out
    assert _frame_lines(out) == 1


def test_no_dedup_preserves_static_frames(static_clip: Path):
    out = _run(static_clip, "--no-dedup")
    assert "near-duplicate" not in out
    assert _frame_lines(out) > 1
