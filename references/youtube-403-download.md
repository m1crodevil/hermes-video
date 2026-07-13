# YouTube 403 Video Download — Troubleshooting Pattern

## Symptom

```
[download] Destination: video.f398.mp4
ERROR: unable to download video data: HTTP Error 403: Forbidden
yt-dlp did not produce a video file
```

Metadata, subtitles, and format listing work fine. Only the actual video stream download fails with 403.

## Root Cause (YouTube 2026+)

YouTube added three requirements for video stream access:

1. **Player client selection** — `android_vr` player client bypasses JS challenge solving entirely and is the most reliable. Format strings like `bv*[height<=720]+ba` may trigger `tv downgraded` which requires JS solving and often gets 403.
2. **JavaScript runtime** — YouTube serves a JS challenge during format extraction. Without a runtime (Deno recommended), the extracted format URLs are invalid/expired → 403 on download.
3. **Browser impersonation** — YouTube detects non-browser HTTP clients and blocks them. `curl_cffi` provides TLS fingerprint impersonation that matches Chrome.

**Priority order:** Fix #1 first (player client), then #2 (deno), then #3 (curl_cffi). Most 403 errors are player client issues, not missing dependencies.

Warning messages that confirm this:
```
WARNING: No supported JavaScript runtime could be found. Only deno is enabled by default
WARNING: The extractor specified to use impersonation for this download, but no impersonate target is available
```

## Fix

### 0. Force android_vr player client (PRIMARY FIX — v1.13.0)

Add to `_yt_dlp_network_opts()` in `download.py`:

```python
# Force android_vr player client (bypasses JS challenge)
opts += ["--extractor-args", "youtube:player_client=android_vr,web_creator"]
```

The `android_vr` client doesn't require JS challenge solving. `web_creator` is fallback.

### 1. Install Deno (JS runtime)

```bash
curl -fsSL https://deno.land/install.sh | sh
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 2. Install curl_cffi (browser impersonation)

```bash
# System Python
pip install --break-system-packages curl-cffi

# Or in a venv
uv pip install --python /path/to/venv/bin/python curl-cffi
```

### 3. yt-dlp config (auto-created by setup.py)

`~/.config/yt-dlp/config`:
```
--impersonate
chrome
--js-runtimes
deno
```

This makes the flags permanent — no need to pass them manually.

### 4. Verify

```bash
# Quick test
yt-dlp --impersonate chrome --js-runtimes deno -f "best[height<=720]" -o test.mp4 "https://youtu.be/VIDEO_ID"

# Or via setup.py
python3 ~/.hermes/skills/content-creation/watch/scripts/setup.py --json
# Check: "ytdlp_deps": {"deno": true, "curl_cffi": true}
```

## Why metadata works but download doesn't

yt-dlp uses different code paths:
- **Metadata + subtitles** → Android VR player API (no JS challenge, no impersonation needed)
- **Video stream** → Web player (requires JS challenge solving + browser fingerprint)

This is why `--detail transcript` works perfectly without deno/curl_cffi — it only needs subtitles.

## What the watch skill does

`download.py` has `_yt_dlp_network_opts()` that automatically adds:
- `--extractor-args "youtube:player_client=android_vr,web_creator"` (primary fix)
- `--js-runtimes deno` (if deno is detected — checks PATH + fallback `~/.deno/bin/deno`)
- `--impersonate chrome` (if curl_cffi is importable)
- `--cookies-from-browser chrome` (if deno present AND Chrome cookies exist)

The setup script (`setup.py`) checks both deps and reports them in `--json` output as `ytdlp_deps: {deno: bool, curl_cffi: bool}`.

## Pitfall: setup.py reports ready but download still 403

**Scenario:** `setup.py --json` shows `"deno": true` but video download still gets 403.

**Root cause:** `setup.py` and `download.py` must use the **same** deno detection logic. Both check `shutil.which("deno")` (PATH) with a fallback to `~/.deno/bin/deno` (direct file check). If one has the fallback and the other doesn't, they disagree — setup says "ready" but download doesn't pass `--js-runtimes deno`.

**Diagnosis:**
```bash
# Check if deno is in PATH
which deno

# Check if deno exists but isn't in PATH
ls -la ~/.deno/bin/deno

# Verify download.py detects it (without PATH)
python3 -c "
import shutil; from pathlib import Path
has = shutil.which('deno') is not None
if not has: has = (Path.home()/'.deno/bin/deno').is_file()
print(f'deno detected: {has}')
"
```

**Fix:** Both files must have matching detection:
```python
has_deno = shutil.which("deno") is not None
# Fallback: check ~/.deno/bin/deno directly (may not be in PATH yet)
if not has_deno:
    has_deno = (Path.home() / ".deno" / "bin" / "deno").is_file()
```

**System fix:** Add `~/.deno/bin` to PATH in `~/.bashrc` so yt-dlp can also resolve deno:
```bash
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Related Issues

- YouTube 429 rate limiting on subtitles → separate issue, see `youtube-429-rate-limit.md`
- `--cookies-from-browser chrome` alone does NOT fix 403 — cookies are for subtitle auth, not video stream auth
- Bug fixed in commit `d6fc14e`: download.py lacked the `~/.deno/bin/deno` fallback that setup.py had

## Pitfall: Player client mismatch — format string triggers wrong API

**Scenario:** `download.py` gets 403 even with deno + curl_cffi working. Manual `yt-dlp` with same flags works fine.

**Root cause:** yt-dlp selects different player APIs based on the format string:
- `bv*[height<=720]+ba/b[height<=720]/bv+ba/b` → may trigger `tv downgraded` player API → **403**
- `bestvideo[height<=720]+bestaudio/best[height<=720]` → triggers `android_vr` player API → **works**

The `android_vr` client doesn't require JS challenge solving — it's the most reliable for YouTube 2026+.

**Diagnosis:**
```bash
# See which player API yt-dlp selects
yt-dlp -v --skip-download --dump-json "https://youtu.be/VIDEO_ID" 2>&1 | grep "player API"
# Output: "Downloading android vr player API JSON" → good
# Output: "Downloading tv downgraded player API JSON" → will 403
```

**Fix — already applied in v1.13.0:**
```python
# In _yt_dlp_network_opts() — forces android_vr client
opts += ["--extractor-args", "youtube:player_client=android_vr,web_creator"]
```

**Alternative — fix the format string:**
Change `bv*[height<=720]+ba/b[height<=720]/bv+ba/b` to use `bestvideo`/`bestaudio` selectors which don't trigger the tv downgraded path. But this may select higher-quality formats than intended.

## `.mp4.webm` extension after merge

When video (mp4 container) + audio (webm/opus) are merged by yt-dlp/ffmpeg, the output file is named `.mp4.webm` instead of `.mp4`. This is cosmetic — ffmpeg reads it fine. But code expecting `.mp4` may fail to find the file. `_pick_video()` in download.py already handles `.mp4.webm` combined extensions (since v1.13.0), so this doesn't break the watch pipeline.
