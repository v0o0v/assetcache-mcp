"""Seed vocabulary + LabelRegistry tests.

The registry layers an in-memory cache on top of the ``labels`` SQLite
table and is the single source of truth for label vocabulary used by
analyzers, the CLIP labeler, and the future M3 search backend.
"""

from __future__ import annotations

import pytest

from gah.core.labels import SEED_LABELS, LabelRegistry, LabelValidationError
from gah.core.store import Store


EXPECTED_AXES = {
    # 시각 14축
    "category", "style", "mood", "palette", "color", "view",
    "material", "lighting", "time_of_day", "weather", "theme",
    "size_hint", "domain", "animation",
    # 사운드 10축
    "sound_category", "sound_mood", "sound_timbre", "sound_environment",
    "sound_instrument", "sound_tempo", "sound_intensity", "sound_use",
    "sound_genre", "sound_voice_type",
}

# DESIGN.md §4.2.2 의 9개 시트 라벨 — animation 축이 이들을 포함해야 함
DESIGN_ANIMATION_TOKENS = {
    "idle", "walk", "run", "attack", "hurt", "death",
    "jump", "cast", "other",
}


# ── 시드 데이터 자체의 무결성 ────────────────────────────────────────


class TestSeed:
    def test_seed_has_expected_axes(self) -> None:
        assert set(SEED_LABELS.keys()) == EXPECTED_AXES

    def test_seed_no_duplicates_within_axis(self) -> None:
        for axis, items in SEED_LABELS.items():
            labels = [token for token, _desc in items]
            assert len(labels) == len(set(labels)), f"duplicate in {axis}"

    def test_total_seed_count_in_range_290_to_340(self) -> None:
        total = sum(len(v) for v in SEED_LABELS.values())
        assert 290 <= total <= 340, f"total seed count {total} out of range"

    def test_seed_animation_axis_matches_design_doc(self) -> None:
        animation = {token for token, _desc in SEED_LABELS["animation"]}
        assert DESIGN_ANIMATION_TOKENS.issubset(animation)


# ── bootstrap ────────────────────────────────────────────────────────


class TestBootstrap:
    def test_bootstrap_inserts_seed_on_empty_db_then_noop_on_second_call(
        self, store: Store
    ) -> None:
        registry = LabelRegistry(store)
        first = registry.bootstrap()
        assert first > 0
        second = registry.bootstrap()
        assert second == 0

    def test_bootstrap_includes_description_for_every_seed_label(
        self, store: Store
    ) -> None:
        LabelRegistry(store).bootstrap()
        empty = store.conn.execute(
            "SELECT COUNT(*) FROM labels"
            " WHERE source='seed' AND (description IS NULL OR description='')"
        ).fetchone()[0]
        assert empty == 0


# ── list_labels ──────────────────────────────────────────────────────


class TestListLabels:
    def test_list_labels_returns_only_enabled_by_default(self, store: Store) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        registry.set_enabled("style", "pixel_art", False)
        visible = registry.list_labels(axis="style")
        assert "pixel_art" not in visible

    def test_list_labels_returns_stable_sorted_order(self, store: Store) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        labels = registry.list_labels(axis="style")
        assert labels == sorted(labels)

    def test_list_labels_with_description_true_returns_descriptions(
        self, store: Store
    ) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        rows = registry.list_labels(axis="style", with_description=True)
        assert rows, "expected at least one style label"
        assert all(hasattr(r, "description") for r in rows)
        assert all(r.description for r in rows)

    def test_list_labels_with_description_false_omits_descriptions(
        self, store: Store
    ) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        rows = registry.list_labels(axis="style", with_description=False)
        # plain string labels when description not requested
        assert all(isinstance(r, str) for r in rows)


# ── add_label / set_description / set_enabled ───────────────────────


class TestAddLabel:
    @pytest.mark.parametrize(
        "bad",
        ["Pixel Art", "한글", "with space", "UPPER",
         "1starts_with_digit", "a" * 64],
    )
    def test_add_label_rejects_invalid_token(self, store: Store, bad: str) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        with pytest.raises(LabelValidationError):
            registry.add_label("style", bad)

    def test_add_label_accepts_valid_user_token_with_source_user_and_null_description(
        self, store: Store
    ) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        id_, was_new = registry.add_label("style", "custom_token")
        assert was_new is True
        row = store.conn.execute(
            "SELECT source, description FROM labels WHERE id=?", (id_,)
        ).fetchone()
        assert row[0] == "user"
        assert row[1] is None

    def test_add_label_with_description_persists_string(self, store: Store) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        id_, _ = registry.add_label("style", "shiny", description="Glossy surfaces")
        row = store.conn.execute(
            "SELECT description FROM labels WHERE id=?", (id_,)
        ).fetchone()
        assert row[0] == "Glossy surfaces"

    def test_set_label_description_updates_row_and_updated_at(
        self, store: Store
    ) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        before = store.conn.execute(
            "SELECT updated_at FROM labels WHERE axis='style' AND label='pixel_art'"
        ).fetchone()
        registry.set_description("style", "pixel_art", "Updated description text")
        after = store.conn.execute(
            "SELECT description, updated_at FROM labels"
            " WHERE axis='style' AND label='pixel_art'"
        ).fetchone()
        assert after[0] == "Updated description text"
        assert after[1] >= before[0]

    def test_add_label_existing_pair_returns_was_new_false_and_activates(
        self, store: Store
    ) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        registry.set_enabled("style", "pixel_art", False)
        id_, was_new = registry.add_label("style", "pixel_art")
        assert was_new is False
        row = store.conn.execute(
            "SELECT enabled FROM labels WHERE id=?", (id_,)
        ).fetchone()
        assert row[0] == 1

    def test_set_enabled_false_excludes_from_list_labels_default(
        self, store: Store
    ) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        registry.set_enabled("mood", "heroic", False)
        visible = registry.list_labels(axis="mood")
        assert "heroic" not in visible


# ── 캐시 ─────────────────────────────────────────────────────────────


class TestCacheBehavior:
    def test_invalidate_clears_in_memory_cache(self, store: Store) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        first = registry.list_labels(axis="style")
        # 캐시 우회 — DB 만 변경하고 registry 는 모르게
        store.conn.execute(
            "UPDATE labels SET enabled=0 WHERE axis='style' AND label='pixel_art'"
        )
        stale = registry.list_labels(axis="style")
        assert stale == first  # 캐시가 stale 한 채로 응답
        registry.invalidate()
        fresh = registry.list_labels(axis="style")
        assert "pixel_art" not in fresh


# ── catalog signature ───────────────────────────────────────────────


class TestCatalogSignature:
    def test_label_catalog_signature_changes_on_add_disable_describe(
        self, store: Store
    ) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        sig0 = registry.label_catalog_signature()
        registry.add_label("style", "novel_token")
        sig1 = registry.label_catalog_signature()
        registry.set_enabled("style", "novel_token", False)
        sig2 = registry.label_catalog_signature()
        registry.set_description("style", "pixel_art", "New description")
        sig3 = registry.label_catalog_signature()
        assert len({sig0, sig1, sig2, sig3}) == 4

    def test_label_catalog_signature_stable_when_no_changes(
        self, store: Store
    ) -> None:
        registry = LabelRegistry(store)
        registry.bootstrap()
        sig1 = registry.label_catalog_signature()
        sig2 = registry.label_catalog_signature()
        assert sig1 == sig2
