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
