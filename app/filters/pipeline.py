"""Filtering pipeline combining keyword and semantic matchers.

This module orchestrates per-filter matching using:
- app.filters.keyword_matcher
- app.filters.semantic_matcher

It is intentionally domain-oriented (works with app.domain.entities.FilterRule).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from app.config.settings import get_settings
from app.domain.entities import (
    FilterMatchResult,
    FilterMode,
    FilterRule,
    MatchType,
    NormalizedText,
    SemanticOptions,
)
from app.filters.keyword_matcher import get_match_score as get_keyword_score
from app.filters.keyword_matcher import match_filter_keywords
from app.filters.semantic_matcher import get_semantic_score, match_filter_semantic
from app.nlp.preprocess import normalize_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime pipeline switches (typically derived from settings)."""

    enable_keyword: bool = True
    enable_semantic: bool = True
    max_message_length: int = 4096


class _NormalizerCache:
    """Cache for NormalizedText objects keyed by normalization parameters."""

    def __init__(self, text: str):
        self._text = text
        self._cache: dict[tuple, NormalizedText] = {}

    def get_for_keywords(self, *, options) -> NormalizedText:
        # Mirror keyword_matcher.normalize_text call parameters.
        effective_use_lemmatization = options.use_lemmatization and (not options.case_sensitive)
        key = (
            "kw",
            options.language.value,
            not options.case_sensitive,
            effective_use_lemmatization,
            options.min_keyword_length,
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        norm = normalize_text(
            self._text,
            language=options.language,
            lowercase=not options.case_sensitive,
            use_lemmatization=effective_use_lemmatization,
            min_token_length=options.min_keyword_length,
        )
        self._cache[key] = norm
        return norm

    def get_for_semantic(self, *, options: SemanticOptions) -> NormalizedText:
        # Semantic matcher uses normalized_text.normalized; lemmatization is unnecessary.
        key = ("sem", options.language.value)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        norm = normalize_text(
            self._text,
            language=options.language,
            lowercase=True,
            use_lemmatization=False,
            min_token_length=1,
        )
        self._cache[key] = norm
        return norm


def _requirement_satisfied_by_keyword_match(rule: FilterRule, keyword_match) -> bool:
    if not keyword_match.has_match:
        return False
    if rule.config.require_all_keywords:
        # Treat match as satisfied only if all configured keywords were hit.
        # Note: matched_keywords can contain normalized variants; for current pipeline
        # behavior we compare lengths.
        return len(keyword_match.matched_keywords) == len(rule.config.keywords)
    return True


def apply_filter(
    *,
    text: str,
    message_id: int,
    rule: FilterRule,
    normalized_text: Optional[NormalizedText] = None,
    pipeline_config: Optional[PipelineConfig] = None,
) -> FilterMatchResult:
    """Apply a single filter rule to message text."""

    cfg = pipeline_config or PipelineConfig()

    keyword_match = None
    semantic_match = None
    keyword_score = 0.0
    semantic_score = 0.0

    # Normalized text can be precomputed by user-bot. We still compute per-filter
    # normalization for correctness (case_sensitive / lemmatization options).
    cache = _NormalizerCache(text)

    do_keyword = (
        cfg.enable_keyword
        and rule.is_active
        and bool(rule.config.keywords)
        and rule.config.mode in (FilterMode.KEYWORD_ONLY, FilterMode.COMBINED)
    )
    do_semantic = (
        cfg.enable_semantic
        and rule.is_active
        and bool(rule.config.topics)
        and rule.config.mode in (FilterMode.SEMANTIC_ONLY, FilterMode.COMBINED)
    )

    # Keyword matching
    keyword_satisfied = False
    if do_keyword:
        kw_norm = cache.get_for_keywords(options=rule.config.keyword_options)
        keyword_match = match_filter_keywords(text, rule.config, kw_norm)
        keyword_satisfied = _requirement_satisfied_by_keyword_match(rule, keyword_match)
        keyword_score = get_keyword_score(keyword_match)

    # Semantic matching
    semantic_satisfied = False
    if do_semantic:
        # Prefer precomputed normalized_text if provided and non-empty; otherwise compute.
        sem_norm = normalized_text if (normalized_text and not normalized_text.is_empty) else None
        if sem_norm is None:
            sem_norm = cache.get_for_semantic(options=rule.config.semantic_options)
        semantic_match = match_filter_semantic(text, rule.config, sem_norm)
        semantic_satisfied = semantic_match.has_match
        semantic_score = get_semantic_score(semantic_match)

    # Combine according to mode
    if rule.config.mode == FilterMode.KEYWORD_ONLY:
        matched = keyword_satisfied
    elif rule.config.mode == FilterMode.SEMANTIC_ONLY:
        matched = semantic_satisfied
    else:
        matched = keyword_satisfied or semantic_satisfied

    if keyword_satisfied and semantic_satisfied:
        match_type = MatchType.COMBINED
        score = max(keyword_score, semantic_score)
    elif keyword_satisfied:
        match_type = MatchType.KEYWORD
        score = keyword_score
    elif semantic_satisfied:
        match_type = MatchType.SEMANTIC
        score = semantic_score
    else:
        match_type = (
            MatchType.KEYWORD
            if rule.config.mode == FilterMode.KEYWORD_ONLY
            else MatchType.SEMANTIC
            if rule.config.mode == FilterMode.SEMANTIC_ONLY
            else MatchType.COMBINED
        )
        score = 0.0

    return FilterMatchResult(
        filter_id=int(rule.id or 0),
        message_id=message_id,
        match_type=match_type,
        matched=matched,
        keyword_match=keyword_match,
        semantic_match=semantic_match,
        score=score,
    )


def run_pipeline(
    *,
    text: str,
    message_id: int,
    rules: Iterable[FilterRule],
    normalized_text: Optional[NormalizedText] = None,
    pipeline_config: Optional[PipelineConfig] = None,
) -> list[FilterMatchResult]:
    """Run message through all filter rules and return matched results."""

    settings = get_settings()
    cfg = pipeline_config or PipelineConfig(
        enable_keyword=settings.filter.enable_keyword,
        enable_semantic=settings.filter.enable_semantic,
        max_message_length=settings.filter.max_message_length,
    )

    if text is None:
        text = ""

    # Apply global truncation to prevent large payloads.
    if cfg.max_message_length and len(text) > cfg.max_message_length:
        text = text[: cfg.max_message_length]

    # Materialize once to avoid consuming iterables multiple times (and to log counts).
    rules_list = list(rules)

    out: list[FilterMatchResult] = []
    for rule in rules_list:
        if not rule.is_active:
            continue
        res = apply_filter(
            text=text,
            message_id=message_id,
            rule=rule,
            normalized_text=normalized_text,
            pipeline_config=cfg,
        )
        if res.matched:
            out.append(res)

    # Sort: higher score first
    out.sort(key=lambda r: r.score, reverse=True)

    logger.debug(
        "Pipeline finished: message_id=%s, rules=%s, matched=%s",
        message_id,
        len(rules_list),
        len(out),
    )

    return out
