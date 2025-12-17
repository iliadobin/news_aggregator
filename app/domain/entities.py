"""
Domain entities for the News Aggregator application.

This module defines Pydantic models for domain entities that represent
business logic objects independent of the database layer.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    """Type of Telegram source."""

    CHANNEL = "channel"
    GROUP = "group"
    PRIVATE = "private"


class FilterMode(str, Enum):
    """Filter matching mode."""

    KEYWORD_ONLY = "keyword_only"
    SEMANTIC_ONLY = "semantic_only"
    COMBINED = "combined"


class MatchType(str, Enum):
    """Type of filter match."""

    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    COMBINED = "combined"


class Language(str, Enum):
    """Supported languages for text processing."""

    RUSSIAN = "ru"
    ENGLISH = "en"
    AUTO = "auto"  # Auto-detect language


# ================================================================================
# Filter Configuration Entities
# ================================================================================


class KeywordOptions(BaseModel):
    """
    Options for keyword matching.

    Controls how keywords are matched in text.
    """

    case_sensitive: bool = Field(
        default=False,
        description="Whether to perform case-sensitive matching",
    )
    whole_word: bool = Field(
        default=False,
        description="Match only whole words, not partial matches",
    )
    use_lemmatization: bool = Field(
        default=True,
        description="Apply lemmatization before matching",
    )
    language: Language = Field(
        default=Language.AUTO,
        description="Language for text processing",
    )
    min_keyword_length: int = Field(
        default=2,
        ge=1,
        description="Minimum keyword length to consider",
    )


class SemanticOptions(BaseModel):
    """
    Options for semantic matching.

    Controls semantic similarity calculation.
    """

    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score to consider a match (0.0-1.0)",
    )
    use_cached_embeddings: bool = Field(
        default=True,
        description="Use cached embeddings for better performance",
    )
    language: Language = Field(
        default=Language.AUTO,
        description="Language for text processing",
    )


class FilterConfig(BaseModel):
    """
    Configuration for a filter.

    Defines how a filter should match messages, including keywords, topics,
    mode, and options for both keyword and semantic matching.
    """

    mode: FilterMode = Field(
        default=FilterMode.COMBINED,
        description="Filter matching mode",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="List of keywords/phrases to match",
    )
    topics: list[str] = Field(
        default_factory=list,
        description="List of topics for semantic matching",
    )
    keyword_options: KeywordOptions = Field(
        default_factory=KeywordOptions,
        description="Options for keyword matching",
    )
    semantic_options: SemanticOptions = Field(
        default_factory=SemanticOptions,
        description="Options for semantic matching",
    )
    require_all_keywords: bool = Field(
        default=False,
        description="If True, all keywords must match; if False, any keyword match is sufficient",
    )

    @field_validator("keywords", "topics")
    @classmethod
    def validate_not_empty_strings(cls, v: list[str]) -> list[str]:
        """Remove empty strings from keywords and topics."""
        return [item.strip() for item in v if item.strip()]

    def validate_for_mode(self) -> None:
        """
        Validate configuration based on filter mode.

        Raises:
            ValueError: If configuration is invalid for the selected mode.
        """
        if self.mode == FilterMode.KEYWORD_ONLY and not self.keywords:
            raise ValueError("Keywords are required for KEYWORD_ONLY mode")
        if self.mode == FilterMode.SEMANTIC_ONLY and not self.topics:
            raise ValueError("Topics are required for SEMANTIC_ONLY mode")
        if self.mode == FilterMode.COMBINED and not self.keywords and not self.topics:
            raise ValueError("Either keywords or topics must be provided for COMBINED mode")


class FilterRule(BaseModel):
    """
    A filter rule with metadata.

    Represents a complete filter with ID, name, user association, and configuration.
    This is the domain representation of a filter.
    """

    id: Optional[int] = Field(default=None, description="Filter ID (None for new filters)")
    user_id: int = Field(description="ID of the user who owns this filter")
    name: str = Field(min_length=1, max_length=255, description="Filter name")
    is_active: bool = Field(default=True, description="Whether the filter is active")
    config: FilterConfig = Field(description="Filter configuration")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    def validate(self) -> None:
        """
        Validate the entire filter rule.

        Raises:
            ValueError: If the filter rule is invalid.
        """
        self.config.validate_for_mode()


# ================================================================================
# Message Entities
# ================================================================================


class MessageEntity(BaseModel):
    """
    Domain representation of a message.

    Represents a message from a Telegram source with its content and metadata.
    """

    id: Optional[int] = Field(default=None, description="Message ID in database")
    telegram_message_id: int = Field(description="Telegram message ID")
    chat_id: int = Field(description="Telegram chat ID")
    source_id: int = Field(description="Source ID in database")
    text: Optional[str] = Field(default=None, description="Message text content")
    date: datetime = Field(description="Message timestamp from Telegram")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (media info, links, language, etc.)",
    )
    is_processed: bool = Field(default=False, description="Whether message was processed")


class NormalizedText(BaseModel):
    """
    Normalized text representation.

    Contains original text, normalized text, tokens, and detected language.
    """

    original: str = Field(description="Original text")
    normalized: str = Field(description="Normalized text (lowercased, cleaned)")
    tokens: list[str] = Field(default_factory=list, description="Tokenized words")
    language: Optional[str] = Field(default=None, description="Detected language code")
    lemmas: Optional[list[str]] = Field(
        default=None,
        description="Lemmatized forms of tokens (optional)",
    )

    @property
    def is_empty(self) -> bool:
        """Check if normalized text is empty."""
        return not self.normalized.strip()


# ================================================================================
# Filter Match Entities
# ================================================================================


class KeywordMatch(BaseModel):
    """
    Result of keyword matching.

    Contains matched keywords and their positions in text.
    """

    matched_keywords: list[str] = Field(
        default_factory=list,
        description="List of keywords that matched",
    )
    match_count: int = Field(default=0, ge=0, description="Total number of matches")
    positions: dict[str, list[int]] = Field(
        default_factory=dict,
        description="Positions of each keyword in text (keyword -> list of char positions)",
    )

    @property
    def has_match(self) -> bool:
        """Check if any keywords matched."""
        return self.match_count > 0


class SemanticMatch(BaseModel):
    """
    Result of semantic matching.

    Contains similarity scores for each topic.
    """

    matched_topics: list[str] = Field(
        default_factory=list,
        description="List of topics that matched (exceeded threshold)",
    )
    scores: dict[str, float] = Field(
        default_factory=dict,
        description="Similarity scores for each topic (topic -> score)",
    )
    max_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Maximum similarity score")

    @property
    def has_match(self) -> bool:
        """Check if any topics matched."""
        return len(self.matched_topics) > 0


class FilterMatchResult(BaseModel):
    """
    Complete result of applying a filter to a message.

    Contains results from both keyword and semantic matching.
    """

    filter_id: int = Field(description="ID of the filter that was applied")
    message_id: int = Field(description="ID of the message that was checked")
    match_type: MatchType = Field(description="Type of match that occurred")
    matched: bool = Field(description="Whether the filter matched the message")
    keyword_match: Optional[KeywordMatch] = Field(
        default=None,
        description="Keyword match details (if applicable)",
    )
    semantic_match: Optional[SemanticMatch] = Field(
        default=None,
        description="Semantic match details (if applicable)",
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        description="Overall match score (0.0-1.0 for semantic, count for keyword)",
    )

    @property
    def details(self) -> dict[str, Any]:
        """Get match details as a dictionary."""
        result: dict[str, Any] = {
            "match_type": self.match_type.value,
            "matched": self.matched,
            "score": self.score,
        }
        if self.keyword_match:
            result["keyword_match"] = {
                "matched_keywords": self.keyword_match.matched_keywords,
                "match_count": self.keyword_match.match_count,
            }
        if self.semantic_match:
            result["semantic_match"] = {
                "matched_topics": self.semantic_match.matched_topics,
                "max_score": self.semantic_match.max_score,
            }
        return result


# ================================================================================
# Source and Subscription Entities
# ================================================================================


class SourceEntity(BaseModel):
    """Domain representation of a news source."""

    id: Optional[int] = Field(default=None)
    telegram_chat_id: int = Field(description="Telegram chat ID")
    title: Optional[str] = Field(default=None, max_length=255)
    username: Optional[str] = Field(default=None, max_length=255)
    type: SourceType = Field(description="Source type")
    is_active: bool = Field(default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserEntity(BaseModel):
    """Domain representation of a user."""

    id: Optional[int] = Field(default=None)
    telegram_id: int = Field(description="Telegram user ID")
    username: Optional[str] = Field(default=None, max_length=255)
    first_name: Optional[str] = Field(default=None, max_length=255)
    last_name: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    target_chat_id: Optional[int] = Field(default=None)
    preferences: dict[str, Any] = Field(default_factory=dict)
