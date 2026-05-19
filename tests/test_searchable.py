"""Tests for the searchable-text builder (FTS5 vs embedding split)."""

from __future__ import annotations

from assetcache.core.searchable import build_searchable
from assetcache.core.store import LabelScore, SpriteMeta


def _sample_inputs():
    sprite_meta = SpriteMeta(
        width=32, height=32, has_alpha=True, is_pixel_art=True,
        dominant_colors=["#ff0000", "#00ff00"],
    )
    labels = [
        LabelScore("category", "character", 0.95, "gemma", "primary"),
        LabelScore("style", "pixel_art", 0.92, "gemma", "primary"),
        LabelScore("style", "pixel_art", 0.88, "clip", None),
        LabelScore("mood", "heroic", 0.80, "gemma", "primary"),
        LabelScore("mood", "serious", 0.40, "gemma", "secondary"),
        LabelScore("color", "red_palette", 0.30, "clip", None),
    ]
    label_descs = {
        ("category", "character"): "Animate or anthropomorphic entity.",
        ("style", "pixel_art"):
            "Low-resolution sprite art with visible square pixels.",
        ("mood", "heroic"): "Bold, courageous, larger-than-life energy.",
        ("mood", "serious"): "Sober, grounded, without humor.",
        ("color", "red_palette"): "Red is the dominant hue.",
    }
    description = "검을 든 중세 기사 캐릭터의 측면 도트 스프라이트"
    return sprite_meta, labels, label_descs, description


def test_for_fts_includes_label_prefixed_tokens() -> None:
    sm, labels, descs, desc = _sample_inputs()
    out = build_searchable(
        meta=sm, labels=labels, label_descriptions=descs,
        description=desc, rel_path="kenney_hero/idle_03.png",
    )
    assert "label:pixel_art" in out.for_fts
    assert "label:heroic" in out.for_fts
    assert "label:character" in out.for_fts


def test_for_fts_includes_axis_prefixed_tokens() -> None:
    sm, labels, descs, desc = _sample_inputs()
    out = build_searchable(
        meta=sm, labels=labels, label_descriptions=descs,
        description=desc, rel_path="kenney_hero/idle_03.png",
    )
    assert "category:character" in out.for_fts
    assert "style:pixel_art" in out.for_fts
    assert "mood:heroic" in out.for_fts


def test_for_fts_includes_label_descriptions_in_quotes() -> None:
    sm, labels, descs, desc = _sample_inputs()
    out = build_searchable(
        meta=sm, labels=labels, label_descriptions=descs,
        description=desc, rel_path="kenney_hero/idle_03.png",
    )
    # 라벨 description 자연어가 BM25 매칭에 사용됨
    assert "Low-resolution sprite art" in out.for_fts


def test_for_fts_includes_path_and_size_meta() -> None:
    sm, labels, descs, desc = _sample_inputs()
    out = build_searchable(
        meta=sm, labels=labels, label_descriptions=descs,
        description=desc, rel_path="kenney_hero/idle_03.png",
    )
    assert "kenney_hero" in out.for_fts
    assert "32" in out.for_fts  # width/height surfaced


def test_for_embed_truncates_to_short_summary() -> None:
    sm, labels, descs, desc = _sample_inputs()
    out = build_searchable(
        meta=sm, labels=labels, label_descriptions=descs,
        description=desc, rel_path="kenney_hero/idle_03.png",
    )
    assert len(out.for_embed.split()) <= 256


def test_for_embed_uses_top_n_labels_by_score() -> None:
    sm, labels, descs, desc = _sample_inputs()
    out = build_searchable(
        meta=sm, labels=labels, label_descriptions=descs,
        description=desc, rel_path="kenney_hero/idle_03.png",
    )
    # 점수 상위 라벨이 임베딩 텍스트에 등장
    assert "character" in out.for_embed
    assert "pixel_art" in out.for_embed
    assert "heroic" in out.for_embed


def test_for_embed_includes_asset_description() -> None:
    sm, labels, descs, desc = _sample_inputs()
    out = build_searchable(
        meta=sm, labels=labels, label_descriptions=descs,
        description=desc, rel_path="kenney_hero/idle_03.png",
    )
    assert "기사" in out.for_embed or "중세" in out.for_embed


def test_for_embed_excludes_path_and_low_score_labels() -> None:
    sm, labels, descs, desc = _sample_inputs()
    out = build_searchable(
        meta=sm, labels=labels, label_descriptions=descs,
        description=desc, rel_path="kenney_hero/idle_03.png",
    )
    # 경로 토큰은 임베딩 의미 압축에 노이즈라 제외
    assert "kenney_hero/idle_03.png" not in out.for_embed
    # 매우 낮은 점수 라벨도 제외 (top-N=5)
    assert "red_palette" not in out.for_embed


def test_for_fts_and_for_embed_are_distinct_strings() -> None:
    sm, labels, descs, desc = _sample_inputs()
    out = build_searchable(
        meta=sm, labels=labels, label_descriptions=descs,
        description=desc, rel_path="kenney_hero/idle_03.png",
    )
    assert out.for_fts != out.for_embed
