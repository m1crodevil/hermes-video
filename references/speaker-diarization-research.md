# Speaker Diarization Research (July 2026)

## Overview

Speaker diarization is the process of determining "who spoke when" in audio/video. This research was conducted to explore solutions for connecting transcript segments with visual evidence in multi-speaker videos.

## Audio-Based Diarization Tools

### WhisperX (Most Practical)
- **Approach:** Whisper + pyannote + word-level alignment
- **Accuracy:** 90-95% for 2-3 speakers in clean recordings
- **Cost:** Free (local, requires GPU recommended)
- **Integration:** `whisperx.DiarizationPipeline` + `whisperx.assign_word_speakers()`
- **Caveat:** Requires HuggingFace token for pyannote model

### pyannote.audio
- **Approach:** End-to-end diarization pipeline
- **Accuracy:** 85-92%
- **Cost:** Free (local)
- **Integration:** Standalone, can be used with Whisper output
- **Caveat:** Requires HuggingFace token

### Faster-Whisper + Pyannote
- **Approach:** Custom stack combining fast transcription with diarization
- **Accuracy:** 90%+
- **Cost:** Free (local)
- **Integration:** More complex setup, custom pipeline

### Cloud APIs
- **Google Cloud Speech-to-Text:** Built-in diarization, $0.009/15s
- **AssemblyAI:** API with diarization, $0.37/hr
- **Groq Whisper:** No native diarization

## Visual/Audio-Visual Diarization

### SyncNet
- **Approach:** Audio-visual synchronization model
- **Status:** Research-level, not production-ready
- **GitHub:** wangyz1999/syncnet-speaker-diarization

### HumanOmni-Speaker
- **Approach:** Multimodal (audio+visual) speaker identification
- **Status:** Recent research (2025-2026)
- **Capability:** Identifies who said what and when using both modalities

### Active Speaker Detection
- **Approach:** Face detection + lip movement analysis
- **Status:** Research-level
- **Use case:** Identifying who is speaking in video frames

## Practical Recommendations for Watch Skill

### Current Approach (Recommended)
Use **LLM-driven moment detection** via `--auto-moments`:
- Zero hardcoding, works across languages
- Agent-driven workflow (LLM analysis in agent context)
- No additional dependencies required
- Already implemented in watch skill v1.9.0

### Future Enhancement: WhisperX Integration
For videos without captions, consider adding WhisperX for speaker-labeled transcripts:
```python
# Future implementation pattern
import whisperx

model = whisperx.load_model("large-v3", device)
result = model.transcribe(audio)

# Align for word timestamps
model_a, metadata = whisperx.align_model(language_code=result["language"], device=device)
result = whisperx.align(result["segments"], model_a, metadata, audio, device)

# Diarize and assign speakers
diarize_model = whisperx.DiarizationPipeline(use_auth_token="HF_TOKEN", device=device)
diarize_segments = diarize_model(audio, min_speakers=2, max_speakers=5)
result = whisperx.assign_word_speakers(diarize_segments, result)
```

**Benefits:**
- Speaker-labeled transcript segments
- Word-level timestamps with speaker attribution
- Works with any language

**Drawbacks:**
- Requires GPU for reasonable speed
- Requires HuggingFace token
- Adds complexity to the pipeline

### When to Use Each Approach

| Scenario | Approach |
|----------|----------|
| Multi-speaker video with captions | `--auto-moments` + visual verification |
| Video without captions | Whisper fallback (Groq/OpenAI) |
| Need speaker labels | WhisperX (future enhancement) |
| Need visual speaker ID | Vision analysis of Discord UI/facecam |

## Key Learnings

1. **ASR confidence scores not always available:** YouTube Indonesian auto-captions return `acAsrConf: 0` for all words. Cannot rely on confidence-based filtering.

2. **Transcript alone cannot identify speakers:** Without visual context, "I recruited him" could be said by either speaker. Always cross-reference with visual evidence.

3. **Hardcoded keywords break cross-language support:** Initial approaches often hardcode language-specific keywords (e.g., Indonesian deictic markers). LLM-driven detection is more universal.

4. **Visual evidence is critical for speaker identification:** Discord UI, streamer facecam, and game UI provide speaker identity clues that transcript alone cannot.

## References

- WhisperX: github.com/m-bain/whisperx
- pyannote.audio: github.com/pyannote/pyannote-audio
- SyncNet: github.com/wangyz1999/syncnet-speaker-diarization
- HumanOmni-Speaker: arxiv.org/html/2603.21664v3
