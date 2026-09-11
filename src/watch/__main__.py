"""Entry point for the /watch skill (delegates to cli)."""
from __future__ import annotations
from watch.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
