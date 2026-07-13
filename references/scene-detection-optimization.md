# Scene Detection Optimization

## Current Implementation

The watch skill uses ffmpeg's `select='gt(scene,THRESHOLD)'` filter for scene detection:
- **Default threshold:** 0.20 (SCENE_MIN_FRAMES=8)
- **Engine:** `extract_scene_candidates()` in frames.py
- **Behavior:** Detects all scene changes (uncapped), then even-samples down to max_frames

## Problem: Long Videos with Gradual Transitions

For documentary/vlog content (40+ min), threshold 0.20 produces sparse coverage:
- 44-min video → only 25 frames detected
- Gaps up to 8.2 minutes between frames
- Many gradual transitions (slow pans, lighting changes) missed

**Core bottleneck:** Scene detection requires full video decode — frame-by-frame score computation. A 54-min video at 30fps = ~97,000 frames to decode. This dominates processing time (~300s for 54 min).

## Threshold Guidelines (from ffmpeg-cookbook.com, GDELT Project)

| Threshold | Use Case | Notes |
|-----------|----------|-------|
| 0.45-0.50 | Hard cuts only | Very conservative, misses most transitions |
| 0.35 | Significant cuts | Standard "significant changes" |
| 0.25-0.30 | Fast-cut content | Sports, music videos |
| 0.20 | Default for ≤10 min | Only large visual changes |
| 0.15-0.18 | Gradual transitions | Documentaries, vlogs, talking head |
| 0.10-0.12 | Maximum sensitivity | Many false positives, surveillance footage |

## scdet Filter Alternative

ffmpeg also has `scdet` filter with different scale (0-100, default 10):
```
ffmpeg -i input.mp4 -vf "scdet=t=10" -f null /dev/null
```

- `lavfi.scd.score` → scene change score (higher = larger change)
- `lavfi.scd.time` → timestamp of detection
- Threshold range: 5-50 (documentaries: 10-20, sports: 15-25)

**Note:** `select` scene score and `scdet` score are NOT the same scale.

## Implemented Optimizations (v1.8.0)

### 1. Adaptive Threshold Based on Video Duration

```python
def adaptive_scene_threshold(duration_seconds: float, fps: float = 30.0) -> float:
    """Lower threshold for longer videos to catch more gradual transitions."""
    if duration_seconds <= 60:        # ≤1 min (shorts, clips)
        return 0.25  # Higher threshold for short content
    elif duration_seconds <= 300:     # ≤5 min
        return 0.22  # Moderate
    elif duration_seconds <= 600:     # ≤10 min
        return 0.20  # Current default (works well here)
    elif duration_seconds <= 1800:    # ≤30 min
        return 0.17  # Lower for longer content
    elif duration_seconds <= 3600:    # ≤60 min
        return 0.15  # Even lower for long-form
    else:                             # >60 min
        return 0.12  # Most sensitive for very long videos
```

### 2. Gap-Filling Uniform Sampling

After scene detection, large gaps (>2× expected interval) are filled with uniform frames:

```python
fill_threshold = min(120.0, effective_duration / target_frames * 2)

for gap in large_gaps:
    num_fill = min(int(gap / fill_threshold) - 1, 5)  # Cap at 5 per gap
    # Extract uniform frames at evenly-spaced timestamps within the gap
```

### 3. Minimum Frame Density Guarantee

Videos >10 minutes guarantee at least 1 frame per 60 seconds:

```python
min_fps_for_long_videos = 1.0 / 60.0 if duration_seconds > 600 else 0
fps = max(calculated_fps, min_fps_for_long_videos)
```

### 4. Two-Pass Mode (Token-Burner)

```python
# Pass 1: Scene detection (uncapped, catches hard cuts)
scene_frames = extract_scene_or_uniform(...)

# Pass 2: Uniform sampling at 50% density (catches gradual transitions)
uniform_frames = extract(..., fps=fps * 0.5, max_frames=target_frames // 2)

# Merge + dedup
all_frames = sorted(scene_frames + uniform_frames, key=timestamp)
deduped = dedupe_perceptual(all_frames)
```

## FPS Downsampling for Scene Detection (Proposed)

Scene detection bottleneck: ffmpeg must decode every frame (~30fps) to compute scene scores. For a 54-min video at 30fps, that's ~97,000 frames to decode. Downsampled detection reduces this significantly.

### Approach: Two-Pass with fps Filter

```bash
# Pass 1: Detect scenes at reduced fps (fast)
ffmpeg -i input.mp4 -vf "fps=5,select='gt(scene,0.15)'" -vsync vfr -f null /dev/null 2>&1 | grep pts_time

# Pass 2: Extract at detected timestamps, full quality
for ts in detected_timestamps; do
  ffmpeg -ss $ts -i input.mp4 -frames:v 1 -q:v 2 frame_${ts}.jpg
done
```

### Dynamic FPS Based on Duration

```python
def scene_detection_fps(duration_seconds: float) -> int:
    if duration_seconds <= 300:     # ≤5 min
        return 30                   # Full fps (short video, negligible)
    elif duration_seconds <= 900:   # ≤15 min
        return 10                   # 3x speedup
    elif duration_seconds <= 1800:  # ≤30 min
        return 5                    # 6x speedup
    else:                           # >30 min
        return 2                    # 15x speedup (~20s for 54 min)
```

### Speedup Estimates

| Video Length | 30fps (current) | 5fps | 2fps |
|---|---|---|---|
| 10 min | ~60s | ~10s | ~5s |
| 30 min | ~180s | ~30s | ~12s |
| 54 min | ~300s | ~50s | ~20s |
| 90 min | ~500s | ~85s | ~35s |

### Trade-offs

| | 30fps | 5fps | 2fps |
|---|---|---|---|
| Hard cuts | ✅ | ✅ | ✅ |
| Gradual transitions | ✅ | ⚠️ can miss | ❌ often missed |
| Talking head (static cam) | ✅ | ⚠️ | ❌ |
| Speed | 1x | 6x | 15x |

**Sweet spot for podcast/talk show:** 5fps — hard cuts still detected, gradual transitions reasonably captured.

### PySceneDetect Alternative: frame_skip

PySceneDetect has a `frame_skip` parameter that skips N frames during detection:

```python
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

video = open_video('video.mp4')
sm = SceneManager()
sm.add_detector(ContentDetector(threshold=0.15, frame_skip=5))
sm.detect_scenes(video)
scenes = sm.get_scene_list()
```

**Caveat from PySceneDetect docs:** "Using the frame skip option disallows the use of a stats file, which offsets the speed gain if the same video needs to be processed multiple times. Also reduces frame-accurate scene cuts — only use with high FPS material (ideally >60 FPS), at low values (try not to exceed 1 or 2)."

### Why Rust (watch2) Doesn't Help Here

The bottleneck is ffmpeg's C-based `select` filter decoding every frame. Whether called from Python or Rust, the ffmpeg process takes the same time. Rust speedup applies to orchestration, file I/O, and transcript processing — not the scene detection decode itself.

## Expected Improvement (44-min documentary)

| Metric | Before | After |
|--------|--------|-------|
| Frames | 25 | 60-80 |
| Max gap | 8.2 min | < 2 min |
| Coverage | ~57% | ~90%+ |
| Threshold | Fixed 0.20 | Adaptive 0.12-0.25 |

## References

- GDELT Project: ffmpeg scene detection for TV news analysis
- ffmpeg-cookbook.com: scene detection thresholds
- ffmpeg documentation: select filter, scdet filter
- PySceneDetect: ContentDetector algorithm (HSV histogram difference)
- PySceneDetect CLI: --frame-skip option for speed optimization