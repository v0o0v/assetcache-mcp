"""마이그레이션 후 path rewrite — config.toml 만 (metadata.db 는 무손상).

assets.path 는 pack_manager.ingest_pack 에서 library_root 기준 POSIX 상대경로로
저장되므로 (`file_path.relative_to(library_root).as_posix()`, pack_manager.py:89,
M1 이래 불변), data_dir 마이그레이션 시 DB rewrite 가 필요하지 않다.
config.toml.library_dir_override (절대경로) 만 새 base 로 rewrite 되면 상대경로
assets.path 가 자동으로 새 위치로 resolve 된다.

unity_imports.package_path / projects.external_id 등 다른 path-like 컬럼은
외부 (Asset Store cache, Unity 프로젝트 디렉터리) 라 원래 rewrite 대상이 아니다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

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


def test_rewrite_leaves_metadata_db_untouched(tmp_path):
    """metadata.db 전체를 건드리지 않는다.

    assets.path 는 library_root 기준 상대경로 ("pack/asset.png") 라서 마이그레이션이
    DB 를 열거나 수정할 이유가 없다. 다른 path-like 컬럼 (unity_imports.package_path,
    projects.external_id) 도 외부 경로라 rewrite 대상 아님. 따라서 마이그레이션은
    DB 파일을 그대로 두고, .db.bak 도 만들지 않는다.
    """
    candidate = _make_candidate(tmp_path)
    db_path = candidate.target / "metadata.db"

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, path TEXT)")
    conn.execute(
        "INSERT INTO assets (path) VALUES (?)", ("pack/asset.png",)
    )
    conn.execute(
        "CREATE TABLE unity_imports (id INTEGER PRIMARY KEY, package_path TEXT)"
    )
    conn.execute(
        "INSERT INTO unity_imports (package_path) VALUES (?)",
        ("C:/Users/foo/AppData/Roaming/Unity/Asset Store-5.x/p.unitypackage",),
    )
    conn.commit()
    conn.close()

    before_mtime = db_path.stat().st_mtime_ns
    before_bytes = db_path.read_bytes()

    rewrite_paths_after_migration(candidate)

    # 파일 내용/타임스탬프 무변경
    assert db_path.read_bytes() == before_bytes
    assert db_path.stat().st_mtime_ns == before_mtime
    # 백업 파일도 안 만든다 (수정하지 않으니 백업 불필요)
    assert not (candidate.target / "metadata.db.bak").exists()

    # 행도 그대로 — assets.path 는 상대경로 그대로, unity_imports 도 그대로
    conn = sqlite3.connect(db_path)
    rows = list(conn.execute("SELECT path FROM assets"))
    unity_rows = list(conn.execute("SELECT package_path FROM unity_imports"))
    conn.close()
    assert rows == [("pack/asset.png",)]
    assert "Asset Store-5.x" in unity_rows[0][0]
