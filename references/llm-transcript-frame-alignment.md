# LLM-Driven Transcript-Frame Alignment

## Problem Statement

watch.py extracts frames (scene-based) and transcripts (JSON3/VTT) as **separate streams**. The LLM receives both but must manually cross-reference timestamps. This leads to interpretation errors — e.g., misidentifying who recruited whom because the transcript alone doesn't show who is speaking.

## Root Cause Analysis

### Why Manual Cross-Reference Fails

1. **Speaker ambiguity** — Transcript text like "I recruited him" doesn't identify who "I" is
2. **ASR errors** — Auto-captions mangle proper nouns (e.g., "Raknarok" instead of "Ragnarok")
3. **Visual context missing** — Transcript doesn't capture what's shown on screen
4. **Timestamp drift** — Manual alignment is error-prone

### JSON3 Word-Level Timing

JSON3 transcripts contain **word-level timing** via `tOffsetMs`:
```json
{
  "tStartMs": 54039,
  "segs": [
    {"utf8": "Ya kan ", "tOffsetMs": 0, "acAsrConf": 0},
    {"utf8": "Ragnarok", "tOffsetMs": 1200, "acAsrConf": 0}
  ]
}
```

This enables precise mapping of transcript words to visual moments.

## Solution: LLM-Driven Moment Detection

### Core Principle

**Zero hardcoding** — All detection is LLM-driven. Works across languages and content types.

### Workflow

```
1. watch.py --auto-moments
   → Generates moments_prompt.txt (LLM prompt)

2. LLM analyzes transcript
   → Identifies key moments needing verification
   → Writes key_moments.json

3. extract_moment_frames.py
   → Extracts frames at moment timestamps
   → Updates moments with frame paths

4. batch_vision.py
   → Generates batch vision prompt
   → LLM analyzes frames with specific questions

5. apply_corrections.py
   → Applies corrections to transcript
   → Generates corrected transcript
```

### Key Moments Structure

```json
{
  "timestamp": "0:54",
  "word": "Raknarok",
  "context": "Ya kan Ragnarok. Tahu Raknarok? Raknarok tahu tahu.",
  "reason": "proper_noun",
  "question": "What game name is displayed on screen?",
  "priority": 1
}
```

### Detection Strategies (LLM-Driven)

The LLM identifies moments based on:

1. **Proper nouns** — Names, brands, game titles that might be misspelled
2. **Claims/statistics** — Numbers, prices, dates needing fact-checking
3. **Deictic references** — "this", "that", "look at this" where speaker points
4. **Speaker identity** — Moments where it's unclear who is speaking
5. **Visual context** — Moments where visual context changes interpretation

## Scripts Reference

| Script | Purpose | Key Function |
|--------|---------|--------------|
| `transcript_moments.py` | Generate LLM prompt | `generate_prompt()` |
| `extract_moment_frames.py` | Extract frames | `extract_at_timestamps()` |
| `batch_vision.py` | Batch vision prompt | `generate_batch_prompt()` |
| `apply_corrections.py` | Apply corrections | `apply_corrections_to_segments()` |
| `vision_verify.py` | Vision verification | `process_vision_results()` |
| `synthesis.py` | Grounded synthesis | `generate_synthesis_prompt()` |

## Pitfalls

### 1. ASR Confidence Scores Not Available

YouTube auto-captions for some languages (e.g., Indonesian) return `acAsrConf: 0` for ALL words. Do NOT rely on confidence-based filtering.

**Mitigation:** Use LLM judgment to identify moments needing verification.

### 2. Transcript Alone Cannot Identify Speakers

Without visual context, transcript text is ambiguous about *who* is speaking.

**Mitigation:** Always cross-reference with:
- Discord/game UI (shows participant names)
- Streamer facecam (shows who is live)
- Channel metadata (who is the uploader vs guest)

### 3. Frame Filenames Not Sequential

Scene-change engines name files by extraction index (`frame_0211.jpg`), not timestamp.

**Mitigation:** Use `search_files("*.jpg", path="<workdir>/frames", target="files")` first.

### 4. Vision Models Misidentify Names

When a frame contains multiple logos, vision models often pick the wrong one.

**Mitigation:** Never report channel name based solely on frame analysis. Cross-reference with yt-dlp metadata.

## Example: Tepe46 Video

### Initial Interpretation Error

**Wrong:** "Tepe46 rekrut George" (I said Tepe46 recruited George)
**Correct:** "George rekrut Tepe46" (George recruited Tepe46)

### How It Was Caught

1. User corrected: "loh, kebalik ini"
2. Investigated transcript — found speaker ambiguity
3. Realized transcript alone can't identify speakers
4. Developed LLM-driven moment detection

### Key Moments Identified

```json
[
  {"timestamp": "0:26", "word": "George andika erison", "reason": "proper_noun"},
  {"timestamp": "0:54", "word": "Raknarok", "reason": "proper_noun"},
  {"timestamp": "1:07", "word": "turnamen Ro", "reason": "entity"},
  {"timestamp": "9:28", "word": "1 juta dolar", "reason": "claim"},
  {"timestamp": "9:52", "word": "TYRTR", "reason": "proper_noun"}
]
```

### Corrections Applied

- "Raknarok" → "Ragnarok" (game name)
- "TYRTR" → "TYRTR" (tournament name, confirmed)
- "Glaz Ham" → "Glassem" (server name)

## Design Decisions

1. **Agent-driven workflow** — LLM analysis happens in agent context, not in script
2. **Modular** — Each phase can be skipped or customized
3. **Backward compatible** — Works without --auto-moments flag
4. **Fail-safe** — If moments not loaded, existing behavior continues

## User Preference

User explicitly stated: "intinya segala sesuatunya harus adaptive dan melibatkan LLM decide" — everything must be adaptive and involve LLM decision-making. No hardcoded keywords or language-specific patterns.
