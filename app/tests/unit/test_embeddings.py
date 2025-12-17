"""\
Unit tests for embeddings module.

Important: these tests must be offline and fast.
We therefore replace `SentenceTransformer` with a small deterministic fake.
"""

from __future__ import annotations

import numpy as np
import pytest

import app.nlp.embeddings as embeddings


class _FakeSentenceTransformer:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def get_sentence_embedding_dimension(self) -> int:
        return 8

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        # Deterministic pseudo-embedding from text bytes.
        def vec(s: str) -> np.ndarray:
            raw = np.frombuffer(s.encode("utf-8"), dtype=np.uint8)
            v = np.zeros(self.get_sentence_embedding_dimension(), dtype=np.float32)
            for i, b in enumerate(raw[:256]):
                v[i % v.size] += float(b)
            if normalize_embeddings:
                n = float(np.linalg.norm(v))
                if n > 0:
                    v = v / n
            return v

        arr = np.stack([vec(t) for t in texts], axis=0)
        return arr if convert_to_numpy else arr.tolist()


@pytest.fixture(autouse=True)
def _patch_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure tests do not download real models.
    monkeypatch.setattr(embeddings, "SentenceTransformer", _FakeSentenceTransformer)
    embeddings.EmbeddingModel._instance = None
    embeddings.clear_embedding_cache()


def test_encode_text_returns_vector() -> None:
    v = embeddings.encode_text("hello", use_cache=False)
    assert isinstance(v, np.ndarray)
    assert v.shape == (embeddings.get_embedding_model().embedding_dimension,)


def test_encode_texts_returns_matrix() -> None:
    m = embeddings.encode_texts(["a", "b", "c"], batch_size=2)
    assert isinstance(m, np.ndarray)
    assert m.shape == (3, embeddings.get_embedding_model().embedding_dimension)


def test_cache_grows_and_hits() -> None:
    embeddings.clear_embedding_cache()
    assert embeddings.get_cache_size() == 0

    v1 = embeddings.encode_text("cached", use_cache=True)
    assert embeddings.get_cache_size() == 1

    v2 = embeddings.encode_text("cached", use_cache=True)
    assert embeddings.get_cache_size() == 1
    assert np.allclose(v1, v2)


def test_encode_texts_cached_caches_per_text() -> None:
    embeddings.clear_embedding_cache()
    arr = embeddings.encode_texts_cached(["x", "y", "x"], normalize=True)
    assert arr.shape[0] == 3
    # two unique texts
    assert embeddings.get_cache_size() == 2


def test_compute_similarity_clips_to_unit_range() -> None:
    # identical
    a = np.array([1.0, 0.0, 0.0])
    assert embeddings.compute_similarity(a, a) == pytest.approx(1.0)

    # opposite -> clipped
    b = np.array([-1.0, 0.0, 0.0])
    assert embeddings.compute_similarity(a, b) == pytest.approx(0.0)


def test_compute_similarities_batch() -> None:
    v = np.array([1.0, 0.0, 0.0])
    mat = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    sims = embeddings.compute_similarities(v, mat)
    assert sims.shape == (2,)
    assert sims[0] == pytest.approx(1.0)
    assert sims[1] == pytest.approx(0.0)


def test_preload_model_loads_fake_model() -> None:
    model = embeddings.get_embedding_model()
    assert model._model is None

    embeddings.preload_model()

    model = embeddings.get_embedding_model()
    assert model._model is not None
    assert isinstance(model._model, _FakeSentenceTransformer)
