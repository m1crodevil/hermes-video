"""Shared pytest fixtures for claude-video tests.

Best practices from pytest documentation:
- tmp_path for test isolation
- monkeypatch for mocking
- session-scoped fixtures for expensive operations
- parametrize for multiple test cases
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest

# Make scripts importable (mirrors watch.py's sys.path insert).
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "watch" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Set up scripts as a proper package so relative imports work
# (env.py, opencode_client.py use "from .errors import ...").
import types as _builtin_types  # avoid shadowing by scripts.types
import importlib
import importlib.util

def _init_scripts_package() -> None:
    """Bootstrap the scripts package into sys.modules for test imports."""
    pkg_name = "scripts"
    if pkg_name in sys.modules and hasattr(sys.modules[pkg_name], "__path__"):
        return  # already initialised

    # Create the package module
    pkg = _builtin_types.ModuleType(pkg_name)
    pkg.__path__ = [str(SCRIPTS_DIR)]
    pkg.__package__ = pkg_name
    sys.modules[pkg_name] = pkg

    # Load errors first (no relative imports of its own)
    errors_spec = importlib.util.spec_from_file_location(
        f"{pkg_name}.errors", str(SCRIPTS_DIR / "errors.py"),
        submodule_search_locations=[],
    )
    errors_mod = importlib.util.module_from_spec(errors_spec)
    errors_mod.__package__ = pkg_name
    sys.modules[f"{pkg_name}.errors"] = errors_mod
    errors_spec.loader.exec_module(errors_mod)
    pkg.errors = errors_mod

_init_scripts_package()

# 14 visually distinct fills → 14 abrupt cuts → x264 emits a keyframe per cut.
COLORS = [
    "red", "green", "blue", "white", "black", "yellow", "cyan",
    "magenta", "gray", "orange", "purple", "brown", "navy", "olive",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_ffmpeg(cmd: list[str]) -> None:
    """Run ffmpeg command and raise on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{result.stderr}")


# ---------------------------------------------------------------------------
# Session-scoped: tool availability
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def ffmpeg_installed() -> None:
    """Verify ffmpeg is installed; skip the suite if not."""
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not installed")


@pytest.fixture(scope="session")
def yt_dlp_installed() -> None:
    """Verify yt-dlp is installed; skip the suite if not."""
    if subprocess.run(["which", "yt-dlp"], capture_output=True).returncode != 0:
        pytest.skip("yt-dlp not installed")


# ---------------------------------------------------------------------------
# Session-scoped: synthesized video clips
# ---------------------------------------------------------------------------

def build_cut_clip(
    path: Path,
    n: int = 14,
    seg: float = 0.4,
    size: str = "320x240",
    fps: int = 10,
) -> None:
    """Concatenate ``n`` solid-color segments into one clip with ``n`` cuts.

    Each color change is a hard scene cut, so the scene selector finds ~n-1
    changes.  x264's own scenecut detection is unreliable on flat fills, so we
    force a keyframe at every ``seg`` boundary — giving ~n real keyframes for
    the keyframe engine to find.
    """
    inputs: list[str] = []
    for i in range(n):
        color = COLORS[i % len(COLORS)]
        inputs += ["-f", "lavfi", "-t", str(seg), "-i", f"color=c={color}:s={size}:r={fps}"]
    streams = "".join(f"[{i}:v]" for i in range(n))
    filt = f"{streams}concat=n={n}:v=1:a=0[out]"
    _run_ffmpeg([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        *inputs,
        "-filter_complex", filt, "-map", "[out]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-force_key_frames", f"expr:gte(t,n_forced*{seg})",
        str(path),
    ])


def build_static_clip(
    path: Path,
    duration: float = 3.0,
    size: str = "320x240",
    fps: int = 10,
) -> None:
    """One solid color: 1 keyframe, no scene changes → triggers both fallbacks."""
    _run_ffmpeg([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-t", str(duration), "-i", f"color=c=blue:s={size}:r={fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "600",
        str(path),
    ])


@pytest.fixture(scope="session")
def cut_clip(ffmpeg_installed: None, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a test clip with multiple scene cuts.

    Creates 14 solid-color segments → 14 scene cuts.
    Session-scoped for performance (created once).
    """
    path = tmp_path_factory.mktemp("clips") / "cuts.mp4"
    build_cut_clip(path)
    return path


@pytest.fixture(scope="session")
def static_clip(ffmpeg_installed: None, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a static test clip (single color, no cuts).

    Session-scoped for performance.
    """
    path = tmp_path_factory.mktemp("clips") / "static.mp4"
    build_static_clip(path)
    return path


# ---------------------------------------------------------------------------
# Function-scoped: sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_frames(tmp_path: Path) -> list[Path]:
    """Create 5 sample JPEG frames for testing.

    Function-scoped for isolation — each test gets its own directory.
    """
    frames: list[Path] = []
    for i in range(5):
        frame_path = tmp_path / f"frame_{i:04d}.jpg"
        # Minimal JPEG header + padding — exists on disk for path-based tests.
        frame_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        frames.append(frame_path)
    return frames


@pytest.fixture
def sample_transcript(tmp_path: Path) -> Path:
    """Create a sample VTT transcript file.

    Function-scoped for isolation.
    """
    vtt_path = tmp_path / "transcript.vtt"
    vtt_path.write_text(
        """WEBVTT

00:00:00.000 --> 00:00:04.500
Hello everyone, welcome back.

00:00:04.500 --> 00:00:09.000
Today we're going to talk about video analysis.

00:00:09.000 --> 00:00:13.500
Let's get started with the first example.
""",
        encoding="utf-8",
    )
    return vtt_path


# ---------------------------------------------------------------------------
# Function-scoped: environment mocking
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up mock environment variables.

    Function-scoped for isolation — env vars are restored after each test.
    """
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key-12345678")
    monkeypatch.setenv("OPENCODE_MODEL", "mimo-v2.5-free")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")


@pytest.fixture
def mock_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Mock home directory for config file testing.

    Creates a fake ``~/.config/watch/`` tree inside tmp_path and patches
    ``Path.home`` so code that resolves config via ``Path.home()`` sees it.

    Returns:
        Mocked home directory path
    """
    mock_config_dir = tmp_path / ".config" / "watch"
    mock_config_dir.mkdir(parents=True)

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    return tmp_path
