# Changelog

All notable changes to `/watch` are documented here.

## [2.1.0] — 2026-07-29

### Added
- **Comprehensive analysis workflow** — transcript-first with agent-driven moment selection. Cross-references frames against captions.
- **`screenshot-first` detail mode** — transcript-guided section downloads, fastest for URLs with captions.
- **`transcript-moments` detail mode** (default) — extracts transcript, generates key moments, downloads sections around them.
- **Video caching** (`cache.py`) — SHA256 content hashing + LRU eviction (10GB limit in `~/.cache/watch/`). Cache hit avoids re-downloading.
- **Pipeline tests** (`test_pipeline.py`) — 10 new tests covering pipeline integration, argument parsing, and cache module.

### Changed
- **Restructured to `src/watch/` package layout** — proper Python package with `pyproject.toml`, editable installs.
- **Agent-driven architecture** — binary handles data extraction only, agent handles all intelligence (moment selection, analysis).
- **Two-pass workflow** — run → read report.json → select timestamps → re-run.
- **SKILL.md** rewritten — progressive disclosure, output philosophy alignment with Rust version.
- **README** rewritten — Python-first, no Rust comparisons, comprehensive analysis workflow docs.

### Removed
- `skills/watch/` subdirectory — flattened to `src/watch/`.
- Agent intelligence modules (agent handles moment detection, vision, corrections, synthesis).

## [2.0.0] — 2026-07-25

### Changed
- **Major refactor** — simplified to agent-driven architecture.
- Deleted 6 files (-1509 LOC): `transcript_moments.py`, `batch_vision.py`, `apply_corrections.py`, `vision_verify.py`, `synthesis.py`, `extract_moment_frames.py`.
- Simplified `frames.py` (1039 → 324 LOC), `watch.py` (781 → 485 LOC), `models.py` (609 → 499 LOC).
- Total: -3315 LOC (6687 → 4066, 50% reduction).

## [0.2.0] — 2026-06-29

### Added
- **`--detail` dial** with four modes — `transcript`, `efficient`, `balanced` (default), `token-burner`.
- **Frame deduplication** (default on; `--no-dedup` to disable).
- **Whisper auto-chunking** for audio over 25 MB upload cap.
- **`--timestamps T1,T2,…`** — grab frames at absolute timestamps.
- **`--no-whisper`** — disable transcription entirely.
- pytest suite covering config, dedup, download, fixtures, frames, setup, timestamps, watch, and whisper.

### Changed
- **Restructured into `skills/watch/` package** for cross-harness compatibility.
- `balanced` now full-decodes to detect every scene cut across the whole video.
- `--max-frames` is now an override on top of each mode's default cap.

### Fixed
- Non-Claude installs (`npx skills add`) were dead on arrival.

## [0.1.3] — 2026-05-09

### Fixed
- Windows: `video.info.json` read as UTF-8 (#4).
- `download.py` logs info.json parse failures to stderr.

### Security
- Hardened subprocess argv against option injection (#2).

## [0.1.2] — 2026-04-24

### Fixed
- Windows console crash from emoji in long-video warning.
- `setup.py` prints `winget`/`pip` install commands on Windows.

## [0.1.1] — 2026-04-24

### Fixed
- Added `commands/watch.md` shim for Claude Code plugin slash command.
- `scripts/build-skill.sh` strips `commands/` from `.skill` bundle.

## [0.1.0] — 2026-04-24

Initial marketplace release.
