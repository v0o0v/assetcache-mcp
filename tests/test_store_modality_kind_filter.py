"""M11.2 — chat_image 가 sprite 만, chat_spritesheet 가 spritesheet 만 잡는지 확인."""

import sqlite3

import pytest

from assetcache.core.store import Store


def _seed(store: Store, *, sprites: int, sheets: int, sounds: int) -> None:
    """packs/assets 시드 — pending 상태.

    store API 가 upsert_pack 은 PackManifest 를, upsert_asset 은 pending state 외
    배치/메타 컬럼 default 처리 만큼만 보장하므로, 직접 SQL 로 시드해서 분기 의도를
    그대로 검증한다.
    """
    with sqlite3.connect(str(store.db_path)) as conn:
        conn.execute(
            "INSERT INTO packs (name, enabled, added_at) VALUES ('t', 1, 0)"
        )
        pack_id = conn.execute("SELECT id FROM packs WHERE name='t'").fetchone()[0]
        aid = 0
        for kind, count in (("sprite", sprites), ("spritesheet", sheets), ("sound", sounds)):
            for i in range(count):
                conn.execute(
                    "INSERT INTO assets (pack_id, path, kind, file_hash, file_size,"
                    " added_at, analysis_state) VALUES (?, ?, ?, ?, ?, 0, 'pending')",
                    (pack_id, f"{kind}/{i}.png", kind, f"h{aid}", 10),
                )
                aid += 1
        conn.commit()


def test_count_pending_chat_image_only_includes_sprite(tmp_path):
    """chat_image 카운트가 spritesheet 를 포함하면 안 됨."""
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    assert store.count_pending_by_modality("chat_image") == 3


def test_count_pending_chat_spritesheet_only_includes_spritesheet(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    assert store.count_pending_by_modality("chat_spritesheet") == 4


def test_count_pending_chat_audio_unchanged(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    assert store.count_pending_by_modality("chat_audio") == 2


def test_count_pending_text_embed_unchanged(tmp_path):
    """text_embed 는 dict 에 없으므로 모든 kind 카운트."""
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    assert store.count_pending_by_modality("text_embed") == 9


def test_fetch_pending_chat_spritesheet_returns_only_spritesheet_rows(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    rows = store.fetch_pending_by_modality("chat_spritesheet", limit=100)
    assert len(rows) == 4
    assert {r.kind for r in rows} == {"spritesheet"}
