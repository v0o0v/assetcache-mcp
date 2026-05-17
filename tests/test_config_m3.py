"""M3 — Config 신규 필드 (검색 가중치 + 통일성 임계 + MCP 옵션)."""

from __future__ import annotations

import pytest


def test_new_fields_have_documented_defaults():
    """M4 가 가중치 기본값을 재배분 (5채널 → 6채널) — 본 케이스도 6채널로 갱신.

    semantic 0.40 → 0.35, keyword 0.15 → 0.10, feedback 0.10 신규 (합 1.00 유지).
    """
    from gah.config import Config

    c = Config()
    assert c.weight_semantic == pytest.approx(0.35)
    assert c.weight_keyword == pytest.approx(0.10)
    assert c.weight_label_match == pytest.approx(0.20)
    assert c.weight_consistency == pytest.approx(0.20)
    assert c.weight_recency == pytest.approx(0.05)
    assert c.weight_feedback == pytest.approx(0.10)   # M4 신규
    assert c.consistency_locked_max_packs == 2
    assert c.consistency_locked_min_uses == 5
    assert c.palette_delta_e_threshold == pytest.approx(30.0)
    assert c.implicit_top1_enabled is False
    assert c.mcp_search_default_count == 5
    assert c.recency_window_seconds == 2_592_000


def test_weight_sum_equals_one_within_tolerance():
    """M4 6채널 합 = 1.0 (M3 5채널 단언을 갱신)."""
    from gah.config import Config

    c = Config()
    total = (
        c.weight_semantic + c.weight_keyword + c.weight_label_match
        + c.weight_consistency + c.weight_recency + c.weight_feedback
    )
    assert total == pytest.approx(1.0, abs=1e-6)


def test_implicit_top1_default_is_false():
    from gah.config import Config

    assert Config().implicit_top1_enabled is False


def test_consistency_locked_fields_are_positive_int():
    from gah.config import Config

    c = Config()
    assert isinstance(c.consistency_locked_max_packs, int)
    assert isinstance(c.consistency_locked_min_uses, int)
    assert c.consistency_locked_max_packs > 0
    assert c.consistency_locked_min_uses > 0


def test_mcp_search_default_count_in_range_1_to_50():
    from gah.config import Config

    c = Config()
    assert 1 <= c.mcp_search_default_count <= 50


def test_toml_roundtrip_preserves_new_fields(tmp_path):
    from gah.config import Config, load_config, save_config

    c = Config(
        weight_semantic=0.50, weight_keyword=0.10, weight_label_match=0.15,
        weight_consistency=0.20, weight_recency=0.05,
        consistency_locked_max_packs=3, consistency_locked_min_uses=10,
        implicit_top1_enabled=True, mcp_search_default_count=10,
    )
    path = tmp_path / "config.toml"
    save_config(c, path)
    reloaded = load_config(path)
    assert reloaded.weight_semantic == 0.50
    assert reloaded.consistency_locked_max_packs == 3
    assert reloaded.implicit_top1_enabled is True
    assert reloaded.mcp_search_default_count == 10
