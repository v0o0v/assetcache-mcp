"""Status bar widget that surfaces analysis progress in the main window."""
from __future__ import annotations

import pytest
pytest.skip("M5 Phase 5 가 폐기 예정 — main_window 제거", allow_module_level=True)


def test_statusbar_initially_shows_idle_label(qapp, store) -> None:
    from gah.ui.main_window import MainWindow

    win = MainWindow(store)
    text = win.progress_label.text()
    # 대기 상태 — 빈 텍스트이거나 "대기 중" 등의 표시
    assert "대기" in text or text == ""
    win.close()


def test_statusbar_updates_on_progress_signal(qapp, store) -> None:
    from gah.core.analysis_queue import AnalysisProgress
    from gah.ui.main_window import MainWindow

    win = MainWindow(store)
    snap = AnalysisProgress(
        completed_in_session=3, pending=7,
        in_flight_path="kenney_test/hero.png",
        eta_seconds=60.0, avg_duration_seconds=6.0,
    )
    win.update_progress(snap)
    text = win.progress_label.text()
    assert "3" in text and "10" in text  # 3/(3+7)
    assert "hero.png" in text
    win.close()


def test_statusbar_shows_completed_then_idle_after_queue_drains(qapp, store) -> None:
    from gah.core.analysis_queue import AnalysisProgress
    from gah.ui.main_window import MainWindow

    win = MainWindow(store)
    snap = AnalysisProgress(
        completed_in_session=5, pending=0,
        in_flight_path=None,
        eta_seconds=0.0, avg_duration_seconds=6.0,
    )
    win.update_progress(snap)
    assert "완료" in win.progress_label.text()
    win.close()


def test_tray_tooltip_reflects_current_progress(qapp) -> None:
    from gah.core.analysis_queue import AnalysisProgress
    from gah.tray import make_tray_icon, update_tray_tooltip

    tray = make_tray_icon(qapp, on_open_main=lambda: None)
    snap = AnalysisProgress(
        completed_in_session=2, pending=3,
        in_flight_path=None,
        eta_seconds=30.0, avg_duration_seconds=10.0,
    )
    update_tray_tooltip(tray, snap)
    tip = tray.toolTip()
    assert "2" in tip and "5" in tip  # 2/(2+3)
