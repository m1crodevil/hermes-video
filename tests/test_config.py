"""WATCH_DETAIL resolution, frame_cap mapping, and load_config."""
from __future__ import annotations

from watch import config


# ---------------------------------------------------------------------------
# get_config (legacy)
# ---------------------------------------------------------------------------

def test_default_detail_is_balanced(monkeypatch, tmp_path):
    monkeypatch.delenv("WATCH_DETAIL", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "missing.env")
    assert config.get_config()["detail"] == "balanced"


def test_env_overrides_detail(monkeypatch, tmp_path):
    monkeypatch.setenv("WATCH_DETAIL", "efficient")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "missing.env")
    assert config.get_config()["detail"] == "efficient"


def test_invalid_detail_falls_back_to_default(monkeypatch, tmp_path):
    monkeypatch.setenv("WATCH_DETAIL", "bogus")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "missing.env")
    assert config.get_config()["detail"] == "balanced"


def test_get_config_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("WATCH_DETAIL", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "missing.env")
    cfg = config.get_config()
    assert set(cfg) == {"detail", "config_file", "min_moments"}


# ---------------------------------------------------------------------------
# frame_cap
# ---------------------------------------------------------------------------

def test_frame_cap_mapping():
    assert config.frame_cap("efficient") == 50
    assert config.frame_cap("balanced") == 100
    assert config.frame_cap("token-burner") is None
    assert config.frame_cap("transcript") is None
    assert config.frame_cap("anything-else") == 100


# ---------------------------------------------------------------------------
# load_config (new dataclass-based API)
# ---------------------------------------------------------------------------

def test_load_config_returns_watch_config(monkeypatch, tmp_path):
    monkeypatch.delenv("WATCH_DETAIL", raising=False)
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "missing.env")
    cfg = config.load_config("https://example.com/video.mp4")
    assert isinstance(cfg, config.WatchConfig)
    assert cfg.source == "https://example.com/video.mp4"
    assert cfg.detail == "balanced"


def test_load_config_env_detail(monkeypatch, tmp_path):
    monkeypatch.setenv("WATCH_DETAIL", "efficient")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", tmp_path / "missing.env")
    cfg = config.load_config("https://example.com/video.mp4")
    assert cfg.detail == "efficient"
    assert cfg.max_frames == 50


def test_load_config_explicit_detail_overrides_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WATCH_DETAIL", "efficient")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", tmp_path / "missing.env")
    cfg = config.load_config("src", detail="balanced")
    assert cfg.detail == "balanced"
    assert cfg.max_frames == 100


def test_load_config_invalid_detail_falls_back(monkeypatch, tmp_path):
    monkeypatch.delenv("WATCH_DETAIL", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", tmp_path / "missing.env")
    cfg = config.load_config("src", detail="bogus")
    assert cfg.detail == "balanced"


def test_load_config_token_burner_unlimited(monkeypatch, tmp_path):
    monkeypatch.delenv("WATCH_DETAIL", raising=False)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", tmp_path / "missing.env")
    cfg = config.load_config("src", detail="token-burner")
    assert cfg.max_frames is None


# ---------------------------------------------------------------------------
# get_opencode_config
# ---------------------------------------------------------------------------

def test_get_opencode_config_defaults(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    cfg = config.get_opencode_config()
    assert cfg["api_key"] is None
    assert cfg["model"] is None


def test_get_opencode_config_from_env(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key-12345678")
    monkeypatch.setenv("OPENCODE_MODEL", "mimo-v2.5")
    cfg = config.get_opencode_config()
    assert cfg["api_key"] == "test-key-12345678"
    assert cfg["model"] == "mimo-v2.5"
