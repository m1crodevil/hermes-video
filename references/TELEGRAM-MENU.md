# Telegram BotCommand Menu — `/watch` visibility

## Problem

Telegram Bot API caps slash commands at **100 total**. Hermes has 53 core commands + 68 skill commands = 121. Skills are sorted alphabetically and trimmed at the cap — `/watch` (letter "w") gets cut.

## Diagnosis

```bash
# Check how many commands are hidden
python3 -c "
from hermes_cli.commands import telegram_menu_commands
cmds, hidden = telegram_menu_commands(max_commands=100)
print(f'Total: {len(cmds)}, hidden: {hidden}')
watch = [n for n,d in cmds if 'watch' in n.lower()]
print(f'/watch in menu: {bool(watch)}')
"
```

## Fixes (pick one)

### Option 1: Prioritize `/watch` (recommended)

Edit `~/.hermes/config.yaml` directly:

```yaml
platforms:
  telegram:
    extra:
      command_menu:
        max_commands: 100
        priority_mode: prepend
        priority:
          - watch
```

Then restart gateway: `hermes gateway restart`

**Note:** `hermes config set` saves list values as strings — edit YAML directly.

### Option 2: Disable unused skills for Telegram

```bash
hermes skills config  # interactive, disable per-platform
```

Or edit `config.yaml`:

```yaml
skills:
  platform_disabled:
    telegram:
      - skill_name_1
      - skill_name_2
```

### Option 3: Both — prioritize + disable

Best for >121 total commands.

## Notes

- The BotCommand menu rebuilds on gateway restart
- `/watch` still works when typed manually even if hidden from menu
- `scan_skill_commands()` always finds `/watch` — it's the menu display that's capped
- Telegram command names cannot contain hyphens (auto-replaced with underscores)
