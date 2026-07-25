---
name: watch
version: "2.0.0"
description: "Watch a video (URL or local path). Downloads with yt-dlp, extracts auto-scaled frames with ffmpeg, pulls the transcript from captions (or Whisper API fallback), and hands the result to your agent so it can answer questions about what's in the video."
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
---

# /watch

Downloads a video, pulls its transcript, extracts frames as JPEGs, then hands everything to you so you can answer what's in it.

## Quick Reference

| Flag | Purpose |
|------|---------|
| `--detail transcript` | Captions only — no video download when captions exist |
| `--detail frames` | Download + timestamp extraction (agent provides timestamps) |
| `--start T --end T` | Focus on a section (`SS`, `MM:SS`, or `HH:MM:SS`) |
| `--timestamps T1,T2,…` | Force frame at each timestamp |
| `--max-frames N` | Override preset frame cap |
| `--resolution W` | Frame width in px (default 512; 1024 for on-screen text) |
| `--out-dir DIR` | **CRITICAL** — pin working directory (default: auto tmp) |
| `--output both` | Default: markdown + `report.json` |
| `--stats` | Include analysis stats in output |
| `--keep-video` | Retain downloaded video (default: auto-deleted) |

## Output Philosophy

The user wants to understand what the video is about. Deliver comprehensive analysis — like a thorough article review.

**DO:** Summarize key arguments, main findings, conclusions, important quotes. Match user language. Structure for readability. Cross-reference transcript with visual evidence naturally.

**DON'T:** Show work process. No cross-reference tables, no correction sections, no frame-by-frame notes. No stats block unless user asks.

**Data flow:** `watch.py → report.json → agent reads transcript → agent selects moments → watch.py --timestamps → agent vision_analyze → cross-reference → summary`

**STOP when:** Analysis is comprehensive (key findings + main arguments + conclusions). All cross-references incorporated naturally. No process artifacts leak into output text.

**Frame analysis rule:** After extracting frames, analyze EVERY extracted frame with `vision_analyze`. Minimum 21 frames. NEVER skip frames to "save API calls" — fewer frames = blind spots in visual analysis.

## Resolve `SKILL_DIR` (before any command)

Set `SKILL_DIR` to the **absolute path of the directory containing THIS SKILL.md** — your harness told you that path in the Read result:

```
Read ~/.hermes/skills/content-creation/watch/SKILL.md    → SKILL_DIR=~/.hermes/skills/content-creation/watch
Read ~/.claude/plugins/cache/claude-video/watch/<ver>/skills/watch/SKILL.md → SKILL_DIR=…/skills/watch
Read ~/.codex/skills/watch/SKILL.md                                          → SKILL_DIR=~/.codex/skills/watch
```

Guard once at the start of a run:

```bash
SKILL_DIR="<absolute path of the directory containing the SKILL.md you Read>"
if [ ! -f "$SKILL_DIR/scripts/watch.py" ]; then
  echo "ERROR: scripts/watch.py not found under SKILL_DIR=$SKILL_DIR" >&2
  exit 1
fi
```

## Workflow

1. **Setup preflight** — `python3 "${SKILL_DIR}/scripts/setup.py" --json`
   - `can_proceed: true` → proceed silently
   - `first_run: true` → run installer, scaffold `.env`
   - `can_proceed: false` → run installer to remediate
2. **Run watch.py** — `python3 "${SKILL_DIR}/scripts/watch.py" "<source>" --detail transcript --stats`
   - For videos >10 min: use `background=true, notify_on_complete=true`
   - Wait loop: `process(action='wait')` may timeout at 60s — re-wait until done
3. **Read report.json** — Parse work dir from output: `[watch] working dir: /tmp/watch-XXXX`
4. **Select key moments** — Agent reads transcript, identifies 21+ key moments requiring visual verification (proper nouns, deictic references, claims/statistics, speaker identity)
5. **Re-run with timestamps** — `python3 "${SKILL_DIR}/scripts/watch.py" "$URL" --timestamps 4:32,7:10,9:55 --out-dir <FIXED_DIR>`
   - **Always use `--out-dir <FIXED_DIR>` on BOTH runs** — without it, key_moments.json from run 1 is lost
6. **Vision analyze** — `vision_analyze(image_url="<workdir>/frames/frame_NNNN.jpg", question="...")`
   - Analyze EVERY extracted frame — minimum 21, no exceptions
   - Frame filenames are NOT sequential — use `search_files("*.jpg", path="<workdir>/frames")` first

## Report Parsing

Read `report.json` from the work directory. **Key paths are FLAT, not nested:**

```bash
# Metadata
jq '.metadata | {title, uploader, view_count, like_count, upload_date, duration}' <workdir>/report.json

# Transcript segments (NOT transcript.segments — it's FLAT)
jq '.transcript_segments | length' <workdir>/report.json
jq '.transcript_segments[0:5]' <workdir>/report.json
jq -r '.transcript_text' <workdir>/report.json | head -20

# Frames
jq '.frames | length' <workdir>/report.json
jq '.frames[] | {path: .path, timestamp: .timestamp, reason: .reason}' <workdir>/report.json

# Key moments
jq '.key_moments | length' <workdir>/report.json
jq '.key_moments[] | {timestamp: .timestamp, word: .word, reason: .reason, question: .question}' <workdir>/report.json
```

**Fallback when report.json missing** (timeout/crash):
```bash
jq '{title: .title, uploader: .uploader, duration: .duration}' <workdir>/download/video.info.json
ls <workdir>/frames/*.jpg | wc -l
```

## Output Format

Always use this structure:

🎬 **[Video Title]**
Channel: [Uploader] · Duration: [time]

---

[Comprehensive analysis content — what the video is about, key findings, main arguments, conclusions]

---

**Rules:**
- Use `**bold**` for title only
- Use `·` (middle dot) as separator
- Keep metadata compact on 1-2 lines
- Add `---` separator before and after main content
- **NEVER** use raw markdown table syntax in Telegram output
- **Stats block is OPTIONAL** — include only if user asks
- **NEVER output** cross-reference tables, correction sections, or verification trails

## Example Outputs

**Example 1: Simple video summary**
🎬 **How to Build a REST API in 10 Minutes**
Channel: TechWithTim · Duration: 10:23

---
This video walks through building a REST API using Node.js and Express. The host covers route setup, middleware configuration, and error handling in a practical, step-by-step format.
---

**Example 2: Cross-reference finding**
The transcript mentions "Ragnarok" at 0:54, but the on-screen text shows "Ragnarök" (with umlaut). This is a common ASR error for Scandinavian names.

**Example 3: Error case (no transcript)**
⚠️ No transcript available for this video. Set GROQ_API_KEY or OPENAI_API_KEY for Whisper transcription.

## Configuration

- **Config dir:** `~/.config/watch/`
- **Env file:** `~/.config/watch/.env` (mode `0600`)
- **Default detail:** `WATCH_DETAIL=frames`
- **Whisper backend:** Groq (default) or OpenAI — set `WHISPER_BACKEND` in `.env`
- **API keys:** `GROQ_API_KEY` or `OPENAI_API_KEY` — only needed if captions are missing

## Anti-Hallucination Rules

**Zero fabrication — no exceptions:**
- Answer ONLY from frames (visual) and transcript (audio) you actually see
- **NEVER fabricate metadata** — title, channel, views, likes MUST come from report.json/info.json
- If a frame is unclear: "I can't see clearly in this frame"
- Always cite timestamps: "At 2:35, the speaker says..."
- If transcript language is unknown, say so
- If video doesn't cover the question, say "The video doesn't cover this"
- When terminal output is truncated, read report.json — never fill in from imagination

**See vs Infer:** Distinguish what you SEE from what you INFER. "The screen shows X" vs "It seems like X".

**Flag uncertainty:** Use "appears to be" vs "is". Don't present guesses as facts.

**No assumptions:** Don't fill gaps with plausible guesses. If you can't determine something, say so.

## Pitfalls

1. **`--out-dir` is CRITICAL for two-run workflows.** Each run creates a new `/tmp/watch-XXXX`. Without `--out-dir`, key_moments.json from run 1 is lost on run 2. **Fix: always pass `--out-dir <FIXED_DIR>` on BOTH runs.**

2. **Frame filenames are NOT sequential.** Scene detection names by extraction index (`frame_0211.jpg`), not timestamp. Always `search_files("*.jpg")` first.

3. **report.json keys are FLAT.** Use `d.get("transcript_segments", [])` — NOT `d.get("transcript", {}).get("segments", [])`. Common mistake: falsely concluding "segments: 0".

4. **Long videos (>30 min) timeout on frame extraction.** Primary fix: `background=true` + `notify_on_complete=true` for videos >10 min. If timeout, frames already extracted are still usable.

5. **Vision models misidentify channel names from frames.** Never report channel based solely on frames — always cross-reference with yt-dlp metadata.

6. **Transcript misreads proper nouns.** Auto-captions mangle product/tool names. Cross-reference with frames or web search before reporting.

7. **YouTube 2026 requires deno + curl_cffi.** Without them, transcripts work but video downloads get HTTP 403. `setup.py` auto-installs both.

8. **report.json won't exist on timeout.** Always collect metadata from raw files: `video.info.json`, `frames/`, `.json3` subtitles.

## Token Efficiency

Frames dominate token cost: 80 frames at 512px ≈ 50-80k image tokens. Transcript is cheap. Bumping `--resolution` to 1024 quadruples image tokens — only use for on-screen text.

## Reference Files

- [YouTube 403 fix](references/youtube-403-download.md)
- [YouTube 429 rate limit](references/youtube-429-rate-limit.md)
- [YouTube 2026 requirements](references/youtube-2026-download-requirements.md)
- [Groq Whisper limits](references/groq-whisper-limits.md)
- [Free transcription alternatives](references/free-transcription-alternatives.md)
- [JSON3 transcript-frame alignment](references/json3-transcript-frame-alignment.md)
- [Speaker diarization research](references/speaker-diarization-research.md)
- [Scene detection optimization](references/scene-detection-optimization.md)
- [Optimization benchmarks](references/optimization-benchmarks-2026-07.md)
- [Truncation-fabrication incident](references/truncation-fabrication-incident.md)

## Bundled Scripts

`scripts/watch.py` (entry point), `scripts/download.py` (yt-dlp wrapper), `scripts/frames.py` (timestamp-only frame extraction), `scripts/transcribe.py` (caption selection + Whisper orchestration), `scripts/whisper.py` (Groq/OpenAI clients), `scripts/setup.py` (preflight + installer), `scripts/config.py` (shared config), `scripts/models.py` (Pydantic WatchReport), `scripts/language.py` (language detection), `scripts/errors.py` (exception hierarchy), `scripts/stats_collector.py` (analysis statistics).
