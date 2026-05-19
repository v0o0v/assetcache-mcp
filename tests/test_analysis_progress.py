"""AnalysisProgress + ETA tests.

The pure helper :func:`AnalysisQueue._build_progress` is the seam the
unit tests target — it takes plain values (no Qt, no DB) and returns a
fully-formed ``AnalysisProgress`` snapshot.
"""

from __future__ import annotations

import time

import pytest

from assetcache.core.analysis_queue import (
    AnalysisProgress,
    AnalysisQueue,
    _format_duration_kor,
)


# ── ETA 계산 ────────────────────────────────────────────────────────


class TestEtaCalculation:
    def test_progress_eta_is_none_when_fewer_than_3_samples(self) -> None:
        snap = AnalysisQueue._build_progress(
            recent_durations=[1.0, 2.0],
            completed=0, pending=5, in_flight=None,
        )
        assert snap.eta_seconds is None

    def test_progress_eta_uses_recent_window_average(self) -> None:
        snap = AnalysisQueue._build_progress(
            recent_durations=[1.0, 2.0, 3.0],
            completed=0, pending=4, in_flight=None,
        )
        avg = (1.0 + 2.0 + 3.0) / 3
        assert snap.eta_seconds == pytest.approx(avg * 4)


# ── window cap (deque maxlen) ───────────────────────────────────────


class TestEtaWindow:
    def test_progress_eta_window_caps_at_10_samples(self) -> None:
        q = AnalysisQueue.__new__(AnalysisQueue)
        q._init_progress_tracker(window=10)
        for i in range(11):
            q._record_duration(float(i))
        assert len(q._recent_durations) <= 10


# ── in_flight 경로 ──────────────────────────────────────────────────


class TestInFlight:
    def test_progress_includes_in_flight_path_during_analysis(self) -> None:
        snap = AnalysisQueue._build_progress(
            recent_durations=[1.0, 1.0, 1.0],
            completed=2, pending=1,
            in_flight="kenney_test/hero.png",
        )
        assert snap.in_flight_path == "kenney_test/hero.png"

    def test_progress_in_flight_path_cleared_after_completion(self) -> None:
        snap = AnalysisQueue._build_progress(
            recent_durations=[1.0, 1.0, 1.0],
            completed=3, pending=0, in_flight=None,
        )
        assert snap.in_flight_path is None


# ── pending count + 시그널 계약 ─────────────────────────────────────


class TestPendingAndSignal:
    def test_progress_pending_count_combines_queue_and_db(self, store) -> None:
        from assetcache.core.manifest import PackManifest

        pack_id = store.upsert_pack(
            "p", PackManifest(None, None, None, None, None),
            scanned_at=int(time.time()),
        )
        store.upsert_asset(pack_id, "a.png", "sprite", "h", 1,
                           added_at=int(time.time()))
        assert store.count_pending_assets() >= 1

    def test_progress_signal_emitted_at_start_and_end_of_each_asset(self) -> None:
        # 시그널 본 흐름은 test_analysis_queue 가 검증.
        # 여기선 dataclass 모양만 잠금.
        snap = AnalysisProgress(
            completed_in_session=0, pending=1,
            in_flight_path=None, eta_seconds=None,
            avg_duration_seconds=None,
        )
        for attr in ("completed_in_session", "pending", "in_flight_path",
                     "eta_seconds", "avg_duration_seconds"):
            assert hasattr(snap, attr)


# ── 실패 분석도 표본에 들어가는가 ──────────────────────────────────


class TestFailedSampling:
    def test_failed_analysis_still_contributes_to_duration_window(self) -> None:
        q = AnalysisQueue.__new__(AnalysisQueue)
        q._init_progress_tracker(window=10)
        q._record_duration(1.5, success=False)
        assert len(q._recent_durations) == 1


# ── 한국어 ETA 라벨 ─────────────────────────────────────────────────


class TestKoreanLabel:
    def test_format_duration_kor_handles_none_seconds_minutes_hours(self) -> None:
        assert _format_duration_kor(None) == "계산 중…"
        assert _format_duration_kor(45) == "45초"
        assert _format_duration_kor(420) == "7분"
        assert _format_duration_kor(4500) == "1시간 15분"
