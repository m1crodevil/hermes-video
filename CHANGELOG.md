# Changelog

All notable changes to `/watch` are documented here.

## [2.3.0] — 2026-09-12

### Changed
- **Rust-parity single-pass pipeline**. `pipeline.py` replaced by `core.py` aligned with `hermes-video-rs`: download captions, Whisper fallback, timestamp frame extraction, JSON/Markdown report.
- **Agent-driven frame selection**. Removed automatic scene/keyframe/uniform frame engines. Frames are extracted only at `--timestamps` requested by the agent.

### Removed
- `src/watch/cache.py` (~206 lines) — caching logic no longer used.
- `src/watch/language.py` (~93 lines) — unused subtitle language selection helpers.
- `src/watch/models.py` (~610 lines) — replaced by lightweight `watch.output` dataclasses.
- `src/watch/moments.py` (~401 lines) — zero references.
- `src/watch/stats.py` (~386 lines) — zero references.
- `src/watch/frames/dedup.py` and `src/watch/frames/scene.py` — deduplication and scene detection no longer part of the trimmed pipeline.
- `tests/test_models.py`, `tests/test_download.py`, `tests/test_dedup.py`, `tests/test_timestamps.py` — referenced removed modules.
- Scene-detection metadata from `WatchReport` (`scene_boundaries`, `scene_count`).

### Added
- `src/watch/core.py` — single-pass pipeline.
- `src/watch/output.py` — dataclass-based report models.
- `skills/watch/scripts/` now a symlink view into `src/watch/` to eliminate source duplication.
