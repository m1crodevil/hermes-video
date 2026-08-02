"""Centralized configuration for hermes-video."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "watch"
CONFIG_FILE = CONFIG_DIR / ".env"
DEFAULT_CONFIG_FILE = CONFIG_FILE  # backward compat alias
DEFAULT_DETAIL = "balanced"
DEFAULT_MIN_MOMENTS = 50

DETAILS = {"screenshot-first", "transcript", "transcript-moments", "efficient", "balanced", "token-burner"}


@dataclass(frozen=True)
class WatchConfig:
    source: str
    detail: str = DEFAULT_DETAIL
    max_frames: int | None = None
    resolution: int = 512
    fps: float | None = None
    timestamps: list[float] = field(default_factory=list)
    start: float | None = None
    end: float | None = None
    no_whisper: bool = False
    whisper_backend: str | None = None
    no_dedup: bool = False
    keep_video: bool = False
    cookies: bool = False
    output: str = "both"
    auto_moments: bool = False
    max_moments: int = 15
    min_moments: int = DEFAULT_MIN_MOMENTS
    stats: bool = False
    stats_format: str = "telegram"

    @classmethod
    def from_env(cls, source: str, **overrides) -> WatchConfig:
        file_values = _read_env_file()
        detail = (
            overrides.get("detail")
            or os.environ.get("WATCH_DETAIL")
            or file_values.get("WATCH_DETAIL")
            or DEFAULT_DETAIL
        )
        if detail not in DETAILS:
            detail = DEFAULT_DETAIL

        # Compute max_frames from detail if not explicitly overridden
        max_frames = overrides.get("max_frames")
        if max_frames is None and "max_frames" not in overrides:
            max_frames = frame_cap(detail)

        # Resolve min_moments
        min_moments = overrides.get("min_moments")
        if min_moments is None and "min_moments" not in overrides:
            min_moments = int(
                os.environ.get("WATCH_MIN_MOMENTS")
                or file_values.get("WATCH_MIN_MOMENTS")
                or DEFAULT_MIN_MOMENTS
            )

        return cls(source=source, detail=detail, max_frames=max_frames, min_moments=min_moments, **{
            k: v for k, v in overrides.items() if k not in ("detail", "max_frames", "min_moments")
        })


def frame_cap(detail: str) -> int | None:
    """Return the frame cap for a given detail mode, or None for uncapped."""
    return {"efficient": 50, "balanced": 100, "token-burner": None, "transcript": None}.get(detail, 100)


def get_config() -> dict[str, object]:
    """Legacy dict-based config (backward compat)."""
    file_values = _read_env_file()

    detail = (
        os.environ.get("WATCH_DETAIL")
        or file_values.get("WATCH_DETAIL")
        or DEFAULT_DETAIL
    )
    if detail not in DETAILS:
        detail = DEFAULT_DETAIL

    min_moments = int(
        os.environ.get("WATCH_MIN_MOMENTS")
        or file_values.get("WATCH_MIN_MOMENTS")
        or DEFAULT_MIN_MOMENTS
    )

    return {
        "detail": detail,
        "min_moments": min_moments,
        "config_file": str(CONFIG_FILE),
    }


def load_config(source: str, **overrides) -> WatchConfig:
    """Convenience wrapper around WatchConfig.from_env()."""
    return WatchConfig.from_env(source, **overrides)


def get_opencode_config() -> dict[str, str | None]:
    """Return OpenCode API config from environment."""
    return {
        "api_key": os.environ.get("OPENCODE_API_KEY"),
        "model": os.environ.get("OPENCODE_MODEL"),
    }


def _read_env_file(path: Path | None = None) -> dict[str, str]:
    path = path or CONFIG_FILE
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, _, value = raw.partition("=")
            values[key.strip()] = value.strip().strip("\"'")
    except OSError:
        return {}
    return values
