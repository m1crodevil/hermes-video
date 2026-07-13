# YouTube 429 Rate Limit — Subtitle Download Issue

## Problem Summary

YouTube rate-limits subtitle (caption) downloads, causing HTTP 429 "Too Many Requests" errors. This is a **known open issue** in yt-dlp: [#13831](https://github.com/yt-dlp/yt-dlp/issues/13831) (Jul 2025, still OPEN as of Jul 2026).

## Root Cause

YouTube's `timedtext` endpoint enforces rate limits on:
1. **Consecutive requests from same IP** — multiple `yt-dlp` calls to same video in quick succession
2. **Session age requirement** — auto-translated subs need an "aged" session
3. **Missing PO Token** — requests without proof-of-origin tokens are less trusted

## How It Manifests in /watch

The script makes **two separate yt-dlp calls** to the same video:
1. `fetch_captions()` — `--skip-download --write-auto-subs` → subtitle #1 ✅
2. `download_url()` — `--write-auto-subs` again → subtitle #2 ❌ (429)

**Critical bug:** When download #2 fails with 429, yt-dlp **deletes the file from download #1** because it considers the subtitle write failed. Result: no transcript at all.

## Workarounds (in order of effectiveness)

### 1. Use browser cookies (best — subtitle-only, NOT video download)
```bash
yt-dlp --cookies-from-browser chrome ...
```
Authenticated sessions have higher rate limits. **CRITICAL PITFALL:** cookies + deno works for subtitle downloads, but causes HTTP 403 on video downloads because YouTube returns authenticated format URLs that expire quickly. **Solution:** Only use cookies in `fetch_captions()` for subtitle download, NOT in `download_url()` for video download. The `_cookie_opts()` helper auto-gates: returns cookie flags only when both Chrome cookies AND deno are present.

### 2. Add sleep between subtitle requests
```bash
yt-dlp --sleep-subtitles 3 ...
```
Delays 3 seconds between subtitle downloads. Available in yt-dlp >= 2024.

### 3. Skip re-download if subtitle already exists ✅ IMPLEMENTED
`download_url()` receives `existing_subtitle` from `fetch_captions()` and skips `--write-auto-subs` entirely. This is the primary fix — eliminates the double-request that caused 429.

### 4. PO Token provider (advanced)
```bash
yt-dlp --extractor-args "youtube:po_token=web.gvs+XXX" ...
```
Requires setting up a PO Token provider plugin. See [PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide).

### 5. Deno JS runtime (required for cookies to work)
```bash
curl -fsSL https://deno.land/install.sh | sh
```
Without deno, yt-dlp cannot solve YouTube's n-signature challenges, causing "Only images available" errors. With cookies but without deno, format extraction fails completely.

### 6. EJS remote components (for deno challenge solving)
```bash
yt-dlp --remote-components ejs:github --skip-download URL
```
Downloads the challenge solver library from GitHub. Required for deno to solve YouTube JS challenges. First download caches locally.

## Anti-429 Architecture (implemented in v0.5.0)

```
fetch_captions()                    download_url()
  │                                    │
  ├─ cookies from Chrome?              │
  ├─ deno available?                   ├─ existing_subtitle provided?
  │  ├─ YES: add --cookies-from-browser│  ├─ YES: skip --write-auto-subs ✅
  │  └─ NO: no cookies                 │  └─ NO: download subtitles (first time)
  ├─ --sleep-subtitles 3               │
  ├─ --sub-format json3/best           ├─ NO cookies (prevents 403 on video)
  ├─ --write-subs + --write-auto-subs  ├─ --sleep-subtitles 3
  └─ Return subtitle_path ────────────→└─ Return video_path + subtitle_path
```

## Status

- Issue: yt-dlp#13831 (OPEN)
- Related PR: yt-dlp#15709 (Wait for session to age before downloading auto-translated subs)
- yt-dlp version: stable@2025.07.21+
- Affected: auto-generated subtitles on YouTube
- Manual subtitles less affected (different endpoint behavior)
