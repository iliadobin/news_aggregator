"""
Embeddings module for semantic text analysis.

This module provides functionality for generating text embeddings using sentence-transformers
and includes caching for better performance.
"""

import hashlib
import logging
from typing import Optional, Union

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


# ================================================================================
# Model Management
# ================================================================================


class EmbeddingModel:
    """
    Wrapper for sentence-transformers model with caching.

    This class manages the lifecycle of the embedding model and provides
    efficient text-to-vector conversion with built-in caching.
    """

    _instance: Optional["EmbeddingModel"] = None
    _model: Optional[SentenceTransformer] = None
    _model_name: Optional[str] = None

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize embedding model.

        Args:
            model_name: Name of the sentence-transformers model to use.
                       If None, uses the model from settings.
        """
        settings = get_settings()
        self._model_name = model_name or settings.filter.embedding_model
        self._cache_size = settings.filter.embedding_cache_size
        self._model = None
        logger.info(f"Initialized EmbeddingModel with model: {self._model_name}")

    def _load_model(self) -> SentenceTransformer:
        """
        Lazily load the sentence-transformers model.

        Returns:
            Loaded SentenceTransformer model
        """
        if self._model is None:
            logger.info(f"Loading sentence-transformers model: {self._model_name}")
            try:
                self._model = SentenceTransformer(self._model_name)
                logger.info(f"Successfully loaded model: {self._model_name}")
            except Exception as e:
                logger.error(f"Failed to load model {self._model_name}: {e}")
                raise RuntimeError(f"Failed to load embedding model: {e}") from e
        return self._model

    @property
    def model(self) -> SentenceTransformer:
        """Get the loaded model (loads if not already loaded)."""
        return self._load_model()

    @property
    def embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by the model."""
        return self.model.get_sentence_embedding_dimension()

    def encode(
        self,
        texts: Union[str, list[str]],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Encode texts into embeddings.

        Args:
            texts: Single text or list of texts to encode
            batch_size: Batch size for encoding
            normalize: Whether to normalize embeddings to unit length
            show_progress: Whether to show progress bar

        Returns:
            Numpy array of embeddings (shape: [n_texts, embedding_dim])
        """
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )
            logger.debug(f"Encoded {len(texts)} texts into embeddings")

            # Return single embedding if input was single text
            if is_single:
                return embeddings[0]
            return embeddings

        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            raise RuntimeError(f"Failed to encode texts: {e}") from e

    def encode_with_cache(
        self,
        text: str,
        normalize: bool = True,
    ) -> np.ndarray:
        """
        Encode single text with caching.

        Uses LRU cache to avoid re-encoding the same texts.
        Cache key is based on text hash and model name.

        Args:
            text: Text to encode
            normalize: Whether to normalize embedding

        Returns:
            Numpy array embedding (shape: [embedding_dim])
        """
        # Create cache key from text hash and model name
        cache_key = self._create_cache_key(text)

        # Try to get from cache
        cached = _get_cached_embedding(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for text hash: {cache_key[:16]}...")
            return cached

        # Encode and cache
        embedding = self.encode(text, normalize=normalize)
        _cache_embedding(cache_key, embedding, self._cache_size)

        return embedding

    def _create_cache_key(self, text: str) -> str:
        """
        Create cache key for text.

        Args:
            text: Text to create key for

        Returns:
            Cache key string
        """
        # Combine text hash and model name for unique key
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        return f"{self._model_name}:{text_hash}"

    @classmethod
    def get_instance(cls, model_name: Optional[str] = None) -> "EmbeddingModel":
        """
        Get singleton instance of EmbeddingModel.

        Args:
            model_name: Model name (if None, uses settings)

        Returns:
            EmbeddingModel instance
        """
        if cls._instance is None or (
            model_name is not None and cls._instance._model_name != model_name
        ):
            cls._instance = cls(model_name=model_name)
        return cls._instance


# ================================================================================
# Caching Functions
# ================================================================================


# Global cache for embeddings
_EMBEDDING_CACHE: dict[str, np.ndarray] = {}


def _get_cached_embedding(cache_key: str) -> Optional[np.ndarray]:
    """
    Get embedding from cache.

    Args:
        cache_key: Cache key

    Returns:
        Cached embedding or None if not found
    """
    return _EMBEDDING_CACHE.get(cache_key)


def _cache_embedding(cache_key: str, embedding: np.ndarray, max_size: int) -> None:
    """
    Cache embedding with size limit.

    Uses simple FIFO eviction when cache is full.

    Args:
        cache_key: Cache key
        embedding: Embedding to cache
        max_size: Maximum cache size
    """
    global _EMBEDDING_CACHE

    # If cache is full, remove oldest entry (FIFO)
    if len(_EMBEDDING_CACHE) >= max_size:
        # Remove first item (oldest)
        first_key = next(iter(_EMBEDDING_CACHE))
        del _EMBEDDING_CACHE[first_key]
        logger.debug(f"Cache full, evicted: {first_key[:16]}...")

    _EMBEDDING_CACHE[cache_key] = embedding


def clear_embedding_cache() -> None:
    """Clear the embedding cache."""
    global _EMBEDDING_CACHE
    _EMBEDDING_CACHE.clear()
    logger.info("Cleared embedding cache")


def get_cache_size() -> int:
    """
    Get current size of embedding cache.

    Returns:
        Number of cached embeddings
    """
    return len(_EMBEDDING_CACHE)


# ================================================================================
# High-level API Functions
# ================================================================================


def get_embedding_model(model_name: Optional[str] = None) -> EmbeddingModel:
    """
    Get the embedding model instance.

    This is the main entry point for getting embeddings.

    Args:
        model_name: Optional model name (uses settings if None)

    Returns:
        EmbeddingModel instance
    """
    return EmbeddingModel.get_instance(model_name=model_name)


def encode_text(
    text: str,
    use_cache: bool = True,
    normalize: bool = True,
) -> np.ndarray:
    """
    Encode a single text into embedding.

    Args:
        text: Text to encode
        use_cache: Whether to use caching
        normalize: Whether to normalize embedding

    Returns:
        Embedding vector as numpy array
    """
    model = get_embedding_model()

    if use_cache:
        return model.encode_with_cache(text, normalize=normalize)
    else:
        return model.encode(text, normalize=normalize)


def encode_texts(
    texts: list[str],
    batch_size: int = 32,
    normalize: bool = True,
    show_progress: bool = False,
) -> np.ndarray:
    """
    Encode multiple texts into embeddings.

    Args:
        texts: List of texts to encode
        batch_size: Batch size for encoding
        normalize: Whether to normalize embeddings
        show_progress: Whether to show progress bar

    Returns:
        Array of embeddings (shape: [n_texts, embedding_dim])
    """
    model = get_embedding_model()
    return model.encode(
        texts,
        batch_size=batch_size,
        normalize=normalize,
        show_progress=show_progress,
    )


def encode_texts_cached(
    texts: list[str],
    normalize: bool = True,
) -> np.ndarray:
    """
    Encode multiple texts, using per-text caching.

    This is useful for caching embeddings of filter topics (which are likely to repeat).
    For each text, if it exists in cache it is reused, otherwise it is encoded and cached.

    Notes:
        This function prefers caching over batch throughput. For very large lists, consider
        using `encode_texts` instead.

    Args:
        texts: List of texts to encode
        normalize: Whether to normalize embeddings

    Returns:
        Array of embeddings (shape: [n_texts, embedding_dim])
    """
    model = get_embedding_model()
    if not texts:
        return np.zeros((0, model.embedding_dimension), dtype=np.float32)

    embeddings: list[np.ndarray] = []
    for text in texts:
        embeddings.append(model.encode_with_cache(text, normalize=normalize))
    return np.stack(embeddings, axis=0)


def compute_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Compute cosine similarity between two embeddings.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector

    Returns:
        Cosine similarity score (0.0 to 1.0 for normalized embeddings)
    """
    # If embeddings are normalized, dot product = cosine similarity
    similarity = float(np.dot(embedding1, embedding2))

    # Clip to [0, 1] range (for normalized embeddings this should already be true)
    return max(0.0, min(1.0, similarity))


def compute_similarities(
    embedding: np.ndarray,
    embeddings: np.ndarray,
) -> np.ndarray:
    """
    Compute cosine similarities between one embedding and multiple embeddings.

    Args:
        embedding: Single embedding vector (shape: [embedding_dim])
        embeddings: Multiple embeddings (shape: [n, embedding_dim])

    Returns:
        Array of similarity scores (shape: [n])
    """
    # Matrix multiplication for batch similarity computation
    similarities = np.dot(embeddings, embedding)

    # Clip to [0, 1] range
    return np.clip(similarities, 0.0, 1.0)


# ================================================================================
# Utility Functions
# ================================================================================


def get_model_info() -> dict:
    """
    Get information about the current embedding model.

    Returns:
        Dictionary with model information
    """
    model = get_embedding_model()
    return {
        "model_name": model._model_name,
        "embedding_dimension": model.embedding_dimension,
        "cache_size": get_cache_size(),
        "max_cache_size": model._cache_size,
    }


def preload_model() -> None:
    """
    Preload the embedding model.

    Useful for warming up the model at startup.
    """
    model = get_embedding_model()
    _ = model.model  # Access model property to trigger loading
    logger.info("Embedding model preloaded")
