"""Comprehensive tests for skills/watch/scripts/env.py.

Tests load_env_file, get_env, get_api_key, and edge cases.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.env import load_env_file, get_env, get_api_key, DEFAULT_CONFIG_FILE, DEFAULT_CONFIG_DIR
from scripts.errors import ConfigError


# ---------------------------------------------------------------------------
# load_env_file
# ---------------------------------------------------------------------------

class TestLoadEnvFile:
    """Test .env file parsing with various formats."""

    def test_basic_key_value(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2")
        result = load_env_file(env_file)
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_empty_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("")
        result = load_env_file(env_file)
        assert result == {}

    def test_comments_ignored(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nKEY=value\n# Another comment")
        result = load_env_file(env_file)
        assert result == {"KEY": "value"}

    def test_blank_lines_ignored(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("A=1\n\n\nB=2\n")
        result = load_env_file(env_file)
        assert result == {"A": "1", "B": "2"}

    def test_double_quoted_value(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="hello world"')
        result = load_env_file(env_file)
        assert result == {"KEY": "hello world"}

    def test_single_quoted_value(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY='hello world'")
        result = load_env_file(env_file)
        assert result == {"KEY": "hello world"}

    def test_inline_comment(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value # this is a comment")
        result = load_env_file(env_file)
        assert result == {"KEY": "value"}

    def test_inline_comment_with_tab(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value\t# comment")
        result = load_env_file(env_file)
        assert result == {"KEY": "value"}

    def test_no_equals_line_skipped(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("NOEQUALSSIGN\nKEY=value")
        result = load_env_file(env_file)
        assert result == {"KEY": "value"}

    def test_whitespace_around_key(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("  KEY  =  value  ")
        result = load_env_file(env_file)
        assert result == {"KEY": "value"}

    def test_nonexistent_file_returns_empty(self) -> None:
        result = load_env_file(Path("/nonexistent/.env"))
        assert result == {}

    def test_nonexistent_file_required_raises(self) -> None:
        with pytest.raises(ConfigError, match="Config file not found"):
            load_env_file(Path("/nonexistent/.env"), required=True)

    def test_default_path_when_none(self) -> None:
        """When path is None, uses DEFAULT_CONFIG_FILE."""
        result = load_env_file(None)
        assert isinstance(result, dict)

    def test_value_with_equals_sign(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value=with=equals")
        result = load_env_file(env_file)
        assert result == {"KEY": "value=with=equals"}

    def test_hash_in_value_without_space(self, tmp_path: Path) -> None:
        """Hash without preceding space is NOT treated as inline comment."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=value#no_space")
        result = load_env_file(env_file)
        assert result == {"KEY": "value#no_space"}

    def test_quoted_value_with_hash(self, tmp_path: Path) -> None:
        """Inside quotes, hash is part of the value."""
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="val#ue"')
        result = load_env_file(env_file)
        assert result == {"KEY": "val#ue"}

    def test_multiple_equal_signs(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=a=b=c")
        result = load_env_file(env_file)
        assert result["KEY"] == "a=b=c"


# ---------------------------------------------------------------------------
# get_env
# ---------------------------------------------------------------------------

class TestGetEnv:
    """Test environment variable resolution with fallback chain."""

    def test_from_os_environ(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TEST_GET_ENV_VAR", "from_env")
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_GET_ENV_VAR=from_file")
        result = get_env("TEST_GET_ENV_VAR", env_file=env_file)
        assert result == "from_env"

    def test_from_env_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("TEST_GET_ENV_VAR", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_GET_ENV_VAR=from_file")
        result = get_env("TEST_GET_ENV_VAR", env_file=env_file)
        assert result == "from_file"

    def test_from_default(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("TEST_GET_ENV_VAR", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("")
        result = get_env("TEST_GET_ENV_VAR", default="default_val", env_file=env_file)
        assert result == "default_val"

    def test_not_found_returns_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("TEST_GET_ENV_VAR", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("")
        result = get_env("TEST_GET_ENV_VAR", env_file=env_file)
        assert result is None

    def test_required_not_found_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("TEST_GET_ENV_VAR", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("")
        with pytest.raises(ConfigError, match="Required environment variable not found"):
            get_env("TEST_GET_ENV_VAR", required=True, env_file=env_file)

    def test_os_environ_stripped(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TEST_GET_ENV_VAR", "  value  ")
        env_file = tmp_path / ".env"
        env_file.write_text("")
        result = get_env("TEST_GET_ENV_VAR", env_file=env_file)
        assert result == "value"

    def test_empty_os_environ_falls_through(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Empty string in os.environ should fall through to file/default."""
        monkeypatch.setenv("TEST_GET_ENV_VAR", "")
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_GET_ENV_VAR=file_value")
        result = get_env("TEST_GET_ENV_VAR", env_file=env_file)
        assert result == "file_value"

    def test_priority_os_over_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("TEST_GET_ENV_VAR", "os_val")
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_GET_ENV_VAR=file_val")
        result = get_env("TEST_GET_ENV_VAR", env_file=env_file)
        assert result == "os_val"


# ---------------------------------------------------------------------------
# get_api_key
# ---------------------------------------------------------------------------

class TestGetApiKey:
    """Test API key retrieval with validation.

    Note: get_api_key() only accepts (name, required) — no env_file param.
    We use monkeypatch to control the env var directly.
    """

    def test_valid_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_API_KEY", "test-key-12345678")
        result = get_api_key("TEST_API_KEY")
        assert result == "test-key-12345678"

    def test_key_too_short_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_API_KEY", "short")
        with pytest.raises(ConfigError, match="appears invalid \\(too short\\)"):
            get_api_key("TEST_API_KEY")

    def test_key_with_spaces_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_API_KEY", "key with spaces")
        with pytest.raises(ConfigError, match="appears invalid \\(contains spaces\\)"):
            get_api_key("TEST_API_KEY")

    def test_key_not_found_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TEST_API_KEY", raising=False)
        result = get_api_key("TEST_API_KEY")
        assert result is None

    def test_key_not_found_required_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TEST_API_KEY", raising=False)
        with pytest.raises(ConfigError, match="Required environment variable not found"):
            get_api_key("TEST_API_KEY", required=True)

    def test_exactly_10_chars_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_API_KEY", "1234567890")  # exactly 10 chars
        result = get_api_key("TEST_API_KEY")
        assert result == "1234567890"

    def test_9_chars_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_API_KEY", "123456789")  # 9 chars
        with pytest.raises(ConfigError, match="too short"):
            get_api_key("TEST_API_KEY")

    def test_valid_long_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_API_KEY", "sk-1234567890abcdef1234567890abcdef")
        result = get_api_key("TEST_API_KEY")
        assert result == "sk-1234567890abcdef1234567890abcdef"


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

class TestModuleConstants:
    """Verify module-level constants are set correctly."""

    def test_default_config_dir(self) -> None:
        assert ".config" in str(DEFAULT_CONFIG_DIR)
        assert "watch" in str(DEFAULT_CONFIG_DIR)

    def test_default_config_file(self) -> None:
        assert DEFAULT_CONFIG_FILE.name == ".env"
        assert DEFAULT_CONFIG_DIR in DEFAULT_CONFIG_FILE.parents
