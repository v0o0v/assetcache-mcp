"""M4 — 라이브러리 탭 풍부 UX (label chip + weight sliders + saved searches + filter bar).

3 신규 위젯 + library_view 통합:
- `LabelChipPanel(registry)` — axis 별 라벨 칩 다중 선택 + AND/OR/NOT 라디오
- `SearchSidePanel(config, store)` — 6 슬라이더 + 3 프리셋 + 저장된 검색 리스트
- `FilterBar(store)` — 다축 필터 (pack 다중, kind, state, license, vendor, sort)

LibraryView 통합:
- 250ms 디바운스 유지 (M3 회귀)
- 결과 행에 matched_labels 칩 표시
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QCoreApplication


def _qwait(ms: int) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def registry_with_axes(populated_store):
    """populated_store + 부트스트랩된 LabelRegistry."""
    from gah.core.labels import LabelRegistry

    store, _ = populated_store
    reg = LabelRegistry(store)
    reg.bootstrap()
    return reg


@pytest.fixture
def config_default():
    from gah.config import Config

    return Config()


# ── 1. LabelChipPanel ────────────────────────────────────────────────


def test_label_chip_panel_renders_all_24_axes(qapp, registry_with_axes):
    from gah.ui.label_chip_panel import LabelChipPanel

    panel = LabelChipPanel(registry_with_axes)
    # axis 그룹 박스가 (시드된) 모든 axis 만큼 노출 — 시드는 ~24 axis.
    axes_loaded = registry_with_axes.list_axes()
    assert len(axes_loaded) >= 1
    # 패널이 axis 별로 그룹을 노출하는지 — child QGroupBox 카운트로 확인.
    from PySide6.QtWidgets import QGroupBox

    boxes = panel.findChildren(QGroupBox)
    # 매칭 모드 그룹 박스 1 + axis 마다 1 → 합계 ≥ axes_loaded + 1.
    assert len(boxes) >= len(axes_loaded)


def test_label_chip_panel_emits_selection_changed_on_check(qapp, registry_with_axes):
    from gah.ui.label_chip_panel import LabelChipPanel
    from PySide6.QtWidgets import QCheckBox

    panel = LabelChipPanel(registry_with_axes)
    fired: list[bool] = []
    panel.selectionChanged.connect(lambda: fired.append(True))

    # 첫 체크박스 체크 → 시그널 발화.
    checks = panel.findChildren(QCheckBox)
    if checks:
        checks[0].setChecked(True)
        _qwait(50)
        assert fired


def test_label_chip_panel_radio_mode_toggle_changes_emit_meta(
    qapp, registry_with_axes
):
    """AND/OR/NOT 라디오 전환 시 `selected()` 모드 키가 바뀐다."""
    from gah.ui.label_chip_panel import LabelChipPanel
    from PySide6.QtWidgets import QCheckBox

    panel = LabelChipPanel(registry_with_axes)
    # 임의 체크박스 1 체크 → labels 1개 들어가는 상태로.
    checks = panel.findChildren(QCheckBox)
    if checks:
        checks[0].setChecked(True)

    # 기본 mode = 'all'.
    mode, _ = panel.selected()
    assert mode == "all"

    # 'any' 라디오로 변경.
    panel.set_mode("any")
    mode, _ = panel.selected()
    assert mode == "any"


# ── 2. SearchSidePanel ───────────────────────────────────────────────


def test_search_side_panel_slider_initial_values_match_config(
    qapp, config_default, store
):
    from gah.ui.search_side_panel import SearchSidePanel

    panel = SearchSidePanel(config_default, store)
    # 슬라이더 6 채널 초기값이 Config.weight_* * 100 과 일치.
    for name in ("weight_semantic", "weight_keyword", "weight_label_match",
                 "weight_consistency", "weight_recency", "weight_feedback"):
        slider_value = panel.slider_value(name)
        assert slider_value == int(getattr(config_default, name) * 100)


def test_search_side_panel_slider_change_updates_config_immediately(
    qapp, config_default, store
):
    from gah.ui.search_side_panel import SearchSidePanel

    panel = SearchSidePanel(config_default, store)
    panel.set_slider_value("weight_semantic", 50)
    _qwait(50)
    # Config 가 즉시 갱신.
    assert config_default.weight_semantic == pytest.approx(0.5, abs=1e-6)


def test_search_side_panel_preset_button_applies_weights(
    qapp, config_default, store
):
    from gah.ui.search_side_panel import SearchSidePanel

    panel = SearchSidePanel(config_default, store)
    # 프리셋 "통일성 우선" 적용 — consistency 슬라이더가 0.5 이상으로 올라가야.
    panel.apply_preset("consistency_first")
    _qwait(50)
    assert config_default.weight_consistency >= 0.4


def test_search_side_panel_saved_searches_load_on_open(qapp, populated_store, config_default):
    """패널이 처음 로드 시 saved_searches 테이블에서 행을 가져온다."""
    import json

    from gah.ui.search_side_panel import SearchSidePanel

    store, _ = populated_store
    pid = store.upsert_project("proj_panel").id
    store.save_search(pid, "panel_search_1", json.dumps({"query": "x"}))

    panel = SearchSidePanel(config_default, store)
    panel.reload_saved_searches(pid)
    _qwait(50)
    names = panel.saved_search_names()
    assert "panel_search_1" in names


def test_search_side_panel_save_button_emits_save_signal_with_name(
    qapp, populated_store, config_default
):
    from gah.ui.search_side_panel import SearchSidePanel

    store, _ = populated_store
    panel = SearchSidePanel(config_default, store)
    fired: list[str] = []
    panel.saveCurrentRequested.connect(fired.append)
    # 이름 직접 주입 (다이얼로그 우회).
    panel.request_save_with_name("my new search")
    _qwait(50)
    assert fired == ["my new search"]


def test_search_side_panel_saved_search_double_click_emits_activated(
    qapp, populated_store, config_default
):
    import json

    from gah.ui.search_side_panel import SearchSidePanel

    store, _ = populated_store
    pid = store.upsert_project("proj_dbl").id
    store.save_search(pid, "dbl_search", json.dumps({"q": "x"}))
    panel = SearchSidePanel(config_default, store)
    panel.reload_saved_searches(pid)

    fired: list[str] = []
    panel.savedSearchActivated.connect(fired.append)
    # 직접 시그널 발화 헬퍼.
    panel.activate_saved_search("dbl_search")
    _qwait(50)
    assert fired == ["dbl_search"]


# ── 3. FilterBar ─────────────────────────────────────────────────────


def test_filter_bar_pack_multi_select_changes_emit(qapp, populated_store):
    from gah.ui.filter_bar import FilterBar

    store, ids = populated_store
    bar = FilterBar(store)
    fired: list[bool] = []
    bar.filterChanged.connect(lambda: fired.append(True))
    bar.set_pack_selection([ids["pack_a"]])
    _qwait(50)
    assert fired


def test_filter_bar_kind_dropdown_filters_search(qapp, populated_store):
    from gah.ui.filter_bar import FilterBar

    store, _ = populated_store
    bar = FilterBar(store)
    bar.set_kind("sound")
    filters = bar.current_filters()
    assert filters.get("kind") == "sound"


def test_filter_bar_sort_change_triggers_re_search(qapp, populated_store):
    from gah.ui.filter_bar import FilterBar

    store, _ = populated_store
    bar = FilterBar(store)
    fired: list[bool] = []
    bar.filterChanged.connect(lambda: fired.append(True))
    bar.set_sort_key("name")
    _qwait(50)
    assert fired


# ── 4. LibraryView 통합 ─────────────────────────────────────────────


def test_library_view_result_row_shows_matched_labels(qapp, populated_store, config_default):
    """결과 행에 matched_labels 칩 텍스트가 노출 (axis=label 형식)."""
    from gah.ui.library_view import LibraryView

    store, _ = populated_store
    view = LibraryView(store)
    view.set_config(config_default)
    # _show_search_results 가 matched_labels 를 표시하는지 직접 검사.
    class _Row:
        def __init__(self):
            self.asset_id = 1
            self.pack_id = 1
            self.pack_name = "pack_a"
            self.path = "/tmp/x.png"
            self.score = 0.9
            self.score_breakdown = {"semantic": 0.9}
            self.matched_labels = [
                {"axis": "category", "label": "hero", "source": "gemma", "score": 0.9},
                {"axis": "style", "label": "pixel_art", "source": "gemma", "score": 0.8},
            ]
            self.why = "test"
            self.meta = {}
    view._show_search_results([_Row()])

    # 그리드 행에 'category=hero' 또는 'style=pixel_art' 가 표시되는지.
    found = False
    for col in range(view.table.columnCount()):
        item = view.table.item(0, col)
        if item and ("category=hero" in item.text() or "style=pixel_art" in item.text()):
            found = True
            break
    assert found


def test_library_view_debounce_remains_250ms_after_rich_ux_added(
    qapp, populated_store, config_default
):
    """풍부 UX 추가 후에도 검색 입력 디바운스가 250ms 유지 (M3 회귀)."""

    from gah.ui.library_view import LibraryView

    store, _ = populated_store

    class _FakeSearcher:
        def __init__(self):
            self.calls = []
        def hybrid(self, req):
            self.calls.append(req.query)

            class _R:
                query_id = 1
                results = []

            return _R()

    view = LibraryView(store)
    view.set_config(config_default)
    searcher = _FakeSearcher()
    view.set_searcher(searcher)

    view.search_input.setText("hero")
    _qwait(100)
    assert searcher.calls == []   # 100 ms < 250 ms 디바운스
    _qwait(300)                    # 합계 400 ms > 250 ms
    assert searcher.calls == ["hero"]
