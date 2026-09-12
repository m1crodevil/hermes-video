"""Centralized configuration for hermes-video."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "watch"
CONFIG_FILE = CONFIG_DIR / ".env"


@dataclass(frozen=True)
class WatchConfig:
    source: str
    resolution: int = 512
    timestamps: list[float] | None = None
    no_whisper: bool = False
    whisper_backend: str | None = None
    keep_video: bool = False
    cookies: bool = False
    output: str = "both"


def get_config() -> dict[str, object]:
    """Return active configuration defaults."""
    return {
        "config_file": str(CONFIG_FILE),
    }
