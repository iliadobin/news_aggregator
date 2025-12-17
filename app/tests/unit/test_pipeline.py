"""Unit tests for filtering pipeline.

Covers scenarios:
- no matches
- keyword only
- semantic only
- mixed (keyword + semantic)

Semantic part is tested in offline/mock mode by monkeypatching embedding functions.
"""

from __future__ import annotations

import numpy as np
import pytest

import app.filters.semantic_matcher as sm
from app.domain.entities import FilterConfig, FilterMode, FilterRule, NormalizedText, SemanticOptions
from app.filters.pipeline import run_pipeline


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
        arr = np.stack([_embed_3d(t) for t in texts], axis=0)
        return arr if normalize else arr

    monkeypatch.setattr(sm, "encode_text", fake_encode_text)
    monkeypatch.setattr(sm, "encode_texts", fake_encode_texts)
    monkeypatch.setattr(sm, "encode_texts_cached", fake_encode_texts_cached)


def _norm(text: str) -> NormalizedText:
    # Minimal normalization for semantic matcher usage.
    return NormalizedText(
        original=text,
        normalized=(text or "").lower(),
        tokens=(text or "").lower().split(),
        language="en",
    )


def test_pipeline_no_matches() -> None:
    text = "Cooking pasta for dinner"
    rules = [
        FilterRule(
            id=1,
            user_id=10,
            name="combined",
            config=FilterConfig(
                mode=FilterMode.COMBINED,
                keywords=["python"],
                topics=["quantum physics"],
                semantic_options=SemanticOptions(threshold=0.7),
            ),
        )
    ]

    out = run_pipeline(text=text, message_id=123, rules=rules, normalized_text=_norm(text))
    assert out == []


def test_pipeline_keyword_only_match_type_keyword() -> None:
    text = "Python programming tutorial"
    rules = [
        FilterRule(
            id=1,
            user_id=10,
            name="kw+sem",
            config=FilterConfig(
                mode=FilterMode.COMBINED,
                keywords=["python"],
                topics=["cooking food"],
                semantic_options=SemanticOptions(threshold=0.7),
            ),
        )
    ]

    out = run_pipeline(text=text, message_id=123, rules=rules, normalized_text=_norm(text))
    assert len(out) == 1
    assert out[0].matched is True
    assert out[0].match_type.value == "keyword"
    assert out[0].keyword_match is not None
    assert out[0].keyword_match.has_match is True


def test_pipeline_semantic_only_match_type_semantic() -> None:
    text = "Quantum physics breakthrough"
    rules = [
        FilterRule(
            id=2,
            user_id=10,
            name="sem",
            config=FilterConfig(
                mode=FilterMode.SEMANTIC_ONLY,
                topics=["quantum physics"],
                semantic_options=SemanticOptions(threshold=0.7),
            ),
        )
    ]

    out = run_pipeline(text=text, message_id=123, rules=rules, normalized_text=_norm(text))
    assert len(out) == 1
    assert out[0].matched is True
    assert out[0].match_type.value == "semantic"
    assert out[0].semantic_match is not None
    assert out[0].semantic_match.has_match is True


def test_pipeline_mixed_match_type_combined() -> None:
    text = "Python programming news"
    rules = [
        FilterRule(
            id=3,
            user_id=10,
            name="mixed",
            config=FilterConfig(
                mode=FilterMode.COMBINED,
                keywords=["python"],
                topics=["python coding"],
                semantic_options=SemanticOptions(threshold=0.7),
            ),
        )
    ]

    out = run_pipeline(text=text, message_id=123, rules=rules, normalized_text=_norm(text))
    assert len(out) == 1
    assert out[0].matched is True
    assert out[0].match_type.value == "combined"
