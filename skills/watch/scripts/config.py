#!/usr/bin/env python3
"""Shared /watch configuration helpers.

Uses env.py for .env file parsing and types.py dataclasses for structured
configuration.  Provides:

- ``load_config(source)`` — primary entry point, returns a ``WatchConfig``
- ``get_config()`` — legacy helper, still returns a dict for callers that
  haven't migrated yet
- ``frame_cap(detail)`` — derive ``max_frames`` from a detail level
- ``get_opencode_config()`` — OpenCode API key / model from env

When imported as part of a package (``from scripts.config import ...``) the
new ``env`` and ``types`` modules are used directly.  When imported standalone
(e.g. from ``watch.py`` which adds the scripts dir to ``sys.path``), a
minimal inline fallback keeps things working until the full package migration
is complete.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Module-level constants (kept for backward compatibility)
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".config" / "watch"
CONFIG_FILE = CONFIG_DIR / ".env"

DEFAULT_DETAIL: str = "balanced"

DETAILS: set[str] = {"transcript", "efficient", "balanced", "token-burner"}


# ---------------------------------------------------------------------------
# Import helpers from env.py / types.py with graceful fallback
# ---------------------------------------------------------------------------

def _try_import_env():  # noqa: ANN202
    """Import env helpers; fall back to a local shim."""
    try:
        import importlib
        mod = importlib.import_module("env")
        return mod.load_env_file, mod.get_env, mod.get_api_key, mod.DEFAULT_CONFIG_FILE
    except (ImportError, ModuleNotFoundError):
        pass

    # Inline fallback — minimal reimplementation of env.py's public API
    def _inline_load_env_file(path: Path | None = None) -> dict[str, str]:
        path = path or CONFIG_FILE
        if not path.exists():
            return {}
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}
        values: dict[str, str] = {}
        for line in lines:
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, _, val = raw.partition("=")
            val = val.strip()
            if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
                val = val[1:-1]
            else:
                for i, ch in enumerate(val):
                    if ch == "#" and i > 0 and val[i - 1] in " \t":
                        val = val[:i].rstrip()
                        break
            values[key.strip()] = val
        return values

    def _inline_get_env(
        name: str, default: str | None = None, required: bool = False,
    ) -> str | None:
        value = os.environ.get(name)
        if value:
            return value.strip()
        env_vars = _inline_load_env_file()
        if name in env_vars:
            return env_vars[name]
        if default is not None:
            return default
        if required:
            raise RuntimeError(f"Required environment variable not found: {name}")
        return None

    def _inline_get_api_key(name: str, required: bool = False) -> str | None:
        value = _inline_get_env(name, required=required)
        if value is not None:
            if len(value) < 10:
                raise RuntimeError(f"API key {name} appears invalid (too short)")
            if " " in value:
                raise RuntimeError(f"API key {name} appears invalid (contains spaces)")
        return value

    return _inline_load_env_file, _inline_get_env, _inline_get_api_key, CONFIG_FILE


def _try_import_types():  # noqa: ANN202
    """Import WatchConfig and Detail from types.py; fall back to inline."""
    try:
        import importlib
        import importlib.util
        types_path = Path(__file__).resolve().parent / "types.py"
        spec = importlib.util.spec_from_file_location("_watch_types", str(types_path))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.WatchConfig, mod.Detail
    except Exception:  # noqa: BLE001
        pass

    # Inline fallback — mirrors types.py definitions
    Detail = Literal["transcript", "efficient", "balanced", "token-burner"]

    @dataclass(frozen=True, slots=True)
    class WatchConfig:  # type: ignore[no-redef]
        source: str
        detail: str = "balanced"
        max_frames: int | None = 100
        resolution: int = 512
        fps: float | None = None
        timestamps: str | None = None
        start: str | None = None
        end: str | None = None
        out_dir: str | None = None
        no_whisper: bool = False
        whisper_backend: str | None = None
        no_dedup: bool = False
        config_file: str = str(Path.home() / ".config" / "watch" / ".env")

    return WatchConfig, Detail  # type: ignore[return-value]


# Perform imports once at module load
load_env_file, get_env, get_api_key, DEFAULT_CONFIG_FILE = _try_import_env()
WatchConfig, Detail = _try_import_types()


# ---------------------------------------------------------------------------
# OpenCode configuration
# ---------------------------------------------------------------------------

def get_opencode_config() -> dict[str, str | None]:
    """Return OpenCode API key and model from env / .env file.

    Priority for each value:
      1. OS environment variable
      2. ~/.config/watch/.env file
      3. ``None`` (not configured)

    Returns:
        dict with keys ``api_key`` and ``model``.
    """
    api_key = get_api_key("OPENCODE_API_KEY")
    model = get_env("OPENCODE_MODEL")
    return {"api_key": api_key, "model": model}


# ---------------------------------------------------------------------------
# Frame-cap helper
# ---------------------------------------------------------------------------

def frame_cap(detail: str) -> int | None:
    """Return the maximum number of frames for *detail* level.

    * ``efficient``  → 50
    * ``balanced``   → 100
    * ``token-burner`` / ``transcript`` → ``None`` (unlimited)
    * anything else  → 100 (safe default)
    """
    if detail == "efficient":
        return 50
    if detail == "balanced":
        return 100
    if detail == "token-burner":
        return None
    if detail == "transcript":
        return None
    return 100


# ---------------------------------------------------------------------------
# Main entry point — returns a typed dataclass
# ---------------------------------------------------------------------------

def load_config(
    source: str,
    *,
    detail: str | None = None,
    resolution: int = 512,
    fps: float | None = None,
    timestamps: str | None = None,
    start: str | None = None,
    end: str | None = None,
    out_dir: str | None = None,
    no_whisper: bool = False,
    whisper_backend: str | None = None,
    no_dedup: bool = False,
    max_frames: int | None = None,
) -> WatchConfig:
    """Build a :class:`WatchConfig` from env vars + caller overrides.

    Resolution order for *detail* (each level only used when the next is
    ``None``):

    1. Explicit *detail* argument
    2. ``WATCH_DETAIL`` env / .env file
    3. ``DEFAULT_DETAIL`` constant (``"balanced"``)
    """
    # Resolve detail via env chain
    if detail is None:
        detail = get_env("WATCH_DETAIL", default=DEFAULT_DETAIL)
    if detail not in DETAILS:
        detail = DEFAULT_DETAIL

    # Resolve max_frames via frame_cap when caller didn't supply one
    if max_frames is None:
        max_frames = frame_cap(detail)

    return WatchConfig(
        source=source,
        detail=detail,  # type: ignore[arg-type]
        max_frames=max_frames,
        resolution=resolution,
        fps=fps,
        timestamps=timestamps,
        start=start,  # type: ignore[arg-type]
        end=end,  # type: ignore[arg-type]
        out_dir=out_dir,
        no_whisper=no_whisper,
        whisper_backend=whisper_backend,  # type: ignore[arg-type]
        no_dedup=no_dedup,
        config_file=str(DEFAULT_CONFIG_FILE),
    )


# ---------------------------------------------------------------------------
# Legacy dict-based helper (backward compatibility)
# ---------------------------------------------------------------------------

def get_config() -> dict[str, object]:
    """Return a plain dict with ``detail`` and ``config_file`` keys.

    Prefer :func:`load_config` for new code — it returns a fully-typed
    :class:`WatchConfig` dataclass.
    """
    detail = get_env("WATCH_DETAIL", default=DEFAULT_DETAIL)
    if detail not in DETAILS:
        detail = DEFAULT_DETAIL

    return {
        "detail": detail,
        "config_file": str(CONFIG_FILE),
    }


# ---------------------------------------------------------------------------
# read_env_file kept as an alias for backward compat with callers that
# import it from this module directly.
# ---------------------------------------------------------------------------

def read_env_file(path: Path | None = None) -> dict[str, str]:
    """Delegate to :func:`env.load_env_file`.

    Kept for backward compatibility; prefer ``env.load_env_file`` directly.
    """
    return load_env_file(path=path)
