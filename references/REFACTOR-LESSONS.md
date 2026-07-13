# Refactor Lessons: claude-video → hermes-video

## Principle: Less is More

When forking/adapting a repo for a new platform, keep the original's simplicity. Don't add features — just change what's platform-specific.

## What we did wrong (then fixed)

### Over-engineering
- Added `opencode_client.py` (AI client) — agent IS the AI, script shouldn't call APIs
- Added `hermes_memory.py` — Hermes already has `hindsight_retain/recall`
- Added `hermes_cron.py` — Hermes already has `cronjob` tool
- Added `types.py`, `errors.py`, `video_types.py` — duplicate type systems
- Bloated `config.py` from 40 to 200+ lines
- Added `--engine opencode` flag to watch.py

### What user said
- "ingat: less is more"
- "repo ini untuk semua orang, bukan fit untuk saya pribadi"
- "intinya sama persis seperti original repo, tapi lebih support ke hermes, bukan claude"

### What we ended up with
Back to 8 scripts — same as original `bradautomates/claude-video`:
- watch.py, download.py, frames.py, transcribe.py, whisper.py, config.py, setup.py, build-skill.sh
- Updated SKILL.md for Hermes (metadata, author, platforms)
- Updated README.md (removed MiMo/OpenCode refs)

## Rule of thumb

For a platform fork:
1. Keep ALL original scripts as-is
2. Only change: SKILL.md (metadata), README.md (docs)
3. Don't add platform-specific modules — the agent already has those features
4. If you think "I should add X" — check if the agent already has it first
