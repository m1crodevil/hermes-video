# Implementation Plan: Integrate boul2gom/yt-dlp into /watch download.py

> Status: Plan complete, awaiting implementation
> Created: 2026-07-10

## What is boul2gom/yt-dlp?

Rust crate (v2.7.2, 156★, 47 forks) at `github.com/boul2gom/yt-dlp` and `crates.io/crates/yt-dlp`:
- Wraps yt-dlp for metadata extraction (format info, subtitles, etc.)
- Uses its own **Rust-native Tokio async downloader** with parallel HTTP segments
- Auto-downloads yt-dlp + ffmpeg binaries (no manual dependency management)
- Rich API: `fetch_video_infos()`, `download_video()`, `download_subtitle()`, `download_storyboard()`
- Optional features: hooks, webhooks, statistics, caching, live recording/streaming
- License: GPL-3.0 (compatible with yt-dlp)

**No Python bindings exist** — purely a Rust crate. No PyO3, no PyOxidizer.

## Recommended Approach: Rust CLI Binary (`watch-dl`)

Build a thin Rust CLI that wraps boul2gom/yt-dlp and exposes two subcommands:
- `watch-dl fetch` — metadata + subtitles (replaces `fetch_captions()` for subtitles stays on yt-dlp CLI)
- `watch-dl download` — video+audio via parallel HTTP segments (replaces `download_url()`)

Python calls it via `subprocess.run()` — same pattern as current code.

### Why not PyO3 bindings?
- No existing bindings — must build from scratch
- PyO3 + Tokio integration is non-trivial
- Overkill for a subprocess-based workflow
- boul2gom API is still evolving (v2.7.2, "still in development")

### Architecture

```
Python download.py
  ├── fetch_captions()     → yt-dlp CLI (unchanged, fast <5s, JSON3-specific)
  ├── download_url()       → watch-dl download (parallel HTTP segments, 3-10× faster)
  └── download()           → routes based on WATCH_DOWNLOAD_BACKEND env var
```

## Config

Add to `~/.config/watch/.env`:
```bash
WATCH_DOWNLOAD_BACKEND=auto  # auto|yt-dlp|watch-dl
```

- `auto` — prefer watch-dl if available, fall back to yt-dlp
- `yt-dlp` — force standard yt-dlp (current behavior)
- `watch-dl` — force boul2gom/yt-dlp (error if not installed)

## Key Design Decisions

1. **Subtitles stay on yt-dlp CLI** — JSON3 format is yt-dlp-specific, subtitle fetch is <5s, no benefit from parallel segments for a few KB
2. **Only video download switches** — this is the bottleneck (30s–20min depending on length)
3. **Graceful fallback** — if watch-dl fails, automatically retry with yt-dlp
4. **No binary conflict** — boul2gom auto-downloads its own yt-dlp copy; the skill's setup.py also installs yt-dlp CLI. Both can coexist.

## File Changes

| File | Action | Lines Changed |
|------|--------|---------------|
| `scripts/download.py` | MODIFY | +40 lines (backend detection + watch-dl path) |
| `scripts/setup.py` | MODIFY | +20 lines (install watch-dl binary) |
| `references/youtube-download-throttling.md` | MODIFY | Update boul2gom section |
| `SKILL.md` | MODIFY | Update "Future" → "Integrated" |
| Rust project (external) | CREATE | `~/watch-dl/` — CLI wrapper binary |

## Rust CLI Dependencies

```toml
[dependencies]
yt-dlp = { version = "2.7", features = ["hooks", "statistics"] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
clap = { version = "4", features = ["derive"] }
anyhow = "1"
```

## Rollback

Immediate: set `WATCH_DOWNLOAD_BACKEND=yt-dlp` in `~/.config/watch/.env`
Code: `git checkout scripts/download.py`
Binary: `rm ~/.local/bin/watch-dl`

## Success Criteria

1. Video download speed ≥3× faster than yt-dlp for videos >5 min
2. All existing `/watch` flags work unchanged
3. Subtitle extraction unchanged (still uses yt-dlp CLI)
4. Graceful fallback to yt-dlp if watch-dl fails
5. Binary size <100MB
