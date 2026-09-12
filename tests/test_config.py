"""Configuration tests."""
from __future__ import annotations

from watch import config


def test_get_config_keys():
    cfg = config.get_config()
    assert "config_file" in cfg


def test_watch_config_defaults():
    cfg = config.WatchConfig(source="https://example.com/video.mp4")
    assert cfg.source == "https://example.com/video.mp4"
    assert cfg.resolution == 512
    assert cfg.output == "both"
