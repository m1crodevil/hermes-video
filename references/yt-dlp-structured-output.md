# yt-dlp Structured Output — Channel & Video Stats

## Overview

yt-dlp `--dump-json` extracts rich metadata from YouTube video pages without any API key. The watch skill now includes channel stats (subscribers, views, likes, comments, publish date) in the report output.

## Key Channel Fields

| Field | Type | Description |
|-------|------|-------------|
| `channel` | string | Channel display name (authoritative) |
| `channel_id` | string | Unique ID (starts with `UC`) |
| `channel_url` | string | Full channel URL |
| `channel_follower_count` | int | Subscriber count |
| `channel_is_verified` | bool | Verified badge (✓) |
| `uploader` | string | Same as channel for YouTube |
| `uploader_id` | string | Handle (e.g. `@curhatbang`) |
| `uploader_url` | string | Channel URL via handle |

## Key Video Fields

| Field | Type | Description |
|-------|------|-------------|
| `view_count` | int | Total views |
| `like_count` | int | Total likes |
| `comment_count` | int | Total comments |
| `upload_date` | string | YYYYMMDD format |
| `duration` | float | Seconds |
| `title` | string | Video title |
| `description` | string | Full description |
| `tags` | list | Video tags |
| `categories` | list | YouTube categories |

## Quick Extraction

```bash
yt-dlp --dump-json --skip-download "https://youtu.be/VIDEO_ID" 2>/dev/null | \
  python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Channel: {d.get(\"channel\")} ({d.get(\"channel_follower_count\", \"?\")} subscribers)')
print(f'Views: {d.get(\"view_count\")} | Likes: {d.get(\"like_count\")} | Comments: {d.get(\"comment_count\")}')
print(f'Published: {d.get(\"upload_date\")}')
print(f'Verified: {d.get(\"channel_is_verified\", False)}')
"
```

## Channel Handle Resolution

Channel handles (`@name`) sometimes 404 with yt-dlp. Use channel ID from any video:

```bash
yt-dlp --dump-json --skip-download "https://youtu.be/VIDEO_ID" 2>/dev/null | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['channel_id'])"
```

## Limitations

- **Not available without API:** total channel views, total video count, real-time subscriber changes, channel creation date
- **Flat-playlist mode** (`--flat-playlist`) doesn't return per-video view counts — use `--dump-json` per video for full stats
- **Channel page extraction** (`@handle` URLs) sometimes fails with 404 — use channel ID instead

## YouTube Data API v3 (if full stats needed)

Free tier: 10,000 units/day. Endpoint: `channels?part=statistics&id=CHANNEL_ID`

Returns: `subscriberCount`, `viewCount`, `videoCount`, `hiddenSubscriberCount`
