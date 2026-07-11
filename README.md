# /watch **Give Hermes the ability to watch any video.**

Hermes Agent:

```bash
hermes skill install watch
```

Or install manually:

```bash
git clone https://github.com/m1crodevil/hermes-video.git ~/.hermes/skills/content-creation/watch
```

Zero config to start — `yt-dlp` and `ffmpeg` install on first run via `brew` on macOS (Linux/Windows print exact commands). Captions cover most public videos for free. Whisper API key is only needed when a video has no captions.

---

Hermes can read a webpage, run a script, browse a repo. What it can't do, out of the box, is *watch a video*. You paste a YouTube link and it has to either guess from the title or pull a transcript that's missing 90% of what's on screen.

With hermes-video `/watch` you can paste a URL or a local path, ask a question, and Hermes fetches captions first, downloads only what it needs, extracts frames (scene-aware, or fast keyframes at `efficient` detail), pulls a timestamped transcript (free captions when available, Whisper API as fallback), and analyzes every frame as an image and reads the timestamped transcript. By the time it answers, it has *seen* the video and *heard* the audio.

```
/watch https://youtu.be/dQw4w9WgXcQ what happens at the 30 second mark?
```

## What people actually use it for

**Analyze someone else's content.** `/watch https://youtu.be/<viral-video> what hook did they open with?` Hermes looks at the first frames, reads the opening transcript, breaks down the structure. Same for ad creative, competitor launches, podcast intros, anything where the *how* matters as much as the *what*.

**Diagnose a bug from a video.** Someone sends you a screen recording of something broken. `/watch bug-repro.mov what's going wrong?` Hermes watches the recording, finds the frame where the issue appears, describes what's on screen, often catches the cause without you ever opening the file.

**Summarize a video.** `/watch https://youtu.be/<long-thing> summarize this` does the obvious thing — pulls the structure, the key moments, what was actually said and shown. Faster than watching at 2x.

**Cut the hype out of an update video.** `/watch https://youtu.be/<launch-video> what's actually new — skip the hype` Strip a "game-changer" feature drop down to the few things that matter, so you get the substance without ten minutes of intro and overselling.

**Turn a playlist into notes.** `/watch https://youtu.be/<video> summarize this to a note` Run it across a series and file a per-video summary, so a channel or course becomes a searchable set of notes instead of hours you have to sit through.

## How it works

1. **You paste a video and a question.** URL (anything yt-dlp supports — YouTube, Loom, TikTok, X, Instagram, plus a few hundred more) or a local path (`.mp4`, `.mov`, `.mkv`, `.webm`).
2. **`yt-dlp` checks captions first.** At `transcript` detail, captioned URLs return without downloading video. Otherwise, or when Whisper needs audio, it downloads only what the run needs.
3. **`ffmpeg` extracts frames at the chosen detail.** `efficient` decodes keyframes only (near-instant); `balanced`/`token-burner` prefer scene-change frames and fall back to the duration-aware uniform sampler when they under-produce. JPEGs are 512px wide by default and clamped to 1998px tall for Hermes Read compatibility.
4. **The transcript comes from one of two places.** First try: `yt-dlp` pulls native captions (manual or auto-generated) from the source. Free, instant, accurate-ish. Fallback: extract a mono 16 kHz 64 kbps mp3 audio clip (~480 kB/min) and ship it to Whisper — Groq's `whisper-large-v3` (preferred — cheaper and faster) or OpenAI's `whisper-1`.
5. **Frames + transcript are handed to Hermes.** The script builds a validated Pydantic `WatchReport` model from all pipeline data — metadata, frames with timestamps and reasons, transcript segments with word-level timing. This model renders as a structured markdown report (tables, timelines) for human reading, and serializes to `report.json` for agent pipelines.
6. **Hermes answers grounded in what's actually on screen and in the audio.** Not "based on the description" or "according to the title." It saw the frames. It heard the transcript. It answers the way someone who watched the video would.
7. **Cleanup.** The downloaded video file is **deleted automatically** after frame extraction to save disk space (200MB–1GB per run). Only frames, transcript, and metadata are kept. Pass `--keep-video` to retain the video file.

## Frame budget — why it matters

Token cost is dominated by frames. Every frame is an image; image tokens add up fast. The script's auto-fps logic exists so you don't blow your context budget on a sparse scan of a 30-minute video that would have been better answered by a focused 30-second window.

| Duration | Default frame budget | What you get |
|----------|---------------------|--------------|
| ≤30 s | ~30 frames | Dense — basically every key moment |
| 30 s - 1 min | ~40 frames | Still dense |
| 1 - 3 min | ~60 frames | Comfortable |
| 3 - 10 min | ~80 frames | Sparse but workable |
| > 10 min | 100 frames (capped modes) | "Sparse scan" warning — re-run focused, or `--detail token-burner` for full uncapped coverage |

When the user names a moment ("around 2:30", "the last 30 seconds", "from 0:45 to 1:00"), pass `--start` / `--end`. Focused mode gets denser per-second budgets, capped at 2 fps. Far more useful than a sparse pass over the whole thing.

## Frame deduplication

Frame selection — keyframes (`efficient`), scene-change detection (`balanced`/`token-burner`), or the uniform sampler it falls back to — can still surface near-identical frames: a screen recording that holds one slide for 90 seconds produces a dozen, each billed as a separate image. A dedup pass drops them before frames reach Hermes. It runs by default on every frame mode (`--no-dedup` turns it off):

1. One `ffmpeg` call scales each extracted JPEG to a 16×16 grayscale thumbnail. Everything after is pure-stdlib Python — no image libraries.
2. For each frame, compute the **mean absolute difference** against the *last frame that was kept* (average per-pixel brightness change, 0–255 scale).
3. If that difference is at or below the threshold (`2.0`), the frame is a near-duplicate and is dropped. Otherwise it's kept and becomes the new reference.
4. The frame-budget cap applies *after* dedup, so the budget is spent on distinct frames.

Comparing against the last *kept* frame (not the previous one) catches slow fades that never trip a frame-to-frame threshold. The threshold is deliberately low and measures absolute brightness rather than structure, so a one-line code diff, a terminal scrolling a row, or two differently-colored flat slides all survive. The *Frames* line reports what was collapsed, e.g. `6 selected from 14 candidates (… 8 near-duplicates dropped …)`. On always-moving footage nothing is dropped and you pay what you would have anyway.

## Detail modes — measured

The `--detail` dial trades speed and token cost for visual fidelity.

| Mode | Engine | Frames | Cap | Extraction time | Est. image tokens |
|------|--------|--------|-----|-----------------|-------------------|
| `transcript` | none (captions) | 0 | — | **~4.5 s** (one yt-dlp call, no download) | 0 (text only) |
| `efficient` | keyframe (`-skip_frame nokey`) | 50 | 50 | **~0.5 s** | **~9.8k** |
| `balanced` | scene-change | 100 | 100 | **~20.9 s** | **~19.7k** |
| `token-burner` | scene-change | 116 | uncapped | **~21.0 s** | **~22.8k** |

- **Image tokens** use Anthropic's `(width × height) / 750` — at the default 512px width these 720p frames are 512×288, **≈197 tokens/frame**; `--resolution 1024` roughly 4× that. The transcript is surfaced in every captioned mode and on long videos is often the larger cost.
- **One sampling rule across frame modes.** Each detects all candidates across the full range, then even-samples (first + last always kept) down to its cap. The modes differ only in candidate *source* (keyframes vs. scene cuts) and cap, never in how coverage is spread — so the last frame always lands at the end, not partway through.
- **`efficient` is the speed tier** (~0.5 s) — it only reconstructs keyframes, so it's ~40× faster than the scene modes, which decode every frame to find cuts. It can also return *more* frames than `balanced` on low-motion footage (keyframes outnumber scene cuts); "efficient" means fast extraction, not fewer frames.
- **`token-burner` only diverges from `balanced` past the cap.** This clip had 116 cuts, so `balanced` sampled 100 and `token-burner` kept all 116. On high-motion video with hundreds of cuts, `token-burner` keeps everything (and trips the >250-frame token warning) while `balanced` thins to 100.

## Install

| Surface | Install |
|---------|---------|
| **Hermes Agent** | `hermes skill install watch` |
| **Manual / dev** | `git clone` then symlink `skills/watch` into your skills dir |

### Hermes Agent

```bash
hermes skill install watch
```

### Manual (developer)

Clone the repo and symlink the self-contained skill folder into your skills directory — the symlink keeps the install in sync with your working tree as you edit:

```bash
git clone https://github.com/m1crodevil/hermes-video.git
ln -s "$(pwd)/hermes-video/skills/watch" ~/.hermes/skills/content-creation/watch
```

## First run

On the first `/watch` call, the skill runs `scripts/setup.py --check`. If `ffmpeg` / `yt-dlp` aren't on your PATH, or no Whisper API key is set, it walks you through fixing it:

- **macOS** — auto-runs `brew install ffmpeg yt-dlp`.
- **Linux (Debian/Ubuntu)** — auto-installs ffmpeg via `apt` (sudo), yt-dlp as standalone binary, deno via install script, curl_cffi via pip. `~/.local/bin` and `~/.deno/bin` auto-added to PATH.
- **Linux (no sudo)** — yt-dlp + deno install to user directories; ffmpeg needs manual install.
- **Windows** — prints the `winget` / `pip` commands.
- **YouTube 2026+** — auto-creates `~/.config/yt-dlp/config` with `--impersonate chrome --js-runtimes deno` for YouTube video downloads.
- **API key** — scaffolds `~/.config/watch/.env` (mode `0600`) with commented placeholders for `GROQ_API_KEY` (preferred) and `OPENAI_API_KEY`.

After setup, preflight is silent and `/watch` just works. The check is a sub-100ms lookup, so it doesn't slow you down on subsequent runs.

## Bring your own keys

Captions cover the majority of public videos for free. The Whisper fallback only kicks in when a video genuinely has no caption track — typically local files, TikToks, some Vimeos, and the occasional caption-less YouTube upload.

| Capability | What you need | Cost |
|------------|---------------|------|
| Download + native captions | `yt-dlp` + `ffmpeg` | Free |
| Whisper fallback (preferred) | [Groq API key](https://console.groq.com/keys) — `whisper-large-v3` | Cheap, fast |
| Whisper fallback (alt) | [OpenAI API key](https://platform.openai.com/api-keys) — `whisper-1` | Standard pricing |
| Disable Whisper entirely | `--no-whisper` | Free, frames-only when no captions |

## Usage

```
/watch https://youtu.be/dQw4w9WgXcQ what happens at the 30 second mark?
/watch https://www.tiktok.com/@user/video/123 summarize this
/watch ~/Movies/screen-recording.mp4 when does the UI break?
/watch https://vimeo.com/123 what tools does she mention?
```

Focused on a specific section — denser frame budget, lower token cost:

```
/watch https://youtu.be/abc --start 2:15 --end 2:45
/watch video.mp4 --start 50 --end 60
/watch "$URL" --start 1:12:00            # from 1h12m to end
```

Other knobs (passed to `scripts/watch.py`):

- `--detail transcript|efficient|balanced|token-burner` — fidelity/speed dial. `transcript` skips frames (transcript only); `efficient` uses fast keyframes (cap 50); `balanced` uses scene-aware frames (cap 100); `token-burner` is scene-aware and uncapped.
- `--timestamps T1,T2,…` — grab a frame at each absolute timestamp (`SS`/`MM:SS`/`HH:MM:SS`). Hermes reads the transcript first, then targets the moments the presenter flags ("look here", "as you can see"). Added on top of the detail frames (reserved against the cap); out-of-window cues are dropped in focus mode; with `--detail transcript` these become the only frames.
- `--max-frames N` — lower the frame cap for a tighter token budget.
- `--resolution W` — bump frame width to 1024 px when Hermes needs to read on-screen text (slides, terminals, code).
- `--fps F` — override the auto-fps calculation (still capped at 2 fps).
- `--output markdown|json|both` — output format. `markdown` (default) = structured report to stdout with metadata tables, frame timeline, and transcript. `json` = writes `report.json` to the work directory with validated Pydantic models (metadata, frames, transcript segments with word-level timing). `both` = markdown to stdout + JSON file.
- `--whisper groq|openai` — force a specific Whisper backend.
- `--no-whisper` — disable transcription entirely; frames only.
- `--no-dedup` — keep near-duplicate frames. By default a frame-delta pass drops frames that are visually near-identical to the one before them (held slides, static screen recordings, paused video), so the frame budget is spent on distinct content; this flag turns that off.
- `--keep-video` — keep the downloaded video file after frame extraction. By default, the video is deleted automatically to save disk space (200MB–1GB per run). Only the extracted frames, transcript, and metadata are kept.
- `--out-dir DIR` — keep working files somewhere specific (default: auto-generated tmp dir).

## Limits

- **Long-video accuracy depends on the detail mode.** On the capped modes (`efficient`, default `balanced`) coverage thins out past ~10 minutes — the frame cap spreads across the whole clip, so the script prints a "sparse scan" warning and you're better off re-running focused with `--start`/`--end`. `token-burner` lifts the cap and keeps *every* scene-change frame across the full video, so it stays complete on longer clips at the cost of more image tokens. The 10-minute mark is guidance for the capped modes, not a hard ceiling.
- **Detail is one dial.** Defaults are balanced: scene-aware frames, 2 fps max, 100-frame cap. Use `--detail efficient` for a fast 50-frame keyframe pass, or `--detail token-burner` for uncapped scene candidates. Set `WATCH_DETAIL` in `~/.config/watch/.env` to change the default.

## Structured output

Every `/watch` run produces a validated Pydantic `WatchReport` model containing all pipeline data. This enables two output modes:

**Markdown** (default) — structured report with metadata table, frame timeline, and timestamped transcript. Human-readable, renders well in Telegram/Slack.

**JSON** (`--output json` or `--output both`) — writes `report.json` to the work directory. Machine-readable, ready for downstream pipelines (clipping tools, moment detection, content analysis).

```json
{
  "metadata": {
    "source": "https://youtu.be/...",
    "title": "Video Title",
    "duration": 120.0,
    "duration_fmt": "02:00",
    "resolution": "1280x720"
  },
  "frames": [
    {
      "path": "/tmp/watch-xxx/frames/frame_0001.jpg",
      "timestamp": 10.0,
      "timestamp_fmt": "00:10",
      "reason": "scene-change"
    }
  ],
  "transcript_segments": [
    {
      "start": 10.0,
      "end": 12.0,
      "text": "spoken text here",
      "words": [
        {"word": "spoken", "start": 10.0, "confidence": 0.95}
      ]
    }
  ]
}
```

**Models:** `WatchReport`, `VideoMetadata`, `Frame`, `FrameStats`, `TranscriptSegment`, `WordTiming`, `FocusRange` — all defined in `scripts/models.py` with full type validation and computed fields (`duration_fmt`, `timestamp_fmt`, `resolution`).

## Structure

```
.
├── skills/watch/
│   ├── SKILL.md                  # skill contract
│   ├── assets/
│   │   ├── README.md             # skill-specific README
│   │   └── CHANGELOG.md          # version history
│   └── scripts/
│       ├── watch.py              # entry point
│       ├── models.py             # Pydantic models (WatchReport, Frame, Transcript, etc.)
│       ├── download.py           # yt-dlp wrapper
│       ├── frames.py             # ffmpeg frame extraction
│       ├── transcribe.py         # VTT/JSON3 parsing + Whisper orchestration
│       ├── whisper.py            # Groq / OpenAI clients
│       ├── language.py           # subtitle language detection
│       ├── config.py             # shared config
│       └── setup.py              # preflight + installer
├── tests/
│   └── test_models.py            # Pydantic model unit tests (30 tests)
├── install.sh                    # install script
└── LICENSE                       # MIT
```

## Develop

```bash
# Run the model unit tests
python3 tests/test_models.py

# Or with pytest
python3 -m pytest tests/ -v

# Build the skill bundle
bash skills/watch/scripts/build-skill.sh
```

## Open source

MIT license. Built on `yt-dlp`, `ffmpeg`. Whisper transcription via [Groq](https://groq.com) or [OpenAI](https://openai.com).

Original: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)

---

[github.com/m1crodevil/hermes-video](https://github.com/m1crodevil/hermes-video) · [LICENSE](LICENSE)
