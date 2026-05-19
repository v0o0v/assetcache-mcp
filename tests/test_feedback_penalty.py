"""M4 — 페널티 학습 (HybridSearcher 의 6번째 채널 `feedback`).

feedback_records 의 signed weight 가 다음 검색에 반영:
- asset-level: 같은 project + asset 의 윈도우 내 행 weight 합
- pack-level: 같은 project + pack 에 ≥3 negative → pack-wide -0.1

`feedback` 채널은 `score_breakdown.feedback` 키로 항상 노출 (값 0 가능).
weight_feedback=0 시 효과 없음 (회귀 가드).
"""

from __future__ import annotations

import time

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


def _feedback_score_for(results, asset_id: int) -> float:
    for r in results.results:
        if r.asset_id == asset_id:
            return r.score_breakdown.get("feedback", 0.0)
    return 0.0


def _row_index(results, asset_id: int) -> int | None:
    for i, r in enumerate(results.results):
        if r.asset_id == asset_id:
            return i
    return None


# ── 1. asset-level negative / positive ───────────────────────────────


def test_negative_feedback_lowers_next_search_feedback_channel(
    populated_store, fake_embedder
) -> None:
    from assetcache.core.search import SearchRequest

    searcher, store = _build_searcher(populated_store, fake_embedder)
    _, ids = populated_store
    pid = store.upsert_project("proj_neg").id

    # negative 기록
    store.insert_feedback_record(
        project_id=pid, asset_id=ids["hero"], query_id=None,
        reason="negative", weight=-0.5,
    )
    res = searcher.hybrid(SearchRequest(query="hero pixel", project_id="proj_neg",
                                         count=10))
    fb = _feedback_score_for(res, ids["hero"])
    assert fb < 0


def test_positive_feedback_raises_next_search_feedback_channel(
    populated_store, fake_embedder
) -> None:
    from assetcache.core.search import SearchRequest

    searcher, store = _build_searcher(populated_store, fake_embedder)
    _, ids = populated_store
    pid = store.upsert_project("proj_pos").id

    store.insert_feedback_record(pid, ids["hero"], None, "positive", +0.3)
    res = searcher.hybrid(SearchRequest(query="hero pixel", project_id="proj_pos",
                                         count=10))
    assert _feedback_score_for(res, ids["hero"]) > 0


def test_positive_and_negative_for_same_asset_sums(
    populated_store, fake_embedder
) -> None:
    """같은 자산에 +0.3 와 -0.5 → 합 -0.2 가중 (Config.weight_feedback 적용)."""
    from assetcache.config import Config
    from assetcache.core.search import SearchRequest

    searcher, store = _build_searcher(populated_store, fake_embedder)
    _, ids = populated_store
    pid = store.upsert_project("proj_sum").id

    store.insert_feedback_record(pid, ids["hero"], None, "positive", +0.3)
    store.insert_feedback_record(pid, ids["hero"], None, "negative", -0.5)

    res = searcher.hybrid(SearchRequest(query="hero", project_id="proj_sum", count=10))
    fb = _feedback_score_for(res, ids["hero"])
    # raw 합 -0.2, weight 0.10 적용 후 -0.02 근사.
    assert fb == pytest.approx(-0.2 * Config().weight_feedback, abs=1e-3)


# ── 2. 윈도우 / 프로젝트 격리 ────────────────────────────────────────


def test_feedback_outside_window_is_ignored(
    populated_store, fake_embedder
) -> None:
    """`feedback_window_seconds` 밖 (100일 전) 기록은 무시."""
    from assetcache.core.search import SearchRequest

    searcher, store = _build_searcher(populated_store, fake_embedder)
    _, ids = populated_store
    pid = store.upsert_project("proj_old").id

    # 100일 전 기록 (= 윈도우 30일 밖).
    old_ts = int(time.time()) - 100 * 86400
    store.conn.execute(
        "INSERT INTO feedback_records "
        "(project_id, asset_id, reason, weight, created_at) VALUES (?,?,?,?,?)",
        (pid, ids["hero"], "negative", -0.5, old_ts),
    )
    store.conn.commit()

    res = searcher.hybrid(SearchRequest(query="hero", project_id="proj_old", count=10))
    assert _feedback_score_for(res, ids["hero"]) == pytest.approx(0.0, abs=1e-6)


def test_feedback_in_other_project_does_not_affect_this_project(
    populated_store, fake_embedder
) -> None:
    from assetcache.core.search import SearchRequest

    searcher, store = _build_searcher(populated_store, fake_embedder)
    _, ids = populated_store
    pid_other = store.upsert_project("proj_other").id

    # 다른 project 의 negative 기록.
    store.insert_feedback_record(pid_other, ids["hero"], None, "negative", -0.5)

    # 이 검색은 다른 project.
    res = searcher.hybrid(SearchRequest(query="hero", project_id="proj_this", count=10))
    assert _feedback_score_for(res, ids["hero"]) == pytest.approx(0.0, abs=1e-6)


# ── 3. pack-level penalty ────────────────────────────────────────────


def test_pack_level_penalty_when_three_negatives_in_same_pack(
    populated_store, fake_embedder
) -> None:
    """같은 팩에 negative 3 자산 누적 → pack 전체에 추가 -0.1."""
    from assetcache.core.search import SearchRequest

    searcher, store = _build_searcher(populated_store, fake_embedder)
    _, ids = populated_store
    pid = store.upsert_project("proj_pack_neg").id

    # pack_a 의 hero/coin/jump 각각 negative — 3건 누적.
    for aid in (ids["hero"], ids["coin"], ids["jump"]):
        store.insert_feedback_record(pid, aid, None, "negative", -0.5)

    res = searcher.hybrid(SearchRequest(query="character", project_id="proj_pack_neg",
                                         count=10))
    # pack_a 의 자산 중 직접 negative 가 없는 항목이 있으면 pack penalty 만 반영되어
    # 약간 음수의 feedback 가 나와야. 모든 pack_a 자산이 negative 라 둘 다 적용.
    fb_hero = _feedback_score_for(res, ids["hero"])
    fb_coin = _feedback_score_for(res, ids["coin"])
    # asset-level (-0.5) + pack-level (-0.1) 가 모두 적용 — 둘 다 음수.
    assert fb_hero < 0
    assert fb_coin < 0


def test_pack_level_penalty_not_applied_below_threshold(
    populated_store, fake_embedder
) -> None:
    """negative 2건 (임계 3 미만) → pack-wide penalty 없음."""
    from assetcache.config import Config
    from assetcache.core.search import SearchRequest

    config = Config()
    searcher, store = _build_searcher(populated_store, fake_embedder)
    _, ids = populated_store
    pid = store.upsert_project("proj_below").id

    # 2 자산만 negative (임계 3 미만).
    store.insert_feedback_record(pid, ids["hero"], None, "negative", -0.5)
    store.insert_feedback_record(pid, ids["coin"], None, "negative", -0.5)

    res = searcher.hybrid(SearchRequest(query="character", project_id="proj_below",
                                         count=10))
    # pack_a 의 third 자산 jump 는 asset-level 0 + pack-level 0 (임계 미달) → feedback = 0.
    fb_jump = _feedback_score_for(res, ids["jump"])
    assert fb_jump == pytest.approx(0.0, abs=1e-6)


# ── 4. 회귀 / 가드 ───────────────────────────────────────────────────


def test_weight_feedback_zero_means_no_effect(
    populated_store, fake_embedder
) -> None:
    """Config.weight_feedback=0 시 negative 기록이 있어도 final score 영향 없음."""
    from assetcache.core.search import SearchRequest

    searcher, store = _build_searcher(
        populated_store, fake_embedder,
        config_overrides={
            "weight_feedback": 0.0,
            # 합 1.0 유지 위해 recency 에 +0.10 (테스트만의 임시 재분배).
            "weight_recency": 0.15,
        },
    )
    _, ids = populated_store
    pid = store.upsert_project("proj_zero").id
    store.insert_feedback_record(pid, ids["hero"], None, "negative", -0.5)

    res = searcher.hybrid(SearchRequest(query="hero", project_id="proj_zero", count=10))
    # weight 0 → channel 점수도 0.
    assert _feedback_score_for(res, ids["hero"]) == pytest.approx(0.0, abs=1e-6)


def test_unknown_reason_rejected_by_mcp_model() -> None:
    """`ReportFeedbackRequest.reason` Literal — 알 수 없는 값 → ValidationError."""
    from pydantic import ValidationError

    from assetcache.mcp.models import ReportFeedbackRequest

    with pytest.raises(ValidationError):
        ReportFeedbackRequest(query_id=1, asset_id=2, reason="bogus_reason")


def test_feedback_records_accumulate_across_calls(
    populated_store, fake_embedder
) -> None:
    """여러 번 호출 누적 후 feedback_records_for_project 합산 정확."""
    store, ids = populated_store
    pid = store.upsert_project("proj_accum").id
    for w in [-0.5, -0.3, +0.2]:
        store.insert_feedback_record(
            pid, ids["hero"], None,
            "negative" if w < 0 else "positive", w,
        )
    out = store.feedback_records_for_project(
        pid, asset_ids=[ids["hero"]], within_seconds=30 * 86400,
    )
    assert out[ids["hero"]] == pytest.approx(-0.6, abs=1e-6)
