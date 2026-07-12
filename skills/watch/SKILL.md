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

**Step 2b — read metadata from report.json (MANDATORY).** The script now defaults to `--output both`, which writes `report.json` alongside the markdown output. **Always read this file for metadata** — do NOT rely solely on the markdown output which may be truncated for long videos:

```bash
# Find the work dir from the script output, then:
python3 -c "
import json
with open('<workdir>/report.json') as f:
    d = json.load(f)
m = d['metadata']
print(f'Title: {m[\"title\"]}')
print(f'Channel: {m[\"uploader\"]} ({m.get(\"channel_follower_count\",\"?\")} subs)')
print(f'Views: {m.get(\"view_count\",\"?\")} | Likes: {m.get(\"like_count\",\"?\")}')
print(f'Published: {m.get(\"upload_date\",\"?\")}')
print(f'Duration: {m[\"duration\"]}s')
"
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
- `--output markdown|json|both` — `both` (default) = markdown (compact, no full transcript) + `report.json`; `markdown` = full markdown; `json` = report.json only.
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

  > "Video ini gak punya native captions. Mau transkripsi? Ada beberapa opsi:
  > 1. **faster-whisper lokal** — gratis, jalan di VPS, support Indo ✅
  > 2. **Groq Whisper** — bayar ~$0.04/jam (turbo), super cepat
  > 3. **Frames-only** — visual summary aja tanpa transcript"

  If they want faster-whisper (free local), install with `pip install faster-whisper` and run directly — no API key needed. See [free-transcription-alternatives.md](references/free-transcription-alternatives.md) for code examples and model size guidance. If they want Groq Whisper, run `setup.py`, ask for API key, write it to `.env`, re-run watch script. If they decline all, proceed frames-only.

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

### Anti-hallucination rules (MANDATORY — read before every report)

**Zero fabrication — no exceptions:**
- Answer ONLY from what you see in frames (visual) and read in transcript (audio)
- **NEVER fabricate metadata** (channel name, subscriber count, views, likes, comments, title, upload date). These MUST come from the script output or `info.json` — never from memory, guessing, or pattern-matching
- If a frame is unclear or low quality, say "I can't see clearly in this frame"
- Always cite timestamps: "At 2:35, the speaker says..." or "In the frame at 1:12..."
- If transcript is in a language you don't understand, say so
- If the video has no useful content for the question, say "The video doesn't cover this"
- If you cannot see the script output (truncated, unclear), say so explicitly — do NOT guess

**Output truncation recovery (CRITICAL):**
The terminal tool truncates output beyond ~50K chars. For long videos (>20 min), the markdown report may be truncated. When this happens:
1. **Check if `report.json` exists** in the work dir — read metadata from it
2. **If no report.json**, read `<workdir>/download/video.info.json` directly for metadata
3. **Never fill in missing data from imagination** — report what you can verify, mark the rest as "unavailable in truncated output"
4. Prefer `--output both` for long videos to ensure a JSON backup exists

### Decision guide

- **User asked a specific question** → answer directly citing timestamps
- **User asked "summarize"** → structure, key moments, notable visuals, spoken content
- **No question** → summarize what happens in the video
- **Transcript-only mode** → synthesize structure and key moments, don't paste full transcript

### Output format (Telegram)

Always use this exact structure when delivering watch results:

```
🎬 **[Video Title]**
Channel: [Uploader] ([subscribers] subs)
Published: [date] | Duration: [time]
Views: [N] · Likes: [N] · Comments: [N]

---

[Summary/answer content here]

---

_Work dir: `[path]` — frames + transcript retained._
```

**Rules:**
- Use `**bold**` for title only
- Use plain text for metadata (no `• : ` prefix)
- Use `·` (middle dot) as separator, not `|` or `,`
- Keep metadata compact on 1-2 lines
- Add `---` separator before and after main content
- Always include work dir footer
- **NEVER** use raw markdown table syntax (`| col | col |`) in Telegram output — it doesn't render properly

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

## Pitfalls

**Long videos (>30 min) timeout on frame extraction.** Scene-aware extraction on 80+ minute videos can exceed 300s timeout even when the video downloads fine. Mitigations:
- Use `--detail efficient` (keyframes only, near-instant) for long videos where transcript is the primary evidence
- Use `--detail transcript` when captions exist — no video download needed
- Use `--max-frames 50` to cap extraction even in balanced mode
- If timeout occurs, frames already extracted before timeout are still usable — check the frames directory

**No captions + no Whisper = frames-only.** For videos without native captions, the agent should offer transcription options at Step 3, not before. Options include free local (faster-whisper) and paid cloud (Groq Whisper). If user declines all transcription, frames-only is a valid fallback but severely limits analysis for dialogue-heavy content (podcasts, interviews). See [groq-whisper-limits.md](references/groq-whisper-limits.md) for Groq pricing and [free-transcription-alternatives.md](references/free-transcription-alternatives.md) for free alternatives.

**Groq Whisper practical limits for long videos.** Groq has 2-hour audio/hour rate limit (ASH). Videos up to ~80 min fit in one session. For longer content, chunk the audio first. Files >25MB need either dev-tier account or URL parameter. See [groq-whisper-limits.md](references/groq-whisper-limits.md) for full limits.

**Vision models misidentify channel/watermark names from frames.** When a frame contains multiple logos (channel watermark, sponsor logos, on-screen graphics), vision models often pick the wrong one or hallucinate a channel name. **Never report the channel name based solely on frame analysis.** Always cross-reference with the `channel` field from yt-dlp metadata (`--dump-json` output or the watch script's metadata). The transcript source line (`- **Source:** captions (json3)`) and the video's `info.json` are authoritative for channel identity.

## Troubleshooting

| Problem | Fix | Details |
|---------|-----|---------|
| Video download 403 | Install deno + curl_cffi | [youtube-403-download.md](references/youtube-403-download.md) |
| Subtitle 429 rate limit | Wait + use cookies | [youtube-429-rate-limit.md](references/youtube-429-rate-limit.md) |
| Download throttled | Check network/proxy | [youtube-download-throttling.md](references/youtube-download-throttling.md) |
| Wrong language subs | Auto-detect fixed in v1.2 | [language-detection-pitfall.md](references/language-detection-pitfall.md) |
| No transcript | Offer faster-whisper (free) or Groq Whisper or frames-only | See Step 3 + [free-transcription-alternatives.md](references/free-transcription-alternatives.md) |
| YouTube 2026 deps missing | deno + curl_cffi required | [youtube-2026-download-requirements.md](references/youtube-2026-download-requirements.md) |
| Setup preflight failed (exit 2) | Missing binaries — run installer | `python3 "${SKILL_DIR}/scripts/setup.py"` |
| Frame extraction timeout (>30 min video) | Use --detail efficient or --detail transcript | See "Pitfalls" section above |
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
- [Groq Whisper limits](references/groq-whisper-limits.md) — file size, rate limits, pricing, integration notes
- [Free transcription alternatives](references/free-transcription-alternatives.md) — faster-whisper, whisper.cpp, Qwen3-ASR, Puter.js evaluation, MiMo ASR limits
- [YouTube metadata extraction](references/youtube-metadata-extraction.md) — yt-dlp channel/video stats without API key, channel handle resolution, YouTube Data API v3 free tier

## Bundled scripts

`scripts/watch.py` (entry point), `scripts/download.py` (yt-dlp wrapper), `scripts/frames.py` (ffmpeg frame extraction), `scripts/transcribe.py` (caption selection + Whisper orchestration), `scripts/whisper.py` (Groq / OpenAI clients), `scripts/setup.py` (preflight + installer). Review scripts before first use to verify behavior.
