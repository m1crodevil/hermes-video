# Analysis Stats Output

## Overview

The `--stats` flag adds transparent metrics to the watch output, showing users exactly what happened during analysis. This is especially useful for Telegram deliverables where users want to understand the processing.

## Usage

```bash
# Full stats (Telegram format)
watch.py "$URL" --detail balanced --stats

# Compact stats (single line)
watch.py "$URL" --detail balanced --stats --stats-format compact

# Stats with auto-moments
watch.py "$URL" --detail balanced --auto-moments --stats
```

## Output Formats

### Telegram Format (Default)

```
📊 **Analysis Stats**
━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ Processing Time: 74.9s
🎬 Video Duration: 12:34
📐 Resolution: 1280x720
🖼️ Frames Extracted: 100 @ 512px (scene)
📝 Transcript: 385 segments [captions (json3)]
🎯 Key Moments: 13 detected (8 critical)
🔍 Vision Verifications: 2 completed (1 corrections)
🪙 Tokens: 81,946 (estimated)
━━━━━━━━━━━━━━━━━━━━━━━━
```

### Compact Format

```
⏱️ 74.9s · 🖼️ 100 frames · 📝 385 segs · 🎯 13 moments · 🔍 2 verified
```

## Stats Fields

| Field | Description | When Shown |
|-------|-------------|------------|
| ⏱️ Processing Time | Total analysis time | Always (if --stats) |
| 🎬 Video Duration | Length of video analyzed | Always |
| 📐 Resolution | Video resolution | Always |
| 💾 File Size | Downloaded video size | If video downloaded |
| 🖼️ Frames Extracted | Number of frames + engine | Always |
| 📝 Transcript | Segments + language + source | Always |
| 🎯 Key Moments | Detected moments + priority | If --auto-moments |
| 🔍 Vision Verifications | Completed + corrections | If vision analysis done |
| 🪙 Tokens | Estimated token count (frames + transcript) | Always |

## Implementation

The stats are collected by `scripts/stats_collector.py`:

```python
from stats_collector import collect_stats, format_stats_telegram

# Collect stats from work directory
stats = collect_stats(work_dir)
stats.processing_time = elapsed_seconds

# Format for Telegram
print(format_stats_telegram(stats))
```

## Stats JSON

When `--stats` is used, a `stats.json` file is saved to the work directory:

```json
{
  "processing_time": 74.9,
  "video_duration": 754.261,
  "video_duration_fmt": "12:34",
  "video_resolution": "1280x720",
  "frames_extracted": 100,
  "frames_engine": "scene",
  "transcript_segments": 385,
  "transcript_source": "captions (json3)",
  "key_moments_detected": 13,
  "key_moments_priority_1": 8,
  "vision_verifications": 2,
  "vision_corrections": 1,
  "tokens": 81946
}
```

## Integration with Telegram Deliverable

When delivering results to Telegram, append the stats at the end:

```
🎬 **Video Title**
Channel: Uploader (subs)
Duration: 12:34

---

[Main analysis content]

---

📊 **Analysis Stats**
⏱️ 74.9s · 🖼️ 100 frames · 📝 385 segs

_Work dir: `/tmp/watch-xxx`_
```

## Design Decisions

1. **Non-intrusive** - Stats only appear when `--stats` is explicitly passed
2. **Dual format** - Telegram (full) and compact (single line) for different use cases
3. **JSON backup** - stats.json saved for programmatic access
4. **Extensible** - Easy to add new metrics as features evolve
