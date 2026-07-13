# Groq Whisper — Limits & Practical Notes

Source: console.groq.com/docs/speech-to-text, /model/whisper-large-v3, /model/whisper-large-v3-turbo, /docs/rate-limits

## Models

| | whisper-large-v3 | whisper-large-v3-turbo |
|---|---|---|
| Price | $0.111/hr | $0.04/hr |
| Parameters | 1,550M | Optimized (smaller) |
| Speed | 189x real-time | 216x real-time |
| WER | 10.3% | 12% |
| Translation to EN | Yes | No |
| Languages | 99+ | 99+ |

## File Size Limits

- Free tier: 25 MB upload max
- Developer tier (paid): 100 MB upload max
- Larger files: use url parameter to pass a URL instead of upload

## Audio Requirements

- Formats: FLAC, MP3, M4A, MPEG, MPGA, OGG, WAV, WEBM
- Minimum length: 0.01s
- Minimum billed: 10s (sub-10s still billed as 10s)
- Audio context: Optimized for 30-second segments, min 10s/segment
- Single track only: files with multiple audio tracks -> only first track transcribed
- Downsampling: Groq auto-downsamples to 16KHz mono. Client-side preprocessing recommended for large files:

```bash
ffmpeg -i input.mp4 -ar 16000 -ac 1 -map 0:a -c:a flac output.flac
```

## Rate Limits (Developer tier)

| | RPM | RPD | ASH (audio sec/hr) | ASD (audio sec/day) |
|---|---|---|---|---|
| whisper-large-v3 | 20 | 2,000 | 7,200 (= 2 hrs) | 28,800 (= 8 hrs) |
| whisper-large-v3-turbo | 20 | 2,000 | 7,200 (= 2 hrs) | 28,800 (= 8 hrs) |

## Output Options

- response_format: json, verbose_json, text
- timestamp_granularities: segment, word, or both (requires verbose_json)
- temperature: 0-1 (default 0)
- prompt: Max 224 tokens (style/spelling guidance only)

## Metadata (verbose_json)

- avg_logprob: Confidence. Closer to 0 = better. Below -0.5 = likely issues.
- no_speech_prob: Non-speech probability. Closer to 0 = definite speech.
- compression_ratio: Normal ~1.5-2.0. Outliers indicate stuttering, speed issues, or quality problems.

## Cost Estimates for Common Durations

| Duration | v3 cost | turbo cost |
|---|---|---|
| 10 min | $0.019 | $0.007 |
| 30 min | $0.056 | $0.020 |
| 60 min | $0.111 | $0.040 |
| 80 min | $0.148 | $0.053 |

## Watch Skill Integration Notes

- For videos >30 min without captions: recommend --detail efficient or --detail transcript to avoid frame extraction timeouts
- Audio chunking for files >25MB: see Groq cookbook at https://github.com/groq/groq-api-cookbook/tree/main/tutorials/audio-chunking
- Groq Whisper does NOT support speaker diarization (cannot identify who is speaking)
- No diarization = multi-speaker podcasts get one flat transcript with no speaker labels
