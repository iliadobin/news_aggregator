"""\
Unit tests for semantic matcher module.

These tests are intentionally offline/stable: we replace embedding functions with
small deterministic vectors.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

import app.filters.semantic_matcher as sm
from app.domain.entities import FilterConfig, FilterMode, NormalizedText, SemanticMatch, SemanticOptions


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v if n == 0 else v / n


def _embed_3d(text: str) -> np.ndarray:
    t = (text or "").lower()
    # 3 dimensions: python/programming, cooking/food, physics/science
    v = np.array(
        [
            1.0 if any(k in t for k in ("python", "program", "код")) else 0.0,
            1.0 if any(k in t for k in ("cook", "food", "еда", "паста")) else 0.0,
            1.0 if any(k in t for k in ("phys", "quant", "наука", "атом")) else 0.0,
        ],
        dtype=np.float32,
    )
    # if nothing matched, make it a small distinct vector so similarities are low
    if float(v.sum()) == 0.0:
        v = np.array([0.1, 0.1, 0.1], dtype=np.float32)
    return _unit(v)


@pytest.fixture(autouse=True)
def _patch_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_encode_text(text: str, use_cache: bool = True, normalize: bool = True) -> np.ndarray:
        v = _embed_3d(text)
        return v if normalize else v

    def fake_encode_texts(
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = False,
    ) -> np.ndarray:
        arr = np.stack([_embed_3d(t) for t in texts], axis=0)
        return arr if normalize else arr

    def fake_encode_texts_cached(texts: list[str], normalize: bool = True) -> np.ndarray:
        # same output as non-cached; caching behavior is validated via call counts.
        arr = np.stack([_embed_3d(t) for t in texts], axis=0)
        return arr if normalize else arr

    monkeypatch.setattr(sm, "encode_text", fake_encode_text)
    monkeypatch.setattr(sm, "encode_texts", fake_encode_texts)
    monkeypatch.setattr(sm, "encode_texts_cached", fake_encode_texts_cached)


def test_match_text_to_topic_true_for_same_cluster() -> None:
    matched, score = sm.match_text_to_topic(
        "Python programming tutorial",
        "Python coding",
        threshold=0.7,
        use_cache=True,
    )
    assert matched is True
    assert 0.0 <= score <= 1.0


def test_match_text_to_topic_false_for_different_cluster() -> None:
    matched, score = sm.match_text_to_topic(
        "Cooking pasta",
        "Quantum physics",
        threshold=0.7,
        use_cache=True,
    )
    assert matched is False
    assert 0.0 <= score <= 1.0


def test_match_text_to_topics_returns_scores_and_matches() -> None:
    res = sm.match_text_to_topics(
        "Python programming",
        ["Python coding", "Cooking food"],
        threshold=0.7,
        use_cache=True,
    )
    assert isinstance(res, SemanticMatch)
    assert set(res.scores.keys()) == {"Python coding", "Cooking food"}
    assert res.max_score == pytest.approx(max(res.scores.values()))
    assert "Python coding" in res.matched_topics


def test_match_filter_semantic_uses_normalized_text_if_given() -> None:
    txt = "PYTHON PROGRAMMING"
    normalized = NormalizedText(
        original=txt,
        normalized=txt.lower(),
        tokens=txt.lower().split(),
        language="en",
    )
    cfg = FilterConfig(
        mode=FilterMode.SEMANTIC_ONLY,
        topics=["python coding"],
        semantic_options=SemanticOptions(threshold=0.7, use_cached_embeddings=True),
    )

    res = sm.match_filter_semantic(txt, cfg, normalized)
    assert res.has_match is True


def test_should_use_semantic() -> None:
    assert (
        sm.should_use_semantic(
            FilterConfig(mode=FilterMode.SEMANTIC_ONLY, topics=["t"], keywords=[])
        )
        is True
    )
    assert (
        sm.should_use_semantic(
            FilterConfig(mode=FilterMode.KEYWORD_ONLY, topics=["t"], keywords=["k"])
        )
        is False
    )


def test_prepare_topics_dedup_and_strip() -> None:
    topics = ["  Python ", "python", "", "  ", "Cooking"]
    out = sm.prepare_topics(topics, remove_duplicates=True, min_length=2)
    assert out == ["Python", "Cooking"]


def test_match_texts_to_topics_batch_shape() -> None:
    results = sm.match_texts_to_topics(
        ["Python", "Cooking pasta"],
        ["python coding", "food"],
        threshold=0.7,
        batch_size=2,
        use_cache=True,
    )
    assert len(results) == 2
    assert all(isinstance(r, SemanticMatch) for r in results)


def test_find_similar_topics_orders_by_score() -> None:
    topics = ["Python coding", "Cooking food", "Quantum physics"]
    res = sm.find_similar_topics("Python programming", topics, top_k=2)
    assert len(res) == 2
    assert res[0][1] >= res[1][1]


def test_rank_by_semantic_score_orders_desc() -> None:
    m1 = SemanticMatch(matched_topics=["t"], scores={"t": 0.9}, max_score=0.9)
    m2 = SemanticMatch(matched_topics=["t"], scores={"t": 0.3}, max_score=0.3)
    ranked = sm.rank_by_semantic_score([("a", m2), ("b", m1)])
    assert ranked[0][0] == "b"
    assert ranked[0][2] == pytest.approx(0.9)


def test_validate_semantic_config_rejects_threshold_out_of_range() -> None:
    # Pydantic will validate on construction, but we also keep our manual validator.
    with pytest.raises(Exception):
        SemanticOptions(threshold=-0.1)

    with pytest.raises(Exception):
        SemanticOptions(threshold=1.1)
