"""Language detection helper for subtitle selection."""

# Common language codes to names
LANGUAGE_NAMES = {
    "id": "Indonesian",
    "en": "English",
    "ms": "Malay",
    "jv": "Javanese",
    "su": "Sundanese",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ru": "Russian",
    "hi": "Hindi",
    "th": "Thai",
    "vi": "Vietnamese",
    "tl": "Filipino",
    "tr": "Turkish",
    "pl": "Polish",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
}


def suggest_subtitle_language(video_info: dict, available_subs: dict) -> str:
    """
    Suggest best subtitle language based on:
    1. Video's primary language (from metadata)
    2. Available manual subtitles (preferred)
    3. Available auto-generated subtitles (fallback)
    
    Args:
        video_info: Dict with 'language', 'title', 'description' keys
        available_subs: Dict with 'manual' and 'auto' lists of language codes
    
    Returns:
        Language code (e.g., "id", "en")
    """
    video_lang = video_info.get("language", "en")
    
    manual = available_subs.get("manual", [])
    auto = available_subs.get("auto", [])
    
    # 1. Try manual subs in video language
    if video_lang in manual:
        return video_lang
    
    # 2. Try auto subs in video language
    if video_lang in auto:
        return video_lang
    
    # 3. Fallback to English (most widely available)
    if "en" in manual:
        return "en"
    if "en" in auto:
        return "en"
    
    # 4. Return video language (will try Whisper fallback)
    return video_lang


def get_language_name(code: str) -> str:
    """Get human-readable language name from code."""
    return LANGUAGE_NAMES.get(code, code.upper())


def format_subtitle_info(detected_lang: str, available_subs: dict) -> str:
    """Format subtitle detection info for display."""
    manual = available_subs.get("manual", [])
    auto = available_subs.get("auto", [])
    
    lang_name = get_language_name(detected_lang)
    
    parts = [f"Detected language: {lang_name} ({detected_lang})"]
    
    if manual:
        manual_names = [get_language_name(l) for l in manual[:5]]
        parts.append(f"Manual subtitles: {', '.join(manual_names)}")
    
    if auto:
        auto_names = [get_language_name(l) for l in auto[:5]]
        parts.append(f"Auto subtitles: {', '.join(auto_names)}")
    
    return " | ".join(parts)
