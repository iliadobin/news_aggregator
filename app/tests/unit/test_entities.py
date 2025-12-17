"""
Unit tests for domain entities.

Tests validation, creation, and behavior of domain entity models.
"""

import pytest
from pydantic import ValidationError

from app.domain.entities import (
    FilterConfig,
    FilterMode,
    FilterRule,
    KeywordMatch,
    KeywordOptions,
    Language,
    NormalizedText,
    SemanticMatch,
    SemanticOptions,
)


class TestKeywordOptions:
    """Tests for KeywordOptions configuration."""

    def test_default_options(self) -> None:
        """Test default keyword options."""
        options = KeywordOptions()
        assert options.case_sensitive is False
        assert options.whole_word is False
        assert options.use_lemmatization is True
        assert options.language == Language.AUTO
        assert options.min_keyword_length == 2

    def test_custom_options(self) -> None:
        """Test custom keyword options."""
        options = KeywordOptions(
            case_sensitive=True,
            whole_word=True,
            use_lemmatization=False,
            language=Language.RUSSIAN,
            min_keyword_length=3,
        )
        assert options.case_sensitive is True
        assert options.whole_word is True
        assert options.use_lemmatization is False
        assert options.language == Language.RUSSIAN
        assert options.min_keyword_length == 3


class TestSemanticOptions:
    """Tests for SemanticOptions configuration."""

    def test_default_options(self) -> None:
        """Test default semantic options."""
        options = SemanticOptions()
        assert options.threshold == 0.7
        assert options.use_cached_embeddings is True
        assert options.language == Language.AUTO

    def test_threshold_validation(self) -> None:
        """Test threshold value validation."""
        # Valid thresholds
        SemanticOptions(threshold=0.0)
        SemanticOptions(threshold=0.5)
        SemanticOptions(threshold=1.0)

        # Invalid thresholds
        with pytest.raises(ValidationError):
            SemanticOptions(threshold=-0.1)

        with pytest.raises(ValidationError):
            SemanticOptions(threshold=1.1)


class TestFilterConfig:
    """Tests for FilterConfig."""

    def test_keyword_only_config(self) -> None:
        """Test keyword-only filter configuration."""
        config = FilterConfig(
            mode=FilterMode.KEYWORD_ONLY,
            keywords=["python", "programming"],
        )
        assert config.mode == FilterMode.KEYWORD_ONLY
        assert len(config.keywords) == 2
        assert config.topics == []

        # Should validate successfully
        config.validate_for_mode()

    def test_semantic_only_config(self) -> None:
        """Test semantic-only filter configuration."""
        config = FilterConfig(
            mode=FilterMode.SEMANTIC_ONLY,
            topics=["technology", "science"],
        )
        assert config.mode == FilterMode.SEMANTIC_ONLY
        assert len(config.topics) == 2
        assert config.keywords == []

        # Should validate successfully
        config.validate_for_mode()

    def test_combined_config(self) -> None:
        """Test combined filter configuration."""
        config = FilterConfig(
            mode=FilterMode.COMBINED,
            keywords=["python"],
            topics=["programming"],
        )
        assert config.mode == FilterMode.COMBINED
        assert len(config.keywords) == 1
        assert len(config.topics) == 1

        # Should validate successfully
        config.validate_for_mode()

    def test_validation_keyword_only_without_keywords(self) -> None:
        """Test that keyword-only mode without keywords fails validation."""
        config = FilterConfig(
            mode=FilterMode.KEYWORD_ONLY,
            keywords=[],
        )
        with pytest.raises(ValueError, match="Keywords are required"):
            config.validate_for_mode()

    def test_validation_semantic_only_without_topics(self) -> None:
        """Test that semantic-only mode without topics fails validation."""
        config = FilterConfig(
            mode=FilterMode.SEMANTIC_ONLY,
            topics=[],
        )
        with pytest.raises(ValueError, match="Topics are required"):
            config.validate_for_mode()

    def test_validation_combined_without_keywords_or_topics(self) -> None:
        """Test that combined mode without keywords or topics fails validation."""
        config = FilterConfig(
            mode=FilterMode.COMBINED,
            keywords=[],
            topics=[],
        )
        with pytest.raises(ValueError, match="Either keywords or topics must be provided"):
            config.validate_for_mode()

    def test_empty_strings_removed(self) -> None:
        """Test that empty strings are removed from keywords and topics."""
        config = FilterConfig(
            keywords=["python", "", "  ", "java"],
            topics=["tech", "", "science"],
        )
        assert config.keywords == ["python", "java"]
        assert config.topics == ["tech", "science"]


class TestFilterRule:
    """Tests for FilterRule."""

    def test_create_filter_rule(self) -> None:
        """Test creating a filter rule."""
        config = FilterConfig(
            mode=FilterMode.KEYWORD_ONLY,
            keywords=["test"],
        )
        rule = FilterRule(
            user_id=123,
            name="Test Filter",
            config=config,
        )
        assert rule.user_id == 123
        assert rule.name == "Test Filter"
        assert rule.is_active is True
        assert rule.id is None  # Not persisted yet

    def test_filter_rule_validation(self) -> None:
        """Test filter rule validation."""
        config = FilterConfig(
            mode=FilterMode.KEYWORD_ONLY,
            keywords=["test"],
        )
        rule = FilterRule(
            user_id=123,
            name="Test Filter",
            config=config,
        )
        # Should not raise
        rule.validate()

    def test_filter_rule_validation_fails(self) -> None:
        """Test filter rule validation with invalid config."""
        config = FilterConfig(
            mode=FilterMode.KEYWORD_ONLY,
            keywords=[],  # Invalid for keyword-only mode
        )
        rule = FilterRule(
            user_id=123,
            name="Test Filter",
            config=config,
        )
        with pytest.raises(ValueError):
            rule.validate()


class TestNormalizedText:
    """Tests for NormalizedText."""

    def test_normalized_text(self) -> None:
        """Test normalized text entity."""
        text = NormalizedText(
            original="Hello World!",
            normalized="hello world",
            tokens=["hello", "world"],
            language="en",
        )
        assert text.original == "Hello World!"
        assert text.normalized == "hello world"
        assert len(text.tokens) == 2
        assert text.language == "en"

    def test_is_empty_property(self) -> None:
        """Test is_empty property."""
        empty = NormalizedText(original="", normalized="", tokens=[])
        assert empty.is_empty is True

        whitespace = NormalizedText(original="  ", normalized="  ", tokens=[])
        assert whitespace.is_empty is True

        not_empty = NormalizedText(original="test", normalized="test", tokens=["test"])
        assert not_empty.is_empty is False

    def test_with_lemmas(self) -> None:
        """Test normalized text with lemmas."""
        text = NormalizedText(
            original="Running quickly",
            normalized="running quickly",
            tokens=["running", "quickly"],
            language="en",
            lemmas=["run", "quickly"],
        )
        assert text.lemmas == ["run", "quickly"]


class TestKeywordMatch:
    """Tests for KeywordMatch."""

    def test_no_match(self) -> None:
        """Test keyword match with no matches."""
        match = KeywordMatch()
        assert match.has_match is False
        assert match.match_count == 0
        assert len(match.matched_keywords) == 0

    def test_single_match(self) -> None:
        """Test keyword match with single match."""
        match = KeywordMatch(
            matched_keywords=["python"],
            match_count=1,
            positions={"python": [0]},
        )
        assert match.has_match is True
        assert match.match_count == 1
        assert len(match.matched_keywords) == 1

    def test_multiple_matches(self) -> None:
        """Test keyword match with multiple matches."""
        match = KeywordMatch(
            matched_keywords=["python", "java"],
            match_count=3,
            positions={"python": [0, 10], "java": [20]},
        )
        assert match.has_match is True
        assert match.match_count == 3
        assert len(match.matched_keywords) == 2


class TestSemanticMatch:
    """Tests for SemanticMatch."""

    def test_no_match(self) -> None:
        """Test semantic match with no matches."""
        match = SemanticMatch()
        assert match.has_match is False
        assert match.max_score == 0.0
        assert len(match.matched_topics) == 0

    def test_single_match(self) -> None:
        """Test semantic match with single topic."""
        match = SemanticMatch(
            matched_topics=["technology"],
            scores={"technology": 0.85},
            max_score=0.85,
        )
        assert match.has_match is True
        assert match.max_score == 0.85
        assert len(match.matched_topics) == 1

    def test_multiple_matches(self) -> None:
        """Test semantic match with multiple topics."""
        match = SemanticMatch(
            matched_topics=["technology", "science"],
            scores={"technology": 0.85, "science": 0.75, "sports": 0.3},
            max_score=0.85,
        )
        assert match.has_match is True
        assert match.max_score == 0.85
        assert len(match.matched_topics) == 2
