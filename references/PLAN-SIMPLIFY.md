# Refactor Plan: hermes-video

> Same as original claude-video. Just works on Hermes. Add MiMo as option.

## Principle

Original claude-video = 8 scripts, clean, universal.
Our hermes-video = 14 scripts, bloated, coupled.

Goal: back to 8 scripts + Hermes-compatible SKILL.md + MiMo as AI option.

## Original vs Current

### Original (bradautomates/claude-video) — 8 scripts
```
scripts/
├── watch.py        ← entry point
├── download.py     ← yt-dlp
├── frames.py       ← ffmpeg
├── transcribe.py   ← VTT parser
├── whisper.py      ← Groq/OpenAI
├── config.py       ← 40 lines, clean
├── env.py          ← .env loader
└── setup.py        ← preflight
```

### Current (hermes-video) — 14 scripts + bloat
```
scripts/
├── watch.py              ← +50 lines (--engine opencode block)
├── download.py           ← same
├── frames.py             ← same
├── transcribe.py         ← same
├── whisper.py            ← same
├── config.py             ← BLOATED: 200+ lines (was 40)
├── env.py                ← same
├── setup.py              ← same
├── errors.py             ← NEW (original doesn't have)
├── types.py              ← NEW (original doesn't have)
├── video_types.py        ← NEW (duplicate of types.py)
├── opencode_client.py    ← NEW (OpenCode Zen API)
├── hermes_memory.py      ← NEW (redundant)
└── hermes_cron.py        ← NEW (redundant)
```

## Changes

### DELETE (10 files)
| File | Reason |
|------|--------|
| `opencode_client.py` | Original doesn't have. Agent IS the AI. |
| `hermes_memory.py` | Original doesn't have. Redundant. |
| `hermes_cron.py` | Original doesn't have. Redundant. |
| `video_types.py` | Duplicate of types.py. |
| `errors.py` | Original doesn't have. Re-import from types. |
| `references/PLAN-REBRAND.md` | Outdated. |
| `references/PLAN-MIMO.md` | Outdated. |
| `references/PLAN-REFACTOR.md` | Outdated. |
| `assets/README.md` | Outdated. |
| `assets/CHANGELOG.md` | Outdated. |

### REVERT to original (3 files)

#### `config.py` — revert to original (~40 lines)
```python
# Original: just read_env_file + get_config + frame_cap
# Remove: WatchConfig, get_opencode_config, load_config, inline fallbacks
```

#### `watch.py` — remove --engine block
```python
# Remove: --engine arg, --question arg
# Remove: entire "if engine == opencode:" block (~50 lines)
# Remove: imports of opencode_client, get_opencode_config
```

#### `types.py` — keep if needed, simplify
```python
# Original doesn't have this.
# Keep ONLY if other scripts import from it.
# Otherwise delete and use inline dicts like original.
```

### KEEP as-is (4 files)
- `download.py` — same as original
- `frames.py` — same as original
- `transcribe.py` — same as original
- `whisper.py` — same as original
- `env.py` — same as original
- `setup.py` — same as original

### UPDATE (1 file)

#### `SKILL.md` — Hermes-compatible, agent-agnostic
- Version: keep 1.0.0
- Author: m1crodevil
- Remove: "Claude" references → generic "agent"
- Add: Hermes install section
- Add: MiMo mention as optional AI backend
- Keep: agent-agnostic (works on Hermes, Claude Code, Codex, Cursor)

## Final structure
```
scripts/
├── watch.py        ← entry point (original + Hermes refs)
├── download.py     ← yt-dlp (unchanged)
├── frames.py       ← ffmpeg (unchanged)
├── transcribe.py   ← VTT parser (unchanged)
├── whisper.py      ← Groq/OpenAI (unchanged)
├── config.py       ← reverted to original (~40 lines)
├── env.py          ← .env loader (unchanged)
└── setup.py        ← preflight (unchanged)
```

8 scripts. Clean. Universal. Same as original.

## Execution

### Step 1: Delete files
```bash
rm scripts/opencode_client.py
rm scripts/hermes_memory.py
rm scripts/hermes_cron.py
rm scripts/video_types.py
rm scripts/errors.py
rm references/PLAN-REBRAND.md
rm references/PLAN-MIMO.md
rm references/PLAN-REFACTOR.md
rm assets/README.md
rm assets/CHANGELOG.md
```

### Step 2: Revert config.py
Replace with original 40-line version.

### Step 3: Revert watch.py
Remove --engine, --question, and opencode block.

### Step 4: Check types.py
If scripts import from it → keep (simplified).
If not → delete.

### Step 5: Update SKILL.md
- Agent-agnostic language
- Hermes install section
- MiMo as optional mention

### Step 6: Update README.md
- Same structure as original README
- Replace "Claude" → "your agent"
- Add Hermes install option
- Add MiMo mention

### Step 7: Test
```bash
python3 scripts/watch.py https://youtu.be/dQw4w9WgXcQ
# Should output: frame paths + transcript
```

### Step 8: Push
```bash
git add -A
git commit -m "refactor: simplify to match original claude-video

- Delete 10 redundant files (opencode_client, hermes_memory, etc.)
- Revert config.py to original 40-line version
- Remove --engine opencode block from watch.py
- Update SKILL.md for Hermes compatibility
- Back to 8 scripts, same as original"
git push
```
