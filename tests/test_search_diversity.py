"""M4 — `SearchRequest.diversity` 옵션 (none / mmr / round_robin).

- `none` (M3 호환 default) — pure top-N
- `mmr` — `mmr_i = λ·score_i - (1-λ)·max_sim_to_picked`, sim = 1 if same_pack else 0
- `round_robin` — 팩별 큐 → 라운드 교대

다양성은 순위만 영향 — `score_breakdown` 의 채널 점수는 변경 없음.

`populated_store` 가 pack_a(hero/coin/jump) + pack_b(menu_bg/button/bgm_loop) 6 자산
시드 — 검색 결과가 두 팩에서 고르게 나올 케이스 검증에 적합.
"""

from __future__ import annotations

import pytest


# ── 헬퍼 ─────────────────────────────────────────────────────────────


def _build_searcher(populated_store, fake_embedder, *, config_overrides=None):
    """HybridSearcher 인스턴스 빌드 (분석 외부 의존 없이 deterministic fake 사용)."""
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


def _pack_ids_of(results) -> list[int]:
    return [r.pack_id for r in results.results]


# ── 1. diversity=none — M3 동작 그대로 ─────────────────────────────


def test_diversity_none_preserves_m3_order(populated_store, fake_embedder) -> None:
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res_none = searcher.hybrid(SearchRequest(query="hero sprite", count=5,
                                             diversity="none"))
    # M3 default 와 같아야 한다 (diversity 인자 기본값 "none" 가정).
    res_default = searcher.hybrid(SearchRequest(query="hero sprite", count=5))
    assert [r.asset_id for r in res_none.results] == [r.asset_id for r in res_default.results]


# ── 2. mmr 동작 ──────────────────────────────────────────────────────


def test_mmr_lambda_1_equals_pure_score_order(populated_store, fake_embedder) -> None:
    """λ=1.0 → 다양성 0 → score 순서 그대로 (none 과 동일)."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res_none = searcher.hybrid(SearchRequest(query="hero", count=4, diversity="none"))
    res_mmr1 = searcher.hybrid(SearchRequest(query="hero", count=4,
                                              diversity="mmr", diversity_lambda=1.0))
    assert [r.asset_id for r in res_none.results] == [r.asset_id for r in res_mmr1.results]


def test_mmr_lambda_0_forces_different_packs(populated_store, fake_embedder) -> None:
    """λ=0.0 → 다양성만 → 가능하면 매 픽이 새 팩이어야 한다."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res = searcher.hybrid(SearchRequest(query="hero", count=4,
                                         diversity="mmr", diversity_lambda=0.0))
    pids = _pack_ids_of(res)
    # 팩이 2개 있는 시드. 처음 2 픽은 서로 다른 팩이어야.
    if len(pids) >= 2:
        assert pids[0] != pids[1]


def test_mmr_lambda_07_balances_score_and_diversity(
    populated_store, fake_embedder
) -> None:
    """λ=0.7 → 상위 4 결과가 두 팩에서 모두 등장하는지."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res = searcher.hybrid(SearchRequest(query="character", count=4,
                                         diversity="mmr", diversity_lambda=0.7))
    pids = set(_pack_ids_of(res))
    # 후보가 양쪽 팩에 분포 → mmr 가 둘 다 끌어와야.
    assert len(pids) >= 2


# ── 3. round_robin 동작 ──────────────────────────────────────────────


def test_round_robin_alternates_packs(populated_store, fake_embedder) -> None:
    """round_robin 4 결과 — pack_a, pack_b, pack_a, pack_b 같은 교대 패턴."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res = searcher.hybrid(SearchRequest(query="background ui", count=4,
                                         diversity="round_robin"))
    pids = _pack_ids_of(res)
    if len(pids) >= 4:
        # 첫 2 픽 서로 다른 팩 + 마지막 2 픽도 첫 2 픽과 다름 (교대).
        assert pids[0] != pids[1]
        # 교대 패턴 (a, b, a, b 또는 b, a, b, a) — 짝수/홀수 인덱스 색 동일.
        assert pids[0] == pids[2]
        assert pids[1] == pids[3]


def test_round_robin_single_pack_falls_back_to_score(
    populated_store, fake_embedder
) -> None:
    """후보가 한 팩에 몰려 있으면 round_robin 도 score 순서로 폴백."""
    from assetcache.core.search import SearchRequest

    searcher, store = _build_searcher(populated_store, fake_embedder)
    # force_pack_id 로 pack_a 만 스코프 — 후보 단일 팩.
    pack_a = store.get_pack_by_name("pack_a").id
    res = searcher.hybrid(SearchRequest(query="hero", count=3,
                                         diversity="round_robin",
                                         force_pack_id=pack_a))
    pids = _pack_ids_of(res)
    # 모두 같은 팩 (pack_a) — 폴백 정상.
    assert all(p == pack_a for p in pids)


# ── 4. 경계 케이스 ───────────────────────────────────────────────────


def test_candidates_below_count_returns_all_regardless_of_diversity(
    populated_store, fake_embedder
) -> None:
    """후보 <= count 시 diversity 무관하게 모두 반환."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    # count=100 — 후보 6 자산 전부 통과.
    res_n = searcher.hybrid(SearchRequest(query="hero", count=100, diversity="none"))
    res_m = searcher.hybrid(SearchRequest(query="hero", count=100,
                                           diversity="mmr", diversity_lambda=0.5))
    res_r = searcher.hybrid(SearchRequest(query="hero", count=100,
                                           diversity="round_robin"))
    assert {r.asset_id for r in res_n.results} == {r.asset_id for r in res_m.results}
    assert {r.asset_id for r in res_n.results} == {r.asset_id for r in res_r.results}


def test_mmr_does_not_alter_score_breakdown(populated_store, fake_embedder) -> None:
    """다양성은 순위만 — `score_breakdown` 채널 값은 변경 없음."""
    from assetcache.core.search import SearchRequest

    searcher, _ = _build_searcher(populated_store, fake_embedder)
    res_none = searcher.hybrid(SearchRequest(query="hero", count=4, diversity="none"))
    res_mmr = searcher.hybrid(SearchRequest(query="hero", count=4,
                                             diversity="mmr", diversity_lambda=0.5))
    # 같은 자산이 양쪽 결과에 등장하면 그 자산의 score_breakdown 은 동일.
    breakdown_none = {r.asset_id: r.score_breakdown for r in res_none.results}
    breakdown_mmr = {r.asset_id: r.score_breakdown for r in res_mmr.results}
    common = set(breakdown_none) & set(breakdown_mmr)
    assert common  # 적어도 1 자산 공통
    for aid in common:
        for key in ("semantic", "keyword", "label_match", "consistency", "recency"):
            assert breakdown_none[aid][key] == pytest.approx(
                breakdown_mmr[aid][key], abs=1e-6,
            )


def test_diversity_lambda_none_uses_config_default(
    populated_store, fake_embedder
) -> None:
    """`diversity_lambda=None` 시 Config.diversity_mmr_lambda 적용."""
    from assetcache.core.search import SearchRequest

    searcher_a, _ = _build_searcher(populated_store, fake_embedder,
                                     config_overrides={"diversity_mmr_lambda": 1.0})
    res_a = searcher_a.hybrid(SearchRequest(query="hero", count=3,
                                             diversity="mmr",
                                             diversity_lambda=None))
    # diversity_lambda=None + Config.diversity_mmr_lambda=1.0 → λ=1.0 효과 (다양성 0).
    res_explicit = searcher_a.hybrid(SearchRequest(query="hero", count=3,
                                                     diversity="mmr",
                                                     diversity_lambda=1.0))
    assert [r.asset_id for r in res_a.results] == [r.asset_id for r in res_explicit.results]
