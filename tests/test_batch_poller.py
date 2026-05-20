"""Phase 4 — BatchPoller daemon thread lifecycle."""

import time
from unittest.mock import MagicMock

import pytest

from assetcache.core.batch.poller import BatchPoller


@pytest.fixture
def poller_factory():
    def make(*, poll_interval=0.05):
        store = MagicMock()
        store.list_active_batch_jobs.return_value = []
        chain_registry = MagicMock()
        analysis_queue = MagicMock()
        cfg = MagicMock()
        cfg.batch.poll_interval_seconds = poll_interval
        p = BatchPoller(
            store=store, chain_registry=chain_registry,
            analysis_queue=analysis_queue, cfg=cfg,
        )
        return p, store
    return make


def test_poller_starts_and_stops(poller_factory):
    p, store = poller_factory()
    p.start()
    assert p.is_alive()
    p.stop(timeout=1.0)
    assert not p.is_alive()


def test_poller_calls_list_active_at_boot(poller_factory):
    p, store = poller_factory()
    p.start()
    time.sleep(0.1)  # 부팅 sweep 가 동작할 시간
    p.stop(timeout=1.0)
    assert store.list_active_batch_jobs.call_count >= 1


def test_poller_polls_periodically(poller_factory):
    p, store = poller_factory(poll_interval=0.05)
    p.start()
    time.sleep(0.25)  # ~5 ticks
    p.stop(timeout=1.0)
    # boot + ~4 periodic = 5+
    assert store.list_active_batch_jobs.call_count >= 3


def test_poll_once_swallows_single_job_failure(poller_factory):
    p, store = poller_factory()
    job_a = MagicMock(id=1)
    job_b = MagicMock(id=2)
    store.list_active_batch_jobs.return_value = [job_a, job_b]
    poll_call_count = [0]
    def faulty_poll_job(job):
        poll_call_count[0] += 1
        if job.id == 1:
            raise RuntimeError("network error")
    p._poll_job = faulty_poll_job
    p._poll_once()
    # 둘 다 시도되어야
    assert poll_call_count[0] == 2


def test_is_daemon(poller_factory):
    p, _ = poller_factory()
    assert p.daemon is True


def test_poll_job_running_updates_state(poller_factory):
    import time
    from assetcache.core.batch.types import GeminiBatchStatus
    p, store = poller_factory()
    job = MagicMock(id=1, backend="gemini", backend_job_id="batches/x",
                    modality="chat_image", state="submitted",
                    expires_at=int(time.time()) + 172800)
    store.list_active_batch_jobs.return_value = [job]
    backend = MagicMock()
    backend.batch_get.return_value = GeminiBatchStatus(
        state="JOB_STATE_RUNNING", inlined_responses=None,
        file_name=None, error=None,
    )
    p._chain.get_backend.return_value = backend
    p._poll_once()
    store.update_batch_job_state.assert_called_with(1, state="running")


def test_poll_job_succeeded_calls_handle_succeeded(poller_factory, monkeypatch):
    import time
    from assetcache.core.batch.types import GeminiBatchStatus
    p, store = poller_factory()
    job = MagicMock(id=1, backend="gemini", backend_job_id="batches/x",
                    modality="chat_image", state="running",
                    expires_at=int(time.time()) + 172800)
    store.list_active_batch_jobs.return_value = [job]
    status = GeminiBatchStatus(
        state="JOB_STATE_SUCCEEDED", inlined_responses=[MagicMock()],
        file_name=None, error=None,
    )
    backend = MagicMock()
    backend.batch_get.return_value = status
    p._chain.get_backend.return_value = backend
    handle = MagicMock()
    monkeypatch.setattr(p, "_handle_succeeded", handle)
    p._poll_once()
    handle.assert_called_once_with(job, status, backend)


def test_poll_job_failed_terminal(poller_factory, monkeypatch):
    import time
    from assetcache.core.batch.types import GeminiBatchStatus
    p, store = poller_factory()
    job = MagicMock(id=1, backend="gemini", backend_job_id="batches/x",
                    modality="chat_image", state="running",
                    expires_at=int(time.time()) + 172800)
    store.list_active_batch_jobs.return_value = [job]
    status = GeminiBatchStatus(
        state="JOB_STATE_FAILED", inlined_responses=None,
        file_name=None, error="oops",
    )
    backend = MagicMock()
    backend.batch_get.return_value = status
    p._chain.get_backend.return_value = backend
    handle = MagicMock()
    monkeypatch.setattr(p, "_handle_terminal_failure", handle)
    p._poll_once()
    handle.assert_called_once_with(job, "failed", "oops")


def test_poll_job_past_expiry_marked_expired(poller_factory, monkeypatch):
    import time
    p, store = poller_factory()
    job = MagicMock(id=1, backend="gemini", backend_job_id="batches/x",
                    modality="chat_image", state="submitted",
                    expires_at=int(time.time()) - 10)  # 이미 만료
    store.list_active_batch_jobs.return_value = [job]
    handle = MagicMock()
    monkeypatch.setattr(p, "_handle_terminal_failure", handle)
    backend = MagicMock()
    p._chain.get_backend.return_value = backend
    p._poll_once()
    # safety net — backend.batch_get 호출 안 됨, 바로 terminal_failure('expired')
    backend.batch_get.assert_not_called()
    handle.assert_called_once()
    args = handle.call_args.args
    assert args[0] is job
    assert args[1] == "expired"


def test_poll_job_no_state_change_no_update(poller_factory):
    import time
    from assetcache.core.batch.types import GeminiBatchStatus
    p, store = poller_factory()
    # 이미 'running' 상태인데 다시 RUNNING — update 안 함
    job = MagicMock(id=1, backend="gemini", backend_job_id="batches/x",
                    modality="chat_image", state="running",
                    expires_at=int(time.time()) + 172800)
    store.list_active_batch_jobs.return_value = [job]
    backend = MagicMock()
    backend.batch_get.return_value = GeminiBatchStatus(
        state="JOB_STATE_RUNNING", inlined_responses=None,
        file_name=None, error=None,
    )
    p._chain.get_backend.return_value = backend
    p._poll_once()
    store.update_batch_job_state.assert_not_called()
