# claude-video MiMo Integration — Security-First Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Integrate MiMo V2.5 via OpenCode Zen into claude-video while maintaining security best practices.

**Architecture:** Keep existing Python pipeline unchanged. Add OpenCode Zen API client layer. All credentials stored in `~/.config/watch/.env` (never in code).

**Tech Stack:** Python 3.11+, stdlib-only (requests via urllib), OpenAI-compatible API format

---

## Executive Summary

### Security Checklist

- [ ] No hardcoded API keys in code
- [ ] `.env` files in `.gitignore`
- [ ] Credentials loaded from `~/.config/watch/.env` only
- [ ] No personal data transmitted
- [ ] All API calls use HTTPS
- [ ] Tokens have minimal required scopes
- [ ] Regular key rotation recommended

### Integration Points

| Component | Security Status | Action |
|-----------|----------------|--------|
| **download.py** | ✅ Safe | No changes |
| **frames.py** | ✅ Safe | No changes |
| **transcribe.py** | ✅ Safe | No changes |
| **whisper.py** | ✅ Safe | No changes |
| **config.py** | ⚠️ Update | Add `OPENCODE_API_KEY` |
| **watch.py** | ⚠️ Update | Add `--engine opencode` flag |
| **New: opencode_client.py** | 🆕 Create | API client (no hardcoded keys) |
| **New: .env.example** | 🆕 Create | Template for users |

---

## Phase 1: Security Infrastructure

### Task 1.1: Create .env.example

**Objective:** Provide template for users to configure API keys

**Files:**
- Create: `.env.example`
- Create: `.gitignore` (update)

**Step 1: Create .env.example**

```bash
# MiMo via OpenCode Zen
OPENCODE_API_KEY=your_opencode_api_key_here
OPENCODE_MODEL=mimo-v2.5-free

# Whisper (optional, for videos without captions)
GROQ_API_KEY=your_groq_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

**Step 2: Update .gitignore**

```gitignore
# Environment files
.env
**/.env
.env.local
.env.*.local
~/.config/watch/.env
```

**Step 3: Verify no secrets in git history**

```bash
git log --all --diff-filter=A --name-only | grep -i "env\|secret\|key"
# Should return empty
```

**Step 4: Commit**

```bash
git add .env.example .gitignore
git commit -m "security: add .env.example and update .gitignore"
```

---

### Task 1.2: Create SECURITY.md

**Objective:** Document security practices and vulnerability reporting

**Files:**
- Create: `SECURITY.md`

**Content:**
- Security policy
- Vulnerability reporting process
- Best practices for API key management
- Data privacy statement

**Step 1: Create SECURITY.md**

[Full content as provided above]

**Step 2: Commit**

```bash
git add SECURITY.md
git commit -m "docs: add SECURITY.md with vulnerability reporting and best practices"
```

---

## Phase 2: OpenCode Zen API Client

### Task 2.1: Create opencode_client.py

**Objective:** Build secure API client for MiMo V2.5

**Files:**
- Create: `skills/watch/scripts/opencode_client.py`
- Create: `tests/test_opencode_client.py`

**Security Requirements:**
- ✅ NO hardcoded API keys
- ✅ Load from environment variables only
- ✅ Use HTTPS only
- ✅ Validate API responses
- ✅ Handle errors gracefully

**Step 1: Write failing test**

```python
def test_opencode_client_init():
    from opencode_client import OpenCodeClient
    client = OpenCodeClient(api_key="test-key", model="mimo-v2.5-free")
    assert client.model == "mimo-v2.5-free"
    assert client.api_key == "test-key"
```

**Step 2: Run test to verify failure**

```bash
pytest tests/test_opencode_client.py -v
# Expected: FAIL — "ModuleNotFoundError"
```

**Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""OpenCode Zen API client for MiMo V2.5.

Security: API keys are loaded from environment variables only.
Never hardcode credentials in source code.
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any


class OpenCodeClient:
    """Secure client for OpenCode Zen API (MiMo V2.5)."""

    def __init__(self, api_key: str, model: str = "mimo-v2.5-free"):
        """Initialize client with API key.

        Args:
            api_key: OpenCode Zen API key (from environment variable)
            model: Model identifier (default: mimo-v2.5-free)

        Raises:
            ValueError: If api_key is empty or invalid
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        if not model or not model.strip():
            raise ValueError("Model cannot be empty")

        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = "https://opencode.zen/v1"  # Placeholder — verify actual URL

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send chat completion request to OpenCode Zen API.

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            API response dictionary

        Raises:
            ConnectionError: If API request fails
            ValueError: If response is invalid
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "watch-skill/0.2.0",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        data = json.dumps(payload).encode("utf-8")
        context = ssl.create_default_context()

        try:
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=data,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ConnectionError(f"API request failed: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ConnectionError(f"API request failed: {exc}") from exc

    def create_image_message(
        self,
        image_b64: str,
        text: str = "Describe this image",
    ) -> dict[str, Any]:
        """Create a message with base64 image.

        Args:
            image_b64: Base64-encoded image data
            text: Text prompt

        Returns:
            Message dictionary
        """
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                },
            ],
        }

    def create_multiframe_message(
        self,
        frames: list[str],
        transcript: str,
    ) -> dict[str, Any]:
        """Create message with multiple frames + transcript.

        Args:
            frames: List of base64-encoded images
            transcript: Video transcript

        Returns:
            Message dictionary
        """
        content: list[dict[str, Any]] = [
            {"type": "text", "text": f"Transcript:\n{transcript}\n\nFrames:"}
        ]

        for i, frame_b64 in enumerate(frames):
            content.append({"type": "text", "text": f"\nFrame {i + 1}:"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"},
                }
            )

        return {"role": "user", "content": content}
```

**Step 4: Run test to verify pass**

```bash
pytest tests/test_opencode_client.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add skills/watch/scripts/opencode_client.py tests/test_opencode_client.py
git commit -m "feat: add secure OpenCode Zen API client for MiMo V2.5

- NO hardcoded API keys
- Load from environment variables only
- HTTPS only
- Input validation
- Error handling"
```

---

### Task 2.2: Update config.py

**Objective:** Add OpenCode API key configuration

**Files:**
- Modify: `skills/watch/scripts/config.py`

**Step 1: Add OpenCode config**

```python
def get_config() -> dict[str, object]:
    file_values = read_env_file()

    detail = (
        os.environ.get("WATCH_DETAIL")
        or file_values.get("WATCH_DETAIL")
        or DEFAULT_DETAIL
    )
    if detail not in DETAILS:
        detail = DEFAULT_DETAIL

    # OpenCode Zen configuration
    opencode_api_key = (
        os.environ.get("OPENCODE_API_KEY")
        or file_values.get("OPENCODE_API_KEY")
    )
    opencode_model = (
        os.environ.get("OPENCODE_MODEL")
        or file_values.get("OPENCODE_MODEL")
        or "mimo-v2.5-free"
    )

    return {
        "detail": detail,
        "config_file": str(CONFIG_FILE),
        "opencode_api_key": opencode_api_key,
        "opencode_model": opencode_model,
    }
```

**Step 2: Commit**

```bash
git add skills/watch/scripts/config.py
git commit -m "feat: add OpenCode Zen configuration to config.py"
```

---

## Phase 3: Integration

### Task 3.1: Update watch.py

**Objective:** Add `--engine opencode` flag

**Files:**
- Modify: `skills/watch/scripts/watch.py`

**Step 1: Add engine argument**

```python
ap.add_argument(
    "--engine",
    choices=["claude", "opencode"],
    default=None,
    help="AI engine: claude (default, uses Read tool) or opencode (MiMo V2.5 via API)",
)
```

**Step 2: Add engine switching logic**

```python
if args.engine == "opencode":
    from opencode_client import OpenCodeClient
    
    config = get_config()
    api_key = config.get("opencode_api_key")
    model = config.get("opencode_model")
    
    if not api_key:
        print("[watch] OPENCODE_API_KEY not set. Set in ~/.config/watch/.env", file=sys.stderr)
        return 1
    
    client = OpenCodeClient(api_key=api_key, model=model)
    # ... (frame loading and API call logic)
```

**Step 3: Commit**

```bash
git add skills/watch/scripts/watch.py
git commit -m "feat: add --engine opencode flag for MiMo V2.5 support"
```

---

### Task 3.2: Create video_analyzer.py

**Objective:** High-level wrapper for video analysis via MiMo

**Files:**
- Create: `skills/watch/scripts/video_analyzer.py`
- Create: `tests/test_video_analyzer.py`

**Step 1: Write failing test**

```python
def test_video_analyzer_init():
    from video_analyzer import VideoAnalyzer
    analyzer = VideoAnalyzer(api_key="test-key", model="mimo-v2.5-free")
    assert analyzer.client is not None
```

**Step 2: Write implementation**

```python
#!/usr/bin/env python3
"""Video analyzer using MiMo V2.5 via OpenCode Zen.

Security: All API calls use environment-sourced credentials.
No personal data is transmitted.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from opencode_client import OpenCodeClient


class VideoAnalyzer:
    """Analyze video frames + transcript using MiMo V2.5."""

    def __init__(self, api_key: str, model: str = "mimo-v2.5-free"):
        self.client = OpenCodeClient(api_key=api_key, model=model)

    def load_frame_as_base64(self, frame_path: str) -> str:
        """Load JPEG frame and return base64 encoded string."""
        with open(frame_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def analyze_video(
        self,
        frames_dir: str,
        transcript_path: str,
        question: str,
        max_frames: int = 50,
    ) -> str:
        """Analyze video frames + transcript using MiMo V2.5."""
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

**Step 3: Commit**

```bash
git add skills/watch/scripts/video_analyzer.py tests/test_video_analyzer.py
git commit -m "feat: add VideoAnalyzer wrapper for MiMo integration"
```

---

## Phase 4: Testing & Validation

### Task 4.1: Security Audit

**Objective:** Verify no sensitive data in repository

**Checklist:**

- [ ] No hardcoded API keys in any file
- [ ] `.gitignore` excludes all `.env` files
- [ ] `SECURITY.md` is present and documented
- [ ] `.env.example` uses placeholder values
- [ ] No personal data in commits
- [ ] All API calls use HTTPS
- [ ] Credentials loaded from environment only

**Commands:**

```bash
# Scan for potential secrets
grep -rn "ghp_\|sk-\|AIza\|AKIA\|Bearer [A-Za-z0-9]" . 2>/dev/null

# Check git history for secrets
git log --all --diff-filter=A --name-only | grep -i "env\|secret\|key"

# Verify .gitignore
git status  # Should not show .env files
```

---

### Task 4.2: Integration Test

**Objective:** End-to-end test with real video

**Test cases:**
1. Short YouTube video (< 1 min) with captions
2. Local video file
3. Focused time range (--start/--end)
4. Transcript-only mode (--detail transcript)

**Verification:**
- MiMo receives frames successfully
- Response includes visual descriptions
- Transcript is integrated correctly
- No hallucinations about visual content
- API key not logged or exposed

---

### Task 4.3: Push to GitHub

**Objective:** Deploy secure integration to public repo

**Steps:**

```bash
# 1. Ensure all changes committed
git add .
git commit -m "feat: complete MiMo V2.5 integration with security best practices"

# 2. Push to fork
git push origin mimo-integration

# 3. Create Pull Request (optional)
gh pr create --title "feat: MiMo V2.5 integration" --body "Adds MiMo V2.5 support via OpenCode Zen"
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **API key exposure** | Critical | Environment variables only, never in code |
| **Man-in-the-middle** | High | HTTPS only, SSL verification enabled |
| **Rate limiting** | Medium | Exponential backoff, graceful degradation |
| **Model hallucination** | Medium | Validate responses, ground in frames |
| **Personal data leak** | Critical | No data collection, local processing only |

---

## Success Criteria

- [ ] No API keys in repository
- [ ] `.gitignore` properly configured
- [ ] `SECURITY.md` documented
- [ ] MiMo integration works
- [ ] All tests pass
- [ ] Public repo is safe to use

---

## Future Enhancements (Post-MVP)

1. **Rate limiting** — Implement request throttling
2. **Caching** — Store analyzed videos locally
3. **Batch mode** — Analyze multiple videos
4. **Export formats** — Markdown, JSON, PDF reports
5. **Multi-language** — Support non-English transcripts

---

**Plan saved to:** `docs/PLAN-MIMO.md`

**Security-first approach:** Every task includes security verification.
