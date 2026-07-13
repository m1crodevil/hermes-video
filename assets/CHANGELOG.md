# Changelog

All notable changes to `/watch` are documented here.

## [1.14.0] — 2026-07-13

### Fixed
- **YouTube video download 403: cookies breaking android_vr client.** `_yt_dlp_network_opts()` was passing `--cookies-from-browser chrome` by default, causing yt-dlp to skip `android_vr` (which doesn't support cookies) and fall back to `web_creator` which needs a GVS PO Token. Now cookies are OFF by default — `--cookies` is an opt-in flag. `android_vr` without cookies is the most reliable client for YouTube 2026+.
- **Metadata/subtitle functions no longer inject network opts.** `fetch_metadata_only()` and `fetch_captions()` no longer call `_yt_dlp_network_opts()` — they work fine without cookies/impersonate, and adding them was causing the same android_vr skip issue during subtitle downloads.

### Changed
- `_yt_dlp_network_opts()` now accepts `use_cookies: bool = False` parameter. Cookies only added when explicitly requested.
- `_common_yt_dlp_opts()` now accepts `use_cookies: bool = False` parameter.
- `download_url()` and `download()` now accept `use_cookies: bool = False` parameter, passed through from `watch.py`.
- `watch.py` gained `--cookies` flag (opt-in, documented as breaking android_vr).
- SKILL.md: vision verification minimum raised from 8-15 to 21+ representative frames per video.
- SKILL.md: "Cookies & Rate Limiting" section updated to reflect opt-in behavior.
- SKILL.md: "Security & Permissions" section updated — no browser credentials accessed by default.
- SKILL.md: Video download 403 pitfall updated with v1.14+ fix details.

## [1.13.0] — 2026-07-13

### Fixed
- **YouTube 403 video download fix (android_vr player client).** Added `--extractor-args "youtube:player_client=android_vr,web_creator"` to yt-dlp calls. The `android_vr` player client bypasses YouTube's JS challenge solving requirement and works reliably without deno. This fixes the persistent HTTP 403 error where `tv downgraded player API` failed to download video streams despite having deno + curl_cffi installed.
- **File extension `.mp4.webm` handling.** When yt-dlp merges mp4 video + webm audio, the output file is named `video.mp4.webm`. `_pick_video()` now detects combined extensions before falling back to single extensions, preventing "video file not found" errors.
- **Moment reason validation.** `watch.py` now validates `key_moments.json` reason values against the `MomentReason` enum before passing to Pydantic. Invalid values are normalized to `"unknown"` with a warning, preventing `ValidationError` crashes when LLM-generated moments contain unsupported reason types.
- **Cached bytecode cleanup.** Removed stale `__pycache__` directories to prevent version mismatch errors between installed skill files and cached bytecode.

### Changed
- `_yt_dlp_network_opts()` now injects `android_vr` as primary player client, with `web_creator` as fallback.
- `_pick_video()` priority: combined extensions (`.mp4.webm`) → single extensions → any video extension.

## [1.10.0] — 2026-07-12

### Changed
- **Mandatory stats collection (Step 2b).** Stats are now always collected from the work directory, even when the script times out or crashes. Added a fallback one-liner that reads `video.info.json`, `frames/`, and subtitle `.json3` files when `report.json` is missing.
- Workflow checklist now includes Step 2b as a mandatory step between script execution and transcript check.
- Pitfalls section: timeout on long videos is now framed as expected behavior, not a failure. Agent is instructed to collect stats via fallback path instead of skipping them.
- Version bumped from 1.9.0 to 1.10.0.

## [1.8.1] — 2026-07-12

### Fixed
- **FrameReason enum missing `gap-fill` value.** `frames.py` emits `reason="gap-fill"` for gap-filled frames during scene detection on long videos, but the `FrameReason` enum in `models.py` didn't include it. This caused a `PydanticValidationError` crash on videos >10 min where gap-filling kicked in. Added `GAP_FILL = "gap-fill"` to the enum. Commit: `a616ba6`.

## [1.8.0] — 2026-07-12

### Added
- **Adaptive scene detection threshold** based on video duration. Short videos (≤1 min) use 0.25; long videos (>60 min) use 0.12. The threshold auto-adjusts for 6 duration tiers to balance sensitivity vs. false positives.
- **Gap-filling uniform sampling** for long videos (>10 min). After scene detection, large gaps (>2× expected interval) are filled with uniformly-sampled frames. Capped at 5 fill frames per gap.
- **Minimum frame density guarantee** — videos >10 minutes now produce at least 1 frame per 60 seconds regardless of scene detection results.
- **Two-pass extraction mode** for `token-burner` detail: runs scene detection (Pass 1) + uniform sampling at 50% density (Pass 2), merges and deduplicates for maximum coverage.
- `gap-fill` frame reason label (alongside existing `scene-change`, `uniform`, `keyframe`, `transcript-cue`).

### Changed
- Scene threshold now ranges from 0.12–0.25 based on duration (was fixed at 0.20).
- Long videos (30+ min) get significantly more frames — typically 2–3× improvement.
- `token-burner` mode now uses two-pass extraction (scene + uniform) instead of single-pass.
- `extract_scene_or_uniform()` accepts optional `threshold` and `fill_gaps` parameters.
- `auto_fps()` enforces minimum fps for videos >10 minutes.

### Fixed
- Large gaps in frame coverage for long documentary/vlog content (44-min video: 25 frames → 60–80 frames, max gap 8.2 min → <2 min).
- Sparse frame distribution in slow-transition segments where scene detection misses gradual visual changes.

### Performance
- Adaptive threshold adds ~1s overhead (ffprobe duration call, only when threshold not explicitly provided).
- Gap-filling adds ~5–10s for typical long videos (ffmpeg seeks for fill frames).
- Two-pass mode ~2× slower than single-pass (by design — only used in `token-burner` mode).
- No new dependencies — remains ffmpeg-only (no PySceneDetect).

## [1.5.0] — 2026-07-11

### Added
- **Linux auto-install.** `setup.py` now auto-installs all prerequisites on Linux (Ubuntu/Debian with `sudo`): ffmpeg via `apt`, yt-dlp standalone binary to `~/.local/bin/`, deno via `install.sh` to `~/.deno/bin/`, and curl_cffi via `uv` or `pip`.
- `_install_ffmpeg_linux()` — installs ffmpeg/ffprobe via `sudo apt install -y ffmpeg`. Falls back to manual hints on non-apt distros (Fedora/Arch).
- `_install_ytdlp_linux()` — downloads yt-dlp standalone binary to `~/.local/bin/yt-dlp`. No sudo required.
- `_install_deno()` — installs deno JS runtime via `curl -fsSL https://deno.land/install.sh | sh`. Works on both Linux and macOS. No sudo required.
- `_install_curl_cffi()` — installs curl_cffi Python package via `uv pip install --system` (preferred) or `pip install --break-system-packages` (fallback). No sudo required.
- `_ensure_path()` — idempotently adds `~/.local/bin` and `~/.deno/bin` to PATH in `~/.bashrc`.
- `_has_sudo()` / `_has_apt()` helper functions for distro detection.
- `cmd_install()` Linux branch calls all install functions sequentially; each is idempotent and prints what it did.

### Changed
- `_check_ytdlp_deps()` now also checks `~/.deno/bin/deno` directly (not just PATH).
- `_warn_ytdlp_deps()` now auto-installs missing deno/curl_cffi instead of just printing hints.
- `assets/README.md` updated with platform auto-install table and simpler manual install section.

## [1.4.0] — 2026-07-11

### Fixed
- **YouTube 403 video download fix.** Added Deno (JS runtime) and curl_cffi (browser impersonation) as required dependencies for YouTube video downloads. Without these, metadata + subtitles worked but video streams returned HTTP 403 Forbidden.
- `download.py` now passes `--impersonate chrome --js-runtimes deno` to yt-dlp for all YouTube downloads. Chrome cookies are also passed when Deno is available.
- Consolidated `_impersonate_opts()` + `_cookie_opts()` into single `_yt_dlp_network_opts()` function.

### Added
- `setup.py` checks for `deno` and `curl_cffi` in `--json` output (`ytdlp_deps` field) and prints install hints when missing.
- `setup.py` auto-creates `~/.config/yt-dlp/config` with `--impersonate chrome --js-runtimes deno` flags.
- `assets/README.md` rewritten with accurate prerequisites, post-install steps, and troubleshooting guide.

### Changed
- SKILL.md structured mode reference updated to document `ytdlp_deps` field.

## [1.3.0] — 2026-07-11

### Added
- **Auto-cleanup of downloaded video files.** After frame extraction (and Whisper transcription if needed), the downloaded video is deleted to save disk space (200MB–1GB per run). Only frames, transcript, and metadata are retained.
- `--keep-video` flag to preserve the downloaded video when needed for follow-up analysis.
- Whisper audio chunks (`audio.mp3`, `chunks/`) are also cleaned up after successful transcription.

### Changed
- Footer message now reports cleanup status: "video auto-cleaned" vs "all files retained (--keep-video)".

### Design note
- Video cleanup runs **after** both frame extraction AND Whisper transcription — Whisper needs the video to extract audio, so it must not be deleted beforehand. Audio is only extracted when Whisper is actually triggered (captions missing), not preemptively.

## [0.5.0] — 2026-07-10

### Fixed
- **Subtitle 429 fix** — `download_url()` now receives `existing_subtitle` from `fetch_captions()` and skips re-downloading, eliminating the double-request that caused YouTube rate limiting.
- **Browser cookies** — auto-detects Chrome/Chromium cookies via `--cookies-from-browser chrome` for authenticated sessions, dramatically improving subtitle download reliability.
- **Sleep intervals** — `--sleep-subtitles 3` added to all yt-dlp subtitle requests as rate-limit safety net.

### Changed
- Shared subtitle flags extracted to `_common_yt_dlp_opts()` helper for DRY consistency.
- `download()` and `download_url()` now accept `existing_subtitle` parameter to prevent redundant subtitle downloads.
- `watch.py` passes `existing_subtitle` from `fetch_captions()` result to `download()`.

### Documentation
- `SKILL.md` — new 'Cookies & Rate Limiting' section with setup instructions.

## [0.4.0] — 2026-07-10

### Fixed
- **Subtitle 429 handling** — documented YouTube rate limiting issue and workarounds in `references/youtube-429-rate-limit.md`. Updated failure modes section with guidance: do NOT re-run immediately, use cookies, add sleep intervals.
- `watch.py` now auto-detects JSON3 vs VTT format by file extension and routes to correct parser.

### Added
- `references/youtube-429-rate-limit.md` — comprehensive analysis of YouTube subtitle rate limiting:
  - Root cause: double subtitle download in `fetch_captions()` + `download_url()`
  - Known issue: yt-dlp#13831 (OPEN)
  - Workarounds: `--cookies-from-browser chrome`, `--sleep-subtitles 5`, PO token provider
  - Prevention: skip re-download if subtitle already exists

### Known Issues
- **Double subtitle download bug:** `fetch_captions()` successfully downloads subtitle, but `download_url()` re-downloads and may hit 429. When 429 occurs, yt-dlp deletes the previously fetched file. **Fix pending** in `download.py`.

## [0.3.0] — 2026-07-10

### Changed
- **JSON3 subtitle format is now the primary format.** `download.py` uses `--sub-format "json3/best"` instead of VTT. JSON3 provides word-level timing (`tOffsetMs`) and ASR confidence scores (`acAsrConf`) that VTT lacks — enabling precise transcript-to-frame alignment for clipping workflows.
- `transcribe.py` gained `parse_json3()` as the primary parser; `parse_vtt()` is retained as a fallback for local `.vtt` files.
- `_pick_subtitle()` in `download.py` now prefers `.json3` files over `.vtt` when both exist.
- `watch.py` auto-detects format by file extension and uses the appropriate parser.

### Added
- `references/json3-format.md` — full JSON3 schema reference (event types, segs structure, word-level fields, yt-dlp usage, Python parser, jq one-liners).

## [0.2.0] — 2026-06-29

### Added
- **`--detail` dial** with four modes — `transcript` (captions only, no frames), `efficient` (fast keyframe pass, cap 50), `balanced` (scene-aware, cap 100, default), and `token-burner` (scene-aware, uncapped). Set the default with `WATCH_DETAIL` in `~/.config/watch/.env`.
- **Frame deduplication** (default on; `--no-dedup` to disable). Before the budget cap, a pass downscales each frame to a 16×16 grayscale thumbnail and drops frames whose mean per-pixel difference from the last *kept* frame is within threshold — so the budget goes to distinct content instead of held slides and static recordings. The **Frames** report line shows how many near-duplicates were dropped.
- **Whisper auto-chunking.** Audio over the 25 MB upload cap is split into evenly sized chunks, transcribed per chunk, with segment timestamps shifted back into source time. Partial failures are tolerated — transcription only fails if *every* chunk fails, so length alone no longer breaks it.
- **`--timestamps T1,T2,…`** — grab a frame at each absolute timestamp; reserved against the cap, and the only frames produced under `--detail transcript`.
- **`--no-whisper`** — disable transcription entirely (frames only).
- pytest suite covering config, dedup, download, fixtures, frames, setup, timestamps, watch, and whisper (no network; ffmpeg-synthesized clips).

### Changed
- **Restructured into a self-contained `skills/watch/` package** so `SKILL.md` and its `scripts/` runtime are siblings in one folder. This fixes installs on Codex, Cursor, Copilot, and other Agent Skills hosts: `npx skills add` now copies the skill as a working unit instead of grabbing the root `SKILL.md` without its scripts.
- **Harness-agnostic path resolution** — `SKILL.md` resolves `$SKILL_DIR` from where it was Read instead of the Claude-Code-only `${CLAUDE_SKILL_DIR}`, so script calls work on every host.
- `/watch` is now derived from `SKILL.md` frontmatter; the separate `commands/watch.md` wrapper was dropped to avoid a duplicate slash command.
- `balanced` now full-decodes to detect every scene cut across the whole video. The previous early-exit was faster but kept only the first cuts and dropped the tail of long videos.
- `token-burner` is exempt from the long-video "sparse scan" warning, since it keeps every scene-change frame.
- `--max-frames` is now an override on top of each mode's default cap, rather than a fixed default of 80.

### Fixed
- Non-Claude installs (`npx skills add`) were dead on arrival — the installer copied `SKILL.md` without the `scripts/` it shells out to. The self-contained package layout resolves this.

### Removed
- `V2_PLAN.md` and `V2_CONCERNS.md` planning docs.

## [0.1.3] — 2026-05-09

### Fixed
- Windows: `video.info.json` is read as UTF-8 (#4). Previously `Path.read_text()` defaulted to cp1252 on Windows and crashed on yt-dlp's UTF-8 output, silently dropping Title/Uploader from the report. Same fix applied to `.env` reads/writes in `whisper.py` and `setup.py`.
- `download.py` now logs info.json parse failures to stderr instead of swallowing them.

### Security
- Hardened subprocess argv against option injection (#2): inserted `--` before the URL in the yt-dlp argv, and tightened `is_url` to reject `-`-prefixed sources and require a non-empty netloc. Resolved video/audio paths to absolute via `Path.resolve()` before passing to `ffmpeg`/`ffprobe`, so a relative path starting with `-` can't be misinterpreted as a flag.

## [0.1.2] — 2026-04-24

### Fixed
- Windows console crash: removed the emoji from the long-video warning in `watch.py`; cp1252 consoles couldn't encode it.
- `setup.py` now prints `winget` / `pip` install commands on Windows instead of "unsupported platform" — matches what the README already promised.

### Changed
- `SKILL.md` notes that on Windows the scripts must be invoked with `python`, not `python3` (the latter is the Microsoft Store stub on Windows).

## [0.1.1] — 2026-04-24

### Fixed
- Added `commands/watch.md` shim so `/watch` is callable when installed as a Claude Code plugin. Without it, the plugin loaded but the skill wasn't exposed as a slash command.
- `scripts/build-skill.sh` now strips `commands/` from the claude.ai `.skill` bundle alongside `hooks/` and `.claude-plugin/`.

## [0.1.0] — 2026-04-24

Initial marketplace release.

### Added
- `/watch <url-or-path> [question]` slash command.
- yt-dlp download with native caption extraction (manual + auto-subs).
- ffmpeg frame extraction with auto-scaled fps (≤2 fps, ≤100 frames, duration-aware budget).
- `--start` / `--end` focused mode with denser frame budget and transcript range filtering.
- Whisper fallback (Groq preferred, OpenAI secondary) for videos without captions.
- `setup.py` preflight: silent `--check`, structured `--json`, and installer that auto-runs `brew install` on macOS.
- Session-start hook that prints a one-line status on first run / partial config.
- `.skill` bundle packaging for claude.ai upload via `scripts/build-skill.sh`.
