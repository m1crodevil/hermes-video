"""Tests for pipeline module (src/watch/pipeline.py).

Tests the main entry point, argument parsing, and integration
with download, frames, and transcript modules.
"""
from __future__ import annotations

import io
import contextlib
import json
import sys
from pathlib import Path

import pytest

from watch.pipeline import main as watch_main


def _run(clip: Path, *args: str, out_dir: str | None = None) -> str:
    """Run the watch CLI by calling main() directly with overridden argv."""
    old_argv = sys.argv
    try:
        cmd = ["watch", str(clip), "--no-whisper"]
        if out_dir:
            cmd.extend(["--out-dir", out_dir])
        cmd.extend(args)
        sys.argv = cmd
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


class TestPipelineIntegration:
    """Integration tests for the full pipeline."""
    
    def test_main_returns_zero(self, cut_clip: Path):
        """main() should return 0 on success."""
        out = _run(cut_clip, "--detail", "efficient")
        assert "efficient" in out.lower()
    
    def test_main_creates_report(self, cut_clip: Path, tmp_path: Path):
        """main() should create report output."""
        out_dir = str(tmp_path / "output")
        out = _run(cut_clip, "--detail", "efficient", out_dir=out_dir)
        assert "frame_" in out or "keyframe" in out.lower()
    
    def test_main_transcript_detail(self, cut_clip: Path):
        """main() with transcript detail should skip frame extraction."""
        out = _run(cut_clip, "--detail", "transcript")
        assert "frame_0000.jpg" not in out
    
    def test_main_balanced_detail(self, cut_clip: Path):
        """main() with balanced detail should extract scene frames."""
        out = _run(cut_clip, "--detail", "balanced")
        assert "scene" in out.lower()
        assert "balanced" in out.lower()
    
    def test_main_token_burner_detail(self, cut_clip: Path):
        """main() with token-burner detail should extract many frames."""
        out = _run(cut_clip, "--detail", "token-burner")
        assert "scene" in out.lower()
    
    def test_timestamps_work(self, cut_clip: Path):
        """Timestamps should add cue frames."""
        out = _run(cut_clip, "--detail", "balanced", "--timestamps", "1,3")
        assert "transcript-cue" in out


class TestPipelineArguments:
    """Test argument parsing and validation."""
    
    def test_invalid_source_exits(self):
        """Invalid source should exit with error."""
        old_argv = sys.argv
        try:
            sys.argv = ["watch", "/nonexistent/video.mp4", "--no-whisper"]
            with pytest.raises(SystemExit) as exc_info:
                watch_main()
            assert exc_info.value.code != 0
        finally:
            sys.argv = old_argv


class TestCacheModule:
    """Test video caching functionality."""
    
    def test_cache_roundtrip(self, tmp_path: Path):
        """Cache a file and retrieve it."""
        from watch.cache import cache_video, get_cached_video
        
        # Create a fake video file
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video content")
        
        url = "https://example.com/test.mp4"
        
        # Cache it
        cached_path = cache_video(url, str(video))
        assert Path(cached_path).exists()
        
        # Retrieve it
        retrieved = get_cached_video(url)
        assert retrieved is not None
        assert Path(retrieved).exists()
    
    def test_cache_miss(self):
        """Non-existent URL should return None."""
        from watch.cache import get_cached_video
        
        result = get_cached_video("https://example.com/nonexistent.mp4")
        assert result is None
    
    def test_cache_info(self):
        """cache_info() should return stats dict."""
        from watch.cache import cache_info
        
        info = cache_info()
        assert "count" in info
        assert "total_size" in info
        assert "total_size_human" in info
