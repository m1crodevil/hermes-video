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


def _run(clip: Path | str, *args: str, out_dir: str | None = None) -> str:
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


# ---------------------------------------------------------------------------
# P2: transcript-moments section downloads
# ---------------------------------------------------------------------------

def _make_section_clip(path: Path, color: str = "red", secs: float = 1) -> Path:
    """Build a tiny solid-color clip to stand in for a yt-dlp section download."""
    import subprocess

    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-t", str(secs), "-i", f"color=c={color}:s=160x120:r=5",
            "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def _write_captions_vtt(path: Path) -> Path:
    """Write a small VTT the pipeline can parse into transcript segments."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\nHello world\n\n"
        "00:00:03.000 --> 00:00:04.000\nSecond segment\n",
        encoding="utf-8",
    )
    return path


class TestTranscriptMomentsSections:
    """P2: transcript-moments re-run should download 2s sections, not the full video."""

    URL = "https://www.youtube.com/watch?v=rlOpbu3Enkw"

    def _prepare(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        section_files: dict[float, Path] | None,
        fallback_video: Path,
    ) -> tuple[Path, list[str]]:
        """Common setup: captions + key_moments.json, mocked network calls.

        Returns (out_dir, calls) where calls records full-video download invocations.
        """
        import watch.pipeline as pipeline

        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        vtt = _write_captions_vtt(tmp_path / "caps" / "video.en.vtt")

        # Key moments the agent would have written on run 1
        (out_dir / "key_moments.json").write_text(
            json.dumps([
                {"timestamp": 1.0, "word": "hello", "reason": "claim"},
                {"timestamp": 3.0, "word": "second", "reason": "topic_transition"},
            ]),
            encoding="utf-8",
        )

        # Mock caption fetch (run 1 already did this; avoid yt-dlp network)
        monkeypatch.setattr(
            pipeline,
            "fetch_captions",
            lambda *a, **k: {
                "subtitle_path": str(vtt),
                "info": {"duration": 10, "title": "test"},
                "downloaded": False,
            },
        )
        monkeypatch.setattr(
            pipeline,
            "is_url",
            lambda *a, **k: True,
        )

        if section_files is not None:
            monkeypatch.setattr(
                pipeline,
                "download_sections_parallel",
                lambda *a, **k: {ts: str(p) for ts, p in section_files.items()},
            )
        else:
            monkeypatch.setattr(
                pipeline,
                "download_sections_parallel",
                lambda *a, **k: {},
            )

        # Fallback full-video download — returns the synthesized clip
        calls: list[str] = []
        monkeypatch.setattr(
            pipeline,
            "download",
            lambda *a, **k: calls.append("download") or {
                "video_path": str(fallback_video),
                "subtitle_path": None,
                "info": {"duration": 10, "title": "test"},
                "downloaded": True,
                "cached": False,
            },
        )
        return out_dir, calls

    def test_sections_succeed_skips_full_download(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        ffmpeg_installed: None,
    ):
        """Sections available → frames come from sections; full video never downloaded."""
        import watch.pipeline as pipeline

        clip1 = _make_section_clip(tmp_path / "sec1.mp4", "red")
        clip2 = _make_section_clip(tmp_path / "sec2.mp4", "blue")
        fallback = _make_section_clip(tmp_path / "fallback.mp4", "green", secs=10)

        out_dir, calls = self._prepare(
            monkeypatch, tmp_path,
            section_files={1.0: clip1, 3.0: clip2},
            fallback_video=fallback,
        )

        out = _run(
            self.URL,
            "--detail", "transcript-moments",
            "--min-moments", "2",
            out_dir=str(out_dir),
        )

        assert "frame_0000.jpg" in out
        assert "frame_0001.jpg" in out
        # Sections path used — no full video download
        assert calls == []
        # Sections cleaned up after extraction
        assert not (out_dir / "sections").exists()

    def test_sections_fail_falls_back_to_full_video(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        ffmpeg_installed: None,
    ):
        """All sections failed → full video fallback still extracts the moments."""
        import watch.pipeline as pipeline

        fallback = _make_section_clip(tmp_path / "fallback.mp4", "green", secs=10)

        out_dir, calls = self._prepare(
            monkeypatch, tmp_path,
            section_files=None,
            fallback_video=fallback,
        )

        out = _run(
            self.URL,
            "--detail", "transcript-moments",
            "--min-moments", "2",
            out_dir=str(out_dir),
        )

        assert "cue_0000.jpg" in out
        # Fallback download happened exactly once
        assert calls == ["download"]


# ---------------------------------------------------------------------------
# P3: auto-generated moments (single-pass, no agent round-trip)
# ---------------------------------------------------------------------------

class TestTranscriptMomentsAuto:
    """P3: first run auto-generates key_moments.json and completes in one pass."""

    URL = "https://www.youtube.com/watch?v=rlOpbu3Enkw"

    def _prepare_captions(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> Path:
        """Mock caption fetch + is_url; returns out_dir (no key_moments.json)."""
        import watch.pipeline as pipeline

        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        vtt = _write_captions_vtt(tmp_path / "caps" / "video.en.vtt")
        monkeypatch.setattr(
            pipeline,
            "fetch_captions",
            lambda *a, **k: {
                "subtitle_path": str(vtt),
                "info": {"duration": 10, "title": "test"},
                "downloaded": False,
            },
        )
        monkeypatch.setattr(pipeline, "is_url", lambda *a, **k: True)
        return out_dir

    def test_first_run_auto_generates_moments_from_transcript(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        ffmpeg_installed: None,
    ):
        """No key_moments.json → moments auto-generated from transcript, sections used."""
        import watch.pipeline as pipeline

        out_dir = self._prepare_captions(monkeypatch, tmp_path)
        assert not (out_dir / "key_moments.json").exists()

        clip1 = _make_section_clip(tmp_path / "sec1.mp4", "red")
        clip2 = _make_section_clip(tmp_path / "sec2.mp4", "blue")
        fallback = _make_section_clip(tmp_path / "fallback.mp4", "green", secs=10)

        calls: list[str] = []
        monkeypatch.setattr(
            pipeline,
            "download_sections_parallel",
            lambda *a, **k: {1.0: str(clip1), 3.0: str(clip2)},
        )
        monkeypatch.setattr(
            pipeline,
            "download",
            lambda *a, **k: calls.append("download") or {
                "video_path": str(fallback),
                "subtitle_path": None,
                "info": {"duration": 10, "title": "test"},
                "downloaded": True,
                "cached": False,
            },
        )

        out = _run(
            self.URL,
            "--detail", "transcript-moments",
            "--min-moments", "2",
            out_dir=str(out_dir),
        )

        # Auto-generated moments written (evenly-spaced transcript starts)
        moments = json.loads((out_dir / "key_moments.json").read_text())
        assert [m["timestamp"] for m in moments] == [1.0, 3.0]
        assert all(m["reason"] == "auto" for m in moments)
        # Prompt still written for optional agent refinement
        assert (out_dir / "moments_prompt.txt").exists()
        # Sections path used — no full video download
        assert calls == []
        assert "frame_0000.jpg" in out
        assert "frame_0001.jpg" in out

    def test_first_run_scene_fallback_no_transcript(
        self,
        tmp_path: Path,
        ffmpeg_installed: None,
    ):
        """Local file without captions → scene detection generates the moments."""
        video = _make_section_clip(tmp_path / "local.mp4", "green", secs=10)
        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True, exist_ok=True)

        out = _run(
            video,
            "--detail", "transcript-moments",
            "--min-moments", "5",
            out_dir=str(out_dir),
        )

        moments = json.loads((out_dir / "key_moments.json").read_text())
        assert moments, "expected scene-detected moments"
        assert all(m["reason"] == "topic_transition" for m in moments)
        assert moments[0]["timestamp"] == 0.0
        assert "cue_0000.jpg" in out
