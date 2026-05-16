"""M2 schema + CRUD tests for :class:`gah.core.store.Store`.

M2 extends the M1 schema with sprite_meta, sound_meta, assets_fts
(FTS5), asset_embeddings, asset_labels, clip_label_cache, and labels.
Store grows new methods to write analyzer output and drive the
analysis queue.
"""

from __future__ import annotations

import json
import time

import pytest

from gah.core.manifest import PackManifest
from gah.core.store import (
    LabelScore,
    SoundMeta,
    SpriteMeta,
    Store,
)


def _now() -> int:
    return int(time.time())


def _make_pack(store: Store, name: str = "pack_a") -> int:
    manifest = PackManifest(
        display_name=name, vendor=None, source_url=None,
        license=None, description=None,
    )
    return store.upsert_pack(name, manifest, scanned_at=_now())


def _make_asset(store: Store, pack_id: int, path: str,
                kind: str = "sprite", added_at: int | None = None) -> int:
    return store.upsert_asset(
        pack_id=pack_id, rel_path=path, kind=kind,
        file_hash=f"hash_{path}", file_size=1024,
        added_at=added_at or _now(),
    )


# ── M2 스키마 ────────────────────────────────────────────────────────


class TestM2Schema:
    def test_initialize_creates_m2_tables(self, store: Store) -> None:
        rows = store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        ).fetchall()
        names = {r[0] for r in rows}
        for required in (
            "sprite_meta", "sound_meta", "assets_fts",
            "asset_embeddings", "asset_labels", "clip_label_cache",
            "labels",
        ):
            assert required in names, f"missing M2 table: {required}"

    def test_initialize_is_idempotent_with_m1_tables(self, store: Store) -> None:
        store.initialize()
        store.initialize()
        names = {
            r[0]
            for r in store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for t in ("packs", "assets", "tags", "asset_tags"):
            assert t in names


# ── sprite_meta / sound_meta ─────────────────────────────────────────


class TestMetaTables:
    def test_save_sprite_meta_replaces(self, store: Store) -> None:
        pack_id = _make_pack(store)
        asset_id = _make_asset(store, pack_id, "a.png")
        store.save_sprite_meta(
            asset_id,
            SpriteMeta(width=32, height=32, has_alpha=True, is_pixel_art=True,
                       dominant_colors=["#ff0000"]),
        )
        store.save_sprite_meta(
            asset_id,
            SpriteMeta(width=64, height=64, has_alpha=False, is_pixel_art=False,
                       dominant_colors=["#00ff00"]),
        )
        rows = store.conn.execute(
            "SELECT width, height, has_alpha FROM sprite_meta WHERE asset_id=?",
            (asset_id,),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 64

    def test_save_sound_meta_replaces(self, store: Store) -> None:
        pack_id = _make_pack(store)
        asset_id = _make_asset(store, pack_id, "a.wav", kind="sound")
        first = SoundMeta(
            duration_ms=1000, sample_rate=16000, channels=1, loudness_db=-20.0,
            bpm=None, category="sfx", loopable=False, instruments=None,
            tempo=None, intensity="quiet", genre=None, voice_type=None,
            audio_path_used="native",
        )
        store.save_sound_meta(asset_id, first)
        second = SoundMeta(
            duration_ms=2000, sample_rate=16000, channels=1, loudness_db=-10.0,
            bpm=120.0, category="bgm", loopable=True,
            instruments=["piano", "strings"],
            tempo="medium", intensity="moderate", genre="orchestral",
            voice_type=None, audio_path_used="native",
        )
        store.save_sound_meta(asset_id, second)
        row = store.conn.execute(
            "SELECT duration_ms, category, tempo, genre FROM sound_meta WHERE asset_id=?",
            (asset_id,),
        ).fetchone()
        assert row == (2000, "bgm", "medium", "orchestral")


# ── asset_labels ─────────────────────────────────────────────────────


class TestAssetLabels:
    def test_save_asset_labels_overwrites_per_asset(self, store: Store) -> None:
        pack_id = _make_pack(store)
        a = _make_asset(store, pack_id, "a.png")
        store.save_asset_labels(
            a,
            [
                LabelScore(axis="style", label="pixel_art", score=0.9,
                           source="gemma", weight="primary"),
                LabelScore(axis="mood", label="heroic", score=0.7,
                           source="gemma", weight="primary"),
            ],
        )
        # 두 번째 save 는 이전 라벨을 모두 대체
        store.save_asset_labels(
            a,
            [
                LabelScore(axis="style", label="cel_shaded", score=0.6,
                           source="gemma", weight="primary"),
            ],
        )
        rows = store.conn.execute(
            "SELECT axis, label FROM asset_labels WHERE asset_id=?", (a,)
        ).fetchall()
        assert rows == [("style", "cel_shaded")]

    def test_save_asset_labels_with_dup_axis_label_different_source(
        self, store: Store
    ) -> None:
        pack_id = _make_pack(store)
        a = _make_asset(store, pack_id, "a.png")
        store.save_asset_labels(
            a,
            [
                LabelScore("style", "pixel_art", 0.8, "gemma", "primary"),
                LabelScore("style", "pixel_art", 0.91, "clip", None),
            ],
        )
        sources = sorted(
            r[0]
            for r in store.conn.execute(
                "SELECT source FROM asset_labels"
                " WHERE asset_id=? AND axis='style' AND label='pixel_art'",
                (a,),
            ).fetchall()
        )
        assert sources == ["clip", "gemma"]


# ── asset_embeddings ─────────────────────────────────────────────────


class TestEmbeddings:
    def test_save_embedding_roundtrip(self, store: Store) -> None:
        import numpy as np

        pack_id = _make_pack(store)
        a = _make_asset(store, pack_id, "a.png")
        vec = np.array([0.1, -0.2, 0.3, 0.4], dtype=np.float32)
        store.save_embedding(a, model="nomic-embed-text",
                             vector_bytes=vec.tobytes(), dim=4)
        row = store.conn.execute(
            "SELECT model, dim, vector FROM asset_embeddings WHERE asset_id=?",
            (a,),
        ).fetchone()
        assert row[0] == "nomic-embed-text"
        assert row[1] == 4
        restored = np.frombuffer(row[2], dtype=np.float32)
        assert np.allclose(restored, vec)


# ── FTS5 ─────────────────────────────────────────────────────────────


class TestFts:
    def test_update_fts_can_be_searched(self, store: Store) -> None:
        pack_id = _make_pack(store)
        a = _make_asset(store, pack_id, "hero.png")
        store.update_fts(a, "label:pixel_art label:heroic 'A brave hero character'")
        rows = store.conn.execute(
            "SELECT asset_id FROM assets_fts WHERE searchable_text MATCH 'pixel'"
        ).fetchall()
        assert any(r[0] == a for r in rows)


# ── pending / state transitions ──────────────────────────────────────


class TestPendingFlow:
    def test_next_pending_asset_returns_oldest_first(self, store: Store) -> None:
        pack_id = _make_pack(store)
        a1 = _make_asset(store, pack_id, "a1.png", added_at=1)
        a2 = _make_asset(store, pack_id, "a2.png", added_at=2)
        row = store.next_pending_asset()
        assert row is not None
        assert row.id == a1

    def test_pending_assets_for_pack_filters_correctly(self, store: Store) -> None:
        p1 = _make_pack(store, "p1")
        p2 = _make_pack(store, "p2")
        _make_asset(store, p1, "p1/a.png")
        _make_asset(store, p2, "p2/a.png")
        rows = store.pending_assets_for_pack(p1)
        assert all(r.pack_id == p1 for r in rows)

    def test_mark_asset_state_sets_analyzed_at_when_ok(self, store: Store) -> None:
        pack_id = _make_pack(store)
        a = _make_asset(store, pack_id, "a.png")
        store.mark_asset_state(a, "ok", analyzed_at=12345)
        row = store.conn.execute(
            "SELECT analysis_state, analyzed_at FROM assets WHERE id=?", (a,)
        ).fetchone()
        assert row == ("ok", 12345)

    def test_mark_asset_state_failed_keeps_analyzed_at_null(
        self, store: Store
    ) -> None:
        pack_id = _make_pack(store)
        a = _make_asset(store, pack_id, "a.png")
        store.mark_asset_state(a, "failed", error="boom", analyzed_at=None)
        row = store.conn.execute(
            "SELECT analysis_state, analyzed_at, analysis_error FROM assets"
            " WHERE id=?",
            (a,),
        ).fetchone()
        assert row[0] == "failed"
        assert row[1] is None
        assert row[2] == "boom"


# ── pack aggregate / CLIP label cache ────────────────────────────────


class TestPackAggregate:
    def test_update_pack_aggregate_stores_json(self, store: Store) -> None:
        pack_id = _make_pack(store)
        store.update_pack_aggregate(pack_id, json.dumps({"main_style": "pixel_art"}))
        row = store.conn.execute(
            "SELECT aggregate_meta FROM packs WHERE id=?", (pack_id,)
        ).fetchone()
        assert json.loads(row[0])["main_style"] == "pixel_art"


class TestClipLabelCache:
    def test_clip_label_cache_get_put(self, store: Store) -> None:
        payload = b"\x00\x00\x80?" + b"\x00" * 12
        store.clip_label_cache_put("pixel_art", "ViT-B-32:openai", 4, payload)
        blob = store.clip_label_cache_get("pixel_art", "ViT-B-32:openai")
        assert blob == payload
        missing = store.clip_label_cache_get("unknown", "ViT-B-32:openai")
        assert missing is None


# ── cascade ──────────────────────────────────────────────────────────


class TestCascade:
    def test_delete_asset_cascades_m2_tables(self, store: Store) -> None:
        import numpy as np

        pack_id = _make_pack(store)
        a = _make_asset(store, pack_id, "a.png")
        store.save_sprite_meta(
            a, SpriteMeta(32, 32, True, True, ["#ff0000"])
        )
        store.save_asset_labels(
            a, [LabelScore("style", "pixel_art", 0.9, "gemma", "primary")]
        )
        store.save_embedding(
            a, "nomic-embed-text",
            np.array([0.1], dtype=np.float32).tobytes(), dim=1,
        )
        store.update_fts(a, "hero")
        store.delete_asset(a)
        for table in ("sprite_meta", "asset_labels", "asset_embeddings"):
            count = store.conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE asset_id=?", (a,)
            ).fetchone()[0]
            assert count == 0, f"{table} not cascaded"
        fts_count = store.conn.execute(
            "SELECT COUNT(*) FROM assets_fts WHERE asset_id=?", (a,)
        ).fetchone()[0]
        assert fts_count == 0


# ── labels 테이블 ────────────────────────────────────────────────────


class TestLabelsTable:
    def test_labels_table_enforces_unique_axis_label(self, store: Store) -> None:
        import sqlite3

        now = _now()
        store.conn.execute(
            "INSERT INTO labels (axis, label, source, enabled, created_at, updated_at)"
            " VALUES (?, ?, 'seed', 1, ?, ?)",
            ("style", "pixel_art", now, now),
        )
        with pytest.raises(sqlite3.IntegrityError):
            store.conn.execute(
                "INSERT INTO labels (axis, label, source, enabled, created_at, updated_at)"
                " VALUES (?, ?, 'user', 1, ?, ?)",
                ("style", "pixel_art", now, now),
            )

    def test_labels_table_keeps_disabled_rows(self, store: Store) -> None:
        now = _now()
        store.conn.execute(
            "INSERT INTO labels (axis, label, source, enabled, created_at, updated_at)"
            " VALUES (?, ?, 'seed', 0, ?, ?)",
            ("style", "obsolete_label", now, now),
        )
        rows = store.conn.execute(
            "SELECT axis, label, enabled FROM labels WHERE label='obsolete_label'"
        ).fetchall()
        assert rows == [("style", "obsolete_label", 0)]
