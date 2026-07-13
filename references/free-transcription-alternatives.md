# Free & Local Transcription Alternatives

When videos lack native captions and the user doesn't want to pay for Groq/OpenAI Whisper, these are the viable free options.

## 1. faster-whisper (RECOMMENDED — local, free, best quality)

- **Install:** `pip install faster-whisper`
- **Supports:** 99+ languages including Indonesian ✅
- **Runs:** Locally on CPU/GPU, no internet needed after model download
- **Model sizes:** tiny (75MB), base (150MB), small (500MB), medium (1.5GB), large-v3 (3GB)
- **RAM needed:** ~2GB (small), ~4GB (medium), ~6GB (large) — VPS with 7.6GB can handle medium
- **Speed:** ~5-10x real-time on CPU (80 min audio → 8-16 min processing)
- **Quality:** Same as OpenAI Whisper (uses same model weights)

```bash
pip install faster-whisper
# Quick test
python3 -c "
from faster_whisper import WhisperModel
model = WhisperModel('medium', device='cpu', compute_type='int8')
segments, info = model.transcribe('audio.mp3', language='id')
for seg in segments:
    print(f'[{seg.start:.1f}s -> {seg.end:.1f}s] {seg.text}')
"
```

**Pitfalls:**
- First run downloads model to `~/.cache/huggingface/` — may take a few minutes
- `large-v3` on CPU is slow (~1-2x real-time) — use `medium` for speed/quality balance
- Indonesian accuracy is good but not perfect — proper nouns and slang may error

## 2. whisper.cpp (local, C/C++ — fastest on CPU)

- **Install:** `brew install whisper.cpp` or build from source
- **Speed:** 3-5x faster than Python whisper on same hardware
- **RAM:** Lower than Python versions
- **Quality:** Same model weights as OpenAI Whisper
- **Languages:** 99+ including Indonesian

Best for: maximum speed on CPU-only VPS. Requires building from source on Linux.

## 3. Qwen3-ASR-1.7B (local, very lightweight)

- **Model:** 1.7B parameters (vs Whisper's 1.5B for large-v3)
- **Supports:** 30 languages including Indonesian ✅
- **Install:** `pip install transformers torch` + download model
- **RAM:** ~2-3GB
- **Strengths:** Also handles singing voice, lyrics, noisy environments
- **Weakness:** Newer model, less battle-tested than Whisper for Indonesian

## 4. Groq Whisper (cloud, paid — reference only)

See [groq-whisper-limits.md](groq-whisper-limits.md) for full specs.

- $0.04/hr (turbo) or $0.111/hr (v3)
- Super fast (216x real-time)
- Needs API key + billing setup

## ❌ NOT Recommended

### Puter.js
- JavaScript-only (browser frontend) — no Python SDK
- Requires end-user Puter account authentication
- "Free" means user pays via Puter credits
- Audio sent to Puter → OpenAI servers (privacy concern)
- **Not compatible with hermes-video (Python CLI tool)**

### MiMo-V2.5-ASR
- Only supports Chinese + English — **NO Indonesian**
- Good for Chinese content but useless for Indonesian podcasts/interviews
- $0.074/hr via Xiaomi API

### Vosk
- Offline, open-source, but lower accuracy than Whisper
- Limited Indonesian model quality
- Better suited for real-time streaming than file transcription

## Decision Matrix

| Option | Free | Indonesian | Speed | Quality | Offline | Setup |
|---|---|---|---|---|---|---|
| faster-whisper medium | ✅ | ✅ | ~5-10x | High | ✅ | Easy |
| whisper.cpp | ✅ | ✅ | ~15-30x | High | ✅ | Medium |
| Qwen3-ASR-1.7B | ✅ | ✅ | ~5x | Good | ✅ | Easy |
| Groq Whisper turbo | ❌ $0.04/hr | ✅ | 216x | High | ❌ | Easy |
| Puter.js | ⚠️ | ✅ | Fast | High | ❌ | N/A (JS only) |
| MiMo ASR | ❌ | ❌ | Fast | High | ❌ | N/A |
