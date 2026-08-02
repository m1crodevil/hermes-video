"""yt-dlp argv construction for download.py.

Regression guard: ``--sub-langs all`` makes yt-dlp fetch YouTube's hundreds of
auto-translated caption tracks, which can take minutes and stalls before the
video download even starts. We only support English, so the request must stay
bounded to the English-only pattern.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest

from watch import download

URL = "https://www.youtube.com/watch?v=rlOpbu3Enkw"

def _capture_argv(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Stub subprocess.run inside download.py and record every argv."""
    calls: list[list[str]] = []

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return _Result()

    monkeypatch.setattr(download.subprocess, "run", fake_run)
    return calls


def _sub_langs(argv: list[str]) -> str:
    idx = argv.index("--sub-langs")
    return argv[idx + 1]


def _assert_english_only(langs: str) -> None:
    tokens = langs.split(",")
    assert "all" not in tokens, f"sub-langs must not request all languages, got {langs!r}"
    assert all(t.startswith("en") for t in tokens), f"sub-langs must be English-only, got {langs!r}"


def test_fetch_captions_requests_english_only(monkeypatch, tmp_path):
    calls = _capture_argv(monkeypatch)
    download.fetch_captions(URL, tmp_path / "download")
    # The call with --sub-langs is the 3rd subprocess call (after metadata + list_subs)
    sub_lang_calls = [c for c in calls if "--sub-langs" in c]
    assert sub_lang_calls, "expected at least one subprocess call with --sub-langs"
    _assert_english_only(_sub_langs(sub_lang_calls[0]))


def test_download_url_requests_english_only(monkeypatch, tmp_path):
    calls = _capture_argv(monkeypatch)
    # _pick_video returns None with no real file, which raises SystemExit after
    # the yt-dlp argv is already built — that's all we need to inspect.
    with pytest.raises(SystemExit):
        download.download_url(URL, tmp_path / "download")
    _assert_english_only(_sub_langs(calls[0]))


# ── Video cache wiring ─────────────────────────────────────────────────

def _isolate_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point watch.cache at a throwaway dir so tests never touch ~/.cache/watch."""
    from watch import cache
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(cache, "CACHE_DIR", cache_dir)
    return cache


def test_download_url_cache_hit_skips_ytdlp(monkeypatch, tmp_path):
    """A cached video must be copied to the work dir without re-downloading."""
    cache = _isolate_cache(monkeypatch, tmp_path)

    # Seed the cache with a fake video file.
    seeded = tmp_path / "seed.mp4"
    seeded.write_bytes(b"fake-video-bytes")
    cached_path = cache.cache_video(URL, str(seeded), mode="video")
    assert Path(cached_path).exists()

    calls = _capture_argv(monkeypatch)
    result = download.download_url(URL, tmp_path / "out")

    assert result["cached"] is True
    assert result["video_path"] != cached_path  # a copy lives in the work dir
    assert Path(result["video_path"]).exists()
    assert Path(result["video_path"]).read_bytes() == b"fake-video-bytes"
    # Only the cheap metadata fetch may hit subprocess — never a video download.
    video_cmds = [c for c in calls if "-f" in c]
    assert not video_cmds, "cache hit must not invoke yt-dlp video download"


def test_download_url_cache_miss_still_downloads(monkeypatch, tmp_path):
    """No cached copy → yt-dlp video download runs (SystemExit from _pick_video)."""
    _isolate_cache(monkeypatch, tmp_path)
    calls = _capture_argv(monkeypatch)
    with pytest.raises(SystemExit):
        download.download_url(URL, tmp_path / "out")
    assert calls, "expected yt-dlp to be invoked on cache miss"
    assert any("--download-sections" not in c for c in calls)


def test_download_url_no_cache_bypasses_seeded_cache(monkeypatch, tmp_path):
    """no_cache=True must ignore an existing cache entry."""
    cache = _isolate_cache(monkeypatch, tmp_path)
    seeded = tmp_path / "seed.mp4"
    seeded.write_bytes(b"fake")
    cache.cache_video(URL, str(seeded), mode="video")

    calls = _capture_argv(monkeypatch)
    with pytest.raises(SystemExit):
        download.download_url(URL, tmp_path / "out", no_cache=True)
    assert calls, "no_cache must force a fresh download"


def test_cache_mode_separation(monkeypatch, tmp_path):
    """Audio and video caches must never collide under the same URL."""
    cache = _isolate_cache(monkeypatch, tmp_path)
    seeded = tmp_path / "seed.mp4"
    seeded.write_bytes(b"fake")
    cache.cache_video(URL, str(seeded), mode="video")

    assert cache.get_cached_video(URL, mode="video") is not None
    assert cache.get_cached_video(URL, mode="audio") is None, \
        "an audio-only request must never be satisfied by a cached video"
