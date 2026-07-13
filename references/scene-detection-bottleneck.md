# Scene Detection Bottleneck Analysis

## Core insight

Scene detection (ffmpeg `select` filter, PySceneDetect, or any engine) **must decode every frame** to compute change scores. This is a fundamental constraint — no engine swap can avoid it.

```
64 min × 30fps = ~115K frames
Each frame: partial decode + score computation
→ CPU-bound, ~300-600s on VPS without GPU
```

## Why PySceneDetect doesn't help

| Engine | Full decode? | Speed | Notes |
|--------|-------------|-------|-------|
| ffmpeg `select` filter | Yes | Faster (C-native) | Partial decode + score |
| PySceneDetect (OpenCV) | Yes | **Slower** | Full frame decode + Python overhead |

Both must read every frame. PySceneDetect adds OpenCV overhead on top.

## Transcript-first extraction is superior for long videos

| Approach | Work | Time (64 min video) |
|----------|------|---------------------|
| Scene detection | Decode ~115K frames | 300s+ (timeout) |
| Keyframe extraction | Decode ~200-500 I-frames | 10-20s |
| Transcript-driven | Read text, LLM, extract N frames | ~30s total |

Transcript provides **semantic understanding** (what moments matter) vs scene detection's **visual understanding** (what moments are different).

## Resolution

For videos >10 min with captions available:
1. Use `--detail transcript` (no video download, instant)
2. LLM identifies key timestamps from transcript
3. Extract frames at specific timestamps (per-frame, ~2s each)

For videos >10 min without captions:
1. Use `--detail efficient` (keyframes only, near-instant)
2. Or use `background=true` to avoid terminal timeout
