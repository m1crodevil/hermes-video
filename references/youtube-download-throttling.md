# YouTube Video Download Throttling

## Problem Summary

YouTube intentionally throttles video download speeds for non-browser clients (yt-dlp, youtube-dl, etc.). This is server-side rate limiting, NOT an internet speed issue. A 15 Mbps connection may only achieve 200 KB/s–5 MB/s throughput for yt-dlp downloads.

## Evidence

Observed throttling pattern in yt-dlp output (43-minute video, 311 MB):
```
[download]   0.0% at 246.72 KiB/s  ← initial throttle
[download]   3.5% at  6.93 MiB/s   ← throttle release burst
[download]  14.1% at  78.24 KiB/s  ← throttle again
[download]  14.1% at 485.75 KiB/s  ← release
```

Speed test confirmed: 15.9 Mbps download, 14.19 Mbps upload, 9ms ping — connection is NOT the bottleneck.

## Root Cause

YouTube's server-side throttling is an anti-bot measure:
1. **Format URL expiry** — authenticated format URLs expire quickly
2. **Throughput capping** — non-browser clients get lower bandwidth allocation
3. **Chunked download penalties** — each HTTP range request is individually throttled
4. **Session fingerprinting** — missing browser fingerprint = lower priority

## Impact on /watch

| Video Length | File Size | Expected Download Time |
|-------------|-----------|----------------------|
| < 5 min | ~50-100 MB | 30-60 seconds |
| 10-20 min | ~100-200 MB | 2-5 minutes |
| 20-40 min | ~200-400 MB | 5-10 minutes |
| 40+ min | ~400+ MB | 10-20+ minutes |

## Mitigations

### 1. Default to transcript-only for long videos
For videos > 10 minutes, suggest `--detail transcript` first. Frames only needed if user specifically asks for visual analysis.

### 2. Deno + cookies (partial improvement)
Deno enables n-signature solving, which allows yt-dlp to use format URLs that are less throttled. Improvement is moderate (maybe 2-3x faster).

### 3. yt-dlp impersonation (best current solution)
```bash
pip install curl_cffi
yt-dlp --impersonate chrome ...
```
Makes yt-dlp requests look like real Chrome browser requests. Significantly reduces throttling. Requires `curl_cffi` Python package.

### 4. boul2gom/yt-dlp Rust wrapper (plan ready → see `references/plan-b2gom-integration.md`)
Rust library at `github.com/boul2gom/yt-dlp` that:
- Uses yt-dlp for metadata extraction only
- Downloads format streams via parallel HTTP segments (bypasses yt-dlp sequential engine)
- Async Tokio-based, non-blocking
- Auto-installs yt-dlp + ffmpeg dependencies
- No Python bindings — Rust CLI binary (`watch-dl`) called via subprocess
- Subtitles stay on yt-dlp CLI (JSON3 is yt-dlp-specific); only video download switches

**Status:** Implementation plan complete. Ready to build `watch-dl` Rust CLI wrapper and add `WATCH_DOWNLOAD_BACKEND` config to `download.py`. See `references/plan-b2gom-integration.md`.

### 5. PO Token provider
```bash
yt-dlp --extractor-args "youtube:po_token=web.gvs+XXX" ...
```
Proof-of-origin tokens make requests appear more legitimate.

## User Expectations

When a user runs `/watch` on a long video:
1. **Warn before download**: "Video X minutes (Y MB). Download may take Z minutes due to YouTube throttling."
2. **Offer alternatives**: "Use `--detail transcript` for faster results without frames."
3. **Show progress**: The download progress bar helps, but ETA is unreliable due to throttling.
