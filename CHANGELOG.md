# Changelog

All notable changes to `/watch` are documented here.

## [Unreleased] — 2026-08-02

### Added
- **`--no-cache` CLI flag** — bypass the on-disk video cache and always download fresh.
- **Cache wired into the download flow** — `download_url()` now checks `~/.cache/watch/` before invoking yt-dlp (skips re-download on cache hit) and writes fresh downloads back to cache. Audio-only (Whisper) and full-video downloads are keyed separately so they never satisfy each other.
- **Skill bundle sync** — `skills/watch/scripts/` now includes `cache.py` and the cache-aware `download.py` (flat-import variant).
- **`detect_scene_timestamps()`** — ffmpeg scene-change timestamp detection without writing frame files (`frames/scene.py`); used by the transcript-moments auto fallback.

### Changed
- **transcript-moments re-run downloads 2s sections instead of the full video** — `key_moments.json` timestamps now go through `download_sections_parallel()` + `extract_from_sections()` (the screenshot-first path), cutting a 58-min video from ~342s/413MB to ~60s/~12MB. Falls back to the full video when section downloads fail or the source is a local file.
- **Detail engine no longer overwrites transcript-moments frames** — the re-run's frames at LLM-selected timestamps were previously clobbered by the scene/keyframe engine; they are now preserved.
- **transcript-moments first run is now single-pass (P3)** — instead of stopping to wait for the agent to write `key_moments.json`, the pipeline auto-generates heuristic moments (evenly-spaced transcript segments; ffmpeg scene detection when no transcript exists), writes `key_moments.json`, and completes in one invocation. The agent can still refine the file and re-run; `moments_prompt.txt` is still written for optional refinement.
- **`MomentReason` enum + `_VALID_MOMENT_REASONS`** — added the `auto` reason for heuristically generated moments.

### Tests
- **P2 section-download coverage** — `TestTranscriptMomentsSections`: sections-succeed path never touches full download; all-sections-failed path falls back to the full video exactly once.
- **P3 auto-moments coverage** — `TestTranscriptMomentsAuto`: first run auto-generates moments from transcript (sections path, no full download, prompt still written); local-file scene fallback produces scene-detected moments. 148 passed total.

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
