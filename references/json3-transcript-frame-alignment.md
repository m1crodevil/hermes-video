# JSON3 Transcript-Frame Alignment Guide

## JSON3 Data Structure (from YouTube auto-captions)

```json
{
  "wireMagic": "pb3",
  "events": [
    {
      "tStartMs": 54039,        // Event start time (milliseconds)
      "dDurationMs": 2961,      // Event duration (ms)
      "segs": [                  // Word-level segments
        {
          "utf8": "Ragnarok",    // Word text
          "tOffsetMs": 0,        // Offset from tStartMs (ms)
          "acAsrConf": 0         // ASR confidence (0-1, 0 = no data)
        },
        {
          "utf8": " R",
          "tOffsetMs": 800,
          "acAsrConf": 0
        }
      ]
    }
  ]
}
```

## Key Fields

| Field | Description | Use for Alignment |
|-------|-------------|-------------------|
| `tStartMs` | Event start (ms) | Map to video timestamp |
| `segs[].utf8` | Word text | Detect proper nouns, entities |
| `segs[].tOffsetMs` | Word offset from event start (ms) | Precise word-level timing |
| `segs[].acAsrConf` | ASR confidence (0-1) | Detect uncertain words |

## Confidence Score Availability

**Important:** YouTube auto-captions for some languages return `acAsrConf: 0` for ALL words. Tested with Indonesian auto-captions — all 2,351 words had confidence = 0. This means:

- ❌ Cannot use confidence filtering to detect misheard words
- ✅ Can still use capitalization patterns for proper nouns
- ✅ Can still use LLM judgment for moment detection

## Word-Level Timing Calculation

```python
word_start_seconds = (event["tStartMs"] + seg["tOffsetMs"]) / 1000.0
word_end_seconds = (event["tStartMs"] + event["dDurationMs"]) / 1000.0
```

## Moment Detection Strategies (LLM-Driven)

### Strategy 1: Proper Noun Detection
Words starting with uppercase that aren't sentence starters are likely names, brands, or titles.

```
Transcript: "George andika erison. H ap h ap."
            ^^^^^^
            → Proper noun, needs visual verification
```

### Strategy 2: Deictic References
Words like "ini", "itu", "lihat", "this", "that", "look" indicate the speaker is pointing at something visual.

```
Transcript: "Nah ini tuh ada job baru biar el banget lu PB banget."
            ^^^
            → "ini" = "this" → speaker is showing something
```

### Strategy 3: Domain-Specific Terms
Game names, tool names, tournament names that might be misspelled.

```
Transcript: "Ya kan Ragnarok. Tahu Raknarok? Raknarok tahu tahu."
                         ^^^^^^^^
                         → Likely misspelled game name
```

### Strategy 4: Claims and Statistics
Numbers, prices, dates that need fact-checking.

```
Transcript: "1 juta dolar berarti kalau rupiah sekarang 18 M"
            ^^^^^^^^^^^^
            → Monetary claim, verify against visual/web
```

## LLM Prompt for Moment Detection

```
Analyze this video transcript and identify {N} key moments that need 
visual verification from video frames.

Video Title: {title}
Duration: {duration}s

Transcript:
{transcript}

For each moment, provide:
- timestamp: MM:SS format
- word: the triggering word/phrase
- context: surrounding text
- reason: [proper_noun, claim, deictic, speaker_id, visual_context]
- question: specific question for vision model
- priority: 1 (critical) to 5 (nice-to-have)
```

## Frame Extraction Workflow

1. Parse JSON3 → extract transcript segments with word-level timing
2. LLM identifies key moments → list of timestamps
3. Extract frames at those timestamps via `--timestamps` flag
4. Vision-analyze each frame with moment-specific questions
5. Cross-reference visual evidence with transcript
6. Produce grounded summary

## Anti-Patterns

### ❌ Don't: Hardcode language-specific keywords
```python
# BAD: Only works for Indonesian
DEICTIC_KEYWORDS = ["ini", "itu", "lihat"]
```

### ✅ Do: Let LLM decide what needs verification
```python
# GOOD: Works for all languages
prompt = "Identify moments that need visual verification..."
moments = llm_analyze(transcript, prompt)
```

### ❌ Don't: Use generic vision questions
```python
# BAD: Not specific enough
vision_analyze(frame, "What is shown?")
```

### ✅ Do: Use moment-specific questions
```python
# GOOD: Targeted verification
vision_analyze(frame, "What game name is displayed on screen?")
```

### ❌ Don't: Trust transcript for speaker identification
```python
# BAD: Assumes speaker from text alone
speaker = "Tepe46" if "rekrut" in text else "George"
```

### ✅ Do: Cross-reference with visual evidence
```python
# GOOD: Verify via Discord UI / facecam
speaker = identify_from_discord_ui(frame) or identify_from_facecam(frame)
```
