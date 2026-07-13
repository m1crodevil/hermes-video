# YouTube JSON3 Subtitle Format

YouTube's internal caption format. More structured than VTT/SRT, provides **word-level timing** and **ASR confidence scores**.

## Top-Level Structure

```json
{
  "wireMagic": "pb3",           // Protocol version (protobuf-based)
  "pens": [...],                // Pen styles (usually empty)
  "wsWinStyles": [...],         // Window styling hints
  "wpWinPositions": [...],      // Window positioning hints
  "events": [...]               // Main caption data (see below)
}
```

## `events[]` — Three Types

### 1. Init Event (window/style/position setup)
```json
{
  "tStartMs": 0,                // Start time in milliseconds
  "dDurationMs": 211879,        // Total duration in milliseconds
  "id": 1,                      // Event ID
  "wpWinPosId": 1,              // Reference → wpWinPositions[1]
  "wsWinStyleId": 1             // Reference → wsWinStyles[1]
}
```

### 2. Caption Event (text + timing)
```json
{
  "tStartMs": 18800,            // Start time (ms)
  "dDurationMs": 7160,          // Duration (ms)
  "wWinId": 1,                  // Window ID
  "segs": [                     // Array of segments (per-word)
    {
      "utf8": "We're",          // Text of the word
      "acAsrConf": 0            // ASR confidence (0-1, 0 = no data/manual)
    },
    {
      "utf8": " no",
      "tOffsetMs": 239,         // Offset from tStartMs (word-level timing!)
      "acAsrConf": 0
    }
  ]
}
```

### 3. Newline Marker (line separator)
```json
{
  "tStartMs": 18790,
  "wWinId": 1,
  "aAppend": 1,                 // Flag: this is a newline/append
  "segs": [{"utf8": "\n"}]
}
```

## `segs[]` — Per-Word Fields

| Field | Type | Description |
|-------|------|-------------|
| `utf8` | string | Text of the word/segment (leading space included for non-first words) |
| `tOffsetMs` | int | Offset in ms from `tStartMs` (first word = 0 or absent) |
| `acAsrConf` | float | ASR confidence 0-1 (0 = no data or manual caption) |

## `wsWinStyles[]` — Styling

```json
{
  "mhModeHint": 2,     // Mode hint (2 = rolling/auto)
  "juJustifCode": 0,   // Justification (0=left, 1=right, 2=center)
  "sdScrollDir": 3      // Scroll direction (3 = bottom-to-top)
}
```

## `wpWinPositions[]` — Positioning

```json
{
  "apPoint": 6,         // Anchor point (6 = bottom-left)
  "ahHorPos": 20,      // Horizontal position (%)
  "avVerPos": 100,      // Vertical position (%)
  "rcRows": 2,          // Max rows
  "ccCols": 40          // Max columns
}
```

## Downloading with yt-dlp

```bash
# Preferred: json3 as format preference
yt-dlp --skip-download --write-auto-sub --sub-lang en --sub-format "json3/best" -o 'output' URL

# Fallback to VTT if json3 unavailable
yt-dlp --skip-download --write-auto-sub --sub-lang en --sub-format "vtt" -o 'output' URL
```

**Note:** `--convert-subs json3` does NOT work. Must use `--sub-format "json3/best"`.

## Python Parser

```python
import json
from pathlib import Path

def parse_json3(path: str) -> list[dict]:
    """Parse YouTube JSON3 subtitle file into timestamped segments with word-level timing."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    segments = []
    
    for event in data.get("events", []):
        segs = event.get("segs", [])
        if not segs:
            continue
        
        # Join all segments, skip newline markers
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if not text or text == "\n":
            continue
        
        start = event.get("tStartMs", 0) / 1000.0
        dur = event.get("dDurationMs", 0) / 1000.0
        
        # Extract word-level timing from tOffsetMs
        words = []
        for seg in segs:
            seg_text = seg.get("utf8", "").strip()
            if seg_text:
                word_start = start + seg.get("tOffsetMs", 0) / 1000.0
                words.append({
                    "word": seg_text,
                    "start": round(word_start, 3),
                    "confidence": seg.get("acAsrConf", 0)
                })
        
        segments.append({
            "start": round(start, 2),
            "end": round(start + dur, 2),
            "text": text,
            "words": words  # Word-level timing!
        })
    
    return _dedupe(segments)


def _dedupe(segments: list[dict]) -> list[dict]:
    """Collapse rolling duplicates common in YouTube auto-subs."""
    out = []
    for seg in segments:
        if out and seg["text"] == out[-1]["text"]:
            out[-1]["end"] = seg["end"]
            continue
        if out and seg["text"].startswith(out[-1]["text"] + " "):
            out[-1]["text"] = seg["text"]
            out[-1]["end"] = seg["end"]
            continue
        out.append(seg)
    return out
```

## JSON3 vs VTT Comparison

| Feature | VTT | JSON3 |
|---------|-----|-------|
| Word-level timing | ❌ | ✅ `tOffsetMs` per word |
| ASR confidence | ❌ | ✅ `acAsrConf` |
| Parsing | Regex (fragile) | `json.loads()` (reliable) |
| Newline handling | Manual detection | `aAppend: 1` flag |
| File size | ~14KB (typical) | ~32KB (more data) |
| Format support | Universal | YouTube-specific |

## jq One-Liner for Quick Extraction

```bash
# Get timestamped text (no word-level)
jq -r '.events[] | select(.segs and .segs[0].utf8 != "\n") | (.tStartMs | tostring) + " " + ([.segs[]?.utf8] | join(""))' file.json3

# Get just the text
jq -r '.events[] | select(.segs and .segs[0].utf8 != "\n") | [.segs[].utf8] | join("")' file.json3 | paste -sd' ' -
```
