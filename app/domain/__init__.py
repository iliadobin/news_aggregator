"""
Domain layer module.

Contains business logic entities and domain models.
"""

from app.domain.entities import (
    FilterConfig,
    FilterMatchResult,
    FilterMode,
    FilterRule,
    KeywordMatch,
    KeywordOptions,
    Language,
    MatchType,
    MessageEntity,
    NormalizedText,
    SemanticMatch,
    SemanticOptions,
    SourceEntity,
    SourceType,
    UserEntity,
)

__all__ = [
    "FilterConfig",
    "FilterMatchResult",
    "FilterMode",
    "FilterRule",
    "KeywordMatch",
    "KeywordOptions",
    "Language",
    "MatchType",
    "MessageEntity",
    "NormalizedText",
    "SemanticMatch",
    "SemanticOptions",
    "SourceEntity",
    "SourceType",
    "UserEntity",
]
