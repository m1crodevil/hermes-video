# /watch skill

Agent-agnostic video analysis skill. Downloads captions, falls back to Whisper, and extracts frames at the timestamps the agent asks for.

## Structure

- `skills/watch/SKILL.md` — canonical skill contract the model reads when `/watch` fires.
- `skills/watch/scripts/` — entry points and pipeline modules.
- `src/watch/` — Python source; `skills/watch/scripts/` are symlinks into here.
- `tests/` — pytest suite (ffmpeg-synthesized clips; no network).

## Rules

- Keep the version in sync across `skills/watch/SKILL.md` and `pyproject.toml` when cutting a release.
- Never commit real API keys or `.env` contents; keys live in `~/.config/watch/.env` (mode `0600`) at runtime.
