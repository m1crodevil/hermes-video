#!/usr/bin/env python3
"""Secure environment variable loading for watch skill.

Provides .env file parsing with a priority fallback chain:
1. OS environment variables (highest priority)
2. ~/.config/watch/.env file
3. Default values (lowest priority)

Best practices:
- Never hardcode API keys
- Load from environment variables only
- Validate required variables
- Support .env files with proper parsing
"""
from __future__ import annotations

import os
from pathlib import Path

from errors import ConfigError

# Default config file location
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "watch"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / ".env"


def load_env_file(
    path: Path | None = None,
    required: bool = False,
) -> dict[str, str]:
    """Load environment variables from .env file.

    Parses .env files with support for:
    - Comments (lines starting with #)
    - Quoted values ("value" or 'value')
    - Inline comments (value # comment)

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

    for line in lines:
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
        env_file: Custom .env file path (default: ~/.config/watch/.env)

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
    """Get API key securely with validation.

    Uses get_env internally with additional validation:
    - Minimum length: 10 characters
    - No whitespace allowed

    Args:
        name: API key name (e.g., OPENCODE_API_KEY)
        required: Raise error if not found

    Returns:
        API key or None

    Raises:
        ConfigError: If required but not found or key is invalid
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
