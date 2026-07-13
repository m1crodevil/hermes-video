# Transcript Proofreading & Correction Tools

_Landscape research — July 2026_

## The Problem

Auto-captions (Whisper, YouTube auto-subs) mishear words, especially:
- **Financial jargon**: EBITDA, P/E ratio, ticker symbols, "billion" vs "million"
- **Proper nouns**: brand names, platform names, people names
- **Numbers**: dollar amounts, percentages, dates
- **Indonesian-specific**: mixed Indo-English speech, local slang

For clipping workflows, subtitle typos → misunderstood content → bad clips.

## Tool Landscape

### 1. Whisply (github.com/tsmdt/whisply)
- **Approach**: YAML dictionary-based word replacement
- **How it works**: `--post_correction corrections.yaml`
  ```yaml
  # Single word corrections
  Gardamer: Gadamer
  # Pattern-based corrections
  patterns:
    - pattern: 'Klaus-(Cira|Cyra|Tira)-Stiftung'
      replacement: 'Klaus Tschira Stiftung'
  ```
- **Pros**: Simple, deterministic, no LLM needed
- **Cons**: Manual — must know errors in advance. No contextual understanding.
- **Best for**: Known recurring misheard words (e.g., specific brand names)

### 2. skill-caption-clip (github.com/kwindla/skill-caption-clip)
- **Approach**: LLM-in-the-loop (Claude Code skill)
- **How it works**: After SRT generation, Claude reads and cleans:
  1. Fix transcription errors (context-aware)
  2. Remove filler words ("like", "um", "you know")
  3. Consolidate fragments into sentences
  4. Improve readability
  5. Fix timestamp errors
- **Output**: `clip_clean.srt`
- **Pros**: Context-aware, handles novel errors
- **Cons**: Claude Code specific, not standalone. No JSON3 support (SRT only).
- **Best for**: Short clips where readability matters

### 3. SubtitleEdit (github.com/SubtitleEdit/subtitleedit)
- **Approach**: GUI subtitle editor with built-in spell check
- **Pros**: Mature, supports many formats, visual editing
- **Cons**: Manual editing, not automated
- **Best for**: Manual fine-tuning after automated correction

### 4. Reddit r/LocalLLaMA approach (DIY)
- **Workflow**:
  1. Extract noun list from audio (named entity recognition)
  2. Feed transcript + noun list to LLM
  3. Prompt: "Correct this transcript using this noun list"
- **Pros**: Very accurate for proper nouns
- **Cons**: Requires NER step, manual setup
- **Best for**: High-stakes content where accuracy is critical

### 5. Academic: LLM-based ASR post-correction
- Multiple papers (2024-2026) on using fine-tuned LLMs for ASR error correction
- Key finding: LLMs excel at contextual correction but can introduce new errors
- Not packaged as standalone tools — research prototypes only

## For Our Workflow

**No ready-made tool reads JSON3 + does LLM proofread.**

Viable options:
1. **Dictionary overlay** — maintain YAML of known finance terms, apply post-transcription (Whisply pattern)
2. **Lightweight LLM proofread script** — read JSON3 segments, batch to LLM, output corrected JSON3 (~50-100 lines Python)
3. **Hybrid** — dictionary for known terms + LLM for contextual correction

Cost: transcript is few thousand tokens per 10 min → LLM proofread costs <$0.01 per video.

## Key Insight

Most tools target SRT format. Our pipeline uses JSON3 (word-level timestamps). Any proofreading solution needs to either:
- Convert JSON3 → SRT → proofread → convert back (lossy)
- Read JSON3 directly and preserve word-level timestamps (better)
