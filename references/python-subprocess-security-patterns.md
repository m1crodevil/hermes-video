# Python Subprocess Security Patterns

Collected from security audit of watch skill (2026-07-11). Applicable to any Python project using subprocess calls.

## 1. Always Add Timeouts (CWE-400)

**Problem:** `subprocess.run()` without `timeout` hangs forever if the child process stalls.

```python
# ❌ BAD — hangs forever on slow server
subprocess.run(cmd, capture_output=True)

# ✅ GOOD — kills after 5 minutes
subprocess.run(cmd, capture_output=True, timeout=300)
```

**Timeout guidelines by tool:**
| Tool | Recommended timeout | Reason |
|------|-------------------|--------|
| ffprobe | 120s | Metadata lookup, fast |
| ffmpeg | 600s | Frame extraction, can be slow |
| yt-dlp | 300s | Download, depends on server |
| pip install | 120s | Package download |
| curl | 60s | Single HTTP request |

**Exception handling:**
```python
try:
    result = subprocess.run(cmd, capture_output=True, timeout=300)
except subprocess.TimeoutExpired:
    print(f"Command timed out after 300s: {cmd[0]}")
    # Process is automatically killed by subprocess.run
```

## 2. Never Use `shell=True` (CWE-78)

**Problem:** `shell=True` enables shell metacharacter injection (`;`, `|`, `$()`).

```python
# ❌ BAD — shell injection possible
subprocess.run(f"curl {url} | sh", shell=True)

# ✅ GOOD — no shell interpretation
subprocess.run(["curl", "-fsSL", "-o", "script.sh", url])
subprocess.run(["sh", "script.sh"])
```

**Exception:** `curl | sh` pattern for tool installation. Fix: download to file first, then execute.

## 3. Always Use `--` Before User URLs (CWE-88)

**Problem:** URL like `https://example.com/--output /etc/passwd` injects flags.

```python
# ❌ BAD — URL could contain flags
cmd = ["yt-dlp", "-f", "best", url]

# ✅ GOOD — -- stops flag parsing
cmd = ["yt-dlp", "-f", "best", "--", url]
```

## 4. Atomic File Creation for Secrets (CWE-377)

**Problem:** `write_text()` creates file with default umask (0o644 = world-readable), then `chmod(0o600)` has a TOCTOU race window.

```python
# ❌ BAD — file is world-readable briefly
CONFIG_FILE.write_text(content)
CONFIG_FILE.chmod(0o600)  # race window here

# ✅ GOOD — file created with correct permissions atomically
fd = os.open(
    str(CONFIG_FILE),
    os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
    0o600,  # permissions set at creation
)
with os.fdopen(fd, 'w', encoding='utf-8') as f:
    f.write(content)
```

## 5. Verify Downloaded Binaries (CWE-494)

**Problem:** Downloaded executables without integrity check can be tampered.

```python
# ❌ BAD — no verification
subprocess.run(["curl", "-L", "-o", "/usr/local/bin/tool", URL])

# ✅ GOOD — verify checksum
subprocess.run(["curl", "-L", "-o", "tool", URL])
subprocess.run(["curl", "-L", "-o", "tool.sha256", URL + ".sha256"])
result = subprocess.run(["sha256sum", "-c", "tool.sha256"], capture_output=True)
if result.returncode != 0:
    raise SystemExit("Checksum verification failed!")
```

## 6. Path Safety (CWE-22)

**Problem:** User-controlled paths can escape working directory.

```python
# ❌ BAD — path traversal possible
video_path = user_input  # could be "../../etc/passwd"
subprocess.run(["ffmpeg", "-i", video_path, ...])

# ✅ GOOD — resolve and validate
video_path = Path(user_input).expanduser().resolve()
if not video_path.is_file():
    raise SystemExit(f"File not found: {video_path}")
subprocess.run(["ffmpeg", "-i", str(video_path), ...])
```

## 7. API Key Safety (CWE-200)

**Rules:**
- NEVER log API keys to stdout/stderr
- NEVER write API keys to output files (report.json, logs)
- NEVER pass API keys as subprocess arguments (visible via /proc)
- ONLY pass via HTTP Authorization headers
- Config output: `has_api_key: true/false`, never the actual key

```python
# ❌ BAD — key visible in process list
subprocess.run(["curl", "-H", f"Authorization: Bearer {api_key}", url])

# ✅ GOOD — key only in HTTP header via urllib
import urllib.request
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {api_key}")
response = urllib.request.urlopen(req)
```

## Checklist for Security Review

- [ ] All `subprocess.run()` calls have `timeout`
- [ ] No `shell=True` with user input
- [ ] All user URLs preceded by `--`
- [ ] Secret files created with `os.open()` + explicit permissions
- [ ] Downloaded binaries verified via checksum
- [ ] File paths resolved with `Path.resolve()` before use
- [ ] API keys never logged, never in output files
- [ ] No `eval()` or `exec()` on untrusted input
- [ ] JSON deserialization uses `json.loads()` (safe), not `yaml.load()` (unsafe)
