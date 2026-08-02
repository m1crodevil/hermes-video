"""Video caching with SHA256 content hashing and LRU eviction.

Caches downloaded videos to avoid re-downloading. Cache location:
    ~/.cache/watch/<sha256>.mp4

LRU eviction keeps total cache under 10GB.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path


CACHE_DIR = Path.home() / ".cache" / "watch"
MAX_CACHE_SIZE_GB = 10
METADATA_FILE = "cache_metadata.json"


def _get_cache_dir() -> Path:
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def _load_metadata() -> dict:
    """Load cache metadata (access times, sizes)."""
    meta_path = _get_cache_dir() / METADATA_FILE
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_metadata(metadata: dict) -> None:
    """Save cache metadata."""
    meta_path = _get_cache_dir() / METADATA_FILE
    meta_path.write_text(json.dumps(metadata, indent=2))


def _hash_url(url: str, mode: str = "video") -> str:
    """Generate SHA256 hash of URL + mode for cache key.

    The mode salt keeps audio-only (Whisper) and full-video downloads from
    colliding under the same URL: an audio file must never satisfy a frame
    extraction request, and a video must never be served as a Whisper source.
    """
    return hashlib.sha256(f"{mode}|{url}".encode()).hexdigest()[:16]


def _total_cache_size(metadata: dict) -> int:
    """Calculate total cache size in bytes."""
    total = 0
    for entry in metadata.values():
        path = Path(entry.get("path", ""))
        if path.exists():
            total += path.stat().st_size
    return total


def _evict_lru(metadata: dict, needed_bytes: int = 0) -> dict:
    """Evict least-recently-used entries until under limit."""
    max_bytes = MAX_CACHE_SIZE_GB * (1024 ** 3)
    current = _total_cache_size(metadata)
    
    # Sort by access time (oldest first)
    sorted_entries = sorted(
        metadata.items(),
        key=lambda x: x[1].get("access_time", 0)
    )
    
    for key, entry in sorted_entries:
        if current + needed_bytes <= max_bytes:
            break
        path = Path(entry.get("path", ""))
        if path.exists():
            size = path.stat().st_size
            path.unlink()
            current -= size
            del metadata[key]
    
    return metadata


def get_cached_video(url: str, mode: str = "video") -> str | None:
    """Get cached video path if it exists.

    Args:
        url: Original video URL (cache key input)
        mode: "video" (default) or "audio" — separate keys so audio-only
            downloads never satisfy full-video requests and vice versa.

    Returns:
        Path to cached video file, or None if not cached.
    """
    cache_key = _hash_url(url, mode=mode)
    metadata = _load_metadata()
    
    if cache_key in metadata:
        entry = metadata[cache_key]
        path = Path(entry["path"])
        if path.exists():
            # Update access time
            entry["access_time"] = time.time()
            _save_metadata(metadata)
            return str(path)
        else:
            # File was deleted externally
            del metadata[cache_key]
            _save_metadata(metadata)
    
    return None


def cache_video(url: str, video_path: str, mode: str = "video") -> str:
    """Cache a downloaded video.

    Args:
        url: Original video URL (used as cache key)
        video_path: Path to the downloaded video file
        mode: "video" (default) or "audio" — see get_cached_video().

    Returns:
        Path to the cached video file
    """
    cache_dir = _get_cache_dir()
    cache_key = _hash_url(url, mode=mode)
    ext = Path(video_path).suffix or ".mp4"
    cached_path = cache_dir / f"{cache_key}{ext}"
    
    # Copy to cache
    shutil.copy2(video_path, cached_path)
    
    # Update metadata
    metadata = _load_metadata()
    file_size = cached_path.stat().st_size
    
    # Evict if needed
    metadata = _evict_lru(metadata, file_size)
    
    metadata[cache_key] = {
        "url": url,
        "path": str(cached_path),
        "size": file_size,
        "cached_at": time.time(),
        "access_time": time.time(),
    }
    _save_metadata(metadata)
    
    return str(cached_path)


def clear_cache() -> int:
    """Clear entire video cache.
    
    Returns:
        Number of files removed
    """
    cache_dir = _get_cache_dir()
    count = 0
    
    for item in cache_dir.iterdir():
        if item.is_file() and item.name != METADATA_FILE:
            item.unlink()
            count += 1
    
    # Clear metadata
    meta_path = cache_dir / METADATA_FILE
    if meta_path.exists():
        meta_path.unlink()
    
    return count


def cache_info() -> dict:
    """Get cache statistics.
    
    Returns:
        Dict with count, total_size, total_size_human
    """
    metadata = _load_metadata()
    total_bytes = _total_cache_size(metadata)
    
    # Count actual files
    count = 0
    for entry in metadata.values():
        if Path(entry.get("path", "")).exists():
            count += 1
    
    # Human-readable size
    if total_bytes < 1024 ** 3:
        size_human = f"{total_bytes / (1024 ** 2):.1f} MB"
    else:
        size_human = f"{total_bytes / (1024 ** 3):.1f} GB"
    
    return {
        "count": count,
        "total_size": total_bytes,
        "total_size_human": size_human,
        "max_size": MAX_CACHE_SIZE_GB * (1024 ** 3),
    }
