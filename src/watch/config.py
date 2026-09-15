"""Shared configuration / environment helpers."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "watch"
CONFIG_FILE = CONFIG_DIR / ".env"


def read_env_key(name: str) -> str | None:
    """Read a key from the process environment or ~/.config/watch/.env."""
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()

    config_file = Path.home() / ".config" / "watch" / ".env"
    if not config_file.exists():
        return None

    try:
        for line in config_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw = line.partition("=")
            if key.strip() != name:
                continue
            raw = raw.strip()
            if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
                raw = raw[1:-1]
            return raw or None
    except OSError:
        return None
    return None


def load_api_key(preferred: str | None = None) -> tuple[str, str] | tuple[None, None]:
    """Return (backend, api_key). Prefers Groq, falls back to OpenAI."""
    candidates = (("GROQ_API_KEY", "groq"), ("OPENAI_API_KEY", "openai"))
    if preferred is not None:
        candidates = tuple(c for c in candidates if c[1] == preferred)

    for key_name, backend in candidates:
        value = read_env_key(key_name)
        if value:
            return backend, value

    return None, None


# ---------------------------------------------------------------------------
# yt-dlp network opts (parity with hermes-video-rs download.rs)
# ---------------------------------------------------------------------------

def _has_deno() -> bool:
    return shutil.which("deno") is not None or Path.home().joinpath(".deno/bin/deno").is_file()


def _has_curl_cffi() -> bool:
    try:
        result = shutil.which("yt-dlp")
        if not result:
            return False
        import subprocess
        out = subprocess.run(
            ["yt-dlp", "--list-impersonate-targets"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return "Chrome" in out.stdout and "unavailable" not in out.stdout
    except Exception:
        return False


def ytdlp_network_opts(use_cookies: bool = False, cookies_file: str | None = None) -> list[str]:
    """Build yt-dlp flags for reliable YouTube 2026+ downloads."""
    opts: list[str] = []

    if _has_deno():
        opts.extend(["--js-runtimes", "deno"])

    if _has_curl_cffi():
        opts.extend(["--impersonate", "chrome"])

    opts.extend(["--extractor-args", "youtube:player_client=mweb"])

    if cookies_file:
        opts.extend(["--cookies", cookies_file])
        opts.extend(["--extractor-args", "youtube:player_client=web"])
    elif use_cookies:
        opts.extend(["--cookies-from-browser", "chrome"])
        opts.extend(["--extractor-args", "youtube:player_client=web"])

    return opts
