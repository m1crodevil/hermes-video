# YouTube 403 Forbidden — Deno + curl_cffi Requirements (2026+)

## Problem

YouTube video downloads return `ERROR: unable to download video data: HTTP Error 403: Forbidden` while metadata + subtitles download fine.

## Root Cause (2026)

YouTube now enforces two requirements for video stream access:

1. **JavaScript runtime (Deno)** — Required for challenge solving during format extraction. Without it, yt-dlp can fetch metadata and subtitles but the video stream URLs are invalid/expired.
2. **Browser impersonation (curl_cffi)** — Required to bypass bot detection on video download requests. Without it, YouTube identifies yt-dlp as a bot and blocks the stream.

Both are needed. Having only one may partially work (subtitles still download without either).

## Symptoms

- `yt-dlp --write-info-json` works (metadata OK)
- `yt-dlp --write-auto-subs` works (subtitles OK)
- `yt-dlp` video download fails with 403
- Warning: `No supported JavaScript runtime could be found`
- Warning: `no impersonate target is available`

## Fix

### Install Deno
```bash
curl -fsSL https://deno.land/install.sh | sh
# Add to PATH (add to ~/.bashrc):
export PATH="$HOME/.deno/bin:$PATH"
```

### Install curl_cffi
```bash
# On Ubuntu 24.04+ (PEP 668):
uv pip install --system curl-cffi
# Or:
pip install --break-system-packages curl-cffi
```

### yt-dlp config (auto-created by setup.py)
`~/.config/yt-dlp/config`:
```
--impersonate
chrome
--js-runtimes
deno
```

### download.py usage
The skill's `download.py` auto-detects both and passes flags to yt-dlp:
```python
# _yt_dlp_network_opts() returns:
["--js-runtimes", "deno", "--impersonate", "chrome", "--cookies-from-browser", "chrome"]
```

## setup.py Integration

`setup.py` v1.5.0+ auto-installs both on Linux:
- `_install_deno()` — curl install script, auto-adds to PATH
- `_install_curl_cffi()` — uv/pip install
- `_ensure_ytdlp_config()` — creates yt-dlp config
- `_warn_ytdlp_deps()` — prints hints if auto-install fails

## Relationship to Throttling

See `youtube-download-throttling.md` for speed issues. The 403 is a **hard block** (download fails entirely), while throttling is **slow speeds** (download succeeds but slowly). Both are improved by impersonation, but 403 requires Deno specifically.

## Verification

```bash
# Check deno
which deno && deno --version

# Check curl_cffi
python3 -c "import curl_cffi; print(curl_cffi.__version__)"

# Check yt-dlp config
cat ~/.config/yt-dlp/config

# Test download
yt-dlp --impersonate chrome --js-runtimes deno -f "best[height<=720]" URL
```
