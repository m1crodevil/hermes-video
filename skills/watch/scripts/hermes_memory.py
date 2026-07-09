#!/usr/bin/env python3
"""Hermes memory integration for video analysis.

Provides append-only JSONL storage for video analysis results, enabling
recall of previous analyses and automatic timestamping.

Storage location: ~/.hermes/memory/video_analyses.jsonl

Functions:
    save_to_memory(source, question, answer, metadata)
        Save a video analysis result to Hermes memory.

    recall_analyses(source, limit)
        Recall previous analyses, optionally filtered by source.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MEMORY_DIR: Path = Path.home() / ".hermes" / "memory"
MEMORY_FILE: Path = MEMORY_DIR / "video_analyses.jsonl"
ENTRY_TYPE: str = "video_analysis"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_to_memory(
    source: str,
    question: str,
    answer: str,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Save a video analysis result to Hermes memory.

    Creates an append-only JSONL entry with automatic timestamp.

    Args:
        source: Video source identifier (URL, path, or video ID).
        question: The analysis question that was asked.
        answer: The analysis answer/result.
        metadata: Optional additional metadata (model, duration, etc.).

    Returns:
        True if saved successfully, False otherwise.

    Raises:
        ValueError: If source, question, or answer are empty.
    """
    if not source.strip():
        raise ValueError("source must not be empty")
    if not question.strip():
        raise ValueError("question must not be empty")
    if not answer.strip():
        raise ValueError("answer must not be empty")

    entry = {
        "type": ENTRY_TYPE,
        "source": source.strip(),
        "question": question.strip(),
        "answer": answer.strip(),
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.debug("Saved analysis to memory: %s", MEMORY_FILE)
        return True

    except OSError as exc:
        logger.error("Failed to save to Hermes memory: %s", exc)
        return False
    except (TypeError, ValueError) as exc:
        logger.error("Failed to serialize memory entry: %s", exc)
        return False


def recall_analyses(
    source: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Recall previous video analyses from Hermes memory.

    Reads the JSONL memory file and returns entries, optionally filtered
    by source. Results are returned in chronological order (oldest first).

    Args:
        source: If provided, only return analyses matching this source.
        limit: Maximum number of entries to return (default: 10).

    Returns:
        List of analysis entries as dictionaries. Empty list if no memory
        file exists or no entries match the filter.

    Raises:
        ValueError: If limit is less than 1.
    """
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")

    if not MEMORY_FILE.exists():
        logger.debug("No memory file at %s", MEMORY_FILE)
        return []

    entries: list[dict[str, Any]] = []

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Skipping malformed line %d in %s: %s",
                        line_num,
                        MEMORY_FILE,
                        exc,
                    )
                    continue

                # Filter by source if requested
                if source is not None:
                    if entry.get("source") != source:
                        continue

                entries.append(entry)

    except OSError as exc:
        logger.error("Failed to read Hermes memory: %s", exc)
        return []

    # Return most recent entries (last N)
    if len(entries) > limit:
        entries = entries[-limit:]

    logger.debug(
        "Recalled %d entries (source=%s, limit=%d)",
        len(entries),
        source,
        limit,
    )
    return entries


def memory_exists() -> bool:
    """Check if the memory file exists and is readable.

    Returns:
        True if the memory file exists.
    """
    return MEMORY_FILE.exists() and MEMORY_FILE.is_file()


def memory_count() -> int:
    """Count total entries in the memory file.

    Returns:
        Number of valid JSON lines in the memory file. Returns 0 if
        the file does not exist.
    """
    if not MEMORY_FILE.exists():
        return 0

    count = 0
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        json.loads(line)
                        count += 1
                    except json.JSONDecodeError:
                        pass
    except OSError:
        return 0

    return count


def clear_memory() -> bool:
    """Clear all entries from the memory file.

    WARNING: This is irreversible.

    Returns:
        True if cleared successfully, False otherwise.
    """
    try:
        if MEMORY_FILE.exists():
            MEMORY_FILE.unlink()
        logger.debug("Cleared Hermes memory file")
        return True
    except OSError as exc:
        logger.error("Failed to clear Hermes memory: %s", exc)
        return False
