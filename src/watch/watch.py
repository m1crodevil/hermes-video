"""Entry point for the /watch skill (delegates to cli)."""
from __future__ import annotations

import sys
from pathlib import Path

# When run directly from skills/watch/scripts/, ensure src/ is on path
_src = Path(__file__).resolve().parent.parent  # src/watch -> src
_pkg = Path(__file__).resolve().parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
if str(_pkg) in sys.path:
    sys.path.remove(str(_pkg))

from watch.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
