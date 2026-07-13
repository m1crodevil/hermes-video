# YouTube Metadata Extraction (No API Key)

## yt-dlp Video Metadata

Get full video metadata including channel stats without YouTube Data API:

```bash
yt-dlp --dump-json --skip-download "https://youtu.be/VIDEO_ID" 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
keys = ['id','title','channel','channel_id','channel_url','channel_follower_count',
        'channel_is_verified','uploader','upload_date','duration','view_count',
        'like_count','comment_count','description','tags']
for k in keys:
    v = d.get(k, 'N/A')
    if k == 'description' and v and len(str(v)) > 200:
        v = str(v)[:200] + '...'
    print(f'{k}: {v}')
"
```

### Available Fields

| Field | Description | Source |
|-------|-------------|--------|
| `channel_follower_count` | Subscriber count | ✅ Direct from video page |
| `channel_is_verified` | Verified badge | ✅ Direct |
| `view_count` | Video views | ✅ Direct |
| `like_count` | Video likes | ✅ Direct |
| `comment_count` | Comments | ✅ Direct |
| `channel_id` | UC... channel ID | ✅ Direct |
| `upload_date` | YYYYMMDD format | ✅ Direct |
| `duration` | Seconds | ✅ Direct |
| `tags` | Video tags | ✅ Direct |

### What's NOT available without API

- Total channel views (sum of all videos)
- Total video count on channel
- Real-time subscriber changes
- Channel creation date
- Playlist metadata (partial — flat-playlist mode lacks view counts)

## Channel Video Listing

List recent videos from a channel:

```bash
# Flat playlist (fast, no per-video details)
yt-dlp --flat-playlist --dump-json --playlist-items 1:10 \
  "https://www.youtube.com/channel/CHANNEL_ID/videos" 2>/dev/null

# With full metadata (slower, gets views/likes)
for vid in $(yt-dlp --flat-playlist --get-id --playlist-items 1:10 \
  "https://www.youtube.com/channel/CHANNEL_ID/videos" 2>/dev/null); do
  yt-dlp --dump-json --skip-download "https://youtu.be/$vid" 2>/dev/null | \
    python3 -c "import json,sys; d=json.load(sys.stdin); print(f'{d[\"title\"]} | {d.get(\"view_count\",\"?\")} views')"
done
```

## Channel Handle Resolution

Channel handles (`@name`) sometimes 404 with yt-dlp. Use the channel ID instead:

```bash
# Find channel ID from any video
yt-dlp --dump-json --skip-download "https://youtu.be/VIDEO_ID" 2>/dev/null | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['channel_id'])"
```

## YouTube Data API v3 (Free Tier)

If full channel stats are needed:
- Free: 10,000 units/day (1 call = ~1-10 units)
- Get key: Google Cloud Console → APIs → YouTube Data API v3 → Create credentials
- Channel stats endpoint: `channels?part=statistics&id=CHANNEL_ID`
- Returns: subscriberCount, viewCount, videoCount, hiddenSubscriberCount
