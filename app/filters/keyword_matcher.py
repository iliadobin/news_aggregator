"""
Keyword matching module for filtering messages.

This module provides functionality for matching messages against keyword-based filters.
It supports various matching modes including case sensitivity, whole word matching,
and lemmatization.
"""

import logging
import re
from typing import Optional

from app.domain.entities import (
    FilterConfig,
    KeywordMatch,
    KeywordOptions,
    Language,
    NormalizedText,
)
from app.nlp.preprocess import normalize_text, prepare_keywords

logger = logging.getLogger(__name__)


# ================================================================================
# Keyword Matching Core Functions
# ================================================================================


def _find_keyword_positions(text: str, keyword: str, case_sensitive: bool = False) -> list[int]:
    """
    Find all positions of a keyword in text.

    Args:
        text: Text to search in
        keyword: Keyword to find
        case_sensitive: Whether to use case-sensitive search

    Returns:
        List of character positions where keyword was found
    """
    if not text or not keyword:
        return []

    positions = []
    search_text = text if case_sensitive else text.lower()
    search_keyword = keyword if case_sensitive else keyword.lower()

    start = 0
    while True:
        pos = search_text.find(search_keyword, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1

    return positions


def _is_whole_word_match(text: str, keyword: str, position: int) -> bool:
    """
    Check if keyword at given position is a whole word match.

    A whole word match means the keyword is not part of a larger word,
    i.e., it's surrounded by word boundaries.

    Args:
        text: Text containing the keyword
        keyword: The keyword
        position: Position of keyword in text

    Returns:
        True if it's a whole word match, False otherwise
    """
    if position < 0 or position >= len(text):
        return False

    keyword_end = position + len(keyword)

    # Check if character before keyword is a word boundary
    if position > 0:
        char_before = text[position - 1]
        if re.match(r"\w", char_before, re.UNICODE):
            return False

    # Check if character after keyword is a word boundary
    if keyword_end < len(text):
        char_after = text[keyword_end]
        if re.match(r"\w", char_after, re.UNICODE):
            return False

    return True


def match_keyword_simple(
    text: str,
    keyword: str,
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> tuple[bool, list[int]]:
    """
    Simple keyword matching without normalization.

    Searches for keyword in text and returns match status and positions.

    Args:
        text: Text to search in
        keyword: Keyword to find
        case_sensitive: Whether to use case-sensitive matching
        whole_word: Whether to match only whole words

    Returns:
        Tuple of (matched: bool, positions: list[int])
    """
    if not text or not keyword:
        return False, []

    positions = _find_keyword_positions(text, keyword, case_sensitive=case_sensitive)

    if not positions:
        return False, []

    # Filter positions by whole word requirement
    if whole_word:
        positions = [pos for pos in positions if _is_whole_word_match(text, keyword, pos)]

    return len(positions) > 0, positions


def match_keyword_in_tokens(
    tokens: list[str],
    keyword: str,
    case_sensitive: bool = False,
) -> bool:
    """
    Match keyword against a list of tokens.

    This is useful when working with lemmatized or tokenized text.
    The keyword can be a single word or a phrase.

    Args:
        tokens: List of tokens to search in
        keyword: Keyword to find (can be multi-word)
        case_sensitive: Whether to use case-sensitive matching

    Returns:
        True if keyword was found in tokens
    """
    if not tokens or not keyword:
        return False

    # Split keyword into words
    keyword_tokens = keyword.split()

    if not keyword_tokens:
        return False

    # Prepare tokens for comparison
    if not case_sensitive:
        tokens = [t.lower() for t in tokens]
        keyword_tokens = [k.lower() for k in keyword_tokens]

    # Single word keyword - simple check
    if len(keyword_tokens) == 1:
        return keyword_tokens[0] in tokens

    # Multi-word keyword - check for sequence
    keyword_len = len(keyword_tokens)
    for i in range(len(tokens) - keyword_len + 1):
        if tokens[i : i + keyword_len] == keyword_tokens:
            return True

    return False


# ================================================================================
# Advanced Matching with Normalization
# ================================================================================


def match_keywords_in_text(
    text: str,
    keywords: list[str],
    options: Optional[KeywordOptions] = None,
    normalized_text: Optional[NormalizedText] = None,
) -> KeywordMatch:
    """
    Match multiple keywords in text with advanced options.

    This is the main entry point for keyword matching. It handles:
    - Text normalization (if not provided)
    - Case sensitivity
    - Whole word matching
    - Lemmatization-based matching

    Args:
        text: Original text to search in
        keywords: List of keywords to find
        options: Matching options (if None, uses defaults)
        normalized_text: Pre-normalized text (if available, to avoid re-normalization)

    Returns:
        KeywordMatch object with results
    """
    if not text or not keywords:
        return KeywordMatch(
            matched_keywords=[],
            match_count=0,
            positions={},
        )

    # Use default options if not provided
    if options is None:
        options = KeywordOptions()

    # Lemmatization implies normalization (incl. casing). If caller asked for strict
    # case-sensitive matching, disable lemmatization to preserve expected semantics.
    effective_use_lemmatization = options.use_lemmatization and (not options.case_sensitive)

    # Prepare keywords
    prepared_keywords = prepare_keywords(
        keywords,
        lowercase=not options.case_sensitive,
        remove_duplicates=True,
    )

    if not prepared_keywords:
        return KeywordMatch(
            matched_keywords=[],
            match_count=0,
            positions={},
        )

    # Normalize text if not provided
    if normalized_text is None:
        normalized_text = normalize_text(
            text,
            language=options.language,
            lowercase=not options.case_sensitive,
            use_lemmatization=effective_use_lemmatization,
            min_token_length=options.min_keyword_length,
        )

    matched_keywords = []
    match_count = 0
    positions = {}

    # Choose matching strategy based on options
    if effective_use_lemmatization and normalized_text.lemmas:
        # Use lemma-based matching
        search_tokens = normalized_text.lemmas
        logger.debug(f"Using lemma-based matching with {len(search_tokens)} lemmas")
    else:
        # Use token-based matching
        search_tokens = normalized_text.tokens
        logger.debug(f"Using token-based matching with {len(search_tokens)} tokens")

    # Match each keyword
    for keyword in prepared_keywords:
        if options.whole_word or effective_use_lemmatization:
            # Use token-based matching for whole word or lemmatization
            matched = match_keyword_in_tokens(
                search_tokens,
                keyword,
                case_sensitive=options.case_sensitive,
            )
            if matched:
                matched_keywords.append(keyword)
                match_count += 1
                # For token-based matching, we don't track exact positions
                positions[keyword] = []
        else:
            # Use simple text search for partial matches
            matched, keyword_positions = match_keyword_simple(
                normalized_text.normalized if not options.case_sensitive else text,
                keyword,
                case_sensitive=options.case_sensitive,
                whole_word=False,
            )
            if matched:
                matched_keywords.append(keyword)
                match_count += len(keyword_positions)
                positions[keyword] = keyword_positions

    logger.debug(f"Matched {len(matched_keywords)} keywords out of {len(prepared_keywords)}")

    return KeywordMatch(
        matched_keywords=matched_keywords,
        match_count=match_count,
        positions=positions,
    )


def match_filter_keywords(
    text: str,
    filter_config: FilterConfig,
    normalized_text: Optional[NormalizedText] = None,
) -> KeywordMatch:
    """
    Match keywords from a filter configuration.

    This is a convenience wrapper around match_keywords_in_text that extracts
    keywords and options from a FilterConfig.

    Args:
        text: Text to search in
        filter_config: Filter configuration with keywords and options
        normalized_text: Pre-normalized text (optional)

    Returns:
        KeywordMatch object with results
    """
    return match_keywords_in_text(
        text=text,
        keywords=filter_config.keywords,
        options=filter_config.keyword_options,
        normalized_text=normalized_text,
    )


# ================================================================================
# Validation Functions
# ================================================================================


def check_keywords_match_all(
    text: str,
    keywords: list[str],
    options: Optional[KeywordOptions] = None,
) -> bool:
    """
    Check if ALL keywords match in text.

    This is useful for filters that require all keywords to be present.

    Args:
        text: Text to search in
        keywords: List of keywords (all must match)
        options: Matching options

    Returns:
        True if all keywords matched, False otherwise
    """
    if not keywords:
        return False

    match_result = match_keywords_in_text(text, keywords, options)
    return len(match_result.matched_keywords) == len(keywords)


def check_keywords_match_any(
    text: str,
    keywords: list[str],
    options: Optional[KeywordOptions] = None,
) -> bool:
    """
    Check if ANY keyword matches in text.

    This is useful for filters that require at least one keyword to be present.

    Args:
        text: Text to search in
        keywords: List of keywords (at least one must match)
        options: Matching options

    Returns:
        True if any keyword matched, False otherwise
    """
    if not keywords:
        return False

    match_result = match_keywords_in_text(text, keywords, options)
    return match_result.has_match


def evaluate_filter_keywords(
    text: str,
    filter_config: FilterConfig,
    normalized_text: Optional[NormalizedText] = None,
) -> bool:
    """
    Evaluate if text matches filter keyword requirements.

    Takes into account the require_all_keywords flag in filter config.

    Args:
        text: Text to evaluate
        filter_config: Filter configuration
        normalized_text: Pre-normalized text (optional)

    Returns:
        True if text matches filter keyword requirements
    """
    if not filter_config.keywords:
        return False

    match_result = match_filter_keywords(text, filter_config, normalized_text)

    if not match_result.has_match:
        return False

    # Check if all keywords are required
    if filter_config.require_all_keywords:
        return len(match_result.matched_keywords) == len(filter_config.keywords)

    # Otherwise, any keyword match is sufficient
    return True


# ================================================================================
# Utility Functions
# ================================================================================


def get_match_score(match: KeywordMatch) -> float:
    """
    Calculate a score for keyword match.

    Score is based on the number of unique keywords matched and total match count.
    Returns a value between 0.0 and 1.0 (normalized by number of keywords + matches).

    Args:
        match: KeywordMatch result

    Returns:
        Match score (0.0-1.0)
    """
    if not match.has_match:
        return 0.0

    # Simple scoring: number of unique keywords matched + match count
    # Normalize to 0-1 range (arbitrary scaling)
    unique_keywords = len(match.matched_keywords)
    total_matches = match.match_count

    # Give more weight to unique keywords than total matches
    score = (unique_keywords * 2 + total_matches) / (unique_keywords * 2 + total_matches + 1)

    return min(score, 1.0)


def highlight_keywords(
    text: str,
    match: KeywordMatch,
    highlight_format: str = "**{keyword}**",
) -> str:
    """
    Highlight matched keywords in text.

    Useful for displaying search results to users.

    Args:
        text: Original text
        match: KeywordMatch result
        highlight_format: Format string for highlighting (must contain {keyword})

    Returns:
        Text with highlighted keywords
    """
    if not match.has_match or not text:
        return text

    highlighted = text

    # Sort keywords by length (longest first) to avoid partial replacements
    sorted_keywords = sorted(match.matched_keywords, key=len, reverse=True)

    for keyword in sorted_keywords:
        # Use case-insensitive replacement
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        replacement = highlight_format.replace("{keyword}", r"\g<0>")
        highlighted = pattern.sub(replacement, highlighted)

    return highlighted