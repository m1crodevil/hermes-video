# hermes-video

> 🎬 Video analysis skill for Hermes Agent — powered by MiMo V2.5 multimodal AI

[![Hermes](https://img.shields.io/badge/Agent-Hermes-blue)](https://hermes-agent.nousresearch.com)
[![MiMo](https://img.shields.io/badge/Model-MiMo_V2.5-green)](https://huggingface.co/XiaomiMiMo/MiMo-V2.5)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**hermes-video** is a [Hermes Agent](https://hermes-agent.nousresearch.com) skill for AI-powered video analysis using [Xiaomi MiMo V2.5](https://huggingface.co/XiaomiMiMo/MiMo-V2.5) multimodal model. It downloads videos, extracts frames, transcribes audio, and analyzes content using MiMo's vision capabilities — all for free via [OpenCode Zen](https://opencode.ai).

## ✨ Features

- 🎬 **Multimodal AI analysis** — MiMo sees frames + reads transcript
- 💰 **Free tier** — $0 cost via OpenCode Zen
- 🧠 **1M context window** — analyze long videos without splitting
- 🔧 **Hermes native** — works as Hermes skill with memory & cron
- 📦 **Zero dependencies** — stdlib Python only
- 🎯 **Smart frame extraction** — scene-aware, keyframe, or transcript modes
- 📝 **Transcript support** — auto captions or Whisper API fallback

## 🚀 Installation

```bash
# Quick install
git clone https://github.com/m1crodevil/hermes-video.git
cd hermes-video
./install.sh

# Or via Hermes
hermes skill add m1crodevil/hermes-video
```

**Dependencies:** Python 3.11+, ffmpeg, yt-dlp

## ⚙️ Configuration

```bash
# Set your API key
mkdir -p ~/.config/watch
echo "OPENCODE_API_KEY=your-key" > ~/.config/watch/.env
```

Get a free key at [OpenCode Zen](https://opencode.ai).

## 📖 Usage

```bash
# Via Hermes chat
/watch https://youtu.be/VIDEO_ID summarize this

# Via CLI with MiMo analysis
python3 ~/.hermes/skills/video/scripts/watch.py https://youtu.be/VIDEO_ID --engine opencode --question "what happens at 2:30?"

# Transcript only (cheapest)
python3 ~/.hermes/skills/video/scripts/watch.py https://youtu.be/VIDEO_ID --detail transcript
```

## 📊 Detail Modes

| Mode | Frames | Speed | Use Case |
|------|--------|-------|----------|
| `transcript` | 0 | ~4.5s | Text-only, cheapest |
| `efficient` | 50 | ~0.5s | Fast scan |
| `balanced` | 100 | ~21s | Default |
| `token-burner` | uncapped | ~21s | Full coverage |

## 🔗 Hermes Integration

- **Memory** — analyses saved automatically
- **Cron** — schedule daily/weekly video analysis
- **Bundles** — combine with other Hermes skills

## 🧪 Testing

```bash
python3 -m pytest tests/ -v  # 218 tests
```

## 📚 Documentation

- [SKILL.md](skills/watch/SKILL.md) — Full skill docs
- [SECURITY.md](SECURITY.md) — Security policy
- [Hermes Docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)

## 🔒 Security

- API keys stored locally, never committed
- Videos processed locally, frames sent to MiMo only
- No external data storage

## 🤝 Contributing

1. Fork → Branch → Commit → Push → PR
2. Run tests: `python3 -m pytest tests/ -v`

## 📄 License

MIT — see [LICENSE](LICENSE)

## 🙏 Credits

- Original: [bradautomates/claude-video](https://github.com/bradautomates/claude-video)
- Model: [Xiaomi MiMo V2.5](https://huggingface.co/XiaomiMiMo/MiMo-V2.5)
- Agent: [Hermes Agent](https://hermes-agent.nousresearch.com)
- API: [OpenCode Zen](https://opencode.ai)

---

**Built with ❤️ for the Hermes community**
