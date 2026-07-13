# YouTube 2026 Video Download Requirements

## The Problem

Starting mid-2025, YouTube requires two things for video stream downloads (not just metadata/subtitles):

1. **JavaScript runtime** (Deno recommended) — for challenge solving during format extraction
2. **Browser impersonation** (curl_cffi) — to bypass bot detection

Without these:
- ✅ Metadata loads (title, description, thumbnails)
- ✅ Subtitles/captions download (JSON3, VTT)
- ❌ **Video stream returns HTTP 403 Forbidden**

## Symptoms

```
[youtube] Extracting URL: https://youtu.be/...
[youtube] ...: Downloading webpage
WARNING: No supported JavaScript runtime could be found.
WARNING: The extractor specified to use impersonation, but no impersonate target is available.
ERROR: unable to download video data: HTTP Error 403: Forbidden
```

Key indicator: metadata + subtitles work, but video download fails with 403.

## Required Dependencies

| Dependency | Purpose | Install | Check |
|------------|---------|---------|-------|
| **Deno** | JS runtime for YouTube challenge solving | `curl -fsSL https://deno.land/install.sh \| sh` | `which deno` |
| **curl_cffi** | Browser impersonation (bypasses bot detection) | `pip install --break-system-packages curl-cffi` | `python3 -c "import curl_cffi"` |

After installing Deno, add to PATH:
```bash
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## yt-dlp Flags Required

```bash
# These flags must be passed to ALL yt-dlp calls:
--impersonate chrome          # requires curl_cffi
--js-runtimes deno            # requires deno
--cookies-from-browser chrome # optional, requires deno + Chrome cookies
```

### Global Config (recommended)

Create `~/.config/yt-dlp/config`:
```
--impersonate
chrome
--js-runtimes
deno
```

This makes the flags apply automatically to every yt-dlp invocation.

## Detection in Code

```python
import shutil

def _yt_dlp_network_opts() -> list[str]:
    """Network-related yt-dlp flags for YouTube 2026+."""
    opts = []
    has_deno = shutil.which("deno") is not None

    if has_deno:
        opts += ["--js-runtimes", "deno"]

    try:
        import curl_cffi  # noqa: F401
        opts += ["--impersonate", "chrome"]
    except ImportError:
        pass

    if has_deno and _has_chrome_cookies():
        opts += ["--cookies-from-browser", "chrome"]

    return opts
```

## Setup.py Detection

```python
def _check_ytdlp_deps() -> dict[str, bool]:
    """Check YouTube 2026 download deps."""
    has_deno = shutil.which("deno") is not None
    # Also check ~/.deno/bin/deno directly (may not be in PATH yet)
    if not has_deno:
        has_deno = (Path.home() / ".deno" / "bin" / "deno").is_file()
    
    has_curl_cffi = False
    try:
        import curl_cffi  # noqa: F401
        has_curl_cffi = True
    except ImportError:
        pass
    return {"deno": has_deno, "curl_cffi": has_curl_cffi}
```

## Auto-Install (Linux)

```python
def _install_deno() -> bool:
    """Install deno via official install script."""
    deno_path = Path.home() / ".deno" / "bin" / "deno"
    if deno_path.is_file():
        return True  # already installed
    
    result = subprocess.run(
        "curl -fsSL https://deno.land/install.sh | sh",
        shell=True, capture_output=True, timeout=120,
    )
    return deno_path.is_file()

def _install_curl_cffi() -> bool:
    """Install curl_cffi via uv or pip."""
    try:
        import curl_cffi
        return True  # already installed
    except ImportError:
        pass
    
    # Try uv first (no PEP 668 issues)
    if shutil.which("uv"):
        result = subprocess.run(
            ["uv", "pip", "install", "--system", "curl-cffi"],
            capture_output=True, timeout=120,
        )
        if result.returncode == 0:
            return True
    
    # Fallback to pip with --break-system-packages
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "--break-system-packages", "curl-cffi"],
        capture_output=True, timeout=120,
    )
    return result.returncode == 0
```

## Update Commands

```bash
yt-dlp -U                    # update yt-dlp (most frequent changes)
deno upgrade                 # update deno
pip install --break-system-packages --upgrade curl-cffi  # update curl_cffi
```

## References

- yt-dlp EJS wiki: https://github.com/yt-dlp/yt-dlp/wiki/EJS
- Deno install: https://docs.deno.com/runtime/getting_started/installation/
- curl_cffi: https://github.com/lexiforest/curl_cffi
