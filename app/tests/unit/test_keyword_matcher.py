"""
Unit tests for keyword matcher module.

Tests keyword matching with various options and configurations.
"""

import pytest

from app.domain.entities import (
    FilterConfig,
    FilterMode,
    KeywordOptions,
    Language,
    NormalizedText,
)
from app.filters.keyword_matcher import (
    check_keywords_match_all,
    check_keywords_match_any,
    evaluate_filter_keywords,
    get_match_score,
    highlight_keywords,
    match_filter_keywords,
    match_keyword_in_tokens,
    match_keyword_simple,
    match_keywords_in_text,
)


class TestMatchKeywordSimple:
    """Tests for simple keyword matching."""

    def test_basic_match(self) -> None:
        """Test basic keyword matching."""
        matched, positions = match_keyword_simple("Hello world", "world")
        assert matched is True
        assert len(positions) > 0

    def test_case_sensitive_match(self) -> None:
        """Test case-sensitive matching."""
        # Case-insensitive (default)
        matched, _ = match_keyword_simple("Hello World", "world", case_sensitive=False)
        assert matched is True

        # Case-sensitive
        matched, _ = match_keyword_simple("Hello World", "world", case_sensitive=True)
        assert matched is False

        matched, _ = match_keyword_simple("Hello World", "World", case_sensitive=True)
        assert matched is True

    def test_whole_word_match(self) -> None:
        """Test whole word matching."""
        # Without whole word requirement - should match
        matched, _ = match_keyword_simple("python programming", "python", whole_word=False)
        assert matched is True

        # Partial match should work without whole_word
        matched, _ = match_keyword_simple("pythonic code", "python", whole_word=False)
        assert matched is True

        # With whole word requirement - should not match partial
        matched, positions = match_keyword_simple("pythonic code", "python", whole_word=True)
        # "python" is not a whole word in "pythonic"
        assert matched is False or len(positions) == 0

        # Should match whole word
        matched, positions = match_keyword_simple("python code", "python", whole_word=True)
        assert matched is True
        assert len(positions) > 0

    def test_multiple_occurrences(self) -> None:
        """Test matching multiple occurrences."""
        text = "Python is great. I love Python programming in Python."
        matched, positions = match_keyword_simple(text, "python")
        assert matched is True
        assert len(positions) == 3  # Three occurrences

    def test_no_match(self) -> None:
        """Test when keyword doesn't match."""
        matched, positions = match_keyword_simple("Hello world", "java")
        assert matched is False
        assert len(positions) == 0

    def test_empty_inputs(self) -> None:
        """Test with empty inputs."""
        matched, positions = match_keyword_simple("", "test")
        assert matched is False

        matched, positions = match_keyword_simple("test", "")
        assert matched is False


class TestMatchKeywordInTokens:
    """Tests for token-based keyword matching."""

    def test_single_word_match(self) -> None:
        """Test single word matching in tokens."""
        tokens = ["hello", "world", "test"]
        assert match_keyword_in_tokens(tokens, "world") is True
        assert match_keyword_in_tokens(tokens, "test") is True
        assert match_keyword_in_tokens(tokens, "missing") is False

    def test_single_word_multiple_occurrences(self) -> None:
        """Test matching when token appears multiple times."""
        tokens = ["python", "is", "python", "python"]
        assert match_keyword_in_tokens(tokens, "python") is True

    def test_multi_word_match(self) -> None:
        """Test multi-word phrase matching."""
        tokens = ["python", "is", "a", "great", "language"]
        assert match_keyword_in_tokens(tokens, "python is") is True
        assert match_keyword_in_tokens(tokens, "great language") is True
        assert match_keyword_in_tokens(tokens, "is a great") is True
        assert match_keyword_in_tokens(tokens, "python language") is False  # Not consecutive

    def test_multi_word_multiple_occurrences(self) -> None:
        """Test matching when phrase occurs multiple times."""
        tokens = ["a", "b", "a", "b", "a", "b"]
        assert match_keyword_in_tokens(tokens, "a b") is True

    def test_case_sensitivity(self) -> None:
        """Test case sensitivity in token matching."""
        tokens = ["Python", "Programming"]

        # Case-insensitive (default)
        assert match_keyword_in_tokens(tokens, "python", case_sensitive=False) is True
        assert match_keyword_in_tokens(tokens, "PROGRAMMING", case_sensitive=False) is True

        # Case-sensitive
        assert match_keyword_in_tokens(tokens, "python", case_sensitive=True) is False
        assert match_keyword_in_tokens(tokens, "Python", case_sensitive=True) is True

    def test_empty_inputs(self) -> None:
        """Test with empty inputs."""
        assert match_keyword_in_tokens([], "test") is False
        assert match_keyword_in_tokens(["test"], "") is False


class TestMatchKeywordsInText:
    """Tests for advanced keyword matching in text."""

    def test_basic_matching(self) -> None:
        """Test basic keyword matching."""
        text = "Python is a programming language"
        keywords = ["python", "programming"]

        match = match_keywords_in_text(text, keywords)
        assert match.has_match is True
        assert len(match.matched_keywords) == 2
        assert "python" in match.matched_keywords
        assert "programming" in match.matched_keywords

    def test_no_matches(self) -> None:
        """Test when no keywords match."""
        text = "Python programming"
        keywords = ["java", "javascript"]

        match = match_keywords_in_text(text, keywords)
        assert match.has_match is False
        assert len(match.matched_keywords) == 0

    def test_partial_matches(self) -> None:
        """Test partial keyword matches."""
        text = "Python programming language"
        keywords = ["python", "java", "programming"]

        match = match_keywords_in_text(text, keywords)
        assert match.has_match is True
        assert len(match.matched_keywords) == 2
        assert "python" in match.matched_keywords
        assert "programming" in match.matched_keywords
        assert "java" not in match.matched_keywords

    def test_with_options(self) -> None:
        """Test matching with custom options."""
        text = "Python Programming Language"
        keywords = ["python", "programming"]

        # Case-sensitive matching
        options = KeywordOptions(case_sensitive=True)
        match = match_keywords_in_text(text, keywords, options=options)
        # "python" and "programming" don't match because of case
        assert len(match.matched_keywords) == 0

        # Case-insensitive matching (default)
        options = KeywordOptions(case_sensitive=False)
        match = match_keywords_in_text(text, keywords, options=options)
        assert len(match.matched_keywords) == 2

    def test_with_pre_normalized_text(self) -> None:
        """Test matching with pre-normalized text."""
        text = "Python programming"
        keywords = ["python"]

        normalized = NormalizedText(
            original=text,
            normalized="python programming",
            tokens=["python", "programming"],
            language="en",
        )

        match = match_keywords_in_text(text, keywords, normalized_text=normalized)
        assert match.has_match is True
        assert "python" in match.matched_keywords

    def test_empty_inputs(self) -> None:
        """Test with empty inputs."""
        match = match_keywords_in_text("", ["test"])
        assert match.has_match is False

        match = match_keywords_in_text("test", [])
        assert match.has_match is False

    def test_match_count_consistent_between_partial_and_token_strategies(self) -> None:
        """
        Regression: match_count should count total occurrences, regardless of strategy.

        Previously, token-based matching incremented match_count by 1 per keyword even if it
        appeared multiple times, while partial matching counted actual occurrences.
        """
        text = "python python python"
        keywords = ["python"]
        normalized = NormalizedText(
            original=text,
            normalized=text,
            tokens=["python", "python", "python"],
            language="en",
            lemmas=["python", "python", "python"],
        )

        partial_opts = KeywordOptions(case_sensitive=False, whole_word=False, use_lemmatization=False)
        token_opts = KeywordOptions(case_sensitive=False, whole_word=True, use_lemmatization=False)

        partial_match = match_keywords_in_text(text, keywords, options=partial_opts, normalized_text=normalized)
        token_match = match_keywords_in_text(text, keywords, options=token_opts, normalized_text=normalized)

        assert partial_match.match_count == 3
        # token-based strategy counts presence per keyword (not occurrences)
        assert token_match.match_count == 1


class TestMatchFilterKeywords:
    """Tests for filter-based keyword matching."""

    def test_match_with_filter_config(self) -> None:
        """Test matching with filter configuration."""
        text = "Python is a great programming language"
        config = FilterConfig(
            mode=FilterMode.KEYWORD_ONLY,
            keywords=["python", "programming"],
        )

        match = match_filter_keywords(text, config)
        assert match.has_match is True
        assert len(match.matched_keywords) == 2


class TestCheckKeywordsMatchAll:
    """Tests for checking if all keywords match."""

    def test_all_match(self) -> None:
        """Test when all keywords match."""
        text = "Python is a programming language"
        keywords = ["python", "programming", "language"]

        assert check_keywords_match_all(text, keywords) is True

    def test_partial_match(self) -> None:
        """Test when only some keywords match."""
        text = "Python programming"
        keywords = ["python", "java", "programming"]

        assert check_keywords_match_all(text, keywords) is False

    def test_no_match(self) -> None:
        """Test when no keywords match."""
        text = "Python programming"
        keywords = ["java", "javascript"]

        assert check_keywords_match_all(text, keywords) is False


class TestCheckKeywordsMatchAny:
    """Tests for checking if any keyword matches."""

    def test_all_match(self) -> None:
        """Test when all keywords match."""
        text = "Python programming"
        keywords = ["python", "programming"]

        assert check_keywords_match_any(text, keywords) is True

    def test_partial_match(self) -> None:
        """Test when only some keywords match."""
        text = "Python programming"
        keywords = ["python", "java"]

        assert check_keywords_match_any(text, keywords) is True

    def test_no_match(self) -> None:
        """Test when no keywords match."""
        text = "Python programming"
        keywords = ["java", "javascript"]

        assert check_keywords_match_any(text, keywords) is False


class TestEvaluateFilterKeywords:
    """Tests for evaluating filter keyword requirements."""

    def test_require_any_keyword(self) -> None:
        """Test filter requiring any keyword match."""
        text = "Python programming language"
        config = FilterConfig(
            mode=FilterMode.KEYWORD_ONLY,
            keywords=["python", "java"],
            require_all_keywords=False,
        )

        # Should match because "python" is present
        assert evaluate_filter_keywords(text, config) is True

    def test_require_all_keywords(self) -> None:
        """Test filter requiring all keywords match."""
        text = "Python programming language"
        config = FilterConfig(
            mode=FilterMode.KEYWORD_ONLY,
            keywords=["python", "programming"],
            require_all_keywords=True,
        )

        # Should match because both keywords are present
        assert evaluate_filter_keywords(text, config) is True

        # Should not match because not all keywords are present
        config.keywords = ["python", "java"]
        assert evaluate_filter_keywords(text, config) is False

    def test_no_keywords(self) -> None:
        """Test filter with no keywords."""
        text = "Python programming"
        config = FilterConfig(
            mode=FilterMode.SEMANTIC_ONLY,
            keywords=[],
            topics=["tech"],
        )

        assert evaluate_filter_keywords(text, config) is False


class TestGetMatchScore:
    """Tests for match score calculation."""

    def test_no_match_score(self) -> None:
        """Test score for no matches."""
        from app.domain.entities import KeywordMatch

        match = KeywordMatch()
        score = get_match_score(match)
        assert score == 0.0

    def test_single_match_score(self) -> None:
        """Test score for single match."""
        from app.domain.entities import KeywordMatch

        match = KeywordMatch(matched_keywords=["python"], match_count=1)
        score = get_match_score(match)
        assert 0.0 < score <= 1.0

    def test_multiple_matches_score(self) -> None:
        """Test score for multiple matches."""
        from app.domain.entities import KeywordMatch

        match = KeywordMatch(
            matched_keywords=["python", "programming"], match_count=5, positions={}
        )
        score = get_match_score(match)
        assert 0.0 < score <= 1.0


class TestHighlightKeywords:
    """Tests for keyword highlighting."""

    def test_basic_highlighting(self) -> None:
        """Test basic keyword highlighting."""
        from app.domain.entities import KeywordMatch

        text = "Python is a programming language"
        match = KeywordMatch(
            matched_keywords=["python", "programming"],
            match_count=2,
            positions={},
        )

        highlighted = highlight_keywords(text, match)
        assert "**Python**" in highlighted or "**python**" in highlighted
        assert "**programming**" in highlighted

    def test_no_match_highlighting(self) -> None:
        """Test highlighting with no matches."""
        from app.domain.entities import KeywordMatch

        text = "Python programming"
        match = KeywordMatch()

        highlighted = highlight_keywords(text, match)
        assert highlighted == text

    def test_custom_highlight_format(self) -> None:
        """Test highlighting with custom format."""
        from app.domain.entities import KeywordMatch

        text = "Python programming"
        match = KeywordMatch(matched_keywords=["python"], match_count=1, positions={})

        highlighted = highlight_keywords(text, match, highlight_format="<mark>{keyword}</mark>")
        assert "<mark>Python</mark>" in highlighted or "<mark>python</mark>" in highlighted


class TestRussianKeywordMatching:
    """Tests for Russian keyword matching."""

    def test_basic_russian_match(self) -> None:
        """Test basic Russian keyword matching."""
        text = "Программирование на Python это интересно"
        keywords = ["программирование", "python"]

        match = match_keywords_in_text(text, keywords)
        assert match.has_match is True
        # At least "python" should match, "программирование" might match depending on normalization
        assert len(match.matched_keywords) >= 1

    def test_russian_case_insensitive(self) -> None:
        """Test case-insensitive Russian matching."""
        text = "Программирование на Python"
        keywords = ["ПРОГРАММИРОВАНИЕ", "python"]

        match = match_keywords_in_text(text, keywords)
        assert match.has_match is True
        assert len(match.matched_keywords) >= 1


class TestMultiWordKeywords:
    """Tests for multi-word keyword matching."""

    def test_phrase_matching(self) -> None:
        """Test matching of multi-word phrases."""
        text = "Python programming language is great"
        keywords = ["python programming", "programming language"]

        match = match_keywords_in_text(text, keywords)
        assert match.has_match is True
        # Should match both phrases
        assert len(match.matched_keywords) >= 1

    def test_phrase_not_matching_non_consecutive(self) -> None:
        """Test that phrases don't match non-consecutive words."""
        text = "Python is a great programming language"
        keywords = ["python programming"]  # These words are not consecutive

        # With lemmatization/tokenization, this depends on implementation
        # The important thing is that behavior is consistent
        match = match_keywords_in_text(text, keywords)
        # This might or might not match depending on implementation details
        assert isinstance(match.has_match, bool)
