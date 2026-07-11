# Changelog

All notable changes to `/watch` are documented here.

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
