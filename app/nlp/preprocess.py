"""
Text preprocessing and normalization module.

This module provides functions for:
- Language detection
- Text cleaning (removing noise, URLs, special characters)
- Tokenization
- Lemmatization for Russian and English
- Normalization for keyword matching
"""

import logging
import re
import zipfile
from typing import Optional

import nltk

from app.domain.entities import Language, NormalizedText

logger = logging.getLogger(__name__)

# ================================================================================
# NLTK Data Initialization
# ================================================================================

_NLTK_INITIALIZED = False


def _ensure_nltk_data() -> None:
    """
    Ensure required NLTK data is downloaded.

    Downloads punkt tokenizer and wordnet lemmatizer if not present.
    This function is called lazily when NLTK functionality is first needed.
    """
    global _NLTK_INITIALIZED
    if _NLTK_INITIALIZED:
        return

    try:
        # Try to access punkt data
        nltk.data.find("tokenizers/punkt")
    except (LookupError, zipfile.BadZipFile):
        logger.info("Downloading NLTK punkt tokenizer...")
        nltk.download("punkt", quiet=True)

    try:
        # Try to access wordnet data
        nltk.data.find("corpora/wordnet")
    except (LookupError, zipfile.BadZipFile):
        logger.info("Downloading NLTK wordnet...")
        nltk.download("wordnet", quiet=True)

    try:
        # Try to access omw-1.4 (Open Multilingual Wordnet)
        nltk.data.find("corpora/omw-1.4")
    except (LookupError, zipfile.BadZipFile):
        logger.info("Downloading NLTK omw-1.4...")
        nltk.download("omw-1.4", quiet=True)

    _NLTK_INITIALIZED = True


# ================================================================================
# Lazy Imports for NLP Libraries
# ================================================================================


def _get_langdetect_detector() -> any:
    """Get langdetect detector (lazy import)."""
    try:
        from langdetect import detect

        return detect
    except ImportError:
        logger.warning("langdetect not installed, language detection will not work")
        return None


def _get_pymorphy2_analyzer() -> any:
    """Get pymorphy3 analyzer for Russian (lazy import)."""
    try:
        import pymorphy3

        return pymorphy3.MorphAnalyzer(lang="ru")
    except ImportError:
        logger.warning("pymorphy3 not installed, Russian lemmatization will not work")
        return None


def _get_nltk_lemmatizer() -> any:
    """Get NLTK WordNet lemmatizer for English (lazy import)."""
    try:
        _ensure_nltk_data()
        from nltk.stem import WordNetLemmatizer

        return WordNetLemmatizer()
    except ImportError:
        logger.warning("nltk not installed, English lemmatization will not work")
        return None


# Cache for lazy-loaded objects
_LANG_DETECTOR = None
_RUSSIAN_ANALYZER = None
_ENGLISH_LEMMATIZER = None


# ================================================================================
# Language Detection
# ================================================================================


def detect_language(text: str) -> Optional[str]:
    """
    Detect the language of the given text.

    Uses langdetect library for language detection. Falls back to None if
    detection fails or library is not available.

    Args:
        text: Text to analyze

    Returns:
        Language code ('ru', 'en', etc.) or None if detection failed
    """
    global _LANG_DETECTOR

    if not text or not text.strip():
        return None

    if _LANG_DETECTOR is None:
        _LANG_DETECTOR = _get_langdetect_detector()

    if _LANG_DETECTOR is None:
        return None

    try:
        lang = _LANG_DETECTOR(text)
        logger.debug(f"Detected language: {lang}")
        return lang
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")
        return None


# ================================================================================
# Text Cleaning
# ================================================================================


def clean_text(text: str, remove_urls: bool = True, remove_mentions: bool = False) -> str:
    """
    Clean text by removing noise.

    Removes:
    - URLs (optional)
    - Telegram mentions (optional)
    - Extra whitespace
    - Control characters

    Args:
        text: Text to clean
        remove_urls: Whether to remove URLs
        remove_mentions: Whether to remove Telegram mentions (@username)

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove URLs
    if remove_urls:
        # Remove http/https URLs
        text = re.sub(r"https?://\S+", " ", text)
        # Remove www URLs
        text = re.sub(r"www\.\S+", " ", text)
        # Remove t.me links
        text = re.sub(r"t\.me/\S+", " ", text)

    # Remove Telegram mentions
    if remove_mentions:
        text = re.sub(r"@\w+", " ", text)

    # Remove control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", text)

    # Replace multiple spaces with single space
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def remove_emojis(text: str) -> str:
    """
    Remove emoji characters from text.

    Args:
        text: Text to process

    Returns:
        Text without emojis
    """
    # Emoji pattern (covers most common emoji ranges)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(" ", text)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    Replaces multiple spaces, tabs, newlines with single space.

    Args:
        text: Text to normalize

    Returns:
        Text with normalized whitespace
    """
    # Replace all whitespace sequences with single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ================================================================================
# Tokenization
# ================================================================================


def tokenize_simple(text: str, min_length: int = 1) -> list[str]:
    """
    Simple tokenization by splitting on non-alphanumeric characters.

    Args:
        text: Text to tokenize
        min_length: Minimum token length to include

    Returns:
        List of tokens
    """
    if not text:
        return []

    # Split on non-word characters (keeps letters, numbers, underscores)
    tokens = re.findall(r"\w+", text, re.UNICODE)

    # Filter by minimum length
    tokens = [t for t in tokens if len(t) >= min_length]

    return tokens


def tokenize_nltk(text: str, language: str = "english") -> list[str]:
    """
    Tokenize text using NLTK word tokenizer.

    More sophisticated than simple tokenization, handles punctuation better.

    Args:
        text: Text to tokenize
        language: Language for tokenization ('english', 'russian', etc.)

    Returns:
        List of tokens
    """
    if not text:
        return []

    _ensure_nltk_data()

    try:
        from nltk.tokenize import word_tokenize

        tokens = word_tokenize(text, language=language)
        # Filter out pure punctuation tokens
        tokens = [t for t in tokens if re.search(r"\w", t, re.UNICODE)]
        return tokens
    except Exception as e:
        logger.warning(f"NLTK tokenization failed, falling back to simple: {e}")
        return tokenize_simple(text)


def tokenize(text: str, language: Optional[str] = None, use_nltk: bool = True) -> list[str]:
    """
    Tokenize text using the best available method.

    Args:
        text: Text to tokenize
        language: Language code ('ru', 'en', etc.)
        use_nltk: Whether to use NLTK tokenizer (more accurate but slower)

    Returns:
        List of tokens
    """
    if not text:
        return []

    if use_nltk:
        # Map language codes to NLTK language names
        lang_map = {"ru": "russian", "en": "english"}
        nltk_lang = lang_map.get(language, "english") if language else "english"
        return tokenize_nltk(text, language=nltk_lang)
    else:
        return tokenize_simple(text)


# ================================================================================
# Lemmatization
# ================================================================================


def lemmatize_russian(tokens: list[str]) -> list[str]:
    """
    Lemmatize Russian tokens using pymorphy2.

    Args:
        tokens: List of tokens to lemmatize

    Returns:
        List of lemmatized tokens
    """
    global _RUSSIAN_ANALYZER

    if not tokens:
        return []

    if _RUSSIAN_ANALYZER is None:
        _RUSSIAN_ANALYZER = _get_pymorphy2_analyzer()

    if _RUSSIAN_ANALYZER is None:
        logger.warning("Russian lemmatization not available, returning original tokens")
        return tokens

    lemmas = []
    for token in tokens:
        try:
            # Get the normal form (lemma) of the word
            parsed = _RUSSIAN_ANALYZER.parse(token)[0]
            lemma = parsed.normal_form
            lemmas.append(lemma)
        except Exception as e:
            logger.debug(f"Failed to lemmatize token '{token}': {e}")
            lemmas.append(token.lower())

    return lemmas


def lemmatize_english(tokens: list[str]) -> list[str]:
    """
    Lemmatize English tokens using NLTK WordNet lemmatizer.

    Args:
        tokens: List of tokens to lemmatize

    Returns:
        List of lemmatized tokens
    """
    global _ENGLISH_LEMMATIZER

    if not tokens:
        return []

    if _ENGLISH_LEMMATIZER is None:
        _ENGLISH_LEMMATIZER = _get_nltk_lemmatizer()

    if _ENGLISH_LEMMATIZER is None:
        logger.warning("English lemmatization not available, returning original tokens")
        return tokens

    lemmas = []
    for token in tokens:
        try:
            # Lemmatize as noun by default (most common case)
            lemma = _ENGLISH_LEMMATIZER.lemmatize(token.lower())
            lemmas.append(lemma)
        except Exception as e:
            logger.debug(f"Failed to lemmatize token '{token}': {e}")
            lemmas.append(token.lower())

    return lemmas


def lemmatize(tokens: list[str], language: Optional[str] = None) -> list[str]:
    """
    Lemmatize tokens based on language.

    Args:
        tokens: List of tokens to lemmatize
        language: Language code ('ru', 'en', etc.)

    Returns:
        List of lemmatized tokens
    """
    if not tokens:
        return []

    if language == "ru":
        return lemmatize_russian(tokens)
    elif language == "en":
        return lemmatize_english(tokens)
    else:
        # If language is unknown, try to detect from tokens or skip lemmatization
        logger.debug(f"Unknown language '{language}', skipping lemmatization")
        return [t.lower() for t in tokens]


# ================================================================================
# Main Normalization Function
# ================================================================================


def normalize_text(
    text: str,
    language: Language = Language.AUTO,
    lowercase: bool = True,
    remove_urls: bool = True,
    remove_mentions: bool = False,
    remove_emojis_flag: bool = True,
    use_lemmatization: bool = True,
    use_nltk_tokenizer: bool = False,
    min_token_length: int = 2,
) -> NormalizedText:
    """
    Normalize text for processing.

    This is the main entry point for text normalization. It performs:
    1. Language detection (if AUTO)
    2. Text cleaning (URLs, mentions, emojis, etc.)
    3. Lowercasing (optional)
    4. Tokenization
    5. Lemmatization (optional)

    Args:
        text: Original text to normalize
        language: Language for processing (AUTO for auto-detection)
        lowercase: Whether to convert to lowercase
        remove_urls: Whether to remove URLs
        remove_mentions: Whether to remove @mentions
        remove_emojis_flag: Whether to remove emojis
        use_lemmatization: Whether to apply lemmatization
        use_nltk_tokenizer: Whether to use NLTK tokenizer (vs simple)
        min_token_length: Minimum token length to keep

    Returns:
        NormalizedText object with original text, normalized text, tokens, and metadata
    """
    if not text:
        return NormalizedText(
            original=text,
            normalized="",
            tokens=[],
            language=None,
            lemmas=[],
        )

    # Detect language if AUTO
    detected_lang = None
    if language == Language.AUTO:
        detected_lang = detect_language(text)
        logger.debug(f"Auto-detected language: {detected_lang}")
    else:
        detected_lang = language.value

    # Clean text
    cleaned = clean_text(text, remove_urls=remove_urls, remove_mentions=remove_mentions)

    # Remove emojis if requested
    if remove_emojis_flag:
        cleaned = remove_emojis(cleaned)

    # Remove punctuation / symbols (keep letters, numbers, underscores, whitespace).
    # This matches the unit-test expectation that "Hello World!" -> "hello world".
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)

    # Normalize whitespace
    cleaned = normalize_whitespace(cleaned)

    # Convert to lowercase if requested
    if lowercase:
        normalized = cleaned.lower()
    else:
        normalized = cleaned

    # Tokenize
    tokens = tokenize(normalized, language=detected_lang, use_nltk=use_nltk_tokenizer)

    # Filter by minimum length
    tokens = [t for t in tokens if len(t) >= min_token_length]

    # Lemmatize if requested
    lemmas = None
    if use_lemmatization and tokens:
        lemmas = lemmatize(tokens, language=detected_lang)

    return NormalizedText(
        original=text,
        normalized=normalized,
        tokens=tokens,
        language=detected_lang,
        lemmas=lemmas,
    )


# ================================================================================
# Utility Functions
# ================================================================================


def prepare_keyword(keyword: str, lowercase: bool = True) -> str:
    """
    Prepare a keyword for matching.

    Applies basic normalization to make keyword suitable for matching.

    Args:
        keyword: Keyword to prepare
        lowercase: Whether to convert to lowercase

    Returns:
        Prepared keyword
    """
    keyword = keyword.strip()
    if lowercase:
        keyword = keyword.lower()
    return keyword


def prepare_keywords(
    keywords: list[str],
    lowercase: bool = True,
    remove_duplicates: bool = True,
) -> list[str]:
    """
    Prepare a list of keywords for matching.

    Args:
        keywords: List of keywords
        lowercase: Whether to convert to lowercase
        remove_duplicates: Whether to remove duplicate keywords

    Returns:
        List of prepared keywords
    """
    prepared = [prepare_keyword(kw, lowercase=lowercase) for kw in keywords if kw.strip()]

    if remove_duplicates:
        # Preserve order while removing duplicates
        seen = set()
        unique = []
        for kw in prepared:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique

    return prepared
