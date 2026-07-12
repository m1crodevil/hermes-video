#!/usr/bin/env python3
"""Tests for watch frame extraction and scene detection optimization."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from frames import (
    adaptive_scene_threshold,
    auto_fps,
    fill_gaps_with_uniform,
    extract_two_pass,
    _clamp_fps,
)


# ── Task 1: adaptive_scene_threshold ────────────────────────────────────

def test_adaptive_scene_threshold_short_video():
    assert adaptive_scene_threshold(30) == 0.25  # 30s video

def test_adaptive_scene_threshold_medium_video():
    assert adaptive_scene_threshold(300) == 0.22  # 5 min

def test_adaptive_scene_threshold_default_video():
    assert adaptive_scene_threshold(600) == 0.20  # 10 min

def test_adaptive_scene_threshold_long_video():
    assert adaptive_scene_threshold(1800) == 0.17  # 30 min

def test_adaptive_scene_threshold_very_long_video():
    assert adaptive_scene_threshold(5400) == 0.12  # 90 min

def test_adaptive_scene_threshold_bounds():
    # All values should be between 0.10 and 0.30
    for duration in [10, 60, 300, 600, 1800, 3600, 7200]:
        threshold = adaptive_scene_threshold(duration)
        assert 0.10 <= threshold <= 0.30, f"Threshold {threshold} out of bounds for duration {duration}s"

def test_adaptive_scene_threshold_monotonic():
    # Thresholds should generally decrease (or stay same) as duration increases
    durations = [30, 120, 300, 600, 1800, 3600, 7200]
    thresholds = [adaptive_scene_threshold(d) for d in durations]
    for i in range(1, len(thresholds)):
        assert thresholds[i] <= thresholds[i-1], (
            f"Threshold increased from {thresholds[i-1]} to {thresholds[i]} "
            f"when duration went from {durations[i-1]}s to {durations[i]}s"
        )


# ── Task 3: auto_fps minimum density ────────────────────────────────────

def test_auto_fps_minimum_density_long_video():
    fps, target = auto_fps(3600, max_frames=100)  # 60 min video
    # Should have at least 1 frame per 60 seconds = 60 frames minimum
    assert target >= 60
    assert fps >= 1.0 / 60.0

def test_auto_fps_minimum_density_15min():
    fps, target = auto_fps(900, max_frames=100)  # 15 min video
    # Should have at least 1 frame per 60 seconds
    assert target >= 15  # 900/60 = 15 frames
    assert fps >= 1.0 / 60.0

def test_auto_fps_short_video_no_minimum():
    fps, target = auto_fps(30, max_frames=100)  # 30s video
    # Short videos don't need minimum density
    assert target <= 30

def test_auto_fps_zero_duration():
    fps, target = auto_fps(0, max_frames=100)
    assert target == 1

def test_auto_fps_clamps_to_max_frames():
    fps, target = auto_fps(3600, max_frames=50)
    assert target <= 50


# ── Task 2: fill_gaps_with_uniform (unit test with mocks) ───────────────

def test_fill_gaps_empty_list():
    """Empty scene list should be returned unchanged."""
    result = fill_gaps_with_uniform([], "test.mp4", Path("/tmp/test"))
    assert result == []

def test_fill_gaps_single_frame():
    """Single frame list should be returned unchanged."""
    frames = [{"index": 0, "timestamp_seconds": 0, "path": "f.jpg", "reason": "scene-change"}]
    result = fill_gaps_with_uniform(frames, "test.mp4", Path("/tmp/test"))
    assert len(result) == 1

def test_fill_gaps_small_gap():
    """Small gap should not trigger fill."""
    frames = [
        {"index": 0, "timestamp_seconds": 0, "path": "f0.jpg", "reason": "scene-change"},
        {"index": 1, "timestamp_seconds": 10, "path": "f1.jpg", "reason": "scene-change"},
    ]
    with patch("frames.get_metadata") as mock_meta:
        mock_meta.return_value = {"duration_seconds": 100}
        result = fill_gaps_with_uniform(
            frames, "test.mp4", Path("/tmp/test"),
            max_gap_seconds=60.0, target_frames=10
        )
    # 10s gap < 60s threshold, no fill
    assert len(result) == 2
    assert all(f["reason"] == "scene-change" for f in result)

def test_fill_gaps_large_gap_extracts_fill_frames():
    """Large gap should trigger fill frame extraction (mocked ffmpeg)."""
    frames = [
        {"index": 0, "timestamp_seconds": 0, "path": "f0.jpg", "reason": "scene-change"},
        {"index": 1, "timestamp_seconds": 180, "path": "f1.jpg", "reason": "scene-change"},
    ]
    with patch("frames.get_metadata") as mock_meta, \
         patch("frames.subprocess.run") as mock_run:
        mock_meta.return_value = {"duration_seconds": 180}
        # Simulate ffmpeg success
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            # Create a fake fill file so Path.exists() returns True
            def side_effect(cmd, **kwargs):
                # Extract the output path from the command
                for i, arg in enumerate(cmd):
                    if arg == str(Path("test.mp4").resolve()):
                        # Output path is the last arg
                        fill_path = Path(cmd[-1])
                        fill_path.parent.mkdir(parents=True, exist_ok=True)
                        fill_path.touch()
                        break
                return MagicMock(returncode=0)
            mock_run.side_effect = side_effect

            result = fill_gaps_with_uniform(
                frames, "test.mp4", out_dir,
                max_gap_seconds=60.0, target_frames=100,
            )
    # 180s gap > 60s threshold, should insert fill frames
    assert len(result) > 2
    assert any(f["reason"] == "gap-fill" for f in result)


# ── Task 4: extract_two_pass (signature test) ───────────────────────────

def test_extract_two_pass_signature():
    """Verify extract_two_pass exists and has the expected signature."""
    import inspect
    sig = inspect.signature(extract_two_pass)
    params = list(sig.parameters.keys())
    assert "video_path" in params
    assert "out_dir" in params
    assert "fps" in params
    assert "target_frames" in params
    assert "resolution" in params
    assert "max_frames" in params
    assert "start_seconds" in params
    assert "end_seconds" in params
    assert "dedup" in params


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
