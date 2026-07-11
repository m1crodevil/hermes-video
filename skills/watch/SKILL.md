---
name: watch
version: "1.6.0"
description: Watch a video (URL or local path). Downloads with yt-dlp, extracts auto-scaled frames with ffmpeg, pulls the transcript from captions (or Whisper API fallback), and hands the result to your agent so it can answer questions about what's in the video.
argument-hint: "<video-url-or-path> [question]"
allowed-tools: Bash, Read, AskUserQuestion
homepage: https://github.com/m1crodevil/hermes-video
repository: https://github.com/m1crodevil/hermes-video
author: m1crodevil
license: MIT
user-invocable: true
platforms: [macos, linux]
metadata:
  hermes:
    tags: [video, analysis, multimodal]
    category: content-creation
    requires_toolsets: [terminal]
    config:
      - key: hermes-video.default_detail
        description: "Default detail mode for video analysis"
        default: "balanced"
        prompt: "Default detail mode (transcript|efficient|balanced|token-burner)"
---

# /watch

Downloads a video, pulls its transcript, extracts frames as JPEGs, then hands everything to you so you can answer what's in it.

## When to use /watch

- User shares a video URL (YouTube, TikTok, Vimeo, Instagram, etc.)
- User shares a local video file path (.mp4, .mov, .mkv, .webm)
- User asks about video content ("what happens in this video?")
- User wants to analyze/summarize a video

## When NOT to use /watch

- Download only → use yt-dlp directly
- Edit/cut video → use ffmpeg directly
- Audio transcription only → use whisper.py directly

## Resolve `SKILL_DIR` (do this before any command)

Every `python3 ...` command below runs a bundled script under `SKILL_DIR/scripts/`. Set `SKILL_DIR` to the **absolute path of the directory containing THIS SKILL.md you just Read** — your harness told you that path in the Read result. The scripts are always a direct sibling of this file (`SKILL_DIR/scripts/watch.py`), in every install layout:

```
Read ~/.hermes/skills/content-creation/watch/SKILL.md    → SKILL_DIR=~/.hermes/skills/content-creation/watch
Read ~/.claude/plugins/cache/claude-video/watch/<ver>/skills/watch/SKILL.md → SKILL_DIR=…/skills/watch
Read ~/.codex/skills/watch/SKILL.md                                          → SKILL_DIR=~/.codex/skills/watch
```

Substitute that literal path for `${SKILL_DIR}` in every command. This works on every harness (Claude Code, Codex, Cursor, Gemini CLI, …) without relying on any harness-specific environment variable. Guard once at the start of a run:

```bash
SKILL_DIR="<absolute path of the directory containing the SKILL.md you Read>"
if [ ! -f "$SKILL_DIR/scripts/watch.py" ]; then
  echo "ERROR: scripts/watch.py not found under SKILL_DIR=$SKILL_DIR" >&2
  echo "Re-check the directory of the SKILL.md you Read and substitute it as SKILL_DIR." >&2
  exit 1
fi
```

## Setup preflight

**Python interpreter:** every `python3 ...` command in this skill is for macOS/Linux. On **Windows**, substitute `python`.

Run `setup.py --json` once per session:

```bash
python3 "${SKILL_DIR}/scripts/setup.py" --json
```

Branch on the JSON fields:

- **`can_proceed: true`** → binaries present, config exists. Proceed silently.
- **`first_run: true`** → run installer, scaffold `.env`, write `SETUP_COMPLETE=true`. Optionally ask default detail level (keep `(recommended)` on `balanced`). Do NOT ask about Whisper keys yet — that happens post-run only if captions are missing.
- **`can_proceed: false`** → environment regressed. Run installer to remediate.

For follow-up calls: `python3 "${SKILL_DIR}/scripts/setup.py" --check` — exit 0 = ready.

The installer is idempotent:

```bash
python3 "${SKILL_DIR}/scripts/setup.py"
```

Auto-installs ffmpeg, yt-dlp, and scaffold `~/.config/watch/.env`. YouTube 2026 requires deno (JS runtime for challenge solving) + curl_cffi (browser impersonation) — the installer auto-installs both and writes `~/.config/yt-dlp/config` with `--impersonate chrome --js-runtimes deno`. Without these, transcripts still work but video downloads get HTTP 403.

### Structured mode reference

`setup.py --json` emits `{status, can_proceed, first_run, setup_complete, missing_binaries, ytdlp_deps, whisper_backend, has_api_key, config_file, watch_detail, platform}`. Use `can_proceed`/`first_run` to decide whether to run; **ignore `needs_key`** — Whisper is handled post-run, not here.

`ytdlp_deps` is `{deno: bool, curl_cffi: bool}` — if either is `false`, video downloads will 403 (transcripts still work).

## Workflow

- [ ] Step 0: Setup preflight (`setup.py --json`)
- [ ] Step 1: Parse source + question from user input
- [ ] Step 2: Run `watch.py "<source>"` with appropriate flags
- [ ] Step 3: Check transcript → if missing, offer Whisper
- [ ] Step 4: `vision_analyze` 8-15 representative frames
- [ ] Step 5: Answer user (specific question OR summarize)
- [ ] Step 6: Handle follow-ups from context, cleanup

## How to invoke

**Step 1 — parse the user input.** Separate the video source (URL or path) from any question the user asked. Example: `/watch https://youtu.be/abc what language is this in?` → source = `https://youtu.be/abc`, question = `what language is this in?`.

**Step 2 — run the watch script.** Pass the source verbatim. Do not shell-escape it yourself beyond normal quoting:

```bash
python3 "${SKILL_DIR}/scripts/watch.py" "<source>"
```

**Pitfall:** yt-dlp's `--convert-subs json3` does NOT work. The script handles this automatically via `--sub-format "json3/best"`.

Optional flags:
- `--detail transcript|efficient|balanced|token-burner` — fidelity/speed dial. `transcript` = no frames; `efficient` = keyframes (cap 50); `balanced` = scene-aware (cap 100); `token-burner` = uncapped.
- `--start T` / `--end T` — focus on a section. Accepts `SS`, `MM:SS`, or `HH:MM:SS`. When either is set, fps auto-scales denser (see "Focusing on a section" below).
- `--timestamps T1,T2,…` — grab a frame at each absolute timestamp. Use this after reading the transcript to capture deictic moments ("look here", "notice this"). See "Transcript-cue frames" below.
- `--max-frames N` — override the preset cap (e.g. `--max-frames 40`)
- `--resolution W` — frame width in px (default 512; bump to 1024 only for on-screen text)
- `--fps F` — override auto-fps (clamped to 2 fps max)
- `--out-dir DIR` — working files location (default: auto-generated tmp dir)
- `--output markdown|json|both` — `markdown` (default) = stdout; `json` = writes `report.json`; `both` = both.
- `--whisper groq|openai` — force a specific backend (default: prefer Groq)
- `--no-whisper` — disable Whisper fallback entirely
- `--no-dedup` — keep near-duplicate frames (usually dropped to save budget)
- `--keep-video` — retain downloaded video after frame extraction (default: auto-deleted)

### Focusing on a section (higher frame rate)

When the user asks about a specific moment, pass `--start` and/or `--end`. Focused-mode budgets:

- ≤5s → 2 fps (up to 10 frames)
- 5-15s → 2 fps (up to 30 frames)
- 15-30s → ~2 fps (up to 60 frames)
- 30-60s → ~1.3 fps (up to 80 frames)
- 60-180s → ~0.6 fps (100 frames, capped)

Focused mode is the right call for: any moment/range the user names explicitly; any video >10 minutes where the question targets a specific part; re-runs after a full scan lacked detail in some region. Transcript is auto-filtered to the same range. Frame timestamps are absolute.

```bash
python3 "${SKILL_DIR}/scripts/watch.py" video.mp4 --start 50 --end 60
python3 "${SKILL_DIR}/scripts/watch.py" "$URL" --start 2:15 --end 2:45 --fps 2
python3 "${SKILL_DIR}/scripts/watch.py" "$URL" --start 1:12:00
```

**Step 3 — check the transcript result.** Inspect the `- **Transcript:**` line:

- **Transcript available** (`source: captions (json3)`, `captions (vtt)`, or `whisper (...)`) → proceed to Step 4.
- **Transcript: none available** → captions missing AND Whisper not configured. **This is the moment to offer Whisper**, not before. Ask the user:

  > "Video ini gak punya native captions. Mau setup Whisper API biar bisa transkripsi? (Groq gratis, OpenAI juga bisa) — atau lanjut frames-only aja?"

  If they want Whisper, run `setup.py`, ask for API key, write it to `.env`, re-run watch script. If they decline, proceed frames-only.

**Step 4 — view frames.** The script outputs JPEG frame paths.

**Pitfall: frame filenames are NOT sequential from 0001.** Scene-change engines name files by extraction index (`frame_0211.jpg`), not timestamp. Do NOT guess filenames. Always `search_files("*.jpg", path="<workdir>/frames", target="files")` first, then pick 8-15 representative frames spread across the list for `vision_analyze`.

**Pitfall:** `read_file` cannot handle binary images. Use `vision_analyze` instead:

```bash
vision_analyze(image_url="/tmp/watch-XXXX/frames/frame_0001.jpg", question="What is shown in this frame?")
```

For 50+ frames, sample 8-15 representative frames evenly rather than loading all — vision calls are expensive.

**Step 5 — answer the user.** You now have two streams of evidence:
- **Frames** — what's on screen at each timestamp
- **Transcript** — what's said at each timestamp

### Anti-hallucination rules

- Answer ONLY from what you see in frames (visual) and read in transcript (audio)
- Do not invent details not present in frames or transcript
- If a frame is unclear or low quality, say "I can't see clearly in this frame"
- Always cite timestamps: "At 2:35, the speaker says..." or "In the frame at 1:12..."
- If transcript is in a language you don't understand, say so
- If the video has no useful content for the question, say "The video doesn't cover this"

### Decision guide

- **User asked a specific question** → answer directly citing timestamps
- **User asked "summarize"** → structure, key moments, notable visuals, spoken content
- **No question** → summarize what happens in the video
- **Transcript-only mode** → synthesize structure and key moments, don't paste full transcript

**Step 6 — follow-ups.** The downloaded video is auto-deleted. Frames and transcript remain in the working directory. Answer follow-ups from what you already have — do NOT re-run the script. If no follow-ups expected, clean up with `rm -rf <dir>`.

## Detail and frames

Default behavior comes from `~/.config/watch/.env`:

- `WATCH_DETAIL=transcript|efficient|balanced|token-burner` (default: `balanced`)

**transcript** — captions only; no video download when captions exist. **efficient** — keyframes only (`ffmpeg -skip_frame nokey`), near-instant pass on scene cuts. **balanced** / **token-burner** — scene-aware frames; balanced caps at 100, token-burner is uncapped. Frame report lines include timestamp and selection reason.

## Transcript-cue frames

Visual frame selection can miss moments a presenter explicitly flags ("look here", "notice this") because pointing at a slide is often a *low* visual change. `--timestamps` forces a frame at those moments:

1. Run once to get the timestamped transcript.
2. Scan for deictic cues — phrases where the speaker directs attention on screen.
3. Re-run with `--timestamps 4:32,7:10,9:55`. For a URL, point the second run at the **downloaded local file** so it doesn't re-download.

Behavior: additive by default; cue frames are pinned and counted first; honors focus mode; `--detail transcript --timestamps …` returns *only* cue frames.

## Cookies & Rate Limiting

YouTube aggressively rate-limits subtitle downloads (HTTP 429). The script mitigates with: skip re-download, browser cookies (`--cookies-from-browser chrome` auto-detected), and sleep intervals (`--sleep-subtitles 3`). For best reliability, log in to YouTube in Chrome. See [youtube-429-rate-limit.md](references/youtube-429-rate-limit.md) for workarounds.

## Video cleanup and disk usage

The script auto-deletes the downloaded video after processing to prevent disk usage from ballooning (200MB–1GB per run). Use `--keep-video` to retain when needed for follow-up analysis.

## Troubleshooting

| Problem | Fix | Details |
|---------|-----|---------|
| Video download 403 | Install deno + curl_cffi | [youtube-403-download.md](references/youtube-403-download.md) |
| Subtitle 429 rate limit | Wait + use cookies | [youtube-429-rate-limit.md](references/youtube-429-rate-limit.md) |
| Download throttled | Check network/proxy | [youtube-download-throttling.md](references/youtube-download-throttling.md) |
| Wrong language subs | Auto-detect fixed in v1.2 | [language-detection-pitfall.md](references/language-detection-pitfall.md) |
| No transcript | Offer Whisper or frames-only | See Step 3 above |
| YouTube 2026 deps missing | deno + curl_cffi required | [youtube-2026-download-requirements.md](references/youtube-2026-download-requirements.md) |
| Setup preflight failed (exit 2) | Missing binaries — run installer | `python3 "${SKILL_DIR}/scripts/setup.py"` |
| Whisper request failed | Check key or retry other provider | Error on stderr; try `--whisper openai` if Groq failed |
| Download fails | Check stderr for yt-dlp error | Login-required/region-locked → tell user, don't retry |

## Token efficiency

Frames dominate token cost: 80 frames at 512px ≈ 50-80k image tokens. Transcript is cheap (a few thousand tokens for 10 min). Bumping `--resolution` to 1024 quadruples image tokens — only use when reading on-screen text. Don't re-run if you already have frames+transcript in context.

## Security & Permissions

Runs yt-dlp + ffmpeg locally. Sends only extracted audio to Whisper API (Groq or OpenAI) when captions are missing — never the video itself. Writes to `~/.config/watch/.env` (mode `0600`). Deletes downloaded video after processing. Does not share API keys between providers, log keys, or persist anything outside the working directory and `.env`. When Chrome cookies are auto-detected, `--cookies-from-browser` is passed for authenticated requests — no credentials are stored or transmitted.

## Reference files (load on demand)

- [YouTube 403 fix](references/youtube-403-download.md) — deno + curl_cffi setup
- [YouTube 429 rate limit](references/youtube-429-rate-limit.md) — subtitle throttling
- [YouTube download throttling](references/youtube-download-throttling.md) — network issues
- [YouTube 2026 requirements](references/youtube-2026-download-requirements.md) — full requirements
- [JSON3 format](references/json3-format.md) — subtitle format reference
- [Language detection](references/language-detection-pitfall.md) — subtitle language issues

## Bundled scripts

`scripts/watch.py` (entry point), `scripts/download.py` (yt-dlp wrapper), `scripts/frames.py` (ffmpeg frame extraction), `scripts/transcribe.py` (caption selection + Whisper orchestration), `scripts/whisper.py` (Groq / OpenAI clients), `scripts/setup.py` (preflight + installer). Review scripts before first use to verify behavior.
