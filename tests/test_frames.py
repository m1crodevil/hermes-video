"""Tests for frames.py utility functions.

Covers the core helpers used by the watch pipeline: time formatting/parsing,
timestamp list parsing, frame merging, and metadata probing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the scripts directory is importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "watch" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import frames


# ── format_time ──────────────────────────────────────────────────────────────

class TestFormatTime:
    def test_seconds_only(self):
        assert frames.format_time(65) == "01:05"

    def test_hours(self):
        assert frames.format_time(3661) == "1:01:01"

    def test_zero(self):
        assert frames.format_time(0) == "00:00"

    def test_rounds_to_int(self):
        assert frames.format_time(65.4) == "01:05"
        assert frames.format_time(65.5) == "01:06"

    def test_exactly_one_hour(self):
        assert frames.format_time(3600) == "1:00:00"


# ── parse_time ───────────────────────────────────────────────────────────────

class TestParseTime:
    def test_seconds(self):
        assert frames.parse_time("30") == 30.0

    def test_minutes_seconds(self):
        assert frames.parse_time("1:30") == 90.0

    def test_hours_minutes_seconds(self):
        assert frames.parse_time("1:02:03") == 3723.0

    def test_none_returns_none(self):
        assert frames.parse_time(None) is None

    def test_empty_string_returns_none(self):
        assert frames.parse_time("") is None

    def test_passthrough_numeric(self):
        assert frames.parse_time(42) == 42.0
        assert frames.parse_time(3.14) == 3.14

    def test_invalid_raises_system_exit(self):
        with pytest.raises(SystemExit):
            frames.parse_time("not-a-time")


# ── parse_timestamps ─────────────────────────────────────────────────────────

class TestParseTimestamps:
    def test_comma_separated(self):
        result = frames.parse_timestamps("1:30,2:45,10")
        # Result is sorted and deduplicated
        assert result == [10.0, 90.0, 165.0]

    def test_none_returns_empty(self):
        assert frames.parse_timestamps(None) == []

    def test_empty_returns_empty(self):
        assert frames.parse_timestamps("") == []

    def test_deduplication(self):
        result = frames.parse_timestamps("10,10,10")
        assert result == [10.0]

    def test_spaces_around_tokens(self):
        result = frames.parse_timestamps(" 10 , 20 , 30 ")
        assert result == [10.0, 20.0, 30.0]


# ── merge_frames ─────────────────────────────────────────────────────────────

class TestMergeFrames:
    def test_merge_and_reindex(self):
        primary = [
            {"index": 0, "timestamp_seconds": 5.0, "path": "a.jpg", "reason": "scene"},
        ]
        pinned = [
            {"index": 0, "timestamp_seconds": 2.0, "path": "b.jpg", "reason": "cue"},
        ]
        result = frames.merge_frames(primary, pinned)
        assert len(result) == 2
        assert result[0]["timestamp_seconds"] == 2.0
        assert result[0]["index"] == 0
        assert result[1]["timestamp_seconds"] == 5.0
        assert result[1]["index"] == 1

    def test_empty_lists(self):
        assert frames.merge_frames([], []) == []

    def test_primary_only(self):
        primary = [
            {"index": 0, "timestamp_seconds": 1.0, "path": "a.jpg", "reason": "scene"},
        ]
        result = frames.merge_frames(primary, [])
        assert len(result) == 1
        assert result[0]["index"] == 0

    def test_pinned_only(self):
        pinned = [
            {"index": 0, "timestamp_seconds": 1.0, "path": "a.jpg", "reason": "cue"},
        ]
        result = frames.merge_frames([], pinned)
        assert len(result) == 1
        assert result[0]["index"] == 0

    def test_interleaved_ordering(self):
        primary = [
            {"index": 0, "timestamp_seconds": 10.0, "path": "a.jpg", "reason": "scene"},
            {"index": 1, "timestamp_seconds": 30.0, "path": "b.jpg", "reason": "scene"},
        ]
        pinned = [
            {"index": 0, "timestamp_seconds": 20.0, "path": "c.jpg", "reason": "cue"},
        ]
        result = frames.merge_frames(primary, pinned)
        assert len(result) == 3
        ts = [f["timestamp_seconds"] for f in result]
        assert ts == [10.0, 20.0, 30.0]
        assert [f["index"] for f in result] == [0, 1, 2]


# ── get_metadata ─────────────────────────────────────────────────────────────

class TestGetMetadata:
    def test_missing_ffprobe(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda x: None)
        with pytest.raises(SystemExit):
            frames.get_metadata("/nonexistent.mp4")


# ── auto_fps / auto_fps_focus ────────────────────────────────────────────────

class TestAutoFps:
    def test_zero_duration(self):
        fps, count = frames.auto_fps(0)
        assert fps > 0
        assert count >= 1

    def test_short_video(self):
        fps, count = frames.auto_fps(15, max_frames=50)
        assert fps <= frames.MAX_FPS
        assert count <= 50

    def test_long_video(self):
        fps, count = frames.auto_fps(3600, max_frames=100)
        assert fps <= frames.MAX_FPS
        assert count <= 100


class TestAutoFpsFocus:
    def test_zero_duration(self):
        fps, count = frames.auto_fps_focus(0)
        assert fps > 0

    def test_short_range(self):
        fps, count = frames.auto_fps_focus(5, max_frames=50)
        assert fps <= frames.MAX_FPS
        assert count <= 50
