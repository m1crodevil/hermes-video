# claude-video Refactoring Plan — Python Best Practices

> **Based on:** Python 3.11+ official docs, pytest best practices, security guidelines

**Goal:** Refactor claude-video to follow Python best practices while adding MiMo V2.5 support.

**Principles:**
1. **Type safety** — Use TypeAlias, Protocol, dataclasses
2. **Error handling** — Explicit exceptions, graceful degradation
3. **Security** — Environment variables only, HTTPS only
4. **Testing** — pytest with tmp_path, monkeypatch, parametrize
5. **Documentation** — Docstrings, type hints, comments

---

## Phase 1: Type System Foundation

### Task 1.1: Create Type Definitions

**Objective:** Define type aliases and protocols for the codebase

**Files:**
- Create: `skills/watch/scripts/types.py`

**Implementation:**

```python
#!/usr/bin/env python3
"""Type definitions for claude-video.

Based on Python 3.11+ typing best practices:
- TypeAlias for complex types
- Protocol for structural subtyping
- dataclass for immutable data structures
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeAlias


# --- Type Aliases (PEP 613) ---

# Seconds as float
Seconds: TypeAlias = float

# Base64-encoded image data
Base64Image: TypeAlias = str

# Timestamp string (SS, MM:SS, HH:MM:SS)
Timestamp: TypeAlias = str

# Frame reason type
FrameReason: TypeAlias = str

# Detail mode
DetailMode: TypeAlias = str


# --- Data Classes (PEP 557) ---

@dataclass(frozen=True, slots=True)
class Frame:
    """Represents an extracted video frame.
    
    Attributes:
        index: Frame index in sequence
        timestamp_seconds: Absolute timestamp in source video
        path: Path to JPEG file
        reason: Why this frame was selected
    """
    index: int
    timestamp_seconds: Seconds
    path: Path
    reason: FrameReason

    def __post_init__(self) -> None:
        """Validate frame data."""
        if self.index < 0:
            raise ValueError(f"Frame index must be non-negative: {self.index}")
        if self.timestamp_seconds < 0:
            raise ValueError(f"Timestamp must be non-negative: {self.timestamp_seconds}")
        if not self.path.exists():
            raise FileNotFoundError(f"Frame file not found: {self.path}")


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """Represents a transcript segment with timing.
    
    Attributes:
        start: Start time in seconds
        end: End time in seconds
        text: Transcribed text
    """
    start: Seconds
    end: Seconds
    text: str

    def __post_init__(self) -> None:
        """Validate segment data."""
        if self.start < 0:
            raise ValueError(f"Start time must be non-negative: {self.start}")
        if self.end < self.start:
            raise ValueError(f"End time ({self.end}) must be >= start time ({self.start})")
        if not self.text.strip():
            raise ValueError("Text cannot be empty")


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Video file metadata.
    
    Attributes:
        duration_seconds: Total duration in seconds
        width: Video width in pixels
        height: Video height in pixels
        codec: Video codec name
        has_audio: Whether video has audio track
    """
    duration_seconds: Seconds
    width: int | None
    height: int | None
    codec: str | None
    has_audio: bool


@dataclass(frozen=True, slots=True)
class FrameMetadata:
    """Frame extraction metadata.
    
    Attributes:
        engine: Extraction engine used
        candidate_count: Total candidates found
        selected_count: Frames selected after sampling
        deduped_count: Near-duplicates dropped
        fallback: Whether uniform fallback was used
    """
    engine: str
    candidate_count: int
    selected_count: int
    deduped_count: int = 0
    fallback: bool = False


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Result of video download operation.
    
    Attributes:
        video_path: Path to downloaded video
        subtitle_path: Path to VTT subtitles
        info: Video info dictionary
        downloaded: Whether video was downloaded
    """
    video_path: Path | None
    subtitle_path: Path | None
    info: dict[str, Any]
    downloaded: bool


# --- Protocols (PEP 544) ---

class VideoDownloader(Protocol):
    """Protocol for video download implementations."""
    
    def download(
        self,
        source: str,
        out_dir: Path,
        audio_only: bool = False,
    ) -> DownloadResult:
        """Download video or resolve local file.
        
        Args:
            source: Video URL or local path
            out_dir: Output directory
            audio_only: Download audio only
            
        Returns:
            Download result with paths and metadata
        """
        ...


class FrameExtractor(Protocol):
    """Protocol for frame extraction implementations."""
    
    def extract(
        self,
        video_path: Path,
        out_dir: Path,
        fps: float,
        resolution: int,
        max_frames: int | None,
        start_seconds: Seconds | None,
        end_seconds: Seconds | None,
    ) -> tuple[list[Frame], FrameMetadata]:
        """Extract frames from video.
        
        Args:
            video_path: Path to video file
            out_dir: Output directory for frames
            fps: Frames per second
            resolution: Frame width in pixels
            max_frames: Maximum frames to extract
            start_seconds: Start time (None for beginning)
            end_seconds: End time (None for end)
            
        Returns:
            Tuple of (frames, metadata)
        """
        ...


class Transcriber(Protocol):
    """Protocol for transcription implementations."""
    
    def transcribe(
        self,
        video_path: Path,
        audio_out: Path,
    ) -> tuple[list[TranscriptSegment], str]:
        """Transcribe video audio.
        
        Args:
            video_path: Path to video file
            audio_out: Path for audio output
            
        Returns:
            Tuple of (segments, backend_used)
        """
        ...


class AIClient(Protocol):
    """Protocol for AI model client implementations."""
    
    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Send chat completion request.
        
        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            API response dictionary
        """
        ...


# --- Configuration Types ---

@dataclass(frozen=True, slots=True)
class WatchConfig:
    """Watch skill configuration.
    
    Attributes:
        detail: Detail mode (transcript|efficient|balanced|token-burner)
        config_file: Path to config file
        opencode_api_key: OpenCode Zen API key
        opencode_model: MiMo model identifier
    """
    detail: DetailMode = "balanced"
    config_file: Path = field(default_factory=lambda: Path("~/.config/watch/.env"))
    opencode_api_key: str | None = None
    opencode_model: str = "mimo-v2.5-free"


# --- Exception Types ---

class WatchError(Exception):
    """Base exception for watch skill."""
    pass


class DownloadError(WatchError):
    """Video download failed."""
    pass


class ExtractionError(WatchError):
    """Frame extraction failed."""
    pass


class TranscriptionError(WatchError):
    """Transcription failed."""
    pass


class APIError(WatchError):
    """API request failed."""
    pass


class ConfigError(WatchError):
    """Configuration error."""
    pass
```

**Step 2: Commit**

```bash
git add skills/watch/scripts/types.py
git commit -m "refactor: add type definitions with TypeAlias, Protocol, dataclass

- Frame, TranscriptSegment, VideoMetadata dataclasses (frozen, slots)
- VideoDownloader, FrameExtractor, Transcriber, AIClient protocols
- WatchConfig dataclass for configuration
- Custom exception hierarchy (WatchError base)
- Based on Python 3.11+ best practices"
```

---

### Task 1.2: Update Existing Modules with Type Hints

**Objective:** Add type hints to existing functions

**Files:**
- Modify: `skills/watch/scripts/download.py`
- Modify: `skills/watch/scripts/frames.py`
- Modify: `skills/watch/scripts/transcribe.py`
- Modify: `skills/watch/scripts/config.py`

**Step 1: Add type hints to download.py**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from .types import DownloadResult, Seconds


def is_url(source: str) -> bool:
    """Check if source is a URL.
    
    Args:
        source: String to check
        
    Returns:
        True if source is a valid HTTP/HTTPS URL
    """
    ...


def resolve_local(path: str) -> DownloadResult:
    """Resolve a local file path.
    
    Args:
        path: Local file path
        
    Returns:
        DownloadResult with resolved path
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    ...


def download(
    source: str,
    out_dir: Path,
    audio_only: bool = False,
) -> DownloadResult:
    """Download video or resolve local file.
    
    Args:
        source: Video URL or local path
        out_dir: Output directory
        audio_only: Download audio only
        
    Returns:
        DownloadResult with paths and metadata
    """
    ...
```

**Step 2: Add type hints to frames.py**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from .types import Frame, FrameMetadata, Seconds, VideoMetadata


def get_metadata(video_path: Path) -> VideoMetadata:
    """Get video metadata via ffprobe.
    
    Args:
        video_path: Path to video file
        
    Returns:
        VideoMetadata with file information
        
    Raises:
        ExtractionError: If ffprobe fails
    """
    ...


def extract(
    video_path: Path,
    out_dir: Path,
    fps: float,
    resolution: int = 512,
    max_frames: int = 100,
    start_seconds: Seconds | None = None,
    end_seconds: Seconds | None = None,
) -> tuple[list[Frame], FrameMetadata]:
    """Extract frames at uniform fps.
    
    Args:
        video_path: Path to video file
        out_dir: Output directory
        fps: Frames per second
        resolution: Frame width in pixels
        max_frames: Maximum frames to extract
        start_seconds: Start time (None for beginning)
        end_seconds: End time (None for end)
        
    Returns:
        Tuple of (frames, metadata)
        
    Raises:
        ExtractionError: If ffmpeg fails
    """
    ...
```

**Step 3: Commit**

```bash
git add skills/watch/scripts/*.py
git commit -m "refactor: add type hints to all modules

- download.py: Return types, parameter types
- frames.py: Return types, parameter types
- transcribe.py: Return types, parameter types
- config.py: Return types, parameter types
- Based on Python typing best practices"
```

---

## Phase 2: Error Handling

### Task 2.1: Add Custom Exceptions

**Objective:** Implement proper exception hierarchy

**Files:**
- Modify: `skills/watch/scripts/types.py` (already has exceptions)
- Create: `skills/watch/scripts/errors.py`

**Implementation:**

```python
#!/usr/bin/env python3
"""Custom exceptions for claude-video.

Exception hierarchy:
- WatchError (base)
  - DownloadError (video download failures)
  - ExtractionError (frame extraction failures)
  - TranscriptionError (transcription failures)
  - APIError (API request failures)
  - ConfigError (configuration errors)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class WatchError(Exception):
    """Base exception for watch skill.
    
    Attributes:
        message: Error message
        details: Additional error details
    """
    
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        """Format exception for display."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class DownloadError(WatchError):
    """Video download failed.
    
    Attributes:
        source: Video source URL or path
        return_code: Process return code
        stderr: Process stderr output
    """
    
    def __init__(
        self,
        message: str,
        source: str,
        return_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        details = {"source": source}
        if return_code is not None:
            details["return_code"] = return_code
        if stderr:
            details["stderr"] = stderr[:200]  # Truncate long output
        super().__init__(message, details)
        self.source = source
        self.return_code = return_code
        self.stderr = stderr


class ExtractionError(WatchError):
    """Frame extraction failed.
    
    Attributes:
        video_path: Path to video file
        command: Failed command
        return_code: Process return code
        stderr: Process stderr output
    """
    
    def __init__(
        self,
        message: str,
        video_path: Path,
        command: list[str] | None = None,
        return_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        details = {"video_path": str(video_path)}
        if command:
            details["command"] = " ".join(command)
        if return_code is not None:
            details["return_code"] = return_code
        if stderr:
            details["stderr"] = stderr[:200]
        super().__init__(message, details)
        self.video_path = video_path
        self.command = command
        self.return_code = return_code
        self.stderr = stderr


class TranscriptionError(WatchError):
    """Transcription failed.
    
    Attributes:
        backend: Transcription backend (groq/openai)
        api_error: API error message
        chunk_index: Failed chunk index (if applicable)
    """
    
    def __init__(
        self,
        message: str,
        backend: str,
        api_error: str | None = None,
        chunk_index: int | None = None,
    ) -> None:
        details = {"backend": backend}
        if api_error:
            details["api_error"] = api_error[:200]
        if chunk_index is not None:
            details["chunk_index"] = chunk_index
        super().__init__(message, details)
        self.backend = backend
        self.api_error = api_error
        self.chunk_index = chunk_index


class APIError(WatchError):
    """API request failed.
    
    Attributes:
        endpoint: API endpoint URL
        status_code: HTTP status code
        response_body: API response body
    """
    
    def __init__(
        self,
        message: str,
        endpoint: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        details = {"endpoint": endpoint}
        if status_code is not None:
            details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body[:200]
        super().__init__(message, details)
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_body = response_body


class ConfigError(WatchError):
    """Configuration error.
    
    Attributes:
        config_file: Path to config file
        missing_key: Missing configuration key
    """
    
    def __init__(
        self,
        message: str,
        config_file: Path | None = None,
        missing_key: str | None = None,
    ) -> None:
        details = {}
        if config_file:
            details["config_file"] = str(config_file)
        if missing_key:
            details["missing_key"] = missing_key
        super().__init__(message, details)
        self.config_file = config_file
        self.missing_key = missing_key
```

**Step 2: Commit**

```bash
git add skills/watch/scripts/errors.py
git commit -m "refactor: add custom exception hierarchy

- WatchError (base)
- DownloadError (video download failures)
- ExtractionError (frame extraction failures)
- TranscriptionError (transcription failures)
- APIError (API request failures)
- ConfigError (configuration errors)
- All exceptions include context details for debugging"
```

---

### Task 2.2: Update Modules with Proper Error Handling

**Objective:** Replace generic exceptions with custom exceptions

**Files:**
- Modify: `skills/watch/scripts/download.py`
- Modify: `skills/watch/scripts/frames.py`
- Modify: `skills/watch/scripts/whisper.py`

**Example Update (download.py):**

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .errors import DownloadError
from .types import DownloadResult


def download_url(
    url: str,
    out_dir: Path,
    audio_only: bool = False,
) -> DownloadResult:
    """Download video via yt-dlp.
    
    Args:
        url: Video URL
        out_dir: Output directory
        audio_only: Download audio only
        
    Returns:
        DownloadResult with paths and metadata
        
    Raises:
        DownloadError: If download fails
    """
    if shutil.which("yt-dlp") is None:
        raise DownloadError(
            "yt-dlp is not installed",
            source=url,
            details={"install": "brew install yt-dlp"},
        )
    
    out_dir.mkdir(parents=True, exist_ok=True)
    # ... (rest of implementation)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise DownloadError(
            f"yt-dlp failed with exit code {result.returncode}",
            source=url,
            return_code=result.returncode,
            stderr=result.stderr,
        )
    
    video = _pick_video(out_dir)
    if video is None:
        raise DownloadError(
            "yt-dlp did not produce a video file",
            source=url,
            return_code=result.returncode,
            stderr=result.stderr,
        )
    
    # ... (rest of implementation)
```

**Step 2: Commit**

```bash
git add skills/watch/scripts/*.py
git commit -m "refactor: replace generic exceptions with custom exceptions

- download.py: DownloadError with context
- frames.py: ExtractionError with context
- whisper.py: TranscriptionError with context
- All exceptions include debugging details"
```

---

## Phase 3: Security Hardening

### Task 3.1: Create Environment Loader

**Objective:** Secure environment variable loading

**Files:**
- Create: `skills/watch/scripts/env.py`

**Implementation:**

```python
#!/usr/bin/env python3
"""Secure environment variable loading.

Best practices:
- Never hardcode API keys
- Load from environment variables only
- Validate required variables
- Support .env files with proper parsing
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .errors import ConfigError


# Default config file location
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "watch"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / ".env"


def load_env_file(
    path: Path | None = None,
    required: bool = False,
) -> dict[str, str]:
    """Load environment variables from .env file.
    
    Args:
        path: Path to .env file (default: ~/.config/watch/.env)
        required: Raise error if file doesn't exist
        
    Returns:
        Dictionary of environment variables
        
    Raises:
        ConfigError: If file is required but doesn't exist
    """
    if path is None:
        path = DEFAULT_CONFIG_FILE
    
    if not path.exists():
        if required:
            raise ConfigError(
                f"Config file not found: {path}",
                config_file=path,
            )
        return {}
    
    env_vars: dict[str, str] = {}
    
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(
            f"Failed to read config file: {exc}",
            config_file=path,
        ) from exc
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        
        # Parse key=value
        if "=" not in line:
            continue
        
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        
        # Remove quotes
        if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
            value = value[1:-1]
        
        # Remove inline comments
        for j, ch in enumerate(value):
            if ch == "#" and j > 0 and value[j - 1] in " \t":
                value = value[:j].rstrip()
                break
        
        env_vars[key] = value
    
    return env_vars


def get_env(
    name: str,
    default: str | None = None,
    required: bool = False,
    env_file: Path | None = None,
) -> str | None:
    """Get environment variable with fallback to .env file.
    
    Priority:
    1. Environment variable
    2. .env file
    3. Default value
        
    Args:
        name: Environment variable name
        default: Default value if not found
        required: Raise error if not found
        
    Returns:
        Environment variable value or default
        
    Raises:
        ConfigError: If variable is required but not found
    """
    # Check environment first
    value = os.environ.get(name)
    if value:
        return value.strip()
    
    # Check .env file
    env_vars = load_env_file(env_file)
    if name in env_vars:
        return env_vars[name]
    
    # Use default
    if default is not None:
        return default
    
    # Required but not found
    if required:
        raise ConfigError(
            f"Required environment variable not found: {name}",
            missing_key=name,
        )
    
    return None


def get_api_key(
    name: str,
    required: bool = False,
) -> str | None:
    """Get API key securely.
    
    Args:
        name: API key name (e.g., OPENCODE_API_KEY)
        required: Raise error if not found
        
    Returns:
        API key or None
        
    Raises:
        ConfigError: If required but not found
    """
    value = get_env(name, required=required)
    
    # Validate API key format (basic check)
    if value is not None:
        if len(value) < 10:
            raise ConfigError(
                f"API key {name} appears invalid (too short)",
                missing_key=name,
            )
        if " " in value:
            raise ConfigError(
                f"API key {name} appears invalid (contains spaces)",
                missing_key=name,
            )
    
    return value
```

**Step 2: Commit**

```bash
git add skills/watch/scripts/env.py
git commit -m "refactor: add secure environment variable loading

- load_env_file: Parse .env files with comments
- get_env: Priority chain (env > .env file > default)
- get_api_key: Secure API key loading with validation
- ConfigError for missing/invalid configuration
- Based on Python best practices"
```

---

### Task 3.2: Update Config Module

**Objective:** Use new env loader for configuration

**Files:**
- Modify: `skills/watch/scripts/config.py`

**Implementation:**

```python
#!/usr/bin/env python3
"""Configuration management for watch skill.

Uses secure environment loading with fallback chain:
1. Environment variables
2. ~/.config/watch/.env
3. Defaults
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .env import get_env, get_api_key
from .types import WatchConfig


DEFAULT_DETAIL = "balanced"
DETAILS = {"transcript", "efficient", "balanced", "token-burner"}


def get_config() -> WatchConfig:
    """Load configuration with secure defaults.
    
    Returns:
        WatchConfig with loaded values
    """
    detail = get_env("WATCH_DETAIL", default=DEFAULT_DETAIL)
    if detail not in DETAILS:
        detail = DEFAULT_DETAIL
    
    opencode_api_key = get_api_key("OPENCODE_API_KEY", required=False)
    opencode_model = get_env("OPENCODE_MODEL", default="mimo-v2.5-free")
    
    return WatchConfig(
        detail=detail,
        config_file=Path("~/.config/watch/.env"),
        opencode_api_key=opencode_api_key,
        opencode_model=opencode_model,
    )


def frame_cap(detail: str) -> int | None:
    """Get frame cap for detail mode.
    
    Args:
        detail: Detail mode
        
    Returns:
        Frame cap (None for unlimited)
    """
    caps = {
        "efficient": 50,
        "balanced": 100,
        "token-burner": None,
        "transcript": None,
    }
    return caps.get(detail, 100)
```

**Step 3: Commit**

```bash
git add skills/watch/scripts/config.py
git commit -m "refactor: use secure env loader for configuration

- Replace manual .env parsing with env.py
- Use WatchConfig dataclass
- Secure API key loading
- Type-safe configuration"
```

---

## Phase 4: Testing Framework

### Task 4.1: Create Test Fixtures

**Objective:** Comprehensive test fixtures with pytest best practices

**Files:**
- Modify: `tests/conftest.py`

**Implementation:**

```python
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

# Make scripts importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "watch" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Test colors for synthesized clips
COLORS = [
    "red", "green", "blue", "white", "black", "yellow", "cyan",
    "magenta", "gray", "orange", "purple", "brown", "navy", "olive",
]


def _run_ffmpeg(cmd: list[str]) -> None:
    """Run ffmpeg command and raise on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{result.stderr}")


@pytest.fixture(scope="session")
def ffmpeg_installed() -> None:
    """Verify ffmpeg is installed."""
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not installed")


@pytest.fixture(scope="session")
def yt_dlp_installed() -> None:
    """Verify yt-dlp is installed."""
    if subprocess.run(["which", "yt-dlp"], capture_output=True).returncode != 0:
        pytest.skip("yt-dlp not installed")


@pytest.fixture(scope="session")
def cut_clip(ffmpeg_installed: None, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a test clip with multiple scene cuts.
    
    Creates 14 solid-color segments → 14 scene cuts.
    Session-scoped for performance (created once).
    """
    path = tmp_path_factory.mktemp("clips") / "cuts.mp4"
    n = 14
    seg = 0.4
    
    inputs: list[str] = []
    for i in range(n):
        color = COLORS[i % len(COLORS)]
        inputs += ["-f", "lavfi", "-t", str(seg), "-i", f"color=c={color}:s=320x240:r=10"]
    
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
    
    return path


@pytest.fixture(scope="session")
def static_clip(ffmpeg_installed: None, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a static test clip (single color, no cuts).
    
    Session-scoped for performance.
    """
    path = tmp_path_factory.mktemp("clips") / "static.mp4"
    
    _run_ffmpeg([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-t", "3.0", "-i", "color=c=blue:s=320x240:r=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "600",
        str(path),
    ])
    
    return path


@pytest.fixture
def sample_frames(tmp_path: Path) -> list[Path]:
    """Create sample JPEG frames for testing.
    
    Function-scoped for isolation.
    """
    frames = []
    for i in range(5):
        frame_path = tmp_path / f"frame_{i:04d}.jpg"
        # Create minimal JPEG (not valid, but exists)
        frame_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        frames.append(frame_path)
    return frames


@pytest.fixture
def sample_transcript(tmp_path: Path) -> Path:
    """Create sample VTT transcript file.
    
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


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up mock environment variables.
    
    Function-scoped for isolation.
    """
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key-12345678")
    monkeypatch.setenv("OPENCODE_MODEL", "mimo-v2.5-free")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")


@pytest.fixture
def mock_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Mock home directory for config file testing.
    
    Returns:
        Mocked home directory path
    """
    mock_config_dir = tmp_path / ".config" / "watch"
    mock_config_dir.mkdir(parents=True)
    
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    
    return tmp_path
```

**Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "refactor: add comprehensive pytest fixtures

- tmp_path for test isolation
- monkeypatch for mocking
- Session-scoped fixtures for expensive operations
- sample_frames, sample_transcript for testing
- mock_env, mock_home for environment testing
- Based on pytest best practices"
```

---

### Task 4.2: Create Test Suite

**Objective:** Comprehensive test suite for all modules

**Files:**
- Create: `tests/test_types.py`
- Create: `tests/test_env.py`
- Create: `tests/test_config.py`

**Implementation (test_types.py):**

```python
"""Tests for type definitions."""
from __future__ import annotations

import pytest
from pathlib import Path

from scripts.types import (
    Frame,
    TranscriptSegment,
    VideoMetadata,
    FrameMetadata,
    DownloadResult,
    WatchConfig,
    WatchError,
    DownloadError,
    ExtractionError,
)


class TestFrame:
    """Tests for Frame dataclass."""
    
    def test_valid_frame(self, sample_frames: list[Path]) -> None:
        """Test creating a valid frame."""
        frame = Frame(
            index=0,
            timestamp_seconds=1.5,
            path=sample_frames[0],
            reason="scene-change",
        )
        assert frame.index == 0
        assert frame.timestamp_seconds == 1.5
        assert frame.reason == "scene-change"
    
    def test_negative_index_raises(self, sample_frames: list[Path]) -> None:
        """Test that negative index raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            Frame(
                index=-1,
                timestamp_seconds=1.5,
                path=sample_frames[0],
                reason="test",
            )
    
    def test_negative_timestamp_raises(self, sample_frames: list[Path]) -> None:
        """Test that negative timestamp raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            Frame(
                index=0,
                timestamp_seconds=-1.0,
                path=sample_frames[0],
                reason="test",
            )
    
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            Frame(
                index=0,
                timestamp_seconds=1.5,
                path=tmp_path / "nonexistent.jpg",
                reason="test",
            )


class TestTranscriptSegment:
    """Tests for TranscriptSegment dataclass."""
    
    def test_valid_segment(self) -> None:
        """Test creating a valid segment."""
        seg = TranscriptSegment(start=0.0, end=4.5, text="Hello")
        assert seg.start == 0.0
        assert seg.end == 4.5
        assert seg.text == "Hello"
    
    def test_negative_start_raises(self) -> None:
        """Test that negative start raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            TranscriptSegment(start=-1.0, end=4.5, text="Hello")
    
    def test_end_before_start_raises(self) -> None:
        """Test that end < start raises ValueError."""
        with pytest.raises(ValueError, match="must be >= start"):
            TranscriptSegment(start=5.0, end=4.5, text="Hello")
    
    def test_empty_text_raises(self) -> None:
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            TranscriptSegment(start=0.0, end=4.5, text="  ")


class TestExceptions:
    """Tests for exception hierarchy."""
    
    def test_watch_error_is_base(self) -> None:
        """Test that WatchError is base exception."""
        assert issubclass(DownloadError, WatchError)
        assert issubclass(ExtractionError, WatchError)
    
    def test_download_error_includes_source(self) -> None:
        """Test that DownloadError includes source."""
        err = DownloadError("Failed", source="https://example.com")
        assert err.source == "https://example.com"
        assert "source=https://example.com" in str(err)
```

**Implementation (test_env.py):**

```python
"""Tests for environment loading."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.env import load_env_file, get_env, get_api_key
from scripts.errors import ConfigError


class TestLoadEnvFile:
    """Tests for load_env_file function."""
    
    def test_load_existing_file(self, tmp_path: Path) -> None:
        """Test loading an existing .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "KEY1=value1\nKEY2=value2\n# comment\n\nKEY3=value3",
            encoding="utf-8",
        )
        
        result = load_env_file(env_file)
        assert result == {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
    
    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading a nonexistent .env file."""
        result = load_env_file(tmp_path / "nonexistent.env")
        assert result == {}
    
    def test_required_file_missing_raises(self, tmp_path: Path) -> None:
        """Test that required file raises ConfigError."""
        with pytest.raises(ConfigError, match="not found"):
            load_env_file(tmp_path / "nonexistent.env", required=True)
    
    def test_parse_quoted_values(self, tmp_path: Path) -> None:
        """Test parsing quoted values."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            'KEY1="value1"\nKEY2=\'value2\'',
            encoding="utf-8",
        )
        
        result = load_env_file(env_file)
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"
    
    def test_strip_inline_comments(self, tmp_path: Path) -> None:
        """Test stripping inline comments."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "KEY1=value1 # this is a comment",
            encoding="utf-8",
        )
        
        result = load_env_file(env_file)
        assert result["KEY1"] == "value1"


class TestGetEnv:
    """Tests for get_env function."""
    
    def test_env_variable_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that env variable takes priority."""
        monkeypatch.setenv("TEST_KEY", "env_value")
        
        result = get_env("TEST_KEY")
        assert result == "env_value"
    
    def test_default_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default value when not found."""
        monkeypatch.delenv("TEST_KEY", raising=False)
        
        result = get_env("TEST_KEY", default="default_value")
        assert result == "default_value"
    
    def test_required_missing_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that required missing raises ConfigError."""
        monkeypatch.delenv("TEST_KEY", raising=False)
        
        with pytest.raises(ConfigError, match="not found"):
            get_env("TEST_KEY", required=True)


class TestGetApiKey:
    """Tests for get_api_key function."""
    
    def test_valid_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading a valid API key."""
        monkeypatch.setenv("TEST_API_KEY", "sk-1234567890abcdef")
        
        result = get_api_key("TEST_API_KEY")
        assert result == "sk-1234567890abcdef"
    
    def test_too_short_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that too short key raises ConfigError."""
        monkeypatch.setenv("TEST_API_KEY", "short")
        
        with pytest.raises(ConfigError, match="too short"):
            get_api_key("TEST_API_KEY")
    
    def test_spaces_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that key with spaces raises ConfigError."""
        monkeypatch.setenv("TEST_API_KEY", "key with spaces")
        
        with pytest.raises(ConfigError, match="spaces"):
            get_api_key("TEST_API_KEY")
```

**Step 3: Commit**

```bash
git add tests/test_types.py tests/test_env.py tests/test_config.py
git commit -m "refactor: add comprehensive test suite

- test_types.py: Dataclass validation tests
- test_env.py: Environment loading tests
- test_config.py: Configuration tests
- Based on pytest best practices (tmp_path, monkeypatch, parametrize)"
```

---

## Phase 5: Documentation

### Task 5.1: Add Docstrings

**Objective:** Add comprehensive docstrings to all public functions

**Files:**
- Modify: `skills/watch/scripts/*.py`

**Example (download.py):**

```python
"""Video download module.

This module provides functions to download videos using yt-dlp
and resolve local file paths.

Security:
- No hardcoded credentials
- All URLs validated before download
- Temporary files cleaned up automatically

Usage:
    from download import download
    
    result = download("https://youtu.be/abc", Path("/tmp/output"))
    print(result.video_path)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from .errors import DownloadError
from .types import DownloadResult, Seconds


def is_url(source: str) -> bool:
    """Check if source string is a valid HTTP/HTTPS URL.
    
    Args:
        source: String to check
        
    Returns:
        True if source is a valid URL (http:// or https://)
        
    Examples:
        >>> is_url("https://youtu.be/abc")
        True
        >>> is_url("/path/to/video.mp4")
        False
    """
    ...
```

**Step 2: Commit**

```bash
git add skills/watch/scripts/*.py
git commit -m "docs: add comprehensive docstrings

- All public functions documented
- Args, Returns, Raises documented
- Security notes included
- Usage examples where helpful
- Based on Google/NumPy style"
```

---

## Phase 6: Integration

### Task 6.1: Create OpenCode Client

**Objective:** Implement MiMo V2.5 API client

**Files:**
- Create: `skills/watch/scripts/opencode_client.py`
- Create: `tests/test_opencode_client.py`

[See Task 2.1 in Phase 2 for implementation]

---

### Task 6.2: Update watch.py

**Objective:** Add --engine opencode flag

**Files:**
- Modify: `skills/watch/scripts/watch.py`

[See Task 3.1 in Phase 3 for implementation]

---

## Summary

### Refactoring Checklist

- [x] Type system (TypeAlias, Protocol, dataclass)
- [x] Custom exceptions hierarchy
- [x] Secure environment loading
- [x] Comprehensive test fixtures
- [x] Test suite with pytest
- [x] Documentation (docstrings)
- [x] OpenCode client implementation
- [x] Integration with watch.py

### Best Practices Applied

| Practice | Implementation |
|----------|----------------|
| **Type safety** | TypeAlias, Protocol, dataclass with frozen=True |
| **Error handling** | Custom exception hierarchy with context |
| **Security** | Environment variables only, validation |
| **Testing** | pytest with tmp_path, monkeypatch, parametrize |
| **Documentation** | Comprehensive docstrings |
| **Code style** | PEP 8, PEP 484, PEP 557 |

### Python Version

- **Target:** Python 3.11+ (for modern typing features)
- **Compatibility:** 3.8+ with `from __future__ import annotations`

---

**Refactoring plan saved to:** `docs/PLAN-REFACTOR.md`

**Ready to execute!** 🚀
