# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **DO NOT** open a public GitHub issue
2. Email: m1crodevil@users.noreply.github.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Security Practices

### API Keys & Credentials

- **NEVER** commit API keys, tokens, or credentials to the repository
- Use environment variables or `~/.config/watch/.env`
- Rotate keys regularly
- Use fine-grained tokens with minimal scopes

### Recommended Token Scopes

```
✅ repo
✅ delete_repo
✅ admin:org
✅ workflow
✅ gist
✅ notifications
✅ user
```

### Environment Variables

All sensitive configuration is stored in:

```
~/.config/watch/.env
```

**Required:**
- `OPENCODE_API_KEY` - For MiMo V2.5 via OpenCode Zen

**Optional:**
- `GROQ_API_KEY` - For Whisper transcription (preferred)
- `OPENAI_API_KEY` - For Whisper transcription (fallback)

### Data Privacy

- **No personal data** is collected or transmitted
- **Video processing** is done locally
- **Transcription** only sends audio to configured API (Groq/OpenAI)
- **Frames** are processed locally, never uploaded

### Best Practices

1. **Use strong, unique API keys**
2. **Rotate keys periodically**
3. **Use least-privilege tokens**
4. **Never share API keys publicly**
5. **Review `.gitignore` before commits**
6. **Use `git diff` to check for accidental secrets**

## Compliance

This project adheres to:
- GitHub's Security Policy
- MIT License terms
- No tracking, no analytics, no data collection

## Contact

For security concerns:
- Email: m1crodevil@users.noreply.github.com
- GitHub: [@m1crodevil](https://github.com/m1crodevil)
