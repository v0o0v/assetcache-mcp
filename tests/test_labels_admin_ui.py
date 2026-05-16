"""Labels admin dialog tests (offscreen Qt).

The dialog wraps :class:`LabelRegistry` and writes user actions back to
the DB.  Cosmetic strings flow through ``tr()`` and therefore aren't
asserted verbatim; structural shape (axis combo, column count, helper
APIs) is what we lock down here.
"""

from __future__ import annotations

import pytest

from gah.core.labels import LabelRegistry
from gah.core.store import Store


@pytest.fixture
def registry(store: Store) -> LabelRegistry:
    r = LabelRegistry(store)
    r.bootstrap()
    return r


def test_dialog_lists_seed_axes(qapp, registry: LabelRegistry) -> None:
    from gah.ui.labels_admin import LabelsAdminDialog

    dlg = LabelsAdminDialog(registry)
    axes = [dlg.axis_combo.itemText(i) for i in range(dlg.axis_combo.count())]
    assert "style" in axes
    assert "sound_voice_type" in axes
    dlg.close()


def test_table_shows_labels_with_source_and_state_and_description_columns(
    qapp, registry: LabelRegistry,
) -> None:
    from gah.ui.labels_admin import LabelsAdminDialog

    dlg = LabelsAdminDialog(registry)
    dlg.select_axis("style")
    # 컬럼 4개 이상 — 라벨/상태/출처/설명
    assert dlg.table.columnCount() >= 4
    dlg.close()


def test_add_label_input_writes_to_registry(qapp, registry: LabelRegistry) -> None:
    from gah.ui.labels_admin import LabelsAdminDialog

    dlg = LabelsAdminDialog(registry)
    dlg.select_axis("style")
    dlg.add_label_input.setText("custom_test_label")
    dlg.add_button.click()
    assert "custom_test_label" in registry.list_labels(axis="style")
    dlg.close()


def test_invalid_token_input_shows_inline_error_and_does_not_call_registry(
    qapp, registry: LabelRegistry,
) -> None:
    from gah.ui.labels_admin import LabelsAdminDialog

    dlg = LabelsAdminDialog(registry)
    dlg.select_axis("style")
    before = set(registry.list_labels(axis="style"))
    dlg.add_label_input.setText("Bad Token!")
    dlg.add_button.click()
    after = set(registry.list_labels(axis="style"))
    assert before == after
    assert dlg.error_label.text() != ""
    dlg.close()


def test_toggle_enable_writes_to_registry_and_refreshes_table(
    qapp, registry: LabelRegistry,
) -> None:
    from gah.ui.labels_admin import LabelsAdminDialog

    dlg = LabelsAdminDialog(registry)
    dlg.select_axis("style")
    dlg.toggle_enabled_for("pixel_art", False)
    assert "pixel_art" not in registry.list_labels(axis="style")
    dlg.close()


def test_edit_description_inline_writes_to_registry(
    qapp, registry: LabelRegistry,
) -> None:
    from gah.ui.labels_admin import LabelsAdminDialog

    dlg = LabelsAdminDialog(registry)
    dlg.select_axis("style")
    dlg.edit_description_for("pixel_art", "Updated description")
    rows = registry.list_labels(axis="style", with_description=True)
    target = next(r for r in rows if r.label == "pixel_art")
    assert target.description == "Updated description"
    dlg.close()


def test_user_label_with_empty_description_shows_warning_icon(
    qapp, registry: LabelRegistry,
) -> None:
    from gah.ui.labels_admin import LabelsAdminDialog

    registry.add_label("style", "no_desc_label")
    dlg = LabelsAdminDialog(registry)
    dlg.select_axis("style")
    assert dlg.row_has_warning("no_desc_label") is True
    dlg.close()
