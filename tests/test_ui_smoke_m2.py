"""Smoke tests for M2 UI changes — translated strings + new columns."""
from __future__ import annotations

import pytest
pytest.skip("M5 Phase 5 가 폐기 예정 — main_window 제거", allow_module_level=True)

import json
import time

from gah.core.manifest import PackManifest


def _make_pack_with_analyzed_asset(store) -> int:
    from gah.core.store import LabelScore, SpriteMeta

    pack_id = store.upsert_pack(
        "p", PackManifest(None, None, None, None, None),
        scanned_at=int(time.time()),
    )
    asset_id = store.upsert_asset(
        pack_id, "a.png", "sprite", "h", 1,
        added_at=int(time.time()),
    )
    store.save_sprite_meta(
        asset_id, SpriteMeta(32, 32, True, True, ["#ff0000"])
    )
    store.save_asset_labels(asset_id, [
        LabelScore("style", "pixel_art", 0.9, "gemma", "primary"),
        LabelScore("mood", "heroic", 0.8, "gemma", "primary"),
    ])
    store.mark_asset_state(asset_id, "ok", analyzed_at=int(time.time()))
    return pack_id


def test_main_window_constructs_with_translated_strings(qapp, store) -> None:
    from gah.ui.main_window import MainWindow

    win = MainWindow(store)
    # 탭 위젯의 탭 라벨이 tr() 으로 라우트됨 — 탭이 최소 2개 존재
    assert win.tab_widget.count() >= 2
    win.close()


def test_library_view_renders_label_and_description_columns(qapp, store) -> None:
    from gah.ui.library_view import LibraryView

    _make_pack_with_analyzed_asset(store)
    view = LibraryView(store)
    view.refresh()
    headers = [
        view.table.horizontalHeaderItem(c).text()
        for c in range(view.table.columnCount())
    ]
    assert any("라벨" in h for h in headers)
    assert any("설명" in h for h in headers)
    view.close()


def test_pack_view_renders_aggregate_column(qapp, store) -> None:
    from gah.ui.pack_view import PackView

    pack_id = _make_pack_with_analyzed_asset(store)
    store.update_pack_aggregate(pack_id, json.dumps({
        "main_style": "pixel_art",
        "category_dist": {"character": 0.5},
    }))
    view = PackView(store)
    view.refresh()
    headers = [
        view.table.horizontalHeaderItem(c).text()
        for c in range(view.table.columnCount())
    ]
    assert any("집계" in h for h in headers)
    view.close()
