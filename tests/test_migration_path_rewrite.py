"""마이그레이션 후 path rewrite (config.toml + metadata.db)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from assetcache.core.migration import (
    MigrationCandidate,
    rewrite_paths_after_migration,
)


def _make_candidate(tmp_path: Path) -> MigrationCandidate:
    src = tmp_path / "GameAssetHelper"
    tgt = tmp_path / "AssetCacheMCP"
    src.mkdir()
    tgt.mkdir()
    return MigrationCandidate(
        source=src, target=tgt,
        total_files=0, total_bytes=0,
        has_db=True, has_library=True,
    )


def test_rewrite_config_toml_library_root(tmp_path):
    """config.toml 의 library_root 가 구 base 면 새 base 로 rewrite."""
    candidate = _make_candidate(tmp_path)
    config_path = candidate.target / "config.toml"
    config_path.write_text(
        f'[library]\nlibrary_root = "{candidate.source}/library"\n',
        encoding="utf-8",
    )

    rewrite_paths_after_migration(candidate)

    # config 는 forward slash 정규화 후 저장 — fwd 기준으로 검증
    content = config_path.read_text(encoding="utf-8").replace("\\", "/")
    tgt_lib_fwd = str(candidate.target / "library").replace("\\", "/")
    src_lib_fwd = str(candidate.source / "library").replace("\\", "/")
    assert tgt_lib_fwd in content
    assert src_lib_fwd not in content


def test_rewrite_does_not_touch_external_paths(tmp_path):
    """config.toml 의 unrelated path (C:\\Custom\\Pack) 는 무손상."""
    candidate = _make_candidate(tmp_path)
    config_path = candidate.target / "config.toml"
    config_path.write_text(
        '[library]\nlibrary_root = "C:/Custom/External/Pack"\n',
        encoding="utf-8",
    )

    rewrite_paths_after_migration(candidate)

    assert 'C:/Custom/External/Pack' in config_path.read_text(encoding="utf-8")


def test_rewrite_metadata_db_assets_path(tmp_path):
    """metadata.db 의 assets.path 중 구 base 시작 행만 rewrite."""
    candidate = _make_candidate(tmp_path)
    db_path = candidate.target / "metadata.db"
    src_lib = candidate.source / "library"
    tgt_lib = candidate.target / "library"

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, path TEXT)")
    conn.execute("INSERT INTO assets (path) VALUES (?)", (f"{src_lib}/pack/asset.png",))
    conn.execute("INSERT INTO assets (path) VALUES (?)", ("C:/External/foo.png",))
    conn.commit()
    conn.close()

    rewrite_paths_after_migration(candidate)

    conn = sqlite3.connect(db_path)
    rows = list(conn.execute("SELECT path FROM assets ORDER BY id"))
    conn.close()
    assert str(tgt_lib) in rows[0][0]
    assert rows[1][0] == "C:/External/foo.png"


def test_rewrite_does_not_touch_unity_imports_path(tmp_path):
    """unity_imports.unitypackage_path 는 Asset Store cache 라 rewrite X."""
    candidate = _make_candidate(tmp_path)
    db_path = candidate.target / "metadata.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE unity_imports (id INTEGER PRIMARY KEY, unitypackage_path TEXT)")
    conn.execute(
        "INSERT INTO unity_imports (unitypackage_path) VALUES (?)",
        ("C:/Users/foo/AppData/Roaming/Unity/Asset Store-5.x/...",),
    )
    conn.commit()
    conn.close()

    rewrite_paths_after_migration(candidate)

    conn = sqlite3.connect(db_path)
    rows = list(conn.execute("SELECT unitypackage_path FROM unity_imports"))
    conn.close()
    assert "Asset Store-5.x" in rows[0][0]


def test_rewrite_creates_db_backup(tmp_path):
    """metadata.db 가 .bak 백업 됐는지."""
    candidate = _make_candidate(tmp_path)
    db_path = candidate.target / "metadata.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, path TEXT)")
    conn.commit()
    conn.close()

    rewrite_paths_after_migration(candidate)

    assert (candidate.target / "metadata.db.bak").exists()
