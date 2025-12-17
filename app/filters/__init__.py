"""
Message filtering module.

Provides keyword and semantic matching for filtering messages.
"""

from app.filters.keyword_matcher import (
    check_keywords_match_all,
    check_keywords_match_any,
    evaluate_filter_keywords,
    get_match_score,
    highlight_keywords,
    match_filter_keywords,
    match_keywords_in_text,
)

__all__ = [
    "check_keywords_match_all",
    "check_keywords_match_any",
    "evaluate_filter_keywords",
    "get_match_score",
    "highlight_keywords",
    "match_filter_keywords",
    "match_keywords_in_text",
]
