"""Comprehensive tests for skills/watch/scripts/types.py.

Tests all dataclasses (validation, properties, frozen/slotted behavior),
helper functions, exception hierarchy, and Protocol definitions.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scripts.types import (
    AIClient,
    CueMeta,
    Detail,
    DownloadError,
    DownloadResult,
    FFmpegError,
    Frame,
    FrameExtractor,
    FrameMetadata,
    Seconds,
    Timestamp,
    Transcriber,
    TranscriptSegment,
    VideoDownloader,
    VideoMetadata,
    WatchConfig,
    WatchError,
    WhisperBackend,
    WhisperConfig,
    WatchReport,
    APIError,
    ConfigError,
    TranscriptionError,
    frame_from_dict,
    frame_meta_from_dict,
    download_result_from_dict,
    metadata_from_dict,
    segment_from_dict,
)


# ---------------------------------------------------------------------------
# Type aliases (smoke tests)
# ---------------------------------------------------------------------------

class TestTypeAliases:
    """Verify type aliases resolve to expected types."""

    def test_seconds_is_float(self) -> None:
        s: Seconds = 1.5
        assert isinstance(s, float)

    def test_base64_image_is_str(self) -> None:
        b: str  # Base64Image is str
        assert True

    def test_timestamp_is_str(self) -> None:
        t: Timestamp = "01:23"
        assert isinstance(t, str)

    def test_detail_literal_values(self) -> None:
        for val in ("transcript", "efficient", "balanced", "token-burner"):
            d: Detail = val  # type: ignore[assignment]
            assert val in ("transcript", "efficient", "balanced", "token-burner")

    def test_whisper_backend_literal_values(self) -> None:
        for val in ("groq", "openai"):
            w: WhisperBackend = val  # type: ignore[assignment]
            assert val in ("groq", "openai")


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    """Verify custom exceptions follow expected hierarchy."""

    @pytest.mark.parametrize(
        "exc_cls,exc_name",
        [
            (WatchError, "WatchError"),
            (DownloadError, "DownloadError"),
            (ConfigError, "ConfigError"),
            (TranscriptionError, "TranscriptionError"),
            (FFmpegError, "FFmpegError"),
            (APIError, "APIError"),
        ],
    )
    def test_subclass_of_watch_error(self, exc_cls: type, exc_name: str) -> None:
        assert issubclass(exc_cls, WatchError)

    def test_watch_error_is_exception(self) -> None:
        assert issubclass(WatchError, Exception)

    @pytest.mark.parametrize(
        "exc_cls",
        [DownloadError, ConfigError, TranscriptionError, FFmpegError, APIError],
    )
    def test_catchable_as_watch_error(self, exc_cls: type) -> None:
        with pytest.raises(WatchError):
            raise exc_cls("test")


# ---------------------------------------------------------------------------
# Frame dataclass
# ---------------------------------------------------------------------------

class TestFrame:
    """Test Frame dataclass creation, validation, and frozen behavior."""

    def test_valid_frame(self) -> None:
        frame = Frame(index=0, timestamp_seconds=1.5, path="frame.jpg", reason="test")
        assert frame.index == 0
        assert frame.timestamp_seconds == 1.5
        assert frame.path == "frame.jpg"
        assert frame.reason == "test"

    def test_frame_at_zero(self) -> None:
        frame = Frame(index=0, timestamp_seconds=0.0, path="f.jpg", reason="first-frame")
        assert frame.index == 0
        assert frame.timestamp_seconds == 0.0

    def test_negative_index_raises(self) -> None:
        with pytest.raises(ValueError, match=">= 0"):
            Frame(index=-1, timestamp_seconds=1.5, path="frame.jpg", reason="test")

    def test_negative_timestamp_raises(self) -> None:
        with pytest.raises(ValueError, match=">= 0"):
            Frame(index=0, timestamp_seconds=-0.5, path="frame.jpg", reason="test")

    def test_frozen(self) -> None:
        frame = Frame(index=0, timestamp_seconds=1.0, path="f.jpg", reason="r")
        with pytest.raises(AttributeError):
            frame.index = 1  # type: ignore[misc]

    def test_equality(self) -> None:
        f1 = Frame(index=0, timestamp_seconds=1.0, path="a.jpg", reason="r")
        f2 = Frame(index=0, timestamp_seconds=1.0, path="a.jpg", reason="r")
        assert f1 == f2

    def test_inequality(self) -> None:
        f1 = Frame(index=0, timestamp_seconds=1.0, path="a.jpg", reason="r")
        f2 = Frame(index=1, timestamp_seconds=1.0, path="a.jpg", reason="r")
        assert f1 != f2

    def test_large_index(self) -> None:
        frame = Frame(index=10**9, timestamp_seconds=999999.9, path="big.jpg", reason="r")
        assert frame.index == 10**9

    def test_repr_contains_fields(self) -> None:
        frame = Frame(index=5, timestamp_seconds=2.5, path="x.jpg", reason="scene-change")
        r = repr(frame)
        assert "index=5" in r
        assert "timestamp_seconds=2.5" in r


# ---------------------------------------------------------------------------
# TranscriptSegment dataclass
# ---------------------------------------------------------------------------

class TestTranscriptSegment:
    """Test TranscriptSegment validation and properties."""

    def test_valid_segment(self) -> None:
        seg = TranscriptSegment(start=0.0, end=5.0, text="Hello world")
        assert seg.start == 0.0
        assert seg.end == 5.0
        assert seg.text == "Hello world"

    def test_negative_start_raises(self) -> None:
        with pytest.raises(ValueError, match="start must be >= 0"):
            TranscriptSegment(start=-1.0, end=5.0, text="Hello")

    def test_end_before_start_raises(self) -> None:
        with pytest.raises(ValueError, match="must be >= start"):
            TranscriptSegment(start=10.0, end=5.0, text="Hello")

    def test_end_equals_start_ok(self) -> None:
        seg = TranscriptSegment(start=5.0, end=5.0, text="ok")
        assert seg.start == seg.end

    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            TranscriptSegment(start=0.0, end=1.0, text="")

    def test_whitespace_only_text_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            TranscriptSegment(start=0.0, end=1.0, text="   ")

    def test_frozen(self) -> None:
        seg = TranscriptSegment(start=0.0, end=1.0, text="t")
        with pytest.raises(AttributeError):
            seg.text = "changed"  # type: ignore[misc]

    def test_text_with_newlines(self) -> None:
        seg = TranscriptSegment(start=0.0, end=1.0, text="line1\nline2")
        assert "\n" in seg.text

    def test_equality(self) -> None:
        s1 = TranscriptSegment(start=0.0, end=1.0, text="hello")
        s2 = TranscriptSegment(start=0.0, end=1.0, text="hello")
        assert s1 == s2


# ---------------------------------------------------------------------------
# VideoMetadata dataclass
# ---------------------------------------------------------------------------

class TestVideoMetadata:
    """Test VideoMetadata validation and resolution property."""

    def test_valid_metadata(self) -> None:
        meta = VideoMetadata(
            duration_seconds=120.5, width=1920, height=1080,
            codec="h264", size_bytes=1024000, has_audio=True,
        )
        assert meta.duration_seconds == 120.5
        assert meta.width == 1920
        assert meta.height == 1080
        assert meta.codec == "h264"
        assert meta.has_audio is True

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(ValueError, match="Duration must be >= 0"):
            VideoMetadata(duration_seconds=-1.0, width=100, height=100,
                          codec="h264", size_bytes=0, has_audio=False)

    def test_negative_size_raises(self) -> None:
        with pytest.raises(ValueError, match="Size must be >= 0"):
            VideoMetadata(duration_seconds=10.0, width=100, height=100,
                          codec="h264", size_bytes=-1, has_audio=False)

    def test_zero_width_raises(self) -> None:
        with pytest.raises(ValueError, match="Width must be > 0 or None"):
            VideoMetadata(duration_seconds=10.0, width=0, height=100,
                          codec=None, size_bytes=0, has_audio=False)

    def test_negative_height_raises(self) -> None:
        with pytest.raises(ValueError, match="Height must be > 0 or None"):
            VideoMetadata(duration_seconds=10.0, width=100, height=-1,
                          codec=None, size_bytes=0, has_audio=False)

    def test_none_dimensions_ok(self) -> None:
        meta = VideoMetadata(
            duration_seconds=10.0, width=None, height=None,
            codec=None, size_bytes=0, has_audio=False,
        )
        assert meta.width is None
        assert meta.height is None

    def test_resolution_with_dimensions(self) -> None:
        meta = VideoMetadata(
            duration_seconds=10.0, width=1920, height=1080,
            codec="h264", size_bytes=1000, has_audio=True,
        )
        assert meta.resolution == "1920x1080"

    def test_resolution_without_width(self) -> None:
        meta = VideoMetadata(
            duration_seconds=10.0, width=None, height=1080,
            codec=None, size_bytes=0, has_audio=False,
        )
        assert meta.resolution == "unknown"

    def test_resolution_without_height(self) -> None:
        meta = VideoMetadata(
            duration_seconds=10.0, width=1920, height=None,
            codec=None, size_bytes=0, has_audio=False,
        )
        assert meta.resolution == "unknown"

    def test_resolution_both_none(self) -> None:
        meta = VideoMetadata(
            duration_seconds=10.0, width=None, height=None,
            codec=None, size_bytes=0, has_audio=False,
        )
        assert meta.resolution == "unknown"

    def test_zero_duration_ok(self) -> None:
        meta = VideoMetadata(
            duration_seconds=0.0, width=100, height=100,
            codec="h264", size_bytes=0, has_audio=False,
        )
        assert meta.duration_seconds == 0.0

    def test_frozen(self) -> None:
        meta = VideoMetadata(
            duration_seconds=10.0, width=100, height=100,
            codec="h264", size_bytes=0, has_audio=False,
        )
        with pytest.raises(AttributeError):
            meta.duration_seconds = 20.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FrameMetadata dataclass
# ---------------------------------------------------------------------------

class TestFrameMetadata:
    """Test FrameMetadata validation and defaults."""

    def test_valid_metadata(self) -> None:
        fm = FrameMetadata(engine="scene", candidate_count=20, selected_count=10)
        assert fm.engine == "scene"
        assert fm.candidate_count == 20
        assert fm.selected_count == 10
        assert fm.deduped_count == 0
        assert fm.fallback is False
        assert fm.dropped_out_of_window == 0

    def test_negative_candidate_count_raises(self) -> None:
        with pytest.raises(ValueError, match="candidate_count must be >= 0"):
            FrameMetadata(engine="scene", candidate_count=-1, selected_count=0)

    def test_negative_selected_count_raises(self) -> None:
        with pytest.raises(ValueError, match="selected_count must be >= 0"):
            FrameMetadata(engine="scene", candidate_count=0, selected_count=-1)

    def test_negative_deduped_count_raises(self) -> None:
        with pytest.raises(ValueError, match="deduped_count must be >= 0"):
            FrameMetadata(engine="scene", candidate_count=0, selected_count=0,
                          deduped_count=-1)

    def test_negative_dropped_raises(self) -> None:
        with pytest.raises(ValueError, match="dropped_out_of_window must be >= 0"):
            FrameMetadata(engine="scene", candidate_count=0, selected_count=0,
                          dropped_out_of_window=-1)

    def test_fallback_true(self) -> None:
        fm = FrameMetadata(engine="scene", candidate_count=5, selected_count=2,
                           fallback=True)
        assert fm.fallback is True

    def test_frozen(self) -> None:
        fm = FrameMetadata(engine="scene", candidate_count=1, selected_count=1)
        with pytest.raises(AttributeError):
            fm.engine = "uniform"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DownloadResult dataclass
# ---------------------------------------------------------------------------

class TestDownloadResult:
    """Test DownloadResult validation."""

    def test_valid_result(self) -> None:
        dr = DownloadResult(
            video_path="/tmp/video.mp4", subtitle_path=None,
            info={"source": "test"}, downloaded=True,
        )
        assert dr.video_path == "/tmp/video.mp4"
        assert dr.downloaded is True

    def test_downloaded_true_requires_path(self) -> None:
        with pytest.raises(ValueError, match="downloaded=True requires a video_path"):
            DownloadResult(
                video_path=None, subtitle_path=None,
                info={"source": "test"}, downloaded=True,
            )

    def test_downloaded_false_no_path_ok(self) -> None:
        dr = DownloadResult(
            video_path=None, subtitle_path=None,
            info={"source": "test"}, downloaded=False,
        )
        assert dr.video_path is None

    def test_empty_info_raises(self) -> None:
        with pytest.raises(ValueError, match="info dict must not be empty"):
            DownloadResult(
                video_path="/tmp/v.mp4", subtitle_path=None,
                info={}, downloaded=True,
            )

    def test_frozen(self) -> None:
        dr = DownloadResult(
            video_path="/tmp/v.mp4", subtitle_path=None,
            info={"k": "v"}, downloaded=True,
        )
        with pytest.raises(AttributeError):
            dr.downloaded = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CueMeta dataclass
# ---------------------------------------------------------------------------

class TestCueMeta:
    """Test CueMeta defaults and validation."""

    def test_defaults(self) -> None:
        cm = CueMeta()
        assert cm.engine == "timestamps"
        assert cm.candidate_count == 0
        assert cm.selected_count == 0
        assert cm.dropped_out_of_window == 0
        assert cm.fallback is False

    def test_custom_values(self) -> None:
        cm = CueMeta(engine="custom", candidate_count=10, selected_count=5)
        assert cm.engine == "custom"
        assert cm.candidate_count == 10

    def test_negative_candidate_raises(self) -> None:
        with pytest.raises(ValueError, match="candidate_count must be >= 0"):
            CueMeta(candidate_count=-1)

    def test_negative_selected_raises(self) -> None:
        with pytest.raises(ValueError, match="selected_count must be >= 0"):
            CueMeta(selected_count=-1)

    def test_negative_dropped_raises(self) -> None:
        with pytest.raises(ValueError, match="dropped_out_of_window must be >= 0"):
            CueMeta(dropped_out_of_window=-1)

    def test_frozen(self) -> None:
        cm = CueMeta()
        with pytest.raises(AttributeError):
            cm.engine = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# WhisperConfig dataclass
# ---------------------------------------------------------------------------

class TestWhisperConfig:
    """Test WhisperConfig validation and defaults."""

    def test_valid_config(self) -> None:
        wc = WhisperConfig(backend="groq", api_key="test-key-12345678")
        assert wc.backend == "groq"
        assert wc.api_key == "test-key-12345678"
        assert wc.max_upload_bytes == 24 * 1024 * 1024
        assert wc.max_attempts == 4
        assert wc.max_429_retries == 2

    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(ValueError, match="api_key must not be empty"):
            WhisperConfig(backend="groq", api_key="")

    def test_zero_upload_bytes_raises(self) -> None:
        with pytest.raises(ValueError, match="max_upload_bytes must be > 0"):
            WhisperConfig(backend="groq", api_key="test-key-12345678",
                          max_upload_bytes=0)

    def test_zero_attempts_raises(self) -> None:
        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            WhisperConfig(backend="groq", api_key="test-key-12345678",
                          max_attempts=0)

    def test_openai_backend(self) -> None:
        wc = WhisperConfig(backend="openai", api_key="test-key-12345678")
        assert wc.backend == "openai"

    def test_frozen(self) -> None:
        wc = WhisperConfig(backend="groq", api_key="test-key-12345678")
        with pytest.raises(AttributeError):
            wc.api_key = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# WhisperConfig — edge cases
# ---------------------------------------------------------------------------

class TestWhisperConfigEdge:
    """Edge-case tests for WhisperConfig."""

    def test_min_upload_bytes(self) -> None:
        wc = WhisperConfig(backend="groq", api_key="test-key-12345678",
                           max_upload_bytes=1)
        assert wc.max_upload_bytes == 1

    def test_min_attempts(self) -> None:
        wc = WhisperConfig(backend="groq", api_key="test-key-12345678",
                           max_attempts=1)
        assert wc.max_attempts == 1

    def test_negative_429_retries_ok(self) -> None:
        # max_429_retries has no validation in __post_init__
        wc = WhisperConfig(backend="groq", api_key="test-key-12345678",
                           max_429_retries=-1)
        assert wc.max_429_retries == -1


# ---------------------------------------------------------------------------
# WatchConfig dataclass
# ---------------------------------------------------------------------------

class TestWatchConfig:
    """Test WatchConfig validation, defaults, and work_dir property."""

    def test_valid_config(self) -> None:
        cfg = WatchConfig(source="https://example.com/video.mp4")
        assert cfg.source == "https://example.com/video.mp4"
        assert cfg.detail == "balanced"
        assert cfg.max_frames == 100
        assert cfg.resolution == 512

    def test_empty_source_raises(self) -> None:
        with pytest.raises(ValueError, match="source must not be empty"):
            WatchConfig(source="")

    def test_whitespace_source_raises(self) -> None:
        with pytest.raises(ValueError, match="source must not be empty"):
            WatchConfig(source="   ")

    def test_zero_resolution_raises(self) -> None:
        with pytest.raises(ValueError, match="resolution must be > 0"):
            WatchConfig(source="src", resolution=0)

    def test_negative_resolution_raises(self) -> None:
        with pytest.raises(ValueError, match="resolution must be > 0"):
            WatchConfig(source="src", resolution=-1)

    def test_max_frames_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="max_frames must be >= 1 or None"):
            WatchConfig(source="src", max_frames=0)

    def test_negative_fps_raises(self) -> None:
        with pytest.raises(ValueError, match="fps must be > 0 or None"):
            WatchConfig(source="src", fps=-1.0)

    def test_max_frames_none_ok(self) -> None:
        cfg = WatchConfig(source="src", max_frames=None)
        assert cfg.max_frames is None

    def test_fps_none_ok(self) -> None:
        cfg = WatchConfig(source="src", fps=None)
        assert cfg.fps is None

    def test_work_dir_with_out_dir(self, tmp_path: Path) -> None:
        out = str(tmp_path / "output")
        cfg = WatchConfig(source="src", out_dir=out)
        assert cfg.work_dir == Path(out).expanduser().resolve()

    def test_work_dir_without_out_dir(self) -> None:
        cfg = WatchConfig(source="src")
        wd = cfg.work_dir
        assert isinstance(wd, Path)
        assert wd.exists()

    def test_frozen(self) -> None:
        cfg = WatchConfig(source="src")
        with pytest.raises(AttributeError):
            cfg.source = "other"  # type: ignore[misc]

    def test_all_detail_values(self) -> None:
        for detail in ("transcript", "efficient", "balanced", "token-burner"):
            cfg = WatchConfig(source="src", detail=detail)  # type: ignore[arg-type]
            assert cfg.detail == detail


# ---------------------------------------------------------------------------
# WatchReport dataclass
# ---------------------------------------------------------------------------

class TestWatchReport:
    """Test WatchReport properties and defaults."""

    def _make_report(self, **overrides) -> WatchReport:
        defaults = dict(
            source="https://example.com/video.mp4",
            title="Test Video",
            uploader="Test User",
            duration_seconds=120.0,
            focused=False,
            effective_start=0.0,
            effective_end=120.0,
            effective_duration=120.0,
            detail="balanced",
            metadata=VideoMetadata(
                duration_seconds=120.0, width=1920, height=1080,
                codec="h264", size_bytes=1000000, has_audio=True,
            ),
            frame_metadata=FrameMetadata(
                engine="scene", candidate_count=20, selected_count=10,
            ),
            frames=[],
            cue_frames=[],
            cue_meta=CueMeta(),
            transcript_segments=[],
            transcript_text=None,
            transcript_source=None,
            work_dir=Path(tempfile.mkdtemp()),
        )
        defaults.update(overrides)
        return WatchReport(**defaults)

    def test_has_frames_true(self) -> None:
        frames = [Frame(index=0, timestamp_seconds=0.0, path="f.jpg", reason="r")]
        report = self._make_report(frames=frames)
        assert report.has_frames is True

    def test_has_frames_false_empty(self) -> None:
        report = self._make_report(frames=[])
        assert report.has_frames is False

    def test_has_transcript_true(self) -> None:
        report = self._make_report(transcript_text="Hello world")
        assert report.has_transcript is True

    def test_has_transcript_false_none(self) -> None:
        report = self._make_report(transcript_text=None)
        assert report.has_transcript is False

    def test_has_transcript_false_empty(self) -> None:
        report = self._make_report(transcript_text="")
        assert report.has_transcript is False

    def test_has_transcript_false_whitespace(self) -> None:
        report = self._make_report(transcript_text="   \n  ")
        assert report.has_transcript is False

    def test_total_frames_no_frames(self) -> None:
        report = self._make_report(frames=[], cue_frames=[])
        assert report.total_frames == 0

    def test_total_frames_with_cue_frames(self) -> None:
        frames = [Frame(index=0, timestamp_seconds=0.0, path="a.jpg", reason="r")]
        cue_frames = [Frame(index=1, timestamp_seconds=1.0, path="b.jpg", reason="cue")]
        report = self._make_report(frames=frames, cue_frames=cue_frames)
        assert report.total_frames == 2

    def test_default_labels(self) -> None:
        report = self._make_report()
        assert report.frame_cap_label == "100"
        assert report.engine_label == "scene-aware frames"
        assert report.range_mode == "full"


# ---------------------------------------------------------------------------
# Helper functions — frame_from_dict
# ---------------------------------------------------------------------------

class TestFrameFromDict:
    """Test frame_from_dict helper."""

    def test_basic_conversion(self) -> None:
        d = {"index": 5, "timestamp_seconds": 2.5, "path": "f.jpg", "reason": "scene"}
        frame = frame_from_dict(d)
        assert frame.index == 5
        assert frame.timestamp_seconds == 2.5

    def test_missing_reason_defaults(self) -> None:
        d = {"index": 0, "timestamp_seconds": 0.0, "path": "f.jpg"}
        frame = frame_from_dict(d)
        assert frame.reason == "selected"

    def test_timestamp_coerced_to_float(self) -> None:
        d = {"index": 0, "timestamp_seconds": "3.14", "path": "f.jpg", "reason": "r"}
        frame = frame_from_dict(d)
        assert isinstance(frame.timestamp_seconds, float)
        assert frame.timestamp_seconds == pytest.approx(3.14)


# ---------------------------------------------------------------------------
# Helper functions — segment_from_dict
# ---------------------------------------------------------------------------

class TestSegmentFromDict:
    """Test segment_from_dict helper."""

    def test_basic_conversion(self) -> None:
        d = {"start": 0.0, "end": 5.0, "text": "Hello"}
        seg = segment_from_dict(d)
        assert seg.start == 0.0
        assert seg.end == 5.0
        assert seg.text == "Hello"

    def test_timestamp_coercion(self) -> None:
        d = {"start": "1.5", "end": "3.0", "text": "Hi"}
        seg = segment_from_dict(d)
        assert isinstance(seg.start, float)
        assert seg.start == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# Helper functions — metadata_from_dict
# ---------------------------------------------------------------------------

class TestMetadataFromDict:
    """Test metadata_from_dict helper."""

    def test_full_dict(self) -> None:
        d = {
            "duration_seconds": 60.0,
            "width": 1280,
            "height": 720,
            "codec": "h264",
            "size_bytes": 500000,
            "has_audio": True,
        }
        meta = metadata_from_dict(d)
        assert meta.duration_seconds == 60.0
        assert meta.width == 1280
        assert meta.has_audio is True

    def test_minimal_dict_defaults(self) -> None:
        meta = metadata_from_dict({})
        assert meta.duration_seconds == 0.0
        assert meta.width is None
        assert meta.height is None
        assert meta.codec is None
        assert meta.size_bytes == 0
        assert meta.has_audio is False


# ---------------------------------------------------------------------------
# Helper functions — frame_meta_from_dict
# ---------------------------------------------------------------------------

class TestFrameMetaFromDict:
    """Test frame_meta_from_dict helper."""

    def test_full_dict(self) -> None:
        d = {
            "engine": "scene",
            "candidate_count": 20,
            "selected_count": 10,
            "deduped_count": 3,
            "fallback": True,
            "dropped_out_of_window": 2,
        }
        fm = frame_meta_from_dict(d)
        assert fm.engine == "scene"
        assert fm.candidate_count == 20
        assert fm.fallback is True

    def test_minimal_dict_defaults(self) -> None:
        fm = frame_meta_from_dict({})
        assert fm.engine == "unknown"
        assert fm.candidate_count == 0
        assert fm.selected_count == 0
        assert fm.deduped_count == 0
        assert fm.fallback is False
        assert fm.dropped_out_of_window == 0


# ---------------------------------------------------------------------------
# Helper functions — download_result_from_dict
# ---------------------------------------------------------------------------

class TestDownloadResultFromDict:
    """Test download_result_from_dict helper."""

    def test_full_dict(self) -> None:
        d = {
            "video_path": "/tmp/v.mp4",
            "subtitle_path": "/tmp/v.vtt",
            "info": {"source": "test"},
            "downloaded": True,
        }
        dr = download_result_from_dict(d)
        assert dr.video_path == "/tmp/v.mp4"
        assert dr.downloaded is True

    def test_minimal_dict_defaults(self) -> None:
        # Empty info dict triggers DownloadResult validation error
        with pytest.raises(ValueError, match="info dict must not be empty"):
            download_result_from_dict({})

    def test_empty_info_raises(self) -> None:
        with pytest.raises(ValueError):
            download_result_from_dict({"downloaded": True, "video_path": "/v.mp4"})


# ---------------------------------------------------------------------------
# Protocol structural checks
# ---------------------------------------------------------------------------

class TestProtocols:
    """Verify Protocol classes define the expected interface."""

    def test_video_downloader_has_download(self) -> None:
        assert hasattr(VideoDownloader, "download")

    def test_frame_extractor_has_extract_frames(self) -> None:
        assert hasattr(FrameExtractor, "extract_frames")

    def test_transcriber_has_transcribe(self) -> None:
        assert hasattr(Transcriber, "transcribe")

    def test_ai_client_has_analyse_frames(self) -> None:
        assert hasattr(AIClient, "analyse_frames")
