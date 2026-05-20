"""Phase 1 — batch_jobs table + assets.batch_job_id/batch_state 컬럼 마이그레이션."""

import sqlite3

import pytest

from assetcache.core.store import Store


@pytest.fixture
def fresh_store(tmp_path):
    db = tmp_path / "test.db"
    store = Store(str(db))
    store.initialize()
    return store


def test_batch_jobs_table_created(fresh_store):
    with sqlite3.connect(str(fresh_store.db_path)) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='batch_jobs'"
        ).fetchone()
        assert row is not None


def test_batch_jobs_columns(fresh_store):
    with sqlite3.connect(str(fresh_store.db_path)) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(batch_jobs)").fetchall()]
    expected = {
        "id", "backend", "modality", "backend_job_id", "asset_count",
        "submitted_at", "expires_at", "state", "completed_at",
        "success_count", "failure_count", "error", "display_name",
    }
    assert expected.issubset(set(cols))


def test_assets_batch_columns_added(fresh_store):
    with sqlite3.connect(str(fresh_store.db_path)) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(assets)").fetchall()}
    assert "batch_job_id" in cols
    assert "batch_state" in cols


def test_assets_batch_state_default_none(fresh_store):
    with sqlite3.connect(str(fresh_store.db_path)) as conn:
        conn.execute(
            "INSERT INTO packs (name, enabled, added_at) VALUES ('p', 1, 0)"
        )
        pack_id = conn.execute("SELECT id FROM packs").fetchone()[0]
        conn.execute(
            "INSERT INTO assets (pack_id, path, kind, file_hash, file_size, added_at, analysis_state) "
            "VALUES (?, 'a.png', 'sprite', 'h', 1, 0, 'pending')",
            (pack_id,),
        )
        row = conn.execute(
            "SELECT batch_state, batch_job_id FROM assets WHERE path='a.png'"
        ).fetchone()
        assert row == ("none", None)


def test_indexes_present(fresh_store):
    with sqlite3.connect(str(fresh_store.db_path)) as conn:
        idx = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
    assert "idx_batch_jobs_state" in idx
    assert "idx_assets_batch_state" in idx
    assert "idx_batch_jobs_backend_job_id" in idx


def test_initialize_idempotent(fresh_store):
    fresh_store.initialize()
    fresh_store.initialize()
    with sqlite3.connect(str(fresh_store.db_path)) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='batch_jobs'"
        ).fetchone()[0]
    assert count == 1


# ── Task 1.2: batch_jobs CRUD ──────────────────────────────────────────


def test_save_batch_job_returns_id(fresh_store):
    job_id = fresh_store.save_batch_job(
        backend="gemini",
        modality="chat_image",
        backend_job_id="batches/abc",
        asset_count=30,
        submitted_at=1000,
        expires_at=1000 + 172800,
        display_name="test-job",
    )
    assert isinstance(job_id, int) and job_id > 0


def test_get_batch_job_roundtrip(fresh_store):
    job_id = fresh_store.save_batch_job(
        backend="gemini", modality="chat_image",
        backend_job_id="batches/xyz", asset_count=10,
        submitted_at=2000, expires_at=2000 + 172800,
        display_name="d",
    )
    row = fresh_store.get_batch_job(job_id)
    assert row.backend == "gemini"
    assert row.modality == "chat_image"
    assert row.backend_job_id == "batches/xyz"
    assert row.state == "submitted"
    assert row.asset_count == 10
    assert row.success_count == 0
    assert row.failure_count == 0
    assert row.error is None
    assert row.completed_at is None


def test_update_batch_job_state(fresh_store):
    job_id = fresh_store.save_batch_job(
        backend="gemini", modality="chat_image",
        backend_job_id="batches/a", asset_count=5,
        submitted_at=0, expires_at=172800, display_name="d",
    )
    fresh_store.update_batch_job_state(
        job_id, state="succeeded", completed_at=100,
        success_count=4, failure_count=1,
    )
    row = fresh_store.get_batch_job(job_id)
    assert row.state == "succeeded"
    assert row.completed_at == 100
    assert row.success_count == 4
    assert row.failure_count == 1


def test_list_active_batch_jobs_filters_terminal(fresh_store):
    active_id = fresh_store.save_batch_job(
        backend="gemini", modality="chat_image",
        backend_job_id="batches/active", asset_count=1,
        submitted_at=0, expires_at=172800, display_name="d",
    )
    done_id = fresh_store.save_batch_job(
        backend="gemini", modality="chat_audio",
        backend_job_id="batches/done", asset_count=1,
        submitted_at=0, expires_at=172800, display_name="d",
    )
    fresh_store.update_batch_job_state(done_id, state="succeeded", completed_at=10)
    active = fresh_store.list_active_batch_jobs()
    ids = {r.id for r in active}
    assert active_id in ids
    assert done_id not in ids


def test_list_active_includes_running(fresh_store):
    job_id = fresh_store.save_batch_job(
        backend="gemini", modality="chat_image",
        backend_job_id="batches/r", asset_count=1,
        submitted_at=0, expires_at=172800, display_name="d",
    )
    fresh_store.update_batch_job_state(job_id, state="running")
    rows = fresh_store.list_active_batch_jobs()
    assert any(r.id == job_id for r in rows)


def test_get_batch_job_missing(fresh_store):
    assert fresh_store.get_batch_job(99999) is None
