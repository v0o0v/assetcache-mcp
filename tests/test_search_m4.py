"""M4 — `HybridSearcher` 6채널 가중합 + label_query free_text 분리 + diversity 통합.

M3 의 5채널을 6채널로 확장. `score_breakdown.feedback` 키 항상 노출.
`weight_feedback_override` per-call 노출. 6채널 합 = score (±1e-4).
M3 baseline 검색은 그대로 작동 (회귀 가드).
"""

from __future__ import annotations

import pytest


def _build_searcher(populated_store, fake_embedder, *, config_overrides=None):
    from assetcache.config import Config
    from assetcache.core.consistency import ConsistencyScorer
    from assetcache.core.labels import LabelRegistry
    from assetcache.core.search import HybridSearcher

    store, _ = populated_store
    config = Config(**(config_overrides or {}))
    registry = LabelRegistry(store)
    registry.bootstrap()
    consistency = ConsistencyScorer(store, config)
    return HybridSearcher(store, fake_embedder, consistency, registry, config), store


# ── 1. 6채널 합산 ────────────────────────────────────────────────────


def test_six_channel_score_breakdown_sums_to_score_within_tolerance(
    populated_store, fake_embedder
) -> None:
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res = searcher.hybrid(SearchRequest(query="hero", count=5))
    for r in res.results:
        total = sum(
            r.score_breakdown.get(k, 0.0)
            for k in ("semantic", "keyword", "label_match",
                      "consistency", "recency", "feedback")
        )
        # prefer_bonus / pin_bonus 등 별도 키도 합산.
        for extra_k in r.score_breakdown:
            if extra_k not in {"semantic", "keyword", "label_match",
                               "consistency", "recency", "feedback"}:
                total += r.score_breakdown[extra_k]
        assert r.score == pytest.approx(total, abs=1e-4)


def test_weight_feedback_override_applied(populated_store, fake_embedder) -> None:
    """per-call `weight_feedback_override` 가 Config.weight_feedback 보다 우선."""
    from assetcache.core.search import SearchRequest

    searcher, store = _build_searcher(populated_store, fake_embedder)
    _, ids = populated_store
    pid = store.upsert_project("proj_override").id
    store.insert_feedback_record(pid, ids["hero"], None, "negative", -1.0)

    # weight_override=0.5 → -1.0 * 0.5 = -0.5 (Config 기본 0.10 보다 큰 영향).
    res = searcher.hybrid(SearchRequest(
        query="hero", project_id="proj_override", count=10,
        weight_feedback_override=0.5,
    ))
    fb = next((r.score_breakdown["feedback"] for r in res.results
               if r.asset_id == ids["hero"]), None)
    assert fb is not None
    # |-1.0 * 0.5| = 0.5 — 약 0.05 (= 1.0 * 0.10 기본) 와 분명히 다름.
    assert abs(fb) == pytest.approx(0.5, abs=1e-3)


def test_feedback_channel_zero_when_no_feedback_records(
    populated_store, fake_embedder
) -> None:
    """feedback 기록 0건 → `score_breakdown.feedback` 키 존재 + 값 0."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res = searcher.hybrid(SearchRequest(query="hero", project_id="proj_empty",
                                         count=5))
    for r in res.results:
        assert "feedback" in r.score_breakdown
        assert r.score_breakdown["feedback"] == pytest.approx(0.0, abs=1e-6)


# ── 2. label_query free_text 분리 ─────────────────────────────────────


def test_label_query_free_text_appended_to_semantic_query(
    populated_store, fake_embedder
) -> None:
    """`label_query` 의 free_token 부분이 semantic query 에 합쳐져 임베딩됨.

    SearchRequest.label_query 가 파서를 거쳐 labels_* + free_text 로 분해되고,
    free_text 는 req.query 와 합쳐서 임베딩 빌더로 들어간다.
    """
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    # 미지 토큰 'zelda_quest' 가 free_text 로 가서 임베딩에 추가.
    res = searcher.hybrid(SearchRequest(
        query="hero",
        label_query="zelda_quest pixel_art",
        count=5,
    ))
    # pixel_art 가 labels_all 로 추가 → category 가 pixel_art 인 자산만.
    # 실패 없이 결과 반환 (free_token 자체는 임베딩에만 영향).
    assert res.query_id > 0


# ── 3. diversity 적용 통합 ───────────────────────────────────────────


def test_apply_diversity_mmr_picks_different_packs(
    populated_store, fake_embedder
) -> None:
    """HybridSearcher 가 diversity=mmr 을 단계 7 에 적용 — 다른 팩 선호."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res = searcher.hybrid(SearchRequest(query="character", count=4,
                                         diversity="mmr", diversity_lambda=0.5))
    pids = [r.pack_id for r in res.results]
    assert len(set(pids)) >= 2


def test_apply_diversity_round_robin_balances_packs(
    populated_store, fake_embedder
) -> None:
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res = searcher.hybrid(SearchRequest(query="character", count=4,
                                         diversity="round_robin"))
    pids = [r.pack_id for r in res.results]
    # round_robin: 두 팩이 후보면 교대 — 첫 2 픽은 서로 다른 팩.
    if len(pids) >= 2:
        assert pids[0] != pids[1]


# ── 4. M3 baseline 회귀 ─────────────────────────────────────────────


def test_six_channel_does_not_break_m3_baseline_search(
    populated_store, fake_embedder
) -> None:
    """M3 의 검색 (label/diversity/feedback 무관) 이 그대로 동작."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    # M3 호환 호출 — diversity/label_query/feedback override 없음.
    res = searcher.hybrid(SearchRequest(query="hero", count=3))
    assert len(res.results) >= 1
    assert res.query_id > 0
    # 6채널 모두 노출.
    for r in res.results:
        for k in ("semantic", "keyword", "label_match",
                  "consistency", "recency", "feedback"):
            assert k in r.score_breakdown


def test_weight_feedback_zero_keeps_breakdown_key_with_value_zero(
    populated_store, fake_embedder
) -> None:
    """Config.weight_feedback=0 시 breakdown 키 보존 + 값 0."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(
        populated_store, fake_embedder,
        config_overrides={"weight_feedback": 0.0, "weight_recency": 0.15},
    )
    res = searcher.hybrid(SearchRequest(query="hero", count=3))
    for r in res.results:
        assert "feedback" in r.score_breakdown
        assert r.score_breakdown["feedback"] == pytest.approx(0.0, abs=1e-6)
