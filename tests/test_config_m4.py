"""M4 — Config 신규 필드 + 가중치 재배분.

M3 가 5채널 합 1.0 (semantic 0.40 / keyword 0.15 / label 0.20 / cons 0.20 /
recency 0.05) 였다. M4 는 6 채널로 확장하고 기본값 재배분:
    semantic 0.35 / keyword 0.10 / label 0.20 / cons 0.20 / recency 0.05 / feedback 0.10 = 1.00

추가로 다양성 / 피드백 페널티 / 윈도우 관련 필드 셋.
"""

from __future__ import annotations

import pytest


def test_weight_feedback_default_is_010():
    from gah.config import Config

    config = Config()
    assert config.weight_feedback == pytest.approx(0.10, abs=1e-9)


def test_six_channel_weights_sum_equals_one_within_tolerance():
    from gah.config import Config

    config = Config()
    total = (
        config.weight_semantic
        + config.weight_keyword
        + config.weight_label_match
        + config.weight_consistency
        + config.weight_recency
        + config.weight_feedback
    )
    assert total == pytest.approx(1.0, abs=1e-6)


def test_diversity_default_is_none():
    from gah.config import Config

    config = Config()
    assert config.diversity_default == "none"


def test_diversity_mmr_lambda_default_is_07():
    from gah.config import Config

    config = Config()
    assert config.diversity_mmr_lambda == pytest.approx(0.7, abs=1e-9)


def test_feedback_weights_have_expected_signs():
    """negative < 0, positive > 0, irrelevant < 0 — 부호 검증."""
    from gah.config import Config

    config = Config()
    assert config.feedback_negative_weight < 0
    assert config.feedback_positive_weight > 0
    assert config.feedback_irrelevant_weight < 0
    # pack-level 임계 (>=3 negative 자산) 와 페널티 (음수) 검증.
    assert config.feedback_pack_threshold >= 1
    assert config.feedback_pack_penalty < 0
    # 윈도우 (30일 기본) — 양수.
    assert config.feedback_window_seconds > 0


def test_toml_roundtrip_preserves_all_m4_fields(tmp_path):
    """save_config → load_config 로 모든 M4 필드가 보존되는지."""
    from gah.config import Config, load_config, save_config

    config = Config(
        weight_semantic=0.30,
        weight_keyword=0.10,
        weight_label_match=0.20,
        weight_consistency=0.20,
        weight_recency=0.10,
        weight_feedback=0.10,
        diversity_default="mmr",
        diversity_mmr_lambda=0.5,
        feedback_negative_weight=-0.7,
        feedback_positive_weight=0.4,
        feedback_irrelevant_weight=-0.2,
        feedback_pack_threshold=5,
        feedback_pack_penalty=-0.15,
        feedback_window_seconds=86_400,
    )
    target = tmp_path / "config.toml"
    save_config(config, target)
    loaded = load_config(target)
    assert loaded.weight_semantic == pytest.approx(0.30)
    assert loaded.weight_keyword == pytest.approx(0.10)
    assert loaded.weight_feedback == pytest.approx(0.10)
    assert loaded.diversity_default == "mmr"
    assert loaded.diversity_mmr_lambda == pytest.approx(0.5)
    assert loaded.feedback_negative_weight == pytest.approx(-0.7)
    assert loaded.feedback_positive_weight == pytest.approx(0.4)
    assert loaded.feedback_irrelevant_weight == pytest.approx(-0.2)
    assert loaded.feedback_pack_threshold == 5
    assert loaded.feedback_pack_penalty == pytest.approx(-0.15)
    assert loaded.feedback_window_seconds == 86_400
