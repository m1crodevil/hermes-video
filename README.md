# /watch

> Give Hermes the ability to watch any video.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Hermes Agent](https://img.shields.io/badge/Hermes-Agent-purple)](https://hermes-agent.nousresearch.com)
[![GitHub stars](https://img.shields.io/github/stars/m1crodevil/hermes-video)](https://github.com/m1crodevil/hermes-video/stargazers)

Hermes can read a webpage, run a script, browse a repo. What it can't do, out of the box, is *watch a video*. You paste a YouTube link and it has to either guess from the title or pull a transcript that's missing 90% of what's on screen.

With `/watch`, you paste a URL or a local path, ask a question, and Hermes fetches captions, downloads only what it needs, extracts frames, pulls a timestamped transcript, and analyzes everything. By the time it answers, it has *seen* the video and *heard* the audio.

```bash
hermes skill install watch
```

Zero config to start. `yt-dlp` and `ffmpeg` install on first run. Captions cover most public videos for free. Whisper API key is only needed when a video has no captions.

---

## Use Cases

**Analyze someone else's content.** `/watch https://youtu.be/<video> what hook did they open with?` Hermes looks at the first frames, reads the opening transcript, breaks down the structure. Same for ad creative, competitor launches, podcast intros -- anything where the *how* matters as much as the *what*.

**Diagnose a bug from a video.** Someone sends you a screen recording of something broken. `/watch bug-repro.mov what's going wrong?` Hermes watches the recording, finds the frame where the issue appears, describes what's on screen, often catches the cause without you ever opening the file.

**Summarize a video.** `/watch https://youtu.be/<long-thing> summarize this` pulls the structure, the key moments, what was actually said and shown. Faster than watching at 2x.

**Cut the hype out of an update video.** `/watch https://youtu.be/<launch-video> what's actually new -- skip the hype` Strip a "game-changer" feature drop down to the few things that matter.

**Turn a playlist into notes.** `/watch https://youtu.be/<video> summarize this to a note` Run it across a series and file a per-video summary, so a channel or course becomes a searchable set of notes instead of hours you have to sit through.

---

## How It Works

1. **You paste a video and a question.** URL (anything yt-dlp supports -- YouTube, Loom, TikTok, X, Instagram, plus a few hundred more) or a local path (`.mp4`, `.mov`, `.mkv`, `.webm`).
2. **`yt-dlp` checks captions first.** At `transcript` detail, captioned URLs return without downloading video. Otherwise, or when Whisper needs audio, it downloads only what the run needs.
3. **`ffmpeg` extracts frames at the chosen detail.** `efficient` decodes keyframes only (near-instant); `balanced`/`token-burner` prefer scene-change frames and fall back to the duration-aware uniform sampler when they under-produce. JPEGs are 512px wide by default and clamped to 1998px tall for Hermes Read compatibility.
4. **The transcript comes from one of two places.** First try: `yt-dlp` pulls native captions (manual or auto-generated) from the source. Fallback: extract a mono 16 kHz 64 kbps mp3 audio clip and ship it to Whisper -- Groq's `whisper-large-v3` (preferred) or OpenAI's `whisper-1`.
5. **Frames + transcript are handed to Hermes.** The script builds a validated Pydantic `WatchReport` model from all pipeline data -- metadata, frames with timestamps and reasons, transcript segments with word-level timing.
6. **Hermes answers grounded in what's actually on screen and in the audio.** Not "based on the description" or "according to the title." It saw the frames. It heard the transcript.
7. **Cleanup.** The downloaded video file is deleted automatically after frame extraction to save disk space (200MB--1GB per run). Pass `--keep-video` to retain it.

---

## Usage

```
/watch https://youtu.be/dQw4w9WgXcQ what happens at the 30 second mark?
/watch https://www.tiktok.com/@user/video/123 summarize this
/watch ~/Movies/screen-recording.mp4 when does the UI break?
/watch https://vimeo.com/123 what tools does she mention?
```

**Focused on a specific section** -- denser frame budget, lower token cost:

```
/watch https://youtu.be/abc --start 2:15 --end 2:45
/watch video.mp4 --start 50 --end 60
/watch "$URL" --start 1:12:00            # from 1h12m to end
```

**Detail modes:**

| Mode | Speed | Frames | Best For |
|------|-------|--------|----------|
| `transcript` | Fastest | 0 | Transcript-only, no video download |
| `efficient` | ~0.5s | 50 | Quick scan, keyframes only |
| `balanced` | ~20s | 100 | General analysis (default) |
| `token-burner` | ~21s | Uncapped | Full visual coverage |

```
/watch https://youtu.be/abc --detail transcript    # transcript only
/watch https://youtu.be/abc --detail efficient     # fast keyframes
/watch https://youtu.be/abc --detail balanced      # scene-aware (default)
/watch https://youtu.be/abc --detail token-burner  # uncapped
```

**Other options:**

| Flag | Description |
|------|-------------|
| `--timestamps T1,T2,...` | Grab frames at specific timestamps |
| `--max-frames N` | Override frame cap |
| `--resolution W` | Frame width (default 512, use 1024 for on-screen text) |
| `--fps F` | Override auto-fps (max 2.0) |
| `--output markdown\|json\|both` | Output format |
| `--whisper groq\|openai` | Force Whisper backend |
| `--no-whisper` | Disable transcription |
| `--no-dedup` | Keep near-duplicate frames |
| `--keep-video` | Retain downloaded video |
| `--out-dir DIR` | Custom working directory |

---

## Frame Budget

Token cost is dominated by frames. Every frame is an image; image tokens add up fast. The script's auto-fps logic exists so you don't blow your context budget on a sparse scan of a 30-minute video that would have been better answered by a focused 30-second window.

| Duration | Default Frame Budget | Coverage |
|----------|---------------------|----------|
| 30s or less | ~30 frames | Dense |
| 30s -- 1 min | ~40 frames | Dense |
| 1 -- 3 min | ~60 frames | Comfortable |
| 3 -- 10 min | ~80 frames | Sparse but workable |
| 10+ min | 100 frames (capped) | Sparse -- re-run with `--start`/`--end` |

When the user names a moment ("around 2:30", "the last 30 seconds"), pass `--start` / `--end`. Focused mode gets denser per-second budgets, capped at 2 fps.

**Frame deduplication** runs by default. A dedup pass drops near-identical frames before they reach Hermes, so the frame budget is spent on distinct content. Use `--no-dedup` to disable.

---

## Installation

**Hermes Agent (recommended):**

```bash
hermes skill install watch
```

**Manual:**

```bash
git clone https://github.com/m1crodevil/hermes-video.git
ln -s "$(pwd)/hermes-video/skills/watch" ~/.hermes/skills/content-creation/watch
```

**First run** auto-installs dependencies:

- **macOS** -- `brew install ffmpeg yt-dlp`
- **Linux** -- `apt install ffmpeg`, yt-dlp + deno via installer
- **Windows** -- `winget` / `pip` commands printed

After setup, preflight is silent and `/watch` just works.

---

## API Keys

Captions cover the majority of public videos for free. The Whisper fallback only kicks in when a video has no caption track.

| Capability | Requirement | Cost |
|------------|-------------|------|
| Download + native captions | `yt-dlp` + `ffmpeg` | Free |
| Whisper fallback (preferred) | [Groq API key](https://console.groq.com/keys) | ~$0.04/hr |
| Whisper fallback (alt) | [OpenAI API key](https://platform.openai.com/api-keys) | Standard pricing |
| Disable Whisper | `--no-whisper` | Free, frames-only |

---

## Structured Output

Every run produces a validated Pydantic `WatchReport` model. Two output modes:

**Markdown** (default) -- structured report with metadata table, frame timeline, and timestamped transcript. Human-readable, renders well in Telegram/Slack.

**JSON** (`--output json` or `--output both`) -- machine-readable, ready for downstream pipelines.

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

Models: `WatchReport`, `VideoMetadata`, `Frame`, `FrameStats`, `TranscriptSegment`, `WordTiming`, `FocusRange` -- defined in `scripts/models.py`.

---

## Project Structure

```
.
├── skills/watch/
│   ├── SKILL.md                  # skill contract
│   ├── assets/
│   │   ├── README.md             # skill-specific README
│   │   └── CHANGELOG.md          # version history
│   └── scripts/
│       ├── watch.py              # entry point
│       ├── models.py             # Pydantic models
│       ├── download.py           # yt-dlp wrapper
│       ├── frames.py             # ffmpeg frame extraction
│       ├── transcribe.py         # caption parsing + Whisper
│       ├── whisper.py            # Groq / OpenAI clients
│       ├── language.py           # subtitle language detection
│       ├── config.py             # shared config
│       └── setup.py              # preflight + installer
├── tests/
│   └── test_models.py            # 30 unit tests
├── install.sh                    # install script
└── LICENSE                       # MIT
```

---

## Development

```bash
# Run tests
python3 -m pytest tests/ -v

# Build skill bundle
bash skills/watch/scripts/build-skill.sh
```

---

## Related Projects

- [bradautomates/claude-video](https://github.com/bradautomates/claude-video) -- Original (7.6k stars)
- [m1crodevil/hermes-video-rs](https://github.com/m1crodevil/hermes-video-rs) -- Rust rewrite (faster startup)

---

## License

MIT. Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org). Whisper transcription via [Groq](https://groq.com) or [OpenAI](https://openai.com).

Original: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)
