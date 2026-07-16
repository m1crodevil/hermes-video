#!/usr/bin/env python3
"""Setup / preflight for /watch.

Modes:
  setup.py --check      Silent preflight. Exit 0 if ready, 2/3/4 on failure.
  setup.py --json       Machine-readable status for Claude to parse.
  setup.py              Installer. Auto-installs deps, scaffolds .env, marks SETUP_COMPLETE.

Design:
- Silent on success: --check exits 0 with no output when everything's ready so
  that /watch doesn't spam "setup is complete" on every turn.
- Idempotent: re-running the installer is safe — it never clobbers existing
  keys and only appends missing ones.
- SETUP_COMPLETE=true in ~/.config/watch/.env tells us the user has been
  through a successful installer run at least once.
- macOS: auto-install via brew. Linux: auto-install via apt / standalone binaries.
- Never write an API key to disk automatically — only scaffold placeholders.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from watch.config import get_config  # noqa: E402


REQUIRED_BINARIES = ["ffmpeg", "ffprobe", "yt-dlp"]
CONFIG_DIR = Path.home() / ".config" / "watch"
CONFIG_FILE = CONFIG_DIR / ".env"
ENV_TEMPLATE = """# /watch API configuration
#
# Whisper transcription fallback — used only when yt-dlp cannot get captions
# (or when you point /watch at a local file with no subtitles).
#
# Groq is preferred: it runs whisper-large-v3 at a fraction of OpenAI's price
# and is faster in practice. OpenAI is the compatible fallback.
#
# Get a Groq key:  https://console.groq.com/keys
# Get an OpenAI key:  https://platform.openai.com/api-keys
#
# Leave both blank to disable Whisper — /watch will still work, but videos
# without native captions will come back frames-only.

GROQ_API_KEY=
OPENAI_API_KEY=

# Default watch behavior (the /watch first-run wizard sets this for you):
# WATCH_DETAIL=balanced            # transcript | efficient | balanced | token-burner
"""
def _write_env(content: str) -> None:
    """Write .env file atomically with 0o600 permissions.

    Avoids TOCTOU race: file is created with correct permissions
    from the start, never world-readable.
    """
    fd = os.open(str(CONFIG_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception:
        os.close(fd)
        raise


def _which(name: str) -> str | None:
    return shutil.which(name)


def _check_binaries() -> list[str]:
    return [b for b in REQUIRED_BINARIES if not _which(b)]


def _check_ytdlp_deps() -> dict[str, bool]:
    """Check YouTube 2026 download deps: deno (JS runtime) + curl_cffi (impersonation).

    Without these, metadata + subtitles still work but video download gets 403.
    """
    has_deno = _which("deno") is not None
    # Also check ~/.deno/bin/deno directly (may not be in PATH yet)
    if not has_deno:
        deno_path = Path.home() / ".deno" / "bin" / "deno"
        has_deno = deno_path.is_file()
    has_curl_cffi = False
    try:
        import curl_cffi  # noqa: F401
        has_curl_cffi = True
    except ImportError:
        pass
    return {"deno": has_deno, "curl_cffi": has_curl_cffi}


_PERM_WARNED: set[str] = set()


def _check_file_permissions(path: Path) -> None:
    """Warn to stderr (once per path per process) if a secrets file is
    world/group readable."""
    key = str(path)
    if key in _PERM_WARNED:
        return
    try:
        mode = path.stat().st_mode
        if mode & 0o044:
            _PERM_WARNED.add(key)
            sys.stderr.write(
                f"[watch] WARNING: {path} is readable by other users. "
                f"Run: chmod 600 {path}\n"
            )
            sys.stderr.flush()
    except OSError:
        pass


_PLACEHOLDER_PATTERNS = (
    "your_", "your-", "YOUR_", "YOUR-",
    "changeme", "CHANGEME", "ChangeMe",
    "sk-your", "sk-your-",  # common API key prefixes with placeholder
)
# Values that are NOT placeholders even though they're short
_VALID_NON_PLACEHOLDERS = {"true", "false", "yes", "no"}


def _is_placeholder(value: str) -> bool:
    """Return True if *value* looks like a template/placeholder rather
    than a real credential.  The default .env template ships with
    ``your_groq_api_key_here``, ``your_opencode_api_key_here``, etc. and
    those must be treated as unset — otherwise setup reports 'ready' and
    Whisper fails with 401."""
    stripped = value.strip().lower()
    if not stripped:
        return True
    if stripped in _VALID_NON_PLACEHOLDERS:
        return False
    if any(stripped.startswith(p.lower()) for p in _PLACEHOLDER_PATTERNS):
        return True
    # A real production API key is never a single word under 12 chars
    # that looks like readable English.
    if len(stripped) < 12 and " " not in stripped:
        return True
    return False


def _read_env_key(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        stripped = value.strip()
        if stripped and not _is_placeholder(stripped):
            return stripped
    if not CONFIG_FILE.exists():
        return None
    _check_file_permissions(CONFIG_FILE)
    try:
        for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw = line.partition("=")
            if key.strip() != name:
                continue
            raw = raw.strip()
            if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
                raw = raw[1:-1]
            if raw and not _is_placeholder(raw):
                return raw
            return None
    except OSError:
        return None
    return None


def _have_api_key() -> tuple[bool, str | None]:
    if _read_env_key("GROQ_API_KEY"):
        return True, "groq"
    if _read_env_key("OPENAI_API_KEY"):
        return True, "openai"
    return False, None

def is_first_run() -> bool:
    """True if the installer hasn't completed successfully yet."""
    return _read_env_key("SETUP_COMPLETE") != "true"

def _scaffold_env() -> bool:
    """Create ~/.config/watch/.env with placeholders if missing."""
    if CONFIG_FILE.exists():
        return False
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _write_env(ENV_TEMPLATE)
    return True


def _write_setup_complete() -> None:
    """Idempotently append SETUP_COMPLETE=true to .env.

    Used only after a fully successful install (deps + key). Future sessions
    detect this marker to skip wizard-style UI and stay silent.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing = ""
    if CONFIG_FILE.exists():
        existing = CONFIG_FILE.read_text(encoding="utf-8")
        for line in existing.splitlines():
            if line.strip().startswith("SETUP_COMPLETE="):
                return
        if existing and not existing.endswith("\n"):
            existing += "\n"
        _write_env(existing + "SETUP_COMPLETE=true\n")
    else:
        _write_env(ENV_TEMPLATE + "\nSETUP_COMPLETE=true\n")


# ---------------------------------------------------------------------------
# macOS auto-install (brew)
# ---------------------------------------------------------------------------

def _brew_pkg(missing: list[str]) -> list[str]:
    pkgs: list[str] = []
    for bin_name in missing:
        if bin_name in ("ffmpeg", "ffprobe"):
            if "ffmpeg" not in pkgs:
                pkgs.append("ffmpeg")
        elif bin_name == "yt-dlp":
            if "yt-dlp" not in pkgs:
                pkgs.append("yt-dlp")
        else:
            pkgs.append(bin_name)
    return pkgs


def _install_macos(missing: list[str]) -> tuple[bool, str]:
    if _which("brew") is None:
        return False, (
            "Homebrew is not installed. Install it from https://brew.sh, then re-run setup. "
            "Or install manually: `brew install " + " ".join(_brew_pkg(missing)) + "`"
        )
    pkgs = _brew_pkg(missing)
    if not pkgs:
        return True, "nothing to install"
    cmd = ["brew", "install", *pkgs]
    print(f"[setup] running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        return False, f"brew install failed with exit code {result.returncode}"
    return True, f"installed via brew: {', '.join(pkgs)}"


# ---------------------------------------------------------------------------
# Linux auto-install helpers
# ---------------------------------------------------------------------------

def _has_sudo() -> bool:
    """Check if sudo is available and the current user can use it (NOPASSWD)."""
    if not _which("sudo"):
        return False
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _has_apt() -> bool:
    """Check if apt package manager is available."""
    return _which("apt") is not None


def _install_ffmpeg_linux() -> bool:
    """Install ffmpeg on Linux via apt. Returns True if already present or installed."""
    if _which("ffmpeg") is not None and _which("ffprobe") is not None:
        print("[setup] ffmpeg/ffprobe already installed", file=sys.stderr)
        return True

    if _has_apt() and _has_sudo():
        print("[setup] installing ffmpeg via apt...", file=sys.stderr)
        try:
            result = subprocess.run(
                ["sudo", "apt", "install", "-y", "ffmpeg"],
                capture_output=True, timeout=120,
            )
            if result.returncode == 0:
                print("[setup] ffmpeg installed successfully", file=sys.stderr)
                return True
            else:
                stderr = result.stderr.decode(errors="replace").strip()
                print(f"[setup] apt install ffmpeg failed: {stderr}", file=sys.stderr)
        except Exception as e:
            print(f"[setup] apt install ffmpeg error: {e}", file=sys.stderr)

    # Fallback: print manual install hint
    print("[setup] could not auto-install ffmpeg. Please install manually:", file=sys.stderr)
    print("  sudo apt install ffmpeg        # Debian/Ubuntu", file=sys.stderr)
    print("  sudo dnf install ffmpeg        # Fedora", file=sys.stderr)
    print("  sudo pacman -S ffmpeg          # Arch", file=sys.stderr)
    return False


def _install_ytdlp_linux() -> bool:
    """Install yt-dlp standalone binary on Linux. Returns True if already present or installed."""
    if _which("yt-dlp") is not None:
        print("[setup] yt-dlp already installed", file=sys.stderr)
        return True

    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    ytdlp_path = local_bin / "yt-dlp"

    print("[setup] downloading yt-dlp standalone binary...", file=sys.stderr)
    try:
        result = subprocess.run(
            ["curl", "-L", "-o", str(ytdlp_path),
             "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            print(f"[setup] yt-dlp download failed: {stderr}", file=sys.stderr)
            return False

        ytdlp_path.chmod(0o755)
        print(f"[setup] yt-dlp installed to {ytdlp_path}", file=sys.stderr)

        # Verify it works
        if _which("yt-dlp") is None:
            print("[setup] NOTE: ~/.local/bin not in PATH yet. Run: source ~/.bashrc", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[setup] yt-dlp install error: {e}", file=sys.stderr)
        return False


def _install_deno() -> bool:
    """Install deno JS runtime on Linux/macOS. Returns True if already present or installed."""
    # Check current PATH
    if _which("deno") is not None:
        print("[setup] deno already installed", file=sys.stderr)
        return True

    # Check ~/.deno/bin/deno directly (may not be in PATH yet)
    deno_path = Path.home() / ".deno" / "bin" / "deno"
    if deno_path.is_file():
        print(f"[setup] deno found at {deno_path} (add to PATH)", file=sys.stderr)
        _ensure_path()
        return True

    print("[setup] installing deno...", file=sys.stderr)
    import tempfile
    script_path = Path(tempfile.mktemp(suffix=".sh"))
    try:
        # Download script first, then execute — no shell=True, no pipe-to-shell
        result = subprocess.run(
            ["curl", "-fsSL", "-o", str(script_path), "https://deno.land/install.sh"],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            print(f"[setup] deno install failed: {stderr}", file=sys.stderr)
            return False

        result = subprocess.run(
            ["sh", str(script_path)],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            print(f"[setup] deno install failed: {stderr}", file=sys.stderr)
            return False

        if deno_path.is_file():
            print("[setup] deno installed successfully", file=sys.stderr)
            _ensure_path()
            return True
        else:
            print("[setup] deno install completed but binary not found at expected path", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[setup] deno install error: {e}", file=sys.stderr)
        return False
    finally:
        script_path.unlink(missing_ok=True)


def _install_curl_cffi() -> bool:
    """Install curl_cffi Python package. Returns True if already present or installed."""
    try:
        import curl_cffi  # noqa: F401
        print("[setup] curl_cffi already installed", file=sys.stderr)
        return True
    except ImportError:
        pass

    # Try uv first (usually available and handles --system well)
    if _which("uv") is not None:
        print("[setup] installing curl_cffi via uv...", file=sys.stderr)
        try:
            result = subprocess.run(
                ["uv", "pip", "install", "--system", "curl-cffi"],
                capture_output=True, timeout=120,
            )
            if result.returncode == 0:
                print("[setup] curl_cffi installed via uv", file=sys.stderr)
                return True
            else:
                stderr = result.stderr.decode(errors="replace").strip()
                print(f"[setup] uv install failed: {stderr}", file=sys.stderr)
        except Exception as e:
            print(f"[setup] uv install error: {e}", file=sys.stderr)

    # Fallback: pip with --break-system-packages (PEP 668 on Ubuntu 24.04+)
    print("[setup] installing curl_cffi via pip...", file=sys.stderr)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--break-system-packages", "curl-cffi"],
            capture_output=True, timeout=120,
        )
        if result.returncode == 0:
            print("[setup] curl_cffi installed via pip", file=sys.stderr)
            return True
        else:
            stderr = result.stderr.decode(errors="replace").strip()
            print(f"[setup] pip install failed: {stderr}", file=sys.stderr)
    except Exception as e:
        print(f"[setup] pip install error: {e}", file=sys.stderr)

    # Last resort: try without --break-system-packages
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "curl-cffi"],
            capture_output=True, timeout=120,
        )
        if result.returncode == 0:
            print("[setup] curl_cffi installed via pip (no --break-system-packages)", file=sys.stderr)
            return True
    except Exception:
        pass

    print("[setup] could not auto-install curl_cffi. Please install manually:", file=sys.stderr)
    print("  pip install --break-system-packages curl-cffi", file=sys.stderr)
    print("  # or: uv pip install --system curl-cffi", file=sys.stderr)
    return False


def _ensure_path() -> None:
    """Add ~/.local/bin and ~/.deno/bin to PATH in ~/.bashrc if not already there."""
    bashrc = Path.home() / ".bashrc"
    marker = "# Added by /watch setup"

    # Check what's already in PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    needs_local = str(Path.home() / ".local" / "bin") not in path_dirs
    needs_deno = str(Path.home() / ".deno" / "bin") not in path_dirs

    if not needs_local and not needs_deno:
        return

    # Check if we already added the marker to .bashrc
    if bashrc.exists():
        try:
            content = bashrc.read_text(encoding="utf-8")
            if marker in content:
                return
        except OSError:
            pass

    # Append PATH export to .bashrc
    path_entry = '\n# Added by /watch setup\nexport PATH="$HOME/.local/bin:$HOME/.deno/bin:$PATH"\n'
    try:
        with open(bashrc, "a", encoding="utf-8") as f:
            f.write(path_entry)
        print("[setup] added ~/.local/bin and ~/.deno/bin to PATH in ~/.bashrc", file=sys.stderr)
        print("[setup] run: source ~/.bashrc   (or open a new terminal)", file=sys.stderr)
    except OSError as e:
        print(f"[setup] could not update ~/.bashrc: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Linux install orchestrator
# ---------------------------------------------------------------------------

def _install_linux(missing: list[str]) -> tuple[bool, str]:
    """Auto-install missing binaries on Linux.

    Returns (success, message). Each sub-installer is idempotent.
    """
    results = []

    # 1. ffmpeg via apt
    ffmpeg_ok = _install_ffmpeg_linux()
    results.append(("ffmpeg", ffmpeg_ok))

    # 2. yt-dlp via standalone binary
    ytdlp_ok = _install_ytdlp_linux()
    results.append(("yt-dlp", ytdlp_ok))

    # 3. deno via install.sh
    deno_ok = _install_deno()
    results.append(("deno", deno_ok))

    # 4. curl_cffi via uv/pip
    curl_cffi_ok = _install_curl_cffi()
    results.append(("curl_cffi", curl_cffi_ok))

    # 5. Ensure PATH is set up
    _ensure_path()

    # Report results
    installed = [name for name, ok in results if ok]
    failed = [name for name, ok in results if not ok]

    if failed:
        msg = f"installed: {', '.join(installed)}; needs manual install: {', '.join(failed)}"
        return False, msg
    else:
        return True, f"all dependencies installed: {', '.join(installed)}"


# ---------------------------------------------------------------------------
# Windows hints (no auto-install)
# ---------------------------------------------------------------------------

def _install_hint_windows(missing: list[str]) -> str:
    pkgs = _brew_pkg(missing)
    hints = []
    if "ffmpeg" in pkgs:
        hints.append("winget: `winget install Gyan.FFmpeg`")
    if "yt-dlp" in pkgs:
        hints.append("winget: `winget install yt-dlp.yt-dlp` or pip: `pip install --user yt-dlp`")
    return "\n  ".join(hints) if hints else "nothing to install"


# ---------------------------------------------------------------------------
# yt-dlp deps
# ---------------------------------------------------------------------------

def _ensure_ytdlp_config() -> None:
    """Create ~/.config/yt-dlp/config with YouTube 2026 flags if missing."""
    ytdlp_config = Path.home() / ".config" / "yt-dlp" / "config"
    if ytdlp_config.exists():
        return
    ytdlp_config.parent.mkdir(parents=True, exist_ok=True)
    ytdlp_config.write_text(
        "--impersonate\nchrome\n--js-runtimes\ndeno\n",
        encoding="utf-8",
    )
    print(f"[setup] created yt-dlp config: {ytdlp_config}", file=sys.stderr)


def _warn_ytdlp_deps() -> None:
    """Auto-install missing deno/curl_cffi — these cause 403 on video downloads."""
    deps = _check_ytdlp_deps()
    missing = [k for k, v in deps.items() if not v]
    if not missing:
        return
    print("[setup] YouTube 2026 download deps missing — installing...", file=sys.stderr)
    if "deno" in missing:
        _install_deno()
    if "curl_cffi" in missing:
        _install_curl_cffi()
    # Re-check after install
    deps_after = _check_ytdlp_deps()
    still_missing = [k for k, v in deps_after.items() if not v]
    if still_missing:
        print(f"[setup] WARNING: could not install {', '.join(still_missing)} — video downloads may 403", file=sys.stderr)


# ---------------------------------------------------------------------------
# Status / check / install
# ---------------------------------------------------------------------------

def _status() -> dict:
    """Structured preflight snapshot.

    `status` describes the *ideal* state — a Whisper key is encouraged but
    never blocks. `can_proceed` is the operational gate: /watch can run as
    long as binaries are present. The installer marks SETUP_COMPLETE=true
    once binaries are confirmed, regardless of whether a Whisper key exists.
    """
    missing = _check_binaries()
    has_key, backend = _have_api_key()
    setup_complete = not is_first_run()
    ytdlp_deps = _check_ytdlp_deps()

    if not missing and has_key:
        status = "ready"
    elif missing and not has_key:
        status = "needs_install_and_key"
    elif missing:
        status = "needs_install"
    else:
        status = "needs_key"

    can_proceed = (not missing) and (has_key or setup_complete)

    cfg = get_config()
    return {
        "status": status,
        "can_proceed": can_proceed,
        "first_run": not setup_complete,
        "setup_complete": setup_complete,
        "missing_binaries": missing,
        "ytdlp_deps": ytdlp_deps,
        "whisper_backend": backend,
        "has_api_key": has_key,
        "config_file": str(CONFIG_FILE),
        "watch_detail": cfg["detail"],
        "platform": platform.system(),
    }


def cmd_check() -> int:
    """Silent-on-success preflight.

    Exit 0 with no output when /watch can run. The only hard blocker is
    missing binaries (ffmpeg / yt-dlp). Whisper API keys are a post-run
    fallback — the script tries JSON3 captions first and only falls back
    to Whisper when captions are missing, so a missing key never blocks
    the initial run.
    """
    missing = _check_binaries()
    if not missing:
        return 0

    installer = Path(__file__).resolve()
    sys.stderr.write(
        f"[watch] missing binaries: {', '.join(missing)}. "
        f"Run: python3 {installer}\n"
    )
    sys.stderr.flush()
    return 2

def cmd_json() -> int:
    json.dump(_status(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_install() -> int:
    missing = _check_binaries()
    installed_deps = False
    if missing:
        system = platform.system()
        if system == "Darwin":
            ok, msg = _install_macos(missing)
            print(f"[setup] {msg}", file=sys.stderr)
            if not ok:
                return 2
            still_missing = _check_binaries()
            if still_missing:
                print(f"[setup] still missing after install: {', '.join(still_missing)}", file=sys.stderr)
                return 2
            installed_deps = True
        elif system == "Linux":
            ok, msg = _install_linux(missing)
            print(f"[setup] {msg}", file=sys.stderr)
            if not ok:
                # Check if at least the hard blockers (ffmpeg, yt-dlp) are resolved
                still_missing = _check_binaries()
                if still_missing:
                    print(f"[setup] still missing: {', '.join(still_missing)}", file=sys.stderr)
                    return 2
            installed_deps = True
        elif system == "Windows":
            print("[setup] dependencies missing on Windows — please install:", file=sys.stderr)
            print("  " + _install_hint_windows(missing), file=sys.stderr)
            return 2
        else:
            print(f"[setup] unsupported platform ({system}) for auto-install. Install manually:", file=sys.stderr)
            print(f"  missing: {', '.join(missing)}", file=sys.stderr)
            return 2

    created = _scaffold_env()
    if created:
        print(f"[setup] created config: {CONFIG_FILE}")
    else:
        print(f"[setup] config exists: {CONFIG_FILE}")

    # Create yt-dlp config for YouTube 2026 (impersonate + JS runtime)
    _ensure_ytdlp_config()

    # Auto-install missing deno/curl_cffi (non-blocking)
    _warn_ytdlp_deps()

    has_key, backend = _have_api_key()

    # Binaries are present → mark setup complete. Whisper is a post-run
    # fallback, not a blocker — JSON3 captions work without any API key.
    if not missing:
        _write_setup_complete()
        if has_key:
            print(f"[setup] ready. whisper backend: {backend}")
        else:
            print("[setup] ready. no whisper key — captions-only mode (whisper fallback available if needed)")
        if installed_deps:
            print("[setup] installed dependencies; /watch is fully set up.")
        return 0

    # Binaries missing → need user action
    return 2


def main() -> int:
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--check":
            return cmd_check()
        if arg == "--json":
            return cmd_json()
    return cmd_install()


if __name__ == "__main__":
    raise SystemExit(main())
