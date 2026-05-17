"""M4 — Store 신규 메서드 + `_M4_SCHEMA` (saved_searches + feedback_records).

스키마:
- saved_searches(id, project_id?, name, query_json, created_at, last_used_at?)
  + UNIQUE(project_id, name)
- feedback_records(id, project_id, asset_id, query_id?, reason, weight: signed, created_at)
  + idx (project_id, asset_id, created_at) / (project_id, asset_id)

write 메서드: `save_search` / `delete_saved_search` / `update_saved_search_last_used` /
              `insert_feedback_record`
read 메서드:  `list_saved_searches` / `get_saved_search` /
              `feedback_records_for_project(project_id, asset_ids|None, within_seconds)` /
              `pack_feedback_count(project_id, pack_ids, within_seconds)`
"""

from __future__ import annotations

import json
import time

import pytest


# ── 헬퍼 ─────────────────────────────────────────────────────────────


def _table_names(store) -> set[str]:
    rows = store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


# ── 1. 스키마 + idempotent ───────────────────────────────────────────


def test_initialize_creates_m4_tables(store) -> None:
    tables = _table_names(store)
    assert {"saved_searches", "feedback_records"} <= tables


def test_initialize_is_idempotent_with_m1_m2_m3_tables(store) -> None:
    # 두 번째 initialize() — 기존 데이터 보존 + IF NOT EXISTS 라 에러 없음.
    store.initialize()
    tables = _table_names(store)
    # M0~M3 의 핵심 테이블 + M4 신규 두 테이블 모두 존재.
    assert {
        "packs", "assets", "labels", "asset_labels", "asset_embeddings",
        "sprite_meta", "sound_meta", "assets_fts",
        "projects", "asset_usage", "search_queries",
        "saved_searches", "feedback_records",
    } <= tables


# ── 2. saved_searches ─────────────────────────────────────────────────


def test_save_search_returns_id(populated_store) -> None:
    store, ids = populated_store
    pid = store.upsert_project("proj_save_a").id
    sid = store.save_search(pid, "my hero search",
                            json.dumps({"query": "hero", "kind": "sprite"}))
    assert isinstance(sid, int) and sid > 0


def test_save_search_duplicate_name_raises_operational_error(
    populated_store,
) -> None:
    """UNIQUE(project_id, name) — 같은 (pid, name) 두 번 → IntegrityError."""
    import sqlite3

    store, _ = populated_store
    pid = store.upsert_project("proj_dup").id
    store.save_search(pid, "dup_name", json.dumps({"query": "a"}))
    with pytest.raises(sqlite3.IntegrityError):
        store.save_search(pid, "dup_name", json.dumps({"query": "b"}))


def test_list_saved_searches_orders_by_last_used_desc(populated_store) -> None:
    """last_used_at DESC NULLS LAST → 최근 쓴 게 먼저, 안 쓴 건 created_at desc 로 정렬."""
    store, _ = populated_store
    pid = store.upsert_project("proj_list").id
    a = store.save_search(pid, "search_a", json.dumps({"q": "a"}))
    b = store.save_search(pid, "search_b", json.dumps({"q": "b"}))
    c = store.save_search(pid, "search_c", json.dumps({"q": "c"}))
    # b 만 최근 사용 마킹
    store.update_saved_search_last_used(b)

    rows = store.list_saved_searches(pid)
    names = [r.name for r in rows]
    assert names[0] == "search_b"   # 가장 최근 사용
    assert set(names[1:]) == {"search_a", "search_c"}


def test_delete_saved_search_returns_true_when_present(populated_store) -> None:
    store, _ = populated_store
    pid = store.upsert_project("proj_del").id
    store.save_search(pid, "to_delete", json.dumps({"q": "x"}))
    ok = store.delete_saved_search(pid, "to_delete")
    assert ok is True
    assert store.get_saved_search(pid, "to_delete") is None


def test_delete_saved_search_returns_false_when_missing(populated_store) -> None:
    store, _ = populated_store
    pid = store.upsert_project("proj_missing").id
    ok = store.delete_saved_search(pid, "nonexistent_name")
    assert ok is False


def test_update_saved_search_last_used_sets_timestamp(populated_store) -> None:
    store, _ = populated_store
    pid = store.upsert_project("proj_touch").id
    sid = store.save_search(pid, "search_touch", json.dumps({"q": "x"}))
    before = store.get_saved_search(pid, "search_touch")
    assert before is not None
    assert before.last_used_at is None  # 처음엔 NULL

    store.update_saved_search_last_used(sid)
    after = store.get_saved_search(pid, "search_touch")
    assert after is not None
    assert after.last_used_at is not None
    assert after.last_used_at >= int(time.time()) - 5


# ── 3. feedback_records ──────────────────────────────────────────────


def test_insert_feedback_record_persists_signed_weight(populated_store) -> None:
    store, ids = populated_store
    pid = store.upsert_project("proj_fb").id
    fid = store.insert_feedback_record(
        project_id=pid, asset_id=ids["hero"], query_id=None,
        reason="negative", weight=-0.5,
    )
    assert isinstance(fid, int) and fid > 0
    # 음수 weight 가 그대로 보존됐는지.
    row = store.conn.execute(
        "SELECT reason, weight FROM feedback_records WHERE id = ?", (fid,),
    ).fetchone()
    assert row[0] == "negative"
    assert row[1] == pytest.approx(-0.5)


def test_feedback_records_for_project_filters_window(populated_store) -> None:
    """`feedback_records_for_project(pid, [aid], within_seconds)`
    → {asset_id: sum(weight)} 윈도우 내 행만 합산."""
    store, ids = populated_store
    pid = store.upsert_project("proj_window").id

    # 최근 행 1, 오래된 행 1 (직접 created_at 박음).
    store.insert_feedback_record(
        project_id=pid, asset_id=ids["hero"], query_id=None,
        reason="negative", weight=-0.5,
    )
    # 오래된 행 — created_at 을 100일 전으로.
    old_ts = int(time.time()) - 100 * 86400
    store.conn.execute(
        "INSERT INTO feedback_records "
        "(project_id, asset_id, reason, weight, created_at) VALUES (?,?,?,?,?)",
        (pid, ids["hero"], "negative", -0.5, old_ts),
    )
    store.conn.commit()

    # 윈도우 30일 — 최근 행만 (-0.5).
    out_30d = store.feedback_records_for_project(
        pid, asset_ids=[ids["hero"]], within_seconds=30 * 86400,
    )
    assert out_30d[ids["hero"]] == pytest.approx(-0.5)
    # 윈도우 200일 — 두 행 합산 (-1.0).
    out_200d = store.feedback_records_for_project(
        pid, asset_ids=[ids["hero"]], within_seconds=200 * 86400,
    )
    assert out_200d[ids["hero"]] == pytest.approx(-1.0)


def test_pack_feedback_count_aggregates_negative_only(populated_store) -> None:
    """pack-level penalty 임계 검사용 — 음수 가중치 행만 카운트."""
    store, ids = populated_store
    pid = store.upsert_project("proj_pack_count").id

    # pack_a (hero, coin) 에 negative 2건 + positive 1건.
    store.insert_feedback_record(pid, ids["hero"], None, "negative", -0.5)
    store.insert_feedback_record(pid, ids["coin"], None, "negative", -0.5)
    store.insert_feedback_record(pid, ids["hero"], None, "positive", +0.3)

    counts = store.pack_feedback_count(
        pid, pack_ids=[ids["pack_a"], ids["pack_b"]],
        within_seconds=30 * 86400,
    )
    # pack_a 의 음수 행 = 2, pack_b 는 0.
    assert counts.get(ids["pack_a"], 0) == 2
    assert counts.get(ids["pack_b"], 0) == 0


def test_delete_project_cascades_saved_and_feedback(populated_store) -> None:
    """프로젝트 삭제 시 saved_searches + feedback_records cascade 삭제."""
    store, ids = populated_store
    pid = store.upsert_project("proj_cascade").id
    store.save_search(pid, "to_die", json.dumps({"q": "x"}))
    store.insert_feedback_record(pid, ids["hero"], None, "negative", -0.5)

    store.conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
    store.conn.commit()

    assert store.list_saved_searches(pid) == []
    assert store.feedback_records_for_project(
        pid, asset_ids=None, within_seconds=30 * 86400,
    ) == {}
