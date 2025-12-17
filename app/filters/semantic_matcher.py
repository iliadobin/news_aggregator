"""
Semantic matching module for filtering messages by meaning.

This module provides functionality for matching messages against semantic filters
using text embeddings and cosine similarity.
"""

import logging
from typing import Optional

from app.domain.entities import (
    FilterConfig,
    FilterMode,
    NormalizedText,
    SemanticMatch,
    SemanticOptions,
)
from app.nlp.embeddings import (
    compute_similarities,
    compute_similarity,
    encode_text,
    encode_texts,
    encode_texts_cached,
)

logger = logging.getLogger(__name__)


# ================================================================================
# Core Semantic Matching Functions
# ================================================================================


def match_text_to_topic(
    text: str,
    topic: str,
    threshold: float = 0.7,
    use_cache: bool = True,
) -> tuple[bool, float]:
    """
    Match text against a single topic using semantic similarity.

    Args:
        text: Text to match
        topic: Topic to match against
        threshold: Minimum similarity threshold (0.0-1.0)
        use_cache: Whether to use embedding cache

    Returns:
        Tuple of (matched: bool, similarity_score: float)
    """
    if not text or not topic:
        return False, 0.0

    try:
        # Get embeddings
        text_embedding = encode_text(text, use_cache=use_cache, normalize=True)
        topic_embedding = encode_text(topic, use_cache=use_cache, normalize=True)

        # Compute similarity
        similarity = compute_similarity(text_embedding, topic_embedding)

        # Check threshold
        matched = similarity >= threshold

        logger.debug(
            f"Semantic match: text='{text[:50]}...', topic='{topic[:30]}...', "
            f"similarity={similarity:.3f}, threshold={threshold:.3f}, matched={matched}"
        )

        return matched, similarity

    except Exception as e:
        logger.error(f"Error in semantic matching: {e}")
        return False, 0.0


def match_text_to_topics(
    text: str,
    topics: list[str],
    threshold: float = 0.7,
    use_cache: bool = True,
) -> SemanticMatch:
    """
    Match text against multiple topics using semantic similarity.

    This function computes similarity scores for all topics and returns
    detailed match information.

    Args:
        text: Text to match
        topics: List of topics to match against
        threshold: Minimum similarity threshold (0.0-1.0)
        use_cache: Whether to use embedding cache

    Returns:
        SemanticMatch object with results
    """
    if not text or not topics:
        return SemanticMatch(
            matched_topics=[],
            scores={},
            max_score=0.0,
        )

    try:
        # Get text embedding
        text_embedding = encode_text(text, use_cache=use_cache, normalize=True)

        # Get topic embeddings (cache-aware to avoid recomputing filter/topic embeddings)
        topic_embeddings = (
            encode_texts_cached(topics, normalize=True) if use_cache else encode_texts(topics, normalize=True)
        )

        # Compute similarities for all topics
        similarities = compute_similarities(text_embedding, topic_embeddings)

        # Build results
        scores = {}
        matched_topics = []
        max_score = 0.0

        for topic, similarity in zip(topics, similarities):
            score = float(similarity)
            scores[topic] = score

            if score > max_score:
                max_score = score

            if score >= threshold:
                matched_topics.append(topic)

        logger.debug(
            f"Semantic match: text='{text[:50]}...', topics={len(topics)}, "
            f"matched={len(matched_topics)}, max_score={max_score:.3f}"
        )

        return SemanticMatch(
            matched_topics=matched_topics,
            scores=scores,
            max_score=max_score,
        )

    except Exception as e:
        logger.error(f"Error in semantic matching: {e}")
        return SemanticMatch(
            matched_topics=[],
            scores={},
            max_score=0.0,
        )


# ================================================================================
# Filter-based Semantic Matching
# ================================================================================


def match_filter_semantic(
    text: str,
    filter_config: FilterConfig,
    normalized_text: Optional[NormalizedText] = None,
) -> SemanticMatch:
    """
    Match text against filter's semantic configuration.

    This is a convenience wrapper that extracts topics and options from
    a FilterConfig and performs semantic matching.

    Args:
        text: Text to match
        filter_config: Filter configuration with topics and semantic options
        normalized_text: Pre-normalized text (optional, currently unused but kept for consistency)

    Returns:
        SemanticMatch object with results
    """
    if not filter_config.topics:
        return SemanticMatch(
            matched_topics=[],
            scores={},
            max_score=0.0,
        )

    # Use normalized text if available, otherwise use original
    match_text = normalized_text.normalized if normalized_text else text

    return match_text_to_topics(
        text=match_text,
        topics=filter_config.topics,
        threshold=filter_config.semantic_options.threshold,
        use_cache=filter_config.semantic_options.use_cached_embeddings,
    )


def evaluate_filter_semantic(
    text: str,
    filter_config: FilterConfig,
    normalized_text: Optional[NormalizedText] = None,
) -> bool:
    """
    Evaluate if text matches filter's semantic requirements.

    Args:
        text: Text to evaluate
        filter_config: Filter configuration
        normalized_text: Pre-normalized text (optional)

    Returns:
        True if text matches semantic requirements, False otherwise
    """
    if not filter_config.topics:
        return False

    match_result = match_filter_semantic(text, filter_config, normalized_text)
    return match_result.has_match


# ================================================================================
# Batch Semantic Matching
# ================================================================================


def match_texts_to_topics(
    texts: list[str],
    topics: list[str],
    threshold: float = 0.7,
    batch_size: int = 32,
    use_cache: bool = True,
) -> list[SemanticMatch]:
    """
    Match multiple texts against multiple topics efficiently.

    Uses batch encoding for better performance.

    Args:
        texts: List of texts to match
        topics: List of topics to match against
        threshold: Minimum similarity threshold
        batch_size: Batch size for encoding

    Returns:
        List of SemanticMatch objects, one per text
    """
    if not texts or not topics:
        return [
            SemanticMatch(matched_topics=[], scores={}, max_score=0.0) for _ in texts
        ]

    try:
        # Encode all texts and topics in batches
        text_embeddings = encode_texts(
            texts, batch_size=batch_size, normalize=True, show_progress=len(texts) > 100
        )
        topic_embeddings = (
            encode_texts_cached(topics, normalize=True) if use_cache else encode_texts(topics, normalize=True)
        )

        results = []

        # Compute similarities for each text
        for text, text_embedding in zip(texts, text_embeddings):
            similarities = compute_similarities(text_embedding, topic_embeddings)

            # Build result
            scores = {}
            matched_topics = []
            max_score = 0.0

            for topic, similarity in zip(topics, similarities):
                score = float(similarity)
                scores[topic] = score

                if score > max_score:
                    max_score = score

                if score >= threshold:
                    matched_topics.append(topic)

            results.append(
                SemanticMatch(
                    matched_topics=matched_topics,
                    scores=scores,
                    max_score=max_score,
                )
            )

        logger.info(f"Batch semantic match: {len(texts)} texts against {len(topics)} topics")

        return results

    except Exception as e:
        logger.error(f"Error in batch semantic matching: {e}")
        # Return empty results on error
        return [
            SemanticMatch(matched_topics=[], scores={}, max_score=0.0) for _ in texts
        ]


# ================================================================================
# Topic Management and Utilities
# ================================================================================


def prepare_topics(
    topics: list[str],
    remove_duplicates: bool = True,
    min_length: int = 2,
) -> list[str]:
    """
    Prepare topics for semantic matching.

    Removes empty strings, short topics, and optionally duplicates.

    Args:
        topics: List of topics
        remove_duplicates: Whether to remove duplicate topics
        min_length: Minimum topic length

    Returns:
        Cleaned list of topics
    """
    # Remove empty and short topics
    cleaned = [t.strip() for t in topics if t.strip() and len(t.strip()) >= min_length]

    # Remove duplicates if requested
    if remove_duplicates:
        # Preserve order while removing duplicates (case-insensitive)
        seen = set()
        unique = []
        for topic in cleaned:
            topic_lower = topic.lower()
            if topic_lower not in seen:
                seen.add(topic_lower)
                unique.append(topic)
        cleaned = unique

    return cleaned


def find_similar_topics(
    query: str,
    topics: list[str],
    top_k: int = 5,
    min_score: float = 0.0,
) -> list[tuple[str, float]]:
    """
    Find most similar topics to a query.

    Useful for topic suggestions or finding related topics.

    Args:
        query: Query text
        topics: List of candidate topics
        top_k: Number of top results to return
        min_score: Minimum similarity score to include

    Returns:
        List of (topic, score) tuples, sorted by score (highest first)
    """
    if not query or not topics:
        return []

    try:
        # Get embeddings
        query_embedding = encode_text(query, normalize=True)
        topic_embeddings = encode_texts(topics, normalize=True)

        # Compute similarities
        similarities = compute_similarities(query_embedding, topic_embeddings)

        # Create list of (topic, score) tuples
        results = [(topic, float(score)) for topic, score in zip(topics, similarities)]

        # Filter by minimum score
        results = [(t, s) for t, s in results if s >= min_score]

        # Sort by score (descending) and take top K
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:top_k]

        return results

    except Exception as e:
        logger.error(f"Error finding similar topics: {e}")
        return []


# ================================================================================
# Scoring and Ranking
# ================================================================================


def get_semantic_score(match: SemanticMatch, normalize: bool = True) -> float:
    """
    Calculate overall semantic match score.

    Args:
        match: SemanticMatch result
        normalize: Whether to normalize by number of topics

    Returns:
        Overall score (0.0-1.0)
    """
    if not match.has_match:
        return 0.0

    # Use max score as the overall score
    score = match.max_score

    # Optionally boost score based on number of matched topics
    if not normalize and len(match.matched_topics) > 1:
        # Small boost for multiple matches (up to 10%)
        boost = min(0.1, (len(match.matched_topics) - 1) * 0.02)
        score = min(1.0, score + boost)

    return score


def rank_by_semantic_score(
    matches: list[tuple[str, SemanticMatch]],
    min_score: float = 0.0,
) -> list[tuple[str, SemanticMatch, float]]:
    """
    Rank texts by semantic match score.

    Args:
        matches: List of (text, SemanticMatch) tuples
        min_score: Minimum score to include

    Returns:
        List of (text, SemanticMatch, score) tuples, sorted by score (highest first)
    """
    # Calculate scores
    results = []
    for text, match in matches:
        score = get_semantic_score(match)
        if score >= min_score:
            results.append((text, match, score))

    # Sort by score (descending)
    results.sort(key=lambda x: x[2], reverse=True)

    return results


# ================================================================================
# Filter Mode Evaluation
# ================================================================================


def should_use_semantic(filter_config: FilterConfig) -> bool:
    """
    Check if semantic matching should be used for this filter.

    Args:
        filter_config: Filter configuration

    Returns:
        True if semantic matching should be used
    """
    mode = filter_config.mode
    has_topics = bool(filter_config.topics)

    return has_topics and mode in (FilterMode.SEMANTIC_ONLY, FilterMode.COMBINED)


def validate_semantic_config(semantic_options: SemanticOptions) -> None:
    """
    Validate semantic configuration.

    Args:
        semantic_options: Semantic options to validate

    Raises:
        ValueError: If configuration is invalid
    """
    if semantic_options.threshold < 0.0 or semantic_options.threshold > 1.0:
        raise ValueError(f"Threshold must be between 0.0 and 1.0, got {semantic_options.threshold}")
