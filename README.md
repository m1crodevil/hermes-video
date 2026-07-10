# /watch

**Give Hermes the ability to watch any video.**

Hermes Agent:

```bash
hermes skill add hermes-video
```

Or install manually:

```bash
git clone https://github.com/m1crodevil/hermes-video.git ~/.hermes/skills/video
```

Zero config to start — `yt-dlp` and `ffmpeg` install on first run via `brew` on macOS (Linux/Windows print exact commands). Captions cover most public videos for free. Whisper API key is only needed when a video has no captions.

---

Hermes can read a webpage, run a script, browse a repo. What it can't do, out of the box, is *watch a video*. You paste a YouTube link and it has to either guess from the title or pull a transcript that's missing 90% of what's on screen.

With hermes-video `/watch` you can paste a URL or a local path, ask a question, and Hermes fetches captions first, downloads only what it needs, extracts frames (scene-aware, or fast keyframes at `efficient` detail), pulls a timestamped transcript (free captions when available, Whisper API as fallback), and analyzes every frame as an image using MiMo V2.5. By the time it answers, it has *seen* the video and *heard* the audio.

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
3. **`ffmpeg` extracts frames at the chosen detail.** `efficient` decodes keyframes only (near-instant); `balanced`/`token-burner` prefer scene-change frames and fall back to the duration-aware uniform sampler when they under-produce. JPEGs are 512px wide by default and clamped to 1998px tall.
4. **The transcript comes from one of two places.** First try: `yt-dlp` pulls native captions (manual or auto-generated) from the source. Free, instant, accurate-ish. Fallback: extract a mono 16 kHz 64 kbps mp3 audio clip (~480 kB/min) and ship it to Whisper — Groq's `whisper-large-v3` (preferred — cheaper and faster) or OpenAI's `whisper-1`.
5. **Frames + transcript are handed to your agent.** The script prints frame paths with timestamps and the transcript. Your agent reads each frame as an image and combines it with the transcript.
6. **Your agent answers grounded in what's actually on screen and in the audio.** Not "based on the description" or "according to the title." It saw the frames. It heard the transcript. It answers the way someone who watched the video would.
7. **Cleanup.** The script prints a working directory at the end. If you're not asking follow-ups, delete it.

## Frame budget — why it matters

Token cost is dominated by frames. Every frame is an image; image tokens add up fast. The script's auto-fps logic exists so you don't blow your context budget on a sparse scan of a 30-minute video that would have been better answered by a focused 30-second window.

| Duration     | Default frame budget      | What you get                                                                                  |
| ------------ | ------------------------- | --------------------------------------------------------------------------------------------- |
| ≤30 s        | ~30 frames                | Dense — basically every key moment                                                            |
| 30 s - 1 min | ~40 frames                | Still dense                                                                                   |
| 1 - 3 min    | ~60 frames                | Comfortable                                                                                   |
| 3 - 10 min   | ~80 frames                | Sparse but workable                                                                           |
| > 10 min     | 100 frames (capped modes) | "Sparse scan" warning — re-run focused, or `--detail token-burner` for full uncapped coverage |

When the user names a moment ("around 2:30", "the last 30 seconds", "from 0:45 to 1:00"), pass `--start` / `--end`. Focused mode gets denser per-second budgets, capped at 2 fps. Far more useful than a sparse pass over the whole thing.

## Detail modes — measured

The `--detail` dial trades speed and token cost for visual fidelity.

| Mode           | Engine                         | Frames | Cap      | Extraction time                            | Est. image tokens      |
| -------------- | ------------------------------ | ------ | -------- | ------------------------------------------ | ---------------------- |
| `transcript`   | none (captions)                | 0      | —        | **~4.5 s** (one yt-dlp call, no download) | 0 (text only)          |
| `efficient`    | keyframe (`-skip_frame nokey`) | 50     | 50       | **~0.5 s**                                 | **~9.8k**              |
| `balanced`     | scene-change                   | 100    | 100      | **~20.9 s**                                | **~19.7k**             |
| `token-burner` | scene-change                   | 116    | uncapped | **~21.0 s**                                | **~22.8k**             |

## Install

| Surface                     | Install                                        |
| --------------------------- | ---------------------------------------------- |
| **Hermes Agent**            | `hermes skill add hermes-video`                |
| **Install script**          | `git clone` then `./install.sh`                |
| **Manual**                  | `git clone` then symlink `skills/watch` into your skills dir |

### Hermes Agent

```bash
hermes skill add hermes-video
```

### Manual (developer)

```bash
git clone https://github.com/m1crodevil/hermes-video.git
cd hermes-video
./install.sh
```

Or symlink directly:

```bash
ln -s "$(pwd)/skills/watch" ~/.hermes/skills/video
```

## First run

On the first `/watch` call, the skill runs `scripts/setup.py --check`. If `ffmpeg` / `yt-dlp` aren't on your PATH, or no Whisper API key is set, it walks you through fixing it:

- **macOS** — auto-runs `brew install ffmpeg yt-dlp`.
- **Linux** — prints the exact `apt` / `dnf` / `pipx` commands.
- **Windows** — prints the `winget` / `pip` commands.
- **API key** — scaffolds `~/.config/watch/.env` (mode `0600`) with commented placeholders for `GROQ_API_KEY` (preferred) and `OPENAI_API_KEY`.

After setup, preflight is silent and `/watch` just works.

## Bring your own keys

Captions cover the majority of public videos for free. The Whisper fallback only kicks in when a video genuinely has no caption track — typically local files, TikToks, some Vimeos, and the occasional caption-less YouTube upload.

| Capability                   | What you need                                                        | Cost                               |
| ---------------------------- | -------------------------------------------------------------------- | ---------------------------------- |
| Download + native captions   | `yt-dlp` + `ffmpeg`                                                  | Free                               |
| Whisper fallback (preferred) | [Groq API key](https://console.groq.com/keys) — `whisper-large-v3`   | Cheap, fast                        |
| Whisper fallback (alt)       | [OpenAI API key](https://platform.openai.com/api-keys) — `whisper-1` | Standard pricing                   |
| Disable Whisper entirely     | `--no-whisper`                                                       | Free, frames-only when no captions |

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

Other knobs:

- `--detail transcript|efficient|balanced|token-burner` — fidelity/speed dial.
- `--timestamps T1,T2,…` — grab a frame at each absolute timestamp.
- `--max-frames N` — lower the frame cap for a tighter token budget.
- `--resolution W` — bump frame width to 1024 px when you need to read on-screen text.
- `--fps F` — override the auto-fps calculation (still capped at 2 fps).
- `--whisper groq|openai` — force a specific Whisper backend.
- `--no-whisper` — disable transcription entirely; frames only.
- `--no-dedup` — keep near-duplicate frames.
- `--out-dir DIR` — keep working files somewhere specific.

## Limits

- **Long-video accuracy depends on the detail mode.** On the capped modes (`efficient`, default `balanced`) coverage thins out past ~10 minutes — the frame cap spreads across the whole clip, so the script prints a "sparse scan" warning and you're better off re-running focused with `--start`/`--end`. `token-burner` lifts the cap and keeps *every* scene-change frame across the full video, so it stays complete on longer clips at the cost of more image tokens.
- **Detail is one dial.** Defaults are balanced: scene-aware frames, 2 fps max, 100-frame cap. Use `--detail efficient` for a fast 50-frame keyframe pass, or `--detail token-burner` for uncapped scene candidates. Set `WATCH_DETAIL` in `~/.config/watch/.env` to change the default.

## Structure

```
.
├── skills/watch/
│   ├── SKILL.md                  # skill contract
│   └── scripts/
│       ├── watch.py              # entry point
│       ├── download.py           # yt-dlp wrapper
│       ├── frames.py             # ffmpeg frame extraction
│       ├── transcribe.py         # VTT parsing + Whisper orchestration
│       ├── whisper.py            # Groq / OpenAI clients
│       ├── config.py             # shared config
│       └── setup.py              # preflight + installer
├── tests/                        # pytest suite
├── install.sh                    # install script
└── LICENSE                       # MIT
```

## Develop

```bash
# Run the test suite
python3 -m pytest tests/ -v

# Build the skill bundle
bash skills/watch/scripts/build-skill.sh
```

## Open source

MIT license. Built on `yt-dlp`, `ffmpeg`. Whisper transcription via [Groq](https://groq.com) or [OpenAI](https://openai.com).

Original: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)

---

[github.com/m1crodevil/hermes-video](https://github.com/m1crodevil/hermes-video) · [LICENSE](LICENSE)
