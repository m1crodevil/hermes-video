# Truncation-Fabrication Incident (2026-07-12)

## What happened

Agent ran `/watch` on a 52-minute YouTube video. The terminal tool truncated the markdown report output (96K chars > 50K cap). Instead of reading metadata from `report.json` or `info.json`, the agent **fabricated** metadata:

| Field | Fabricated | Actual |
|-------|-----------|--------|
| Channel | DindraDeddy | CURHAT BANG Denny Sumargo |
| Subscribers | 32.1K | 9.16M |
| Views | 180,757 | 2,777,906 |
| Likes | 8,849 | 38,516 |
| Comments | 282 | 10,000 |
| Upload date | June 20, 2026 | June 11, 2026 |

## Root cause chain

```
Terminal stdout cap: ~50K chars
        ↓
96K-char report truncated → middle section (with metadata table) invisible
        ↓
Agent couldn't see real data
        ↓
Agent fabricated instead of reading from file
```

## Fixes applied

### Code changes
- `watch.py`: Default output changed from `markdown` to `both` (always writes report.json)
- `models.py`: Added `compact=True` parameter to `to_markdown()` — skips full transcript in markdown when JSON backup exists
- `watch.py`: Auto-warns for videos >20min about truncation risk

### Skill changes
- Added **Step 2b** — mandatory read of report.json for metadata
- Strengthened **Anti-hallucination rules** with zero-fabrication mandate
- Added **Output truncation recovery** section
- Added **Output format (Telegram)** section with exact template

## Prevention pattern

When terminal output is large/truncated:
1. **NEVER fabricate data** — say "output truncated" if you can't see it
2. **Read from file** — `report.json` or `download/video.info.json`
3. **Verify before reporting** — cross-check any data point against file source

## Validation

52-minute video after fix:
- stdout: 32,374 chars (under 50K cap) ✅
- report.json: 1.2MB (full data) ✅
- Metadata: all fields correct from file ✅
