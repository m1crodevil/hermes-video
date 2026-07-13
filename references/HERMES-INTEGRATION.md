# hermes-video Codebase Review

Deep analysis of the hermes-video fork (from `bradautomates/claude-video`) and its Hermes integration. Conducted 2026-07-09.

## Repo Structure

```
hermes-video/
├── SKILL.md                 # Hermes skill manifest (user-invocable)
├── scripts/
│   ├── watch.py             # Entry point — downloads, extracts, analyzes
│   ├── download.py          # yt-dlp wrapper (URL + local file)
│   ├── frames.py            # ffmpeg frame extraction (scene/keyframe/uniform)
│   ├── transcribe.py        # VTT parsing + Whisper orchestration
│   ├── whisper.py           # Groq / OpenAI Whisper API clients
│   ├── setup.py             # Preflight + installer (binaries + .env)
│   ├── config.py            # WatchConfig + env chain helpers
│   ├── env.py               # .env file parser
│   ├── types.py             # Complete type system (dataclasses + Protocols)
│   ├── video_types.py       # DUPLICATE type system (subset of types.py)
│   ├── errors.py            # Custom exception hierarchy
│   ├── opencode_client.py   # OpenCode Zen API client (MiMo V2.5)
│   ├── hermes_memory.py     # REDUNDANT — Hermes has native memory
│   └── hermes_cron.py       # REDUNDANT — Hermes has native cron
├── references/
│   ├── PLAN-REBRAND.md      # Original rebrand plan
│   ├── PLAN-MIMO.md         # MiMo integration plan
│   └── PLAN-REFACTOR.md     # Refactoring plan
└── assets/
    ├── README.md
    └── CHANGELOG.md
```

## What Was Kept from claude-video

The core video processing pipeline is proven and solid:

| Module | What it does | Why keep it |
|--------|-------------|-------------|
| `download.py` | yt-dlp download + captions fetch | Battle-tested, handles edge cases (playlists, geo-blocks, subtitle variants) |
| `frames.py` | ffmpeg scene/keyframe/uniform extraction with perceptual dedup | Complex logic, well-tested (218 tests), 4 extraction modes |
| `transcribe.py` | VTT subtitle parsing + Whisper fallback | Handles chunking, rate limits, partial transcripts |
| `whisper.py` | Groq + OpenAI Whisper API clients | Clean separation, auto-chunking for >25MB audio |

## What Was Added for Hermes

### OpenCode Zen Client (`opencode_client.py`)
- **stdlib only** (urllib.request + ssl) — no requests/httpx dependency
- SSL certificate verification enforced
- API key validation (min length, no whitespace)
- Supports: chat completions, single image, multi-frame, video messages
- Timeout on every request (configurable, max 600s)
- API key never logged or exposed in errors

### Type System (`types.py`)
- Frozen slotted dataclasses with `__post_init__` validation
- Protocol classes for swappable backends (VideoDownloader, FrameExtractor, Transcriber, AIClient)
- `WatchReport` dataclass for complete output
- Conversion helpers (dict → dataclass)

### Config (`config.py`)
- `get_opencode_config()` — loads `OPENCODE_ZEN_API_KEY` + `OPENCODE_MODEL` from env chain
- `WatchConfig` dataclass with validation
- Env priority: OS env → ~/.config/watch/.env → defaults

## Known Technical Debt

### 1. Triple Type System (HIGH)

Three files define overlapping types:

```
video_types.py ─── Frame, VideoMetadata, DownloadResult, exception classes
types.py       ─── Same + WatchConfig, WatchReport, Protocol interfaces
errors.py      ─── Same exception hierarchy (WatchError, DownloadError, etc.)
```

**Impact**: `config.py` has an inline fallback that reimplements `env.py` and `types.py` when imports fail. Modifying one file silently diverges from the others.

**Consolidation plan**:
1. Keep `types.py` as the single source of truth (most complete)
2. Keep `errors.py` for exceptions only, but have it import from `types.py` (or merge)
3. Delete `video_types.py` entirely
4. Update all imports: `from video_types import X` → `from types import X`
5. Remove the inline fallback in `config.py`

### 2. Dead Integration Modules (MEDIUM)

| Module | Problem | Solution |
|--------|---------|----------|
| `hermes_cron.py` | Writes to `~/.hermes/cron/video_analysis.json` — Hermes cron scheduler reads from `state.db`, not this file | Delete. Use `cronjob` tool or `hermes cron` CLI |
| `hermes_memory.py` | Writes to `~/.hermes/memory/video_analyses.jsonl` — Hermes memory (Hindsight, `memory` tool) reads from `state.db` | Delete. Use `hindsight_retain` or `memory` tool |

### 3. Stale Docstrings (LOW)

`errors.py` line 4: `"""Custom exceptions for claude-video."""` → should be `"hermes-video"`.

### 4. Missing Script in Bundled List

SKILL.md's "Bundled scripts" section lists only 6 scripts but there are 14. Missing:
- `config.py`, `env.py`, `types.py`, `video_types.py`, `errors.py`, `hermes_cron.py`, `hermes_memory.py`

### 5. Telegram Menu Visibility (RESOLVED)

The skill IS auto-registered as a slash command via `agent/skill_commands.py::scan_skill_commands()`. Verified:

```python
# ~/.hermes/hermes-agent/agent/skill_commands.py line 377
_skill_commands[f"/{cmd_name}"] = {
    "name": name,
    "description": description,
    "skill_md_path": str(skill_md),
    "skill_dir": str(skill_md.parent),
}
```

`/watch` appears in the scan output. **The issue is Telegram's BotCommand menu cap:**

- Default cap: 60 commands (`_DEFAULT_TELEGRAM_MENU_MAX_COMMANDS = 60`)
- Telegram hard max: 100 (`_TELEGRAM_BOT_API_MAX_COMMANDS = 100`)
- Built-in commands: ~53
- Skill slots remaining: 7 (out of 68+ skills)
- `/watch` alphabetically last → cut off

**The skill WORKS when typed directly** — `/watch <url>` dispatches correctly. Menu cap only affects the `/` picker.

**Config fix** in `~/.hermes/config.yaml`:
```yaml
platforms:
  telegram:
    extra:
      command_menu:
        max_commands: 100
        priority_mode: prepend
        priority:
          - watch
          - video-analysis-mimo
```
Source: `hermes_cli/commands.py::_telegram_command_menu_config()` reads from `platforms.telegram.extra.command_menu`.

**Workaround**: `/commands` shows all commands paginated.

## What's Done Well

- **Frame extraction pipeline**: 4 modes (transcript/efficient/balanced/token-burner) with smart token budgeting
- **Perceptual dedup**: Grayscale thumbnail comparison collapses static frames without external deps
- **Transcript fallback chain**: Native captions → Groq Whisper → OpenAI Whisper → frames-only
- **OpenCode client**: Secure, well-validated, stdlib-only
- **Security posture**: API keys never logged, HTTPS enforced, no video uploaded to APIs
- **Setup flow**: Idempotent installer, auto-detects platform, graceful degradation (keyless allowed)

## Investigation: How Hermes Skill → Slash Command Works

### Scan flow (agent/skill_commands.py)

1. `scan_skill_commands()` scans `~/.hermes/skills/` + `skills.external_dirs`
2. For each `SKILL.md` found:
   - Parse YAML frontmatter (`_parse_frontmatter`)
   - Skip if: platform mismatch, environment mismatch, name in disabled list
   - Normalize name: `watch` → `/watch` (lowercase, hyphens, strip invalid chars)
   - Store: `_skill_commands["/watch"] = {name, description, skill_md_path, skill_dir}`
3. `get_skill_commands()` returns cached dict (rescans on platform change)

### Telegram menu build (hermes_cli/commands.py)

1. `telegram_bot_commands()` — collects built-in `CommandDef` entries (~53)
2. `telegram_menu_commands(max_commands=60)`:
   - Starts with built-in commands (never trimmed)
   - Adds plugin commands (never trimmed)
   - Adds skill commands (trimmed at cap, alphabetical)
3. Result sent to Telegram `setMyCommands` API
4. Menu rebuilds on gateway restart

### Key code paths

| Function | File | Purpose |
|----------|------|---------|
| `scan_skill_commands()` | `agent/skill_commands.py:320` | Scan skills dir → `_skill_commands` dict |
| `get_skill_commands()` | `agent/skill_commands.py:390` | Return cached commands (rescan if stale) |
| `telegram_menu_commands()` | `hermes_cli/commands.py:894` | Build capped Telegram menu |
| `_collect_gateway_skill_entries()` | `hermes_cli/commands.py:769` | Collect plugin + skill entries for gateway |
| `_telegram_command_menu_config()` | `hermes_cli/commands.py:600` | Read config from `platforms.telegram.extra.command_menu` |
| `_get_disabled_skill_names()` | `tools/skills_tool.py:570` | Load disabled skills from config |

### Verification commands

```bash
# Check if a skill is registered
python3 -c "
from agent.skill_commands import scan_skill_commands
cmds = scan_skill_commands()
print('/watch' in cmds)  # True if registered
"

# Check Telegram menu (what actually gets sent)
python3 -c "
from hermes_cli.commands import telegram_menu_commands
cmds, hidden = telegram_menu_commands(max_commands=60)
print(f'Menu: {len(cmds)}, Hidden: {hidden}')
watch = [n for n,d in cmds if 'watch' in n]
print(f'/watch in menu: {bool(watch)}')
"

# Check disabled skills
python3 -c "
from agent.skill_utils import get_disabled_skill_names
print(get_disabled_skill_names(platform='telegram'))
"
```
