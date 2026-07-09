# hermes-video

> 🎬 Video analysis for Hermes Agent powered by MiMo V2.5

[![Hermes](https://img.shields.io/badge/Agent-Hermes-blue)](https://hermes-agent.nousresearch.com)
[![MiMo](https://img.shields.io/badge/Model-MiMo_V2.5-green)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Hermes skill for video analysis using Xiaomi's MiMo V2.5 multimodal model via OpenCode Zen. Analyzes videos frame-by-frame to find viral moments, engagement scoring, and TikTok clipping potential.

## ✨ Features

- 🎬 **Full multimodal analysis** — MiMo sees frames + reads transcript
- 💰 **$0 cost** — OpenCode Zen free tier
- 🧠 **1M context window** — analyze long videos without splitting
- 🔧 **Hermes native** — works as Hermes skill
- 📦 **Zero dependencies** — stdlib Python only (optional: `openai`)
- 🧠 **Memory integration** — saves analyses for future reference
- ⏰ **Cron support** — schedule regular video analysis
- 📊 **Structured output** — Zod-validated JSON with TypeScript
- 🔍 **Keyframe extraction** — PySceneDetect for efficient visual analysis
- 🎯 **SRT integration** — combines visual + dialogue analysis

## 🚀 Installation

### Hermes CLI (Recommended)

```bash
# Install via Hermes
hermes skill install video-analysis-mimo

# Or clone directly
git clone https://github.com/m1crodevil/claude-video.git ~/.hermes/skills/hermes-video
```

### Manual Installation

```bash
# Clone the repo
git clone https://github.com/m1crodevil/claude-video.git
cd claude-video

# Install Python dependencies (optional, for OpenAI client)
pip install openai

# Install Node.js dependencies (for Zod validation)
npm install
```

## ⚙️ Configuration

### Environment Variables

Set your OpenCode Zen API key:

```bash
# Option 1: Export in shell
export OPENCODE_ZEN_API_KEY="your-api-key"

# Option 2: Add to ~/.hermes/.env
echo "OPENCODE_ZEN_API_KEY=your-api-key" >> ~/.hermes/.env
```

### Hermes Config

Add to `~/.hermes/config.yaml`:

```yaml
skills:
  - video-analysis-mimo

env:
  OPENCODE_ZEN_API_KEY: "your-api-key"
```

## 📖 Usage

### Basic Analysis

```bash
# Analyze a video file
python3 scripts/mimo_video_pipeline.py /path/to/video.mp4

# Analyze with custom FPS
python3 mimo-video-analyzer/analyze.py video.mp4 --fps 0.25

# Analyze with custom prompt
python3 mimo-video-analyzer/analyze.py video.mp4 --prompt "Find funny moments"
```

### TypeScript (Zod Validation)

```bash
# Analyze keyframes with structured output
npx tsx mimo-video-analyzer/analyze-zod.ts keyframes_dir/ video_url
```

### Python API

```python
from mimo_video_analyzer.analyze import analyze_video

# Analyze video
result = analyze_video(
    video_path="video.mp4",
    fps=0.5,
    prompt="Find viral moments",
    max_tokens=4096
)

# Access results
moments = result['moments']
usage = result['usage']
```

## 📊 Detail Modes

| Mode | FPS | Tokens/min | Best For |
|------|-----|------------|----------|
| **Quick scan** | 0.125 | 1,050 | Long videos, overview |
| **Balanced** | 0.25 | 2,100 | Most use cases |
| **Detailed** | 0.5 | 4,200 | Short videos, deep analysis |
| **Maximum** | 1.0 | 8,400 | Critical moments, max detail |

### Token Usage Example

For a 33-minute video at 0.25 FPS:
- ~15 frames/min × 33 min = ~500 frames
- ~140 tokens/frame = ~70K tokens
- Cost: $0 (free tier)

## 🔗 Hermes Integration

### Memory

Save analysis results to Hermes memory:

```python
# Results automatically saved to ~/.hermes/memories/video_analysis/
# Access via: session_search(query="video analysis results")
```

### Cron Jobs

Schedule regular video analysis:

```yaml
# ~/.hermes/cron/video_analysis.yaml
schedule: "0 2 * * *"  # Daily at 2 AM
task: |
  Analyze new videos in ~/videos/ directory
  Save results to memory
  Notify if viral moments found
```

### Bundles

Include in Hermes bundles:

```yaml
# ~/.hermes/bundles/content_creation.yaml
skills:
  - video-analysis-mimo
  - clipping-pipeline
  
tasks:
  - analyze_videos
  - generate_clips
```

## 📁 Directory Structure

```
hermes-video/
├── scripts/
│   ├── mimo_video_pipeline.py      # Main pipeline (audio → trim → video)
│   └── mimo_video_test.py          # Test utilities
├── mimo-video-analyzer/
│   ├── analyze.py                  # Python analyzer (OpenAI client)
│   ├── analyze-zod.ts              # TypeScript analyzer (Zod validation)
│   ├── test_limit.py               # API limit testing
│   └── test_limit_real.py          # Real video limit testing
├── clipping-pipeline/
│   └── schema.py                   # Pydantic schemas (fallback)
├── skills/
│   └── watch/                      # Hermes watch skill
├── docs/                           # Documentation
└── README.md
```

## 🔒 Security

### API Key Protection

- **Never commit** `OPENCODE_ZEN_API_KEY` to git
- Store in `~/.hermes/.env` (gitignored)
- Use environment variables in CI/CD
- Rotate keys periodically

### Video Privacy

- Videos are base64-encoded and sent to OpenCode Zen API
- No video data is stored on our servers
- OpenCode Zen processes requests in memory only
- Delete local copies after analysis if needed

### Rate Limiting

- Free tier: Limited requests per minute
- Use fallback providers if rate limited
- Implement retry logic with exponential backoff

## 🧪 Testing

### Unit Tests

```bash
# Run Python tests
python3 -m pytest tests/

# Run TypeScript tests
npm test
```

### Integration Tests

```bash
# Test API limits
python3 mimo-video-analyzer/test_limit.py

# Test with real video
python3 mimo-video-analyzer/test_limit_real.py
```

### Manual Testing

```bash
# Test with small video
python3 scripts/mimo_video_pipeline.py test_video.mp4

# Test keyframe extraction
python3 -c "
from scenedetect import detect, AdaptiveDetector
scenes = detect('video.mp4', AdaptiveDetector(adaptive_threshold=3.0))
print(f'Found {len(scenes)} scenes')
"
```

## 📚 Documentation

- **[SKILL.md](.hermes/skills/video-processing/video-analysis-mimo/SKILL.md)** — Full skill documentation
- **[references/](.hermes/skills/video-processing/video-analysis-mimo/references/)** — Detailed guides
  - `clipping-pipeline-schema.md` — Rust serde schema
  - `pyscenedetect-quickref.md` — PySceneDetect cheatsheet
  - `keyframe-analysis-benchmarks.md` — Token benchmarks
  - `claude-video-reference.md` — Reference implementation

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** changes (`git commit -m 'Add amazing feature'`)
4. **Push** to branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/claude-video.git
cd claude-video

# Install dependencies
pip install openai pytest
npm install

# Run tests
python3 -m pytest tests/
npm test
```

### Code Style

- Python: PEP 8, type hints
- TypeScript: Strict mode, Zod validation
- Follow existing patterns in the codebase

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 🙏 Credits

- **[Xiaomi MiMo](https://huggingface.co/XiaomiMiMo/MiMo-V2.5)** — Multimodal AI model
- **[OpenCode Zen](https://opencode.ai)** — Free API access
- **[Hermes Agent](https://hermes-agent.nousresearch.com)** — AI agent framework
- **[PySceneDetect](https://github.com/ByteDance/scenedetect)** — Scene detection
- **[Zod](https://zod.dev)** — TypeScript schema validation

---

**Built with ❤️ for the Hermes community**
