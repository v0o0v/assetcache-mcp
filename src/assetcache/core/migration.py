"""v0.0.1 데이터 폴더 마이그레이션 helper.

%APPDATA%\\GameAssetHelper\\ → %APPDATA%\\AssetCacheMCP\\
"""

from __future__ import annotations

import asyncio
import shutil
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, Optional

from assetcache.config import AppPaths

MIGRATION_MARKER = ".migrated_from_v001"


class MigrationState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class MigrationRunner:
    """비동기 마이그레이션 실행자.

    self.state, self.error, self.progress (0~1) 로 외부에서 진행 확인.
    """

    def __init__(self):
        self.state = MigrationState.PENDING
        self.error: str = ""
        self.progress: float = 0.0

    async def run(
        self,
        candidate: "MigrationCandidate",
        mode: Literal["copy", "move"],
    ) -> None:
        self.state = MigrationState.RUNNING
        try:
            # 1) 디스크 공간 사전 검사
            target_parent = candidate.target.parent
            target_parent.mkdir(parents=True, exist_ok=True)
            usage = shutil.disk_usage(target_parent)
            required = int(candidate.total_bytes * 1.1)
            if usage.free < required:
                raise OSError(
                    f"디스크 공간 부족: 필요 {required} bytes, 가용 {usage.free} bytes"
                )

            # 2) 복사 또는 이동 (blocking IO 라 thread 로)
            await asyncio.to_thread(
                self._do_transfer, candidate, mode
            )

            # 3) 마커
            (candidate.target / MIGRATION_MARKER).write_text(
                "migrated_at: 2026-05-19\n", encoding="utf-8"
            )

            # 4) path rewrite
            await asyncio.to_thread(rewrite_paths_after_migration, candidate)

            self.progress = 1.0
            self.state = MigrationState.DONE

        except Exception as e:
            self.error = str(e)
            # rollback: target 정리
            if candidate.target.exists():
                try:
                    shutil.rmtree(candidate.target)
                except OSError:
                    pass
            self.state = MigrationState.FAILED

    def _do_transfer(
        self, candidate: "MigrationCandidate", mode: str
    ) -> None:
        if mode == "copy":
            shutil.copytree(
                str(candidate.source), str(candidate.target),
                dirs_exist_ok=False,
            )
        elif mode == "move":
            shutil.move(str(candidate.source), str(candidate.target))
        else:
            raise ValueError(f"unknown mode: {mode}")


@dataclass(frozen=True)
class MigrationCandidate:
    source: Path
    target: Path
    total_files: int
    total_bytes: int
    has_db: bool
    has_library: bool


def is_already_migrated(target: Path) -> bool:
    """target 안에 마이그레이션 완료 마커가 있는지."""
    return (target / MIGRATION_MARKER).exists()


def _is_empty_dir(p: Path) -> bool:
    if not p.exists():
        return True
    return not any(p.iterdir())


def _count_files(root: Path) -> tuple[int, int]:
    n = 0
    sz = 0
    for f in root.rglob("*"):
        if f.is_file():
            n += 1
            try:
                sz += f.stat().st_size
            except OSError:
                pass
    return n, sz


def rewrite_paths_after_migration(candidate: MigrationCandidate) -> None:
    """target 안의 config.toml + metadata.db 의 구 base path 를 새 base 로.

    config.toml: 구 base 시작 path 를 새 base 로 replace.
    metadata.db:
        - assets.path: 구 base 시작 행만 rewrite
        - unity_imports.unitypackage_path: 외부 cache 라 rewrite X
        - projects.path: Unity 프로젝트 외부 경로라 rewrite X
        - .db.bak 사전 백업
    """
    old_base = str(candidate.source)
    new_base = str(candidate.target)
    # Windows: 백슬래시/슬래시 양형 모두 대응 — forward slash 정규화 기반
    old_base_fwd = old_base.replace("\\", "/")
    new_base_fwd = new_base.replace("\\", "/")

    # config.toml — 파일 내용을 forward slash 로 정규화한 뒤 치환
    config_path = candidate.target / "config.toml"
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        # 내용을 forward slash 정규화 후 구 base(fwd) 치환
        text_fwd = text.replace("\\", "/")
        if old_base_fwd in text_fwd:
            text_fwd = text_fwd.replace(old_base_fwd, new_base_fwd)
            config_path.write_text(text_fwd, encoding="utf-8")

    # metadata.db
    db_path = candidate.target / "metadata.db"
    if db_path.exists():
        try:
            # 백업
            shutil.copy2(db_path, db_path.with_suffix(".db.bak"))

            conn = sqlite3.connect(db_path)
            try:
                # assets.path 만 rewrite (unity_imports / projects 무손상)
                tbls = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
                if "assets" in tbls:
                    cursor = conn.execute(
                        "SELECT id, path FROM assets WHERE path LIKE ?",
                        (f"{old_base}%",),
                    )
                    updates = []
                    for row_id, path in cursor:
                        new_path = path.replace(old_base, new_base, 1)
                        updates.append((new_path, row_id))
                    if updates:
                        conn.executemany(
                            "UPDATE assets SET path = ? WHERE id = ?", updates
                        )
                        conn.commit()
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            # invalid db (fake or test fixture) — skip rewrite, keep .bak
            pass


def detect_v001_candidate(paths: AppPaths) -> Optional[MigrationCandidate]:
    """새 폴더가 비어있고 구 폴더에 데이터가 있으면 MigrationCandidate 반환."""
    if paths.legacy_data_dir is None:
        return None

    new_dir = paths.data_dir
    old_dir = paths.legacy_data_dir

    if is_already_migrated(new_dir):
        return None

    if not _is_empty_dir(new_dir):
        return None

    if not old_dir.exists():
        return None

    has_db = (old_dir / "metadata.db").exists()
    has_library = (old_dir / "library").exists()

    if not has_db and not has_library:
        return None

    total_files, total_bytes = _count_files(old_dir)

    return MigrationCandidate(
        source=old_dir,
        target=new_dir,
        total_files=total_files,
        total_bytes=total_bytes,
        has_db=has_db,
        has_library=has_library,
    )
