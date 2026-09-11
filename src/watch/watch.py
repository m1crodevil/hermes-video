"""Entry point for the /watch skill (delegates to pipeline)."""
from __future__ import annotations
import sys
from watch.pipeline import main

if __name__ == "__main__":
    raise SystemExit(main())
