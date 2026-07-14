"""CLI entry point — delegates to pipeline."""
from __future__ import annotations
import sys
from watch.pipeline import main

def main_entry() -> int:
    return main()

if __name__ == "__main__":
    raise SystemExit(main_entry())
