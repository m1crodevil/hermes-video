# Subtitle Language Detection — Pitfall & Fix

## The Problem (Fixed in v1.2)

The original `download.py` hardcoded `--sub-langs en.*` — only downloading English subtitles. For non-English videos (Indonesian, Spanish, etc.), this resulted in:
- Missing transcripts (no English subs available)
- Machine-translated transcripts (low quality auto-generated English)

## The Fix (Automatic)

As of v1.2, `fetch_captions()` now:

1. **Fetches metadata only** (`fetch_metadata_only()`) — gets video title, language, description
2. **Lists available subtitles** (`list_available_subtitles()`) — discovers all available languages
3. **Detects best language** (`suggest_subtitle_language()` from `language.py`) — picks the video's native language
4. **Downloads subtitles in correct language** — uses `--sub-langs {lang}.*` instead of hardcoded `en.*`

## How It Works

```python
# From download.py fetch_captions()
info = fetch_metadata_only(url, out_dir)  # Gets language field
available = list_available_subtitles(url)  # Lists manual/auto subs
best_lang = suggest_subtitle_language(info, available)  # Picks best language
# Downloads: --sub-langs {best_lang}.*
```

## Language Detection Logic

From `language.py suggest_subtitle_language()`:

1. Try manual subs in video language → return video language
2. Try auto subs in video language → return video language
3. Fallback to English (most widely available)
4. Return video language (will try Whisper fallback)

## Verification

Check detected language in output:
```
[watch] detected language: Indonesian (id)
[watch] available: manual=[], auto=['id', 'en', 'ms', ...]...
```

Check subtitle file name:
- Before: `video.en.json3` (English only)
- After: `video.id.json3` or `video.id-orig.json3` (Indonesian)

## Manual Override (if needed)

If auto-detection fails, manually specify language:
```bash
# In download.py, override lang_pattern
lang_pattern = "id.*"  # Force Indonesian
```

## Related Files

- `scripts/download.py` — `fetch_captions()`, `fetch_metadata_only()`, `list_available_subtitles()`
- `scripts/language.py` — `suggest_subtitle_language()`, `get_language_name()`
