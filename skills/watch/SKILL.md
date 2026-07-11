---
name: watch
version: "1.3.0"
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

You don't have a video input; this skill gives you one. A Python script gets captions first, optionally downloads the video, extracts frames as JPEGs (scene-aware, or fast keyframes at `efficient` detail), gets a timestamped transcript (native captions first, then Whisper API as fallback), and prints frame paths. You then `Read` each frame path to see the images and combine them with the transcript to answer the user.

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

## Step 0 — Setup preflight (silent on success)

**Python interpreter:** every `python3 ...` command in this skill is for macOS/Linux. On **Windows**, substitute `python` — the `python3` command on Windows is the Microsoft Store stub and will not run the script.

**Goal:** make sure binaries (ffmpeg, yt-dlp) are installed and `~/.config/watch/.env` exists. Do NOT ask about Whisper API keys here — that happens later, only if captions are missing.

### First run in session

```bash
python3 "${SKILL_DIR}/scripts/setup.py" --json
```

Branch on the JSON fields:

- **`can_proceed: true`** → binaries present, config exists. Proceed to Step 1 silently.
- **`first_run: true`** → genuine first-time setup. Do these in order:
  1. If `missing_binaries` is non-empty, run the installer and confirm binaries land.
  2. Run the installer once more to scaffold `~/.config/watch/.env` (only writes template when file absent).
  3. Write `SETUP_COMPLETE=true` into the config file.
  4. **Optionally** ask the first-run watch preference (detail level) — but do NOT ask about Whisper yet.
  5. Proceed to Step 1.
- **`can_proceed: false` and `first_run: false`** → environment regressed. Run installer to remediate, then proceed.

### Follow-up calls in the same session

```bash
python3 "${SKILL_DIR}/scripts/setup.py" --check
```

Exit 0 = ready. Proceed silently. Non-zero = run installer to fix.

### The installer

Idempotent — safe to re-run:

```bash
python3 "${SKILL_DIR}/scripts/setup.py"
```

On macOS with Homebrew, auto-installs `ffmpeg` and `yt-dlp`. On Linux/Windows, prints exact install commands. Scaffolds `~/.config/watch/.env` with commented placeholders and default watch settings at `0600` perms.

### First-run watch preference (optional, one-time)

After the installer scaffolds `.env`, you may ask one question:

- Default detail (one dial). Present as `AskUserQuestion` options — lightest to heaviest, keep `(recommended)` on `balanced`:
  - `transcript` — no frames at all, transcript only.
  - `efficient` — fast keyframe pass (cap 50).
  - `balanced` (recommended) — scene-aware frames (cap 100, default).
  - `token-burner` — scene-aware, uncapped (maximum fidelity; high token cost).

Write the answer into `~/.config/watch/.env`:

```bash
WATCH_DETAIL=balanced
```

If they skip, keep the recommended default. Do not re-ask when `SETUP_COMPLETE=true`.

### Structured mode reference

`python3 "${SKILL_DIR}/scripts/setup.py" --json` emits `{status, can_proceed, first_run, setup_complete, missing_binaries, ytdlp_deps, whisper_backend, has_api_key, config_file, watch_detail, platform}` where `status` is one of `ready | needs_install | needs_key | needs_install_and_key`. Use `can_proceed`/`first_run` to decide whether to run; **ignore `needs_key`** — Whisper is handled post-run, not here.

`ytdlp_deps` is `{deno: bool, curl_cffi: bool}` — YouTube 2026 requires both for video downloads. If either is `false`, video downloads will 403 (transcripts still work). The installer prints install hints for missing deps.

## Structured output (Pydantic models)

The script produces validated output via Pydantic models (`scripts/models.py`). This enables:

- **JSON serialization** — `report.json` written with `--output json` or `--output both`
- **Markdown rendering** — `report.to_markdown()` produces the human-readable report
- **Programmatic access** — agent can read `report.json` to access `frames[0].path`, `transcript_segments[i].text`, etc.

### Models

| Model | Purpose |
|-------|---------|
| `WatchReport` | Top-level container — metadata, frames, transcript, warnings |
| `VideoMetadata` | Source URL, title, uploader, duration, resolution, codec |
| `Frame` | Path, timestamp, reason (scene-change/keyframe/etc), deduped flag |
| `FrameStats` | Candidates, selected, deduped, engine |
| `TranscriptSegment` | Start/end time, text, word-level timing (JSON3) |
| `WordTiming` | Single word with ASR confidence |
| `FocusRange` | Optional start/end for partial analysis |

### JSON output structure

```json
{
  "metadata": {
    "source": "https://youtu.be/...",
    "title": "...",
    "duration": 120.0,
    "duration_fmt": "02:00",
    "resolution": "1280x720"
  },
  "frames": [
    {"path": "...", "timestamp": 10.0, "timestamp_fmt": "00:10", "reason": "scene-change"}
  ],
  "transcript_segments": [
    {"start": 10.0, "end": 12.0, "text": "...", "words": [{"word": "...", "start": 10.0, "confidence": 0.95}]}
  ]
}
```

## Transcription priority (understand this first)

The script uses a **two-tier** transcription pipeline. JSON3 captions are tried first (free, instant). Whisper is only a fallback for videos without native captions:

1. **JSON3/VTT captions (free, preferred).** `watch.py` calls `fetch_captions()` via yt-dlp which pulls manual or auto-generated subtitles from the source platform. YouTube captions come in JSON3 format with word-level timing (`tOffsetMs`) and ASR confidence (`acAsrConf`). This is the default — no API key needed.
2. **Whisper API fallback (only when captions missing).** If `fetch_captions()` returns nothing, the script extracts audio and sends it to a Whisper API:
   - **Groq** — `whisper-large-v3` (preferred; cheaper, faster). Key at console.groq.com/keys.
   - **OpenAI** — `whisper-1` (fallback). Key at platform.openai.com/api-keys.

**Key insight:** most YouTube videos have auto-generated captions. Whisper is rarely needed. Do NOT ask the user about Whisper keys upfront — wait until the script reports "no transcript available" and THEN offer it.

## How to invoke

**Step 1 — parse the user input.** Separate the video source (URL or path) from any question the user asked. Example: `/watch https://youtu.be/abc what language is this in?` → source = `https://youtu.be/abc`, question = `what language is this in?`.

**Step 2 — run the watch script.** Pass the source verbatim. Do not shell-escape it yourself beyond normal quoting:

```bash
python3 "${SKILL_DIR}/scripts/watch.py" "<source>"
```

**Pitfall:** yt-dlp's `--convert-subs json3` does NOT work. To get JSON3 format, use `--sub-format "json3/best"` as a preference. The script handles this automatically.

Optional flags:
- `--detail transcript|efficient|balanced|token-burner` — fidelity/speed dial. `transcript` = no frames (transcript only, skips video download when captions exist); `efficient` = fast keyframes (cap 50); `balanced` = scene-aware frames (cap 100); `token-burner` = scene-aware, uncapped.
- `--start T` / `--end T` — focus on a section. Accepts `SS`, `MM:SS`, or `HH:MM:SS`. When either is set, fps auto-scales denser (see "Focusing on a section" below).
- `--timestamps T1,T2,…` — grab a frame at each of these absolute timestamps (`SS`, `MM:SS`, or `HH:MM:SS`). Use this after reading the transcript to capture deictic moments the presenter flags ("look here", "as you can see", "notice this") that visual selection alone may miss. See "Transcript-cue frames" below.
- `--max-frames N` — override the preset cap for tighter token budget (e.g. `--max-frames 40`)
- `--resolution W` — change frame width in px (default 512; bump to 1024 only if the user needs to read on-screen text)
- `--fps F` — override auto-fps (clamped to 2 fps max)
- `--out-dir DIR` — keep working files somewhere specific (default: an auto-generated tmp dir)
- `--output markdown|json|both` — output format. `markdown` (default) = human-readable report to stdout; `json` = writes `report.json` to work dir; `both` = markdown to stdout + JSON file.
- `--whisper groq|openai` — force a specific Whisper backend (default: prefer Groq if both keys exist)
- `--no-whisper` — disable the Whisper fallback entirely (frames-only if no captions)
- `--no-dedup` — keep near-duplicate frames. By default a frame-delta pass drops frames that are visually near-identical to the previous kept one (held slides, static screen recordings, paused video) so the frame budget goes to distinct content; the report's **Frames** line notes how many were dropped. Pass this only if the user needs every sampled frame (e.g. judging subtle frame-to-frame motion).
- `--keep-video` — keep the downloaded video file after frame extraction. By default, the video is deleted automatically to save disk space (200MB–1GB per run). Only the extracted frames, transcript, and metadata are kept. Use this when you need the video file for follow-up analysis.

### Focusing on a section (higher frame rate)

When the user asks about a specific moment — "what happens at the 2 minute mark?", "zoom into 0:45 to 1:00", "the first 10 seconds" — pass `--start` and/or `--end`. The script switches to focused-mode budgets, which are denser than full-video budgets (still capped at 2 fps, and still bounded by the detail-mode cap — the counts below assume the default `balanced` cap of 100; `efficient` tops out at 50):

- ≤5s → 2 fps (up to 10 frames)
- 5-15s → 2 fps (up to 30 frames)
- 15-30s → ~2 fps (up to 60 frames)
- 30-60s → ~1.3 fps (up to 80 frames)
- 60-180s → ~0.6 fps (100 frames, capped)

Focused mode is the right call for:
- Any moment/range the user names explicitly ("around 2:30", "the intro", "the last 30 seconds").
- Any video longer than ~10 minutes where the user's question is about a specific part — running focused on the relevant section is far more useful than a sparse scan of the whole thing.
- Re-runs after a full scan didn't have enough detail in some region.

Transcript is auto-filtered to the same range. Frame timestamps are absolute (real video timeline, not offset-from-start).

Examples:
```bash
# Last 10 seconds of a 1 minute video
python3 "${SKILL_DIR}/scripts/watch.py" video.mp4 --start 50 --end 60

# Zoom into 2:15 → 2:45 at 2 fps (60 frames)
python3 "${SKILL_DIR}/scripts/watch.py" "$URL" --start 2:15 --end 2:45 --fps 2

# From 1h12m to the end of the video
python3 "${SKILL_DIR}/scripts/watch.py" "$URL" --start 1:12:00
```

**Step 3 — check the transcript result.** After the script runs, inspect the report header. Look at the `- **Transcript:**` line:

- **Transcript available** (`source: captions (json3)`, `captions (vtt)`, or `whisper (...)`) → proceed to Step 4.
- **Transcript: none available** → captions were missing AND Whisper either has no key or failed. **This is the moment to offer Whisper**, not before. Ask the user:

  > "Video ini gak punya native captions. Mau setup Whisper API biar bisa transkripsi? (Groq gratis, OpenAI juga bisa) — atau lanjut frames-only aja?"

  If they want Whisper, run `python3 "${SKILL_DIR}/scripts/setup.py"` to scaffold `.env`, then ask for the API key and write it. Re-run the watch script with the same URL.
  If they decline, proceed frames-only — answer from frames alone.

**Step 4 — view every frame the script lists.** The script outputs frame paths as JPEG files.

**Pitfall: frame filenames are NOT sequential from 0001.** Scene-change and keyframe engines name files by extraction index (`frame_0211.jpg`, `frame_0345.jpg`, etc.), not by timestamp. Do NOT guess filenames. Always `search_files("*.jpg", path="<workdir>/frames", target="files")` first to see what actually exists, then pick 8-15 representative frames spread across the list for `vision_analyze`.

**Pitfall (Hermes):** The `read_file` tool cannot handle binary images — it returns "Cannot read binary file". Use `vision_analyze` instead to inspect frame images:

```bash
# Example: view a frame
vision_analyze(image_url="/tmp/watch-XXXX/frames/frame_0001.jpg", question="What is shown in this frame?")
```

For large frame counts (50+), sample representative frames spread evenly rather than loading all of them — vision_analyze calls are expensive. Read 8-15 frames across the video timeline for a good visual overview.

**Step 5 — answer the user.** You now have two streams of evidence:
- **Frames** — what's on screen at each timestamp
- **Transcript** — what's said at each timestamp. The report's header shows the source (`captions` = yt-dlp pulled native subs; `whisper (groq)` or `whisper (openai)` = transcribed by API).

If the user asked a specific question, answer it directly citing timestamps. If they didn't ask anything, summarize what happens in the video — structure, key moments, notable visuals, spoken content.

This holds for `transcript` detail too: even with no frames, produce a **summary** like the other modes — do not paste the full transcript into chat. Synthesize structure, key moments, and spoken content with timestamps; quote only the lines that matter. Offer the raw transcript only if the user explicitly asks for it.

**Step 6 — follow-ups.** The downloaded video is already auto-deleted (see "Video cleanup and disk usage"). The frames and transcript remain in the working directory. If the user asks follow-ups about this video, answer from the frames and transcript you already have in context — do NOT re-run the script. If no follow-ups are expected, clean up with `rm -rf <dir>`.

## Detail and frames

Default behavior comes from `~/.config/watch/.env`:

- `WATCH_DETAIL=transcript|efficient|balanced|token-burner` (default: `balanced`)

At `transcript` detail, captions are enough to return a report without downloading video. If captions are missing, the script downloads audio only and tries Whisper. If no transcript can be produced, it reports the limitation clearly; re-run with `--detail balanced` for frames.

At `efficient` detail, the script downloads the video and extracts **keyframes only** (`ffmpeg -skip_frame nokey`) — a near-instant pass that lands frames on scene cuts. If a clip has fewer than 4 keyframes it falls back to uniform sampling.

At `balanced` / `token-burner` detail, the script extracts **scene-aware** frames: ffmpeg scene-change selection first, falling back to uniform sampling only when the video is effectively static. `balanced` caps at 100 frames; `token-burner` is uncapped. Frame report lines include both timestamp and selection reason. Extracted images are clamped to a maximum 1998px height for Claude Read compatibility.

## Transcript-cue frames

Visual frame selection (scene/keyframe) can miss the moments a presenter explicitly flags — "look here", "as you can see", "notice this", "watch what happens" — because pointing at a slide is often a *low* visual change. `--timestamps` lets you force a frame at those exact moments. **You** decide which moments matter, by reading the transcript:

1. Run once at `--detail transcript` (or any detail) to get the timestamped transcript.
2. Scan it for deictic cues — phrases where the speaker directs attention to something on screen. This is a judgment call (ignore rhetorical "look, the point is…"); that's why it's done by you, not a regex.
3. Re-run with `--timestamps 4:32,7:10,9:55` (absolute source times). For a URL, point the second run at the **downloaded local file** in the work dir so it doesn't re-download.

Behavior:
- **Additive by default.** Cue frames (`reason=transcript-cue`) are merged into whatever `--detail` already selected, in chronological order.
- **Pinned and counted first.** Cue frames are reserved against the frame cap before the detail engine runs, so they're never evicted by even-sampling.
- **Honors focus mode.** With `--start/--end`, any cue timestamp outside the window is dropped (reported in the summary). Coordinates are always absolute source time.
- **Cue-only frames.** `--detail transcript --timestamps …` skips scene/keyframe sampling and returns *only* the cue frames (it will download the video to do so, since frames need pixels).

## Cookies & Rate Limiting

YouTube aggressively rate-limits subtitle downloads (HTTP 429). The script mitigates this with three strategies:

1. **Skip re-download** — `fetch_captions()` downloads subtitles once; `download_url()` skips re-downloading if already fetched.
2. **Browser cookies** — If Chrome/Chromium is detected, `--cookies-from-browser chrome` is passed automatically for authenticated sessions.
3. **Sleep intervals** — `--sleep-subtitles 3` adds a 3-second delay between subtitle requests as a safety net.

### Setup cookies (recommended)

For best reliability, log in to YouTube in Chrome. The script auto-detects cookies from:
- `~/.config/google-chrome/Default/Cookies` (Linux)
- `~/.config/chromium/Default/Cookies` (Linux)
- `~/Library/Application Support/Google/Chrome/Default/Cookies` (macOS)

No manual configuration needed — just be logged in to YouTube in Chrome.

### Workaround: PO Token

For production use, consider installing a PO Token provider plugin:
```bash
# See: https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide
yt-dlp --extractor-args "youtube:po_token=web.gvs+XXX" ...
```

## Video cleanup and disk usage

The script automatically deletes the downloaded video file after all processing (frame extraction + Whisper transcription if triggered) to prevent disk usage from ballooning. Each run can leave 200MB–1GB of video behind without this.

**Correct cleanup order:**
1. Fetch captions (JSON3/VTT) — free, instant
2. Download video — only if frames are needed
3. Extract frames from video
4. Whisper transcription (only if captions were NOT available) — needs video for audio extraction
5. **Delete video** — everything that needed it is done

**Pitfall:** Do NOT extract audio "just in case" before frame extraction. Whisper is a fallback that's rarely triggered (most YouTube videos have auto-generated captions). Pre-extracting audio wastes time and disk for the 90%+ case where it's never used.

Use `--keep-video` to retain the downloaded video when needed for follow-up analysis.

## Failure modes and handling

- **Setup preflight failed (exit 2)** → missing binaries. Run `python3 "${SKILL_DIR}/scripts/setup.py"` to install.
- **No transcript available** → captions missing AND (no Whisper key OR Whisper API failed). **Now** ask the user if they want to set up Whisper (see Step 3). Proceed frames-only if they decline.
- **Transcript in wrong language** → The script now auto-detects video language from metadata and downloads subtitles in the correct language (Indonesian, Spanish, etc.). If the transcript still appears in the wrong language, check that `scripts/language.py` exists and `download.py` is v1.2+. See `references/language-detection-pitfall.md`.
- **Long video warning printed** → acknowledge it in your answer. Offer to re-run focused on a specific section via `--start`/`--end` rather than a sparse full-video scan.
- **Subtitle download fails with HTTP 429** → YouTube rate-limits subtitle requests, especially when multiple `yt-dlp` calls hit the same video in quick succession (e.g. `fetch_captions` + `download` both request subs). See `references/youtube-429-rate-limit.md` for full analysis and workarounds. The script tolerates this — if the subtitle file is missing after download, it proceeds without a transcript. **Do NOT re-run immediately** — wait a few minutes or add `--cookies-from-browser chrome` on retry.
- **Download fails** → yt-dlp's error goes to stderr. If it's a login-required or region-locked video, tell the user plainly; do not keep retrying.
- **Whisper request fails** → the error is printed to stderr (likely: invalid key or rate limit). Audio over the API's 25 MB upload cap is split into chunks and transcribed automatically, so length alone won't fail it; if some chunks fail the transcript is partial and the dropped chunks are noted on stderr. The report will say "none available" only if every chunk fails. You can retry with `--whisper openai` if Groq failed (or vice versa).

## Token efficiency

This skill burns tokens primarily on frames. Order of magnitude:
- 80 frames at 512px wide is roughly 50-80k image tokens depending on aspect ratio.
- The transcript is cheap (a few thousand tokens at most for a 10-minute video).
- Bumping `--resolution` to 1024 roughly quadruples the image tokens per frame. Only do it when necessary.

If you already watched a video this session and the user asks a follow-up, do **not** re-run the script — you already have the frames and transcript in context. Just answer from what you have.

## Security & Permissions

**What this skill does:**
- Runs `yt-dlp` locally to download the video and pull native captions when the source supports them (public data; the request goes directly to whatever host the URL points at)
- Runs `ffmpeg` / `ffprobe` locally to extract frames as JPEGs and, when Whisper is needed, a mono 16 kHz audio clip
- **Deletes the downloaded video file after frame extraction** to save disk space (unless `--keep-video` is passed)
- Sends the extracted audio clip to Groq's Whisper API (`api.groq.com/openai/v1/audio/transcriptions`) when `GROQ_API_KEY` is set (preferred — cheaper, faster)
- Sends the extracted audio clip to OpenAI's audio transcription API (`api.openai.com/v1/audio/transcriptions`) when `OPENAI_API_KEY` is set and Groq is not, or when `--whisper openai` is forced
- Writes the downloaded video, frames, audio, and an intermediate transcript to a working directory under the system temp dir (or `--out-dir` if specified) so Claude can `Read` them
- Reads / creates `~/.config/watch/.env` (mode `0600`) to store the Whisper API key(s) and a `SETUP_COMPLETE` marker. As a fallback, also reads `.env` in the current working directory

**What this skill does NOT do:**
- Does not upload the video itself to any API — only the extracted audio goes out, and only when native captions are missing AND Whisper is not disabled with `--no-whisper`
- Does not access any platform account (no login, no session cookies, no posting) — yt-dlp only ever requests public data. **Exception:** when Chrome/Chromium cookies are auto-detected, `--cookies-from-browser chrome` is passed to yt-dlp to use your existing browser session for authenticated requests. No credentials are stored or transmitted by this skill; it only reads the browser's local cookie store.
- Does not share API keys between providers (Groq key only goes to `api.groq.com`, OpenAI key only goes to `api.openai.com`)
- Does not log, cache, or write API keys to stdout, stderr, or output files
- Does not persist anything outside the working directory and `~/.config/watch/.env` — clean up the working directory when you're done (Step 6)

**Bundled scripts:** `scripts/watch.py` (entry point), `scripts/download.py` (yt-dlp wrapper), `scripts/frames.py` (ffmpeg frame extraction), `scripts/transcribe.py` (caption selection + Whisper orchestration), `scripts/whisper.py` (Groq / OpenAI clients), `scripts/setup.py` (preflight + installer)

Review scripts before first use to verify behavior.
