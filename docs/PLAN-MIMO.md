# claude-video Engine Migration Plan
## Claude → OpenCode Zen (MiMo V2.5)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace Claude's native vision engine with OpenCode Zen API (MiMo V2.5) for video analysis, maintaining full multimodal capabilities while leveraging existing MiMo setup.

**Architecture:** Keep Python pipeline (download, frames, transcription, dedup) unchanged. Add OpenCode Zen API client layer that sends frames + transcript to MiMo V2.5, receives multimodal analysis.

**Tech Stack:** Python 3.11+, requests/httpx, OpenAI-compatible API format, base64 image encoding

---

## Executive Summary

### Current Flow (Claude)
```
Video URL → yt-dlp → ffmpeg → frames.jpg + transcript.txt → Claude Read() → Analysis
```

### Target Flow (MiMo)
```
Video URL → yt-dlp → ffmpeg → frames.jpg + transcript.txt → OpenCode Zen API → MiMo V2.5 → Analysis
```

**Key Change:** Replace Claude's multimodal `Read` tool with OpenCode Zen API HTTP calls.

---

## Architecture Comparison

| Aspect | Current (Claude) | Target (MiMo) |
|--------|------------------|---------------|
| **Image Input** | Native `Read` tool | API HTTP POST (base64) |
| **Transcript** | Text in context | API text content |
| **Processing** | Claude's inference | MiMo V2.5 inference |
| **Cost** | Claude token pricing | OpenCode Zen pricing |
| **Latency** | Depends on Claude | Depends on OpenCode Zen |
| **Context Window** | 200K (Claude) | 1M (MiMo) |

---

## Phase 1: OpenCode Zen API Client

**Objective:** Create API client that can send images + text to MiMo V2.5

### Task 1.1: Research OpenCode Zen API Format

**Objective:** Understand API authentication, endpoint, and request format

**Files:**
- Create: `docs/opencode-zen-api-notes.md`

**Steps:**
1. Check OpenCode Zen documentation (if available)
2. Test with simple text completion first
3. Document API endpoint, auth method, request/response format
4. Test with image input (if supported)

**Verification:** Working curl command that sends text to MiMo

---

### Task 1.2: Create API Client Module

**Objective:** Build reusable client for OpenCode Zen API

**Files:**
- Create: `src/opencode_client.py`
- Create: `tests/test_opencode_client.py`

**Step 1: Write failing test**

```python
def test_opencode_client_init():
    from opencode_client import OpenCodeClient
    client = OpenCodeClient(api_key="test", model="mimo-v2.5-free")
    assert client.model == "mimo-v2.5-free"
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_opencode_client.py -v`
Expected: FAIL — "ModuleNotFoundError: No module named 'opencode_client'"

**Step 3: Write minimal implementation**

```python
import requests
from typing import List, Dict, Any

class OpenCodeClient:
    def __init__(self, api_key: str, model: str = "mimo-v2.5-free"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.opencode.zen/v1"  # Placeholder - verify actual URL
    
    def chat_completion(
        self, 
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """Send chat completion request to OpenCode Zen API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_opencode_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/opencode_client.py tests/test_opencode_client.py
git commit -m "feat: add OpenCode Zen API client module"
```

---

### Task 1.3: Add Image Support to API Client

**Objective:** Extend client to send base64 images in messages

**Files:**
- Modify: `src/opencode_client.py`
- Modify: `tests/test_opencode_client.py`

**Step 1: Write failing test**

```python
def test_send_image():
    from opencode_client import OpenCodeClient
    client = OpenCodeClient(api_key="test", model="mimo-v2.5-free")
    
    # Test image message structure
    image_b64 = "base64_encoded_image_placeholder"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]
        }
    ]
    
    # Verify message structure is correct
    assert messages[0]["content"][1]["type"] == "image_url"
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_opencode_client.py::test_send_image -v`
Expected: PASS (structure test only)

**Step 3: Add image helper method**

```python
def create_image_message(self, image_b64: str, text: str = "Describe this image") -> Dict[str, Any]:
    """Create a message with base64 image"""
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
        ]
    }

def create_multiframe_message(self, frames: List[str], transcript: str) -> Dict[str, Any]:
    """Create message with multiple frames + transcript"""
    content = [{"type": "text", "text": f"Transcript:\n{transcript}\n\nFrames:"}]
    
    for i, frame_b64 in enumerate(frames):
        content.append({
            "type": "text", 
            "text": f"\nFrame {i+1}:"
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}
        })
    
    return {"role": "user", "content": content}
```

**Step 3: Run test to verify pass**

Run: `pytest tests/test_opencode_client.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/opencode_client.py tests/test_opencode_client.py
git commit -m "feat: add image support to OpenCode client"
```

---

## Phase 2: Integration with claude-video Pipeline

**Objective:** Replace Claude's `Read` tool with OpenCode Zen API calls

### Task 2.1: Create Video Analyzer Wrapper

**Objective:** High-level wrapper that orchestrates download → frames → API call → analysis

**Files:**
- Create: `src/video_analyzer.py`
- Create: `tests/test_video_analyzer.py`

**Step 1: Write failing test**

```python
def test_video_analyzer_init():
    from video_analyzer import VideoAnalyzer
    analyzer = VideoAnalyzer(api_key="test")
    assert analyzer.client is not None
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_video_analyzer.py -v`
Expected: FAIL — "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
import base64
from pathlib import Path
from typing import Optional
from opencode_client import OpenCodeClient

class VideoAnalyzer:
    def __init__(self, api_key: str, model: str = "mimo-v2.5-free"):
        self.client = OpenCodeClient(api_key=api_key, model=model)
    
    def load_frame_as_base64(self, frame_path: str) -> str:
        """Load JPEG frame and return base64 encoded string"""
        with open(frame_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def analyze_video(
        self,
        frames_dir: str,
        transcript_path: str,
        question: str,
        max_frames: int = 50
    ) -> str:
        """Analyze video frames + transcript using MiMo V2.5"""
        # Load transcript
        with open(transcript_path, "r") as f:
            transcript = f.read()
        
        # Load frames
        frames = sorted(Path(frames_dir).glob("*.jpg"))[:max_frames]
        frames_b64 = [self.load_frame_as_base64(str(f)) for f in frames]
        
        # Create message
        message = self.client.create_multiframe_message(frames_b64, transcript)
        
        # Add user question
        message["content"].append({
            "type": "text",
            "text": f"\n\nQuestion: {question}"
        })
        
        # Call API
        response = self.client.chat_completion(
            messages=[message],
            temperature=0.3,
            max_tokens=4096
        )
        
        return response["choices"][0]["message"]["content"]
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_video_analyzer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/video_analyzer.py tests/test_video_analyzer.py
git commit -m "feat: add VideoAnalyzer wrapper for MiMo integration"
```

---

### Task 2.2: Integrate with Existing watch.py

**Objective:** Modify watch.py to use VideoAnalyzer instead of Claude

**Files:**
- Modify: `skills/watch/scripts/watch.py`

**Step 1: Understand current flow**

Read `skills/watch/scripts/watch.py` to find where Claude's `Read` tool is called.

**Step 2: Add OpenCode mode flag**

Add `--engine opencode` flag to argument parser:
- `--engine claude` (default) - existing behavior
- `--engine opencode` - new MiMo path

**Step 3: Implement engine switching**

```python
if args.engine == "opencode":
    from video_analyzer import VideoAnalyzer
    analyzer = VideoAnalyzer(
        api_key=os.getenv("OPENCODE_API_KEY"),
        model=args.model or "mimo-v2.5-free"
    )
    result = analyzer.analyze_video(
        frames_dir=frames_dir,
        transcript_path=transcript_path,
        question=question,
        max_frames=args.max_frames
    )
    print(result)
else:
    # Existing Claude logic
    pass
```

**Step 4: Commit**

```bash
git add skills/watch/scripts/watch.py
git commit -m "feat: add OpenCode engine option to watch.py"
```

---

## Phase 3: Hermes Skill Integration

**Objective:** Create Hermes skill that wraps the modified claude-video

### Task 3.1: Create Hermes Skill SKILL.md

**Objective:** Define skill contract for Hermes integration

**Files:**
- Create: `skills/hermes-watch/SKILL.md`

**Content:**
```markdown
---
name: hermes-watch
description: "Analyze videos using MiMo V2.5 via OpenCode Zen. Downloads, extracts frames, transcribes, and analyzes video content."
version: 1.0.0
author: microdevil
license: MIT
---

# hermes-watch

Video analysis skill powered by MiMo V2.5 (OpenCode Zen)

## Prerequisites

- Python 3.11+
- ffmpeg (installed on first run)
- yt-dlp (installed on first run)
- OpenCode Zen API key (set in env or .env)

## Usage

```
/watch https://youtu.be/VIDEO_ID what happens at 2:30?
/watch --start 1:00 --end 2:00 https://youtu.be/VIDEO_ID summarize this section
```

## Configuration

Set in `~/.config/watch/.env`:
```
OPENCODE_API_KEY=your_key_here
OPENCODE_MODEL=mimo-v2.5-free
```

## How It Works

1. Downloads video via yt-dlp
2. Extracts frames via ffmpeg (scene-aware)
3. Transcribes audio (captions or Whisper)
4. Sends frames + transcript to MiMo V2.5 via OpenCode Zen API
5. Returns multimodal analysis

## Detail Modes

- `--detail transcript` - Text only (cheapest)
- `--detail efficient` - Keyframes (fast)
- `--detail balanced` - Scene-aware (default)
- `--detail token-burner` - Full coverage (most tokens)

## Token Costs

MiMo V2.5 pricing via OpenCode Zen:
- Input: ~$X per 1M tokens
- Output: ~$Y per 1M tokens
- Image tokens: ~197 tokens per frame (512px width)

## Limitations

- Long videos (>10min) use focused mode for best results
- Frame deduplication enabled by default
- Whisper fallback requires API key (Groq or OpenAI)
```

**Step 2: Commit**

```bash
git add skills/hermes-watch/SKILL.md
git commit -m "docs: add Hermes watch skill contract"
```

---

### Task 3.2: Update Installation Scripts

**Objective:** Modify setup.py to configure OpenCode Zen

**Files:**
- Modify: `skills/watch/scripts/setup.py`

**Step 1: Add OpenCode API key prompt**

In `setup.py`, add section for OpenCode Zen:
```python
def setup_opencode():
    """Configure OpenCode Zen API"""
    config_dir = Path.home() / ".config" / "watch"
    env_file = config_dir / ".env"
    
    if not env_file.exists():
        api_key = input("Enter OpenCode Zen API key (or press Enter to skip): ").strip()
        if api_key:
            with open(env_file, "a") as f:
                f.write(f"\nOPENCODE_API_KEY={api_key}\n")
            print(f"✓ Saved to {env_file}")
```

**Step 2: Commit**

```bash
git add skills/watch/scripts/setup.py
git commit -m "feat: add OpenCode Zen setup to installation"
```

---

## Phase 4: Testing & Validation

### Task 4.1: Create Integration Tests

**Objective:** End-to-end test with real video

**Files:**
- Create: `tests/integration/test_opencode_video.py`

**Test cases:**
1. Short YouTube video (< 1 min)
2. Video with captions
3. Video without captions (Whisper fallback)
4. Local video file
5. Focused time range (--start/--end)

**Verification:**
- MiMo receives frames successfully
- Response includes visual descriptions
- Transcript is integrated correctly
- No hallucinations about visual content

---

### Task 4.2: Benchmark RAM Usage

**Objective:** Compare Python vs Rust memory usage (for future optimization)

**Files:**
- Create: `scripts/benchmark_memory.py`

**Metrics to capture:**
- Peak RSS during frame extraction
- Peak RSS during API call
- Total execution time
- Token usage from API response

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **OpenCode Zen API doesn't support vision** | High | Verify API format in Phase 1; fallback to transcript-only |
| **Base64 image too large** | Medium | Resize frames to 512px, compress JPEG quality |
| **API rate limits** | Medium | Add retry logic, exponential backoff |
| **MiMo vision quality inferior to Claude** | Medium | A/B test, allow engine selection |
| **Token costs higher than expected** | Low | Use `--detail efficient` by default, show cost estimate |

---

## Success Criteria

- [ ] OpenCode Zen API client sends images successfully
- [ ] MiMo V2.5 returns accurate visual descriptions
- [ ] Integration with existing pipeline works
- [ ] Hermes skill loads and executes correctly
- [ ] RAM usage < 150MB for 100 frames
- [ ] End-to-end test passes with real video

---

## Open Questions

1. **OpenCode Zen API format:** Is it OpenAI-compatible? Need to verify in Phase 1.
2. **Image encoding:** Does API accept base64 or only URLs?
3. **Token limits:** What's max input tokens for MiMo via OpenCode Zen?
4. **Pricing:** What's the cost per image token?

**Action:** Answer these in Task 1.1 before proceeding.

---

## Future Enhancements (Post-MVP)

1. **Rust rewrite** - Optimize frame extraction + dedup
2. **Parallel frame processing** - Async API calls for multiple frames
3. **Caching** - Store analyzed videos to avoid re-processing
4. **Batch mode** - Analyze entire YouTube channel
5. **Export formats** - Markdown, JSON, PDF reports

---

**Plan saved to:** `.hermes/plans/2026-07-09_143000-claude-video-opencode-mimo.md`

**Ready to execute using subagent-driven-development?**
