#!/usr/bin/env python3
"""Tests for watch Pydantic models."""
import sys
from pathlib import Path

# src/ is added to path by conftest.py

from watch.models import (
    WatchReport, VideoMetadata, Frame, FrameStats,
    TranscriptSegment, WordTiming, FocusRange,
    TranscriptSource, FrameReason, DetailMode,
    build_report, _fmt_time, _fmt_duration,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def test_fmt_time():
    assert _fmt_time(0.0) == "00:00"
    assert _fmt_time(65.0) == "01:05"
    assert _fmt_time(3661.0) == "1:01:01"
    assert _fmt_time(90.5) == "01:30"


def test_fmt_duration():
    assert _fmt_duration(120.0) == "02:00"
    assert _fmt_duration(3661.0) == "1:01:01"
    assert _fmt_duration(59.0) == "00:59"


# ── Enums ────────────────────────────────────────────────────────────────

def test_transcript_source_enum():
    assert TranscriptSource.JSON3.value == "json3"
    assert TranscriptSource.NONE.value == "none"
    # str Enum base → serializes as string
    assert TranscriptSource.JSON3 == "json3"


def test_frame_reason_enum():
    assert FrameReason.SCENE_CHANGE.value == "scene-change"
    assert FrameReason.FIRST_FRAME.value == "first-frame"


def test_detail_mode_enum():
    assert DetailMode.BALANCED.value == "balanced"
    assert DetailMode.TOKEN_BURNER.value == "token-burner"


# ── WordTiming ───────────────────────────────────────────────────────────

def test_word_timing_creation():
    w = WordTiming(word="hello", start=10.5, confidence=0.95)
    assert w.word == "hello"
    assert w.start == 10.5
    assert w.confidence == 0.95


def test_word_timing_from_dict():
    w = WordTiming.model_validate({"word": "test", "start": 1.0, "confidence": 0.8})
    assert w.word == "test"


# ── TranscriptSegment ────────────────────────────────────────────────────

def test_segment_creation():
    s = TranscriptSegment(start=10.0, end=12.0, text="hello world")
    assert s.start == 10.0
    assert s.text == "hello world"
    assert s.words == []


def test_segment_with_words():
    words = [WordTiming(word="hello", start=10.0, confidence=0.95)]
    s = TranscriptSegment(start=10.0, end=12.0, text="hello", words=words)
    assert len(s.words) == 1
    assert s.words[0].word == "hello"


def test_segment_computed_fields():
    s = TranscriptSegment(start=10.0, end=15.0, text="test")
    assert s.start_fmt == "00:10"
    assert s.end_fmt == "00:15"
    assert s.duration == 5.0


# ── Frame ────────────────────────────────────────────────────────────────

def test_frame_creation():
    f = Frame(path="/tmp/test.jpg", timestamp=60.0, reason=FrameReason.SCENE_CHANGE)
    assert f.path == "/tmp/test.jpg"
    assert f.timestamp == 60.0
    assert f.reason == "scene-change"
    assert f.deduped is False


def test_frame_timestamp_fmt():
    f = Frame(path="/tmp/test.jpg", timestamp=90.0, reason=FrameReason.KEYFRAME)
    assert f.timestamp_fmt == "01:30"

    f2 = Frame(path="/tmp/test.jpg", timestamp=3661.0, reason=FrameReason.FIRST_FRAME)
    assert f2.timestamp_fmt == "1:01:01"


def test_frame_deduped():
    f = Frame(path="/tmp/test.jpg", timestamp=10.0, reason=FrameReason.UNIFORM, deduped=True)
    assert f.deduped is True


# ── FrameStats ───────────────────────────────────────────────────────────

def test_frame_stats_creation():
    fs = FrameStats(total_candidates=367, selected=100, deduped=12, engine="scene")
    assert fs.total_candidates == 367
    assert fs.selected == 100
    assert fs.selection_rate == "27%"


def test_frame_stats_zero_candidates():
    fs = FrameStats(total_candidates=0, selected=0, engine="none")
    assert fs.selection_rate == "0%"


# ── VideoMetadata ────────────────────────────────────────────────────────

def test_video_metadata_creation():
    m = VideoMetadata(source="https://youtu.be/test", duration=120.0)
    assert m.source == "https://youtu.be/test"
    assert m.duration == 120.0
    assert m.title is None
    assert m.duration_fmt == "02:00"


def test_video_metadata_resolution():
    m = VideoMetadata(source="test", duration=60.0, width=1920, height=1080, codec="h264")
    assert m.resolution == "1920x1080"

    m2 = VideoMetadata(source="test", duration=60.0)
    assert m2.resolution is None


def test_video_metadata_long_duration():
    m = VideoMetadata(source="test", duration=7200.0)
    assert m.duration_fmt == "2:00:00"


# ── FocusRange ───────────────────────────────────────────────────────────

def test_focus_range_creation():
    fr = FocusRange(start=60.0, end=120.0)
    assert fr.start == 60.0
    assert fr.end == 120.0
    assert fr.duration == 60.0
    assert fr.start_fmt == "01:00"
    assert fr.end_fmt == "02:00"
    assert fr.duration_fmt == "01:00"


# ── WatchReport ──────────────────────────────────────────────────────────

def test_watch_report_minimal():
    report = WatchReport(
        metadata=VideoMetadata(source="test", duration=60.0),
        detail="balanced",
    )
    assert report.metadata.source == "test"
    assert report.frames == []
    assert report.warnings == []


def test_watch_report_json_serialization():
    report = WatchReport(
        metadata=VideoMetadata(source="test", duration=60.0, title="Test Video"),
        detail="balanced",
        transcript_source="json3",
    )
    json_str = report.to_json()
    assert '"source": "test"' in json_str
    assert '"title": "Test Video"' in json_str
    assert '"transcript_source": "json3"' in json_str


def test_watch_report_json_file():
    report = WatchReport(
        metadata=VideoMetadata(source="test", duration=60.0),
        detail="balanced",
    )
    import tempfile
    out = Path(tempfile.mktemp(suffix=".json"))
    written = report.to_json_file(out)
    assert written.exists()
    content = written.read_text()
    assert '"source": "test"' in content
    out.unlink()


def test_watch_report_markdown():
    report = WatchReport(
        metadata=VideoMetadata(source="https://youtu.be/test", duration=120.0, title="My Video", width=1920, height=1080),
        detail="balanced",
        transcript_source="json3",
        frames=[
            Frame(path="/tmp/f.jpg", timestamp=10.0, reason="scene-change"),
        ],
        frame_stats=FrameStats(total_candidates=50, selected=10, deduped=3, engine="scene"),
        transcript_segments=[
            TranscriptSegment(start=10.0, end=12.0, text="hello world"),
        ],
    )
    md = report.to_markdown()

    # Metadata section
    assert "My Video" in md
    assert "02:00" in md
    assert "1920x1080" in md
    assert "balanced" in md

    # Frame section
    assert "50" in md  # candidates
    assert "10" in md  # selected
    assert "scene-change" in md
    assert "frame_0001.jpg" not in md  # fname from path

    # Transcript section
    assert "json3" in md
    assert "hello world" in md


def test_watch_report_with_focus_range():
    report = WatchReport(
        metadata=VideoMetadata(source="test", duration=300.0),
        detail="balanced",
        focus_range=FocusRange(start=60.0, end=120.0),
    )
    md = report.to_markdown()
    assert "01:00" in md
    assert "02:00" in md


def test_watch_report_warnings():
    report = WatchReport(
        metadata=VideoMetadata(source="test", duration=300.0),
        detail="balanced",
        warnings=["Long video — sparse frame coverage"],
    )
    md = report.to_markdown()
    assert "Long video" in md


def test_watch_report_no_transcript():
    report = WatchReport(
        metadata=VideoMetadata(source="test", duration=60.0),
        detail="balanced",
        transcript_source="none",
    )
    md = report.to_markdown()
    assert "No transcript available" in md


# ── build_report() ───────────────────────────────────────────────────────

def test_build_report_basic():
    report = build_report(
        source="https://youtu.be/abc",
        title="Test Video",
        duration=120.0,
        width=1280,
        height=720,
    )
    assert report.metadata.source == "https://youtu.be/abc"
    assert report.metadata.title == "Test Video"
    assert report.metadata.resolution == "1280x720"
    assert report.frames == []


def test_build_report_with_frames():
    raw_frames = [
        {"path": "/tmp/f1.jpg", "timestamp_seconds": 10.0, "reason": "scene-change"},
        {"path": "/tmp/f2.jpg", "timestamp_seconds": 20.0, "reason": "first-frame"},
    ]
    raw_meta = {"engine": "scene", "candidate_count": 50, "selected_count": 2, "deduped_count": 0}

    report = build_report(
        source="test",
        duration=60.0,
        frames=raw_frames,
        frame_meta=raw_meta,
    )
    assert len(report.frames) == 2
    assert report.frames[0].reason == "scene-change"
    assert report.frame_stats.selected == 2


def test_build_report_with_transcript():
    raw_segments = [
        {"start": 10.0, "end": 12.0, "text": "hello", "words": [{"word": "hello", "start": 10.0, "confidence": 0.9}]},
    ]
    report = build_report(
        source="test",
        duration=60.0,
        transcript_source="json3",
        transcript_segments=raw_segments,
    )
    assert len(report.transcript_segments) == 1
    assert report.transcript_segments[0].words[0].word == "hello"


def test_build_report_with_focus():
    report = build_report(
        source="test",
        duration=300.0,
        focus_start=60.0,
        focus_end=120.0,
    )
    assert report.focus_range is not None
    assert report.focus_range.duration == 60.0


if __name__ == "__main__":
    # Quick smoke test
    import traceback
    passed = 0
    failed = 0
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            try:
                func()
                passed += 1
            except Exception as e:
                failed += 1
                print(f"FAIL: {name}: {e}")
                traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
