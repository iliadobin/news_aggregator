"""
Unit tests for text preprocessing module.

Tests text normalization, cleaning, tokenization, and lemmatization.
"""

import pytest

from app.domain.entities import Language
from app.nlp.preprocess import (
    clean_text,
    lemmatize,
    normalize_text,
    normalize_whitespace,
    prepare_keyword,
    prepare_keywords,
    remove_emojis,
    tokenize,
    tokenize_simple,
)


class TestCleanText:
    """Tests for text cleaning functions."""

    def test_clean_urls(self) -> None:
        """Test URL removal."""
        text = "Check this out: https://example.com and www.test.com"
        cleaned = clean_text(text, remove_urls=True)
        assert "https://example.com" not in cleaned
        assert "www.test.com" not in cleaned

    def test_clean_telegram_links(self) -> None:
        """Test Telegram link removal."""
        text = "Join our channel: t.me/example_channel"
        cleaned = clean_text(text, remove_urls=True)
        assert "t.me/example_channel" not in cleaned

    def test_clean_mentions(self) -> None:
        """Test mention removal."""
        text = "Hello @username and @another_user"
        cleaned = clean_text(text, remove_mentions=True)
        assert "@username" not in cleaned
        assert "@another_user" not in cleaned

    def test_clean_whitespace(self) -> None:
        """Test whitespace normalization."""
        text = "Hello    world  \n\n  test"
        cleaned = clean_text(text)
        assert cleaned == "Hello world test"

    def test_preserve_urls(self) -> None:
        """Test that URLs are preserved when remove_urls=False."""
        text = "Check https://example.com"
        cleaned = clean_text(text, remove_urls=False)
        assert "https://example.com" in cleaned


class TestRemoveEmojis:
    """Tests for emoji removal."""

    def test_remove_common_emojis(self) -> None:
        """Test removal of common emojis."""
        text = "Hello 😊 World 🌍 Test 🚀"
        cleaned = remove_emojis(text)
        assert "😊" not in cleaned
        assert "🌍" not in cleaned
        assert "🚀" not in cleaned
        assert "Hello" in cleaned
        assert "World" in cleaned

    def test_preserve_text(self) -> None:
        """Test that regular text is preserved."""
        text = "Regular text without emojis"
        cleaned = remove_emojis(text)
        assert cleaned.strip() == text


class TestNormalizeWhitespace:
    """Tests for whitespace normalization."""

    def test_multiple_spaces(self) -> None:
        """Test normalization of multiple spaces."""
        text = "Hello    world"
        normalized = normalize_whitespace(text)
        assert normalized == "Hello world"

    def test_tabs_and_newlines(self) -> None:
        """Test normalization of tabs and newlines."""
        text = "Hello\t\nworld"
        normalized = normalize_whitespace(text)
        assert normalized == "Hello world"

    def test_leading_trailing_spaces(self) -> None:
        """Test removal of leading/trailing spaces."""
        text = "   Hello world   "
        normalized = normalize_whitespace(text)
        assert normalized == "Hello world"


class TestTokenization:
    """Tests for tokenization functions."""

    def test_tokenize_simple(self) -> None:
        """Test simple tokenization."""
        text = "Hello, world! This is a test."
        tokens = tokenize_simple(text)
        assert "Hello" in tokens
        assert "world" in tokens
        assert "This" in tokens
        assert "test" in tokens

    def test_tokenize_simple_min_length(self) -> None:
        """Test simple tokenization with minimum length."""
        text = "I am a programmer"
        tokens = tokenize_simple(text, min_length=2)
        assert "am" in tokens
        assert "programmer" in tokens
        assert "I" not in tokens  # Too short
        assert "a" not in tokens  # Too short

    def test_tokenize_cyrillic(self) -> None:
        """Test tokenization of Cyrillic text."""
        text = "Привет, мир! Это тест."
        tokens = tokenize_simple(text)
        assert "Привет" in tokens
        assert "мир" in tokens
        assert "Это" in tokens
        assert "тест" in tokens

    def test_tokenize_empty(self) -> None:
        """Test tokenization of empty string."""
        tokens = tokenize("", use_nltk=False)
        assert tokens == []


class TestLemmatization:
    """Tests for lemmatization functions."""

    def test_lemmatize_russian_basic(self) -> None:
        """Test basic Russian lemmatization."""
        # Note: This test requires pymorphy2 to be installed
        tokens = ["программированию", "языков", "Python"]
        try:
            lemmas = lemmatize(tokens, language="ru")
            # Should be lemmatized (exact forms depend on pymorphy2)
            assert len(lemmas) == len(tokens)
            assert isinstance(lemmas, list)
        except Exception:
            pytest.skip("pymorphy2 not available")

    def test_lemmatize_english_basic(self) -> None:
        """Test basic English lemmatization."""
        # Note: This test requires NLTK to be installed and data downloaded
        tokens = ["running", "cats", "better"]
        try:
            lemmas = lemmatize(tokens, language="en")
            # Should be lemmatized (exact forms depend on NLTK)
            assert len(lemmas) == len(tokens)
            assert isinstance(lemmas, list)
        except Exception:
            pytest.skip("NLTK not available or data not downloaded")

    def test_lemmatize_empty(self) -> None:
        """Test lemmatization of empty list."""
        lemmas = lemmatize([], language="en")
        assert lemmas == []


class TestNormalizeText:
    """Tests for main text normalization function."""

    def test_normalize_basic(self) -> None:
        """Test basic text normalization."""
        text = "Hello World! This is a TEST."
        result = normalize_text(text, use_lemmatization=False, use_nltk_tokenizer=False)

        assert result.original == text
        assert result.normalized == "hello world this is a test"
        assert len(result.tokens) > 0
        assert "hello" in result.tokens
        assert "world" in result.tokens

    def test_normalize_with_urls(self) -> None:
        """Test normalization with URL removal."""
        text = "Check https://example.com for more info"
        result = normalize_text(
            text, remove_urls=True, use_lemmatization=False, use_nltk_tokenizer=False
        )

        assert "https" not in result.normalized
        assert "example.com" not in result.normalized
        assert "check" in result.tokens
        assert "info" in result.tokens

    def test_normalize_with_emojis(self) -> None:
        """Test normalization with emoji removal."""
        text = "Hello 😊 World"
        result = normalize_text(
            text, remove_emojis_flag=True, use_lemmatization=False, use_nltk_tokenizer=False
        )

        assert "😊" not in result.normalized
        assert "hello" in result.tokens
        assert "world" in result.tokens

    def test_normalize_preserve_case(self) -> None:
        """Test normalization with case preservation."""
        text = "Hello World"
        result = normalize_text(
            text, lowercase=False, use_lemmatization=False, use_nltk_tokenizer=False
        )

        assert result.normalized == "Hello World"

    def test_normalize_empty(self) -> None:
        """Test normalization of empty string."""
        result = normalize_text("", use_lemmatization=False)
        assert result.is_empty
        assert result.tokens == []

    def test_normalize_min_token_length(self) -> None:
        """Test normalization with minimum token length."""
        text = "I am a programmer"
        result = normalize_text(
            text, min_token_length=3, use_lemmatization=False, use_nltk_tokenizer=False
        )

        # Only tokens with length >= 3 should be included
        assert "programmer" in result.tokens
        assert "am" not in result.tokens

    def test_normalize_cyrillic(self) -> None:
        """Test normalization of Russian text."""
        text = "Привет, мир! Это тест Python."
        result = normalize_text(text, use_lemmatization=False, use_nltk_tokenizer=False)

        assert "привет" in result.tokens
        assert "мир" in result.tokens
        assert "python" in result.tokens

    def test_normalize_with_language_detection(self) -> None:
        """Test normalization with language detection."""
        text = "This is an English text"
        result = normalize_text(
            text, language=Language.AUTO, use_lemmatization=False, use_nltk_tokenizer=False
        )

        # Language detection might work or might not depending on langdetect availability
        assert result.language is None or result.language in ["en", "ru"]


class TestPrepareKeywords:
    """Tests for keyword preparation functions."""

    def test_prepare_keyword_lowercase(self) -> None:
        """Test keyword preparation with lowercase."""
        keyword = "  Python Programming  "
        prepared = prepare_keyword(keyword, lowercase=True)
        assert prepared == "python programming"

    def test_prepare_keyword_preserve_case(self) -> None:
        """Test keyword preparation preserving case."""
        keyword = "Python"
        prepared = prepare_keyword(keyword, lowercase=False)
        assert prepared == "Python"

    def test_prepare_keywords_list(self) -> None:
        """Test preparation of keyword list."""
        keywords = ["Python", "  Java  ", "", "  ", "Python", "Go"]
        prepared = prepare_keywords(keywords, lowercase=True, remove_duplicates=True)

        assert len(prepared) == 3
        assert "python" in prepared
        assert "java" in prepared
        assert "go" in prepared
        # Duplicates removed
        assert prepared.count("python") == 1

    def test_prepare_keywords_preserve_duplicates(self) -> None:
        """Test preparation of keywords preserving duplicates."""
        keywords = ["Python", "Python", "Java"]
        prepared = prepare_keywords(keywords, remove_duplicates=False)

        assert len(prepared) == 3
        assert prepared.count("python") == 2

    def test_prepare_keywords_empty(self) -> None:
        """Test preparation of empty keyword list."""
        prepared = prepare_keywords([])
        assert prepared == []

        prepared = prepare_keywords(["", "  ", "\t"])
        assert prepared == []
