"""Hermes Cron Integration for Scheduled Video Analysis.

This module provides functions to create and manage cron jobs
for periodic video analysis using the watch skill.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Default Hermes cron directory
CRON_DIR = Path.home() / ".hermes" / "cron"
CRON_FILE = CRON_DIR / "video_analysis.json"


def create_cron_job(
    name: str,
    schedule: str,
    url: str,
    question: str,
    detail: str = "balanced",
) -> dict[str, Any]:
    """Create a cron job configuration for video analysis.

    Args:
        name: Human-readable job name.
        schedule: Cron schedule expression (e.g., "daily 9:00", "weekly Monday 10:00").
        url: Video URL to analyze.
        question: The question to ask about the video.
        detail: Analysis detail level (minimal, balanced, comprehensive).

    Returns:
        Job configuration dictionary.
    """
    prompt = f"Analyze video {url} with question: {question}"
    if detail and detail != "balanced":
        prompt += f" (detail level: {detail})"

    return {
        "name": name,
        "schedule": schedule,
        "prompt": prompt,
        "skills": ["watch"],
        "workdir": str(Path.cwd()),
    }


def save_cron_config(jobs: list[dict[str, Any]]) -> None:
    """Save cron job configurations to ~/.hermes/cron/video_analysis.json.

    Creates the directory if it does not exist.

    Args:
        jobs: List of job configuration dictionaries.
    """
    CRON_DIR.mkdir(parents=True, exist_ok=True)
    with open(CRON_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def load_cron_config() -> list[dict[str, Any]]:
    """Load existing cron configurations from disk.

    Returns:
        List of job dictionaries, or empty list if no config exists.
    """
    if not CRON_FILE.exists():
        return []
    with open(CRON_FILE, encoding="utf-8") as f:
        return json.load(f)


def add_cron_job(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Add a job to existing configuration and save.

    Args:
        job: Job configuration dictionary.

    Returns:
        Updated list of all jobs.
    """
    jobs = load_cron_config()
    jobs.append(job)
    save_cron_config(jobs)
    return jobs


def remove_cron_job(name: str) -> list[dict[str, Any]]:
    """Remove a job by name from configuration and save.

    Args:
        name: Name of the job to remove.

    Returns:
        Updated list of remaining jobs.
    """
    jobs = load_cron_config()
    jobs = [j for j in jobs if j.get("name") != name]
    save_cron_config(jobs)
    return jobs


if __name__ == "__main__":
    # Example usage
    job = create_cron_job(
        name="daily-tech-review",
        schedule="daily 09:00",
        url="https://www.youtube.com/watch?v=example",
        question="Summarize the key technical points",
        detail="comprehensive",
    )
    add_cron_job(job)
    print(f"Created cron job: {job['name']}")
    print(f"Saved to: {CRON_FILE}")
