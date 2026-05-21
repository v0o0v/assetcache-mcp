"""LIVE Gemini batch 검증 헬퍼 — Qt tray 없이 BatchManager + BatchPoller 직접 구동.

사용:

    $env:GEMINI_API_KEY = "AIza..."
    python scripts/drive_live_batch.py <data_dir>

`<data_dir>` 안의 ``library/`` 를 스캔 → ``config.toml`` 자동 작성 (gemini
enabled + chains = gemini + batch.toggle="forced_on") → chat_image →
chat_spritesheet → polling 까지 진행 → SQL 측정 결과를 stdout 으로.

M11.3 LIVE v1 의 ``drive_batch.py`` 패턴 (project memory
``project_batch_path_drive_pattern``) 의 재구현 — M11.5+ LIVE 검증에서 반복
사용 가능.  Qt 의존성 + tray single-instance lock + 웹 서버 부팅을 모두
우회한다.

API key 는 환경변수에서만 읽고 파일에 기록되는 곳은 ``<data_dir>/config.toml``
하나 (`.gitignore` 적용된 임시 dir 권장).
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path


def _format_toml(api_key: str) -> str:
    # 따옴표 보존을 위해 raw 식으로.  API key 에는 영숫자/하이픈 외 문자 없음.
    return (
        "[backends.gemini]\n"
        "enabled = true\n"
        f'api_key = "{api_key}"\n\n'
        "[chains]\n"
        'chat_image = ["gemini"]\n'
        'chat_spritesheet = ["gemini"]\n\n'
        "[batch]\n"
        'toggle = "forced_on"\n'
        "threshold = 100\n"
        "poll_interval_seconds = 15\n"
    )


def _print_jobs(db_path: Path, label: str) -> list[tuple]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT id, modality, state, asset_count, success_count, failure_count "
            "FROM batch_jobs ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    print(f"[{label}] batch_jobs = {rows}")
    return rows


def _all_terminal(rows: list[tuple]) -> bool:
    if not rows:
        return False
    terminal = {"succeeded", "failed", "cancelled", "expired"}
    return all(r[2] in terminal for r in rows)


def main(data_dir: Path) -> int:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        return 1

    library_dir = data_dir / "library"
    if not library_dir.exists():
        print(f"ERROR: library_dir missing: {library_dir}", file=sys.stderr)
        return 1

    config_path = data_dir / "config.toml"
    db_path = data_dir / "metadata.db"
    config_path.write_text(_format_toml(api_key), encoding="utf-8")
    print(f"wrote {config_path}  ({len(_format_toml(api_key))} bytes)")

    # 무거운 import 는 config 작성 후
    from assetcache.config import load_config
    from assetcache.core.analysis_queue import AnalysisQueue
    from assetcache.core.analyzer.sound import SoundAnalyzer
    from assetcache.core.analyzer.sprite import SpriteAnalyzer
    from assetcache.core.analyzer.spritesheet import SpritesheetAnalyzer
    from assetcache.core.batch.manager import BatchManager
    from assetcache.core.batch.poller import BatchPoller
    from assetcache.core.embedding import EmbeddingEncoder
    from assetcache.core.labels import LabelRegistry
    from assetcache.core.llm.registry import BackendRegistry
    from assetcache.core.scanner import reconcile_library
    from assetcache.core.store import Store

    config = load_config(config_path)
    store = Store(db_path)
    store.initialize()
    registry = LabelRegistry(store)
    registry.bootstrap()

    report = reconcile_library(store, library_dir)
    print(f"reconciled: +{len(report.added)} -{len(report.removed)} ={len(report.rescanned)}")

    registry_llm = BackendRegistry.from_config(config)
    chain_image = registry_llm.get_chain("chat_image")
    chain_audio = registry_llm.get_chain("chat_audio")
    chain_embed = registry_llm.get_chain("text_embed")

    embedder = EmbeddingEncoder(chain_embed, model=config.model_embed)
    sprite = SpriteAnalyzer(
        ollama=chain_image, clip=None, embedder=embedder, registry=registry,
    )
    spritesheet = SpritesheetAnalyzer(
        sprite=sprite, ollama=chain_image, registry=registry,
        embedder=embedder, clip=None,
        alpha_color_weight=config.grid_detect_alpha_color_weight,
    )
    sound = SoundAnalyzer(
        ollama=chain_audio, embedder=embedder, registry=registry,
        spectrogram_cache_dir=data_dir / "cache" / "spectrograms",
        max_clip_seconds=config.audio_max_seconds,
        chunk_strategy=config.audio_chunk_strategy,
    )

    # concurrency=0 — sync analyzer 비활성, batch path 만 사용
    queue = AnalysisQueue(
        store, sprite=sprite, spritesheet=spritesheet, sound=sound,
        concurrency=0, library_root=library_dir,
    )

    manager = BatchManager(
        store=store, chain_registry=registry_llm,
        analysis_queue=queue, cfg=config,
        library_dir=library_dir, registry=registry,
    )
    queue.set_batch_manager(manager)

    poller = BatchPoller(
        store=store, chain_registry=registry_llm,
        analysis_queue=queue, cfg=config,
        registry=registry, library_dir=library_dir,
    )

    # Phase 1: chat_image batch — 시트는 promote, sprite 만 batch 진입
    print("\n=== Phase 1: try_submit('chat_image') ===")
    jid_image = manager.try_submit("chat_image")
    print(f"chat_image → job_id={jid_image}")

    # Phase 2: chat_spritesheet batch — chat_image 가 promote 한 시트가 보임
    print("\n=== Phase 2: try_submit('chat_spritesheet') ===")
    jid_sheet = manager.try_submit("chat_spritesheet")
    print(f"chat_spritesheet → job_id={jid_sheet}")

    # 두 job 이 동시에 active.  poller foreground 로 polling.
    print("\n=== Phase 3: poll until terminal (max 10 min) ===")
    deadline = time.time() + 600
    while time.time() < deadline:
        poller._poll_once()
        rows = _print_jobs(db_path, "poll")
        if _all_terminal(rows):
            break
        time.sleep(5)

    # 결과 dump
    print("\n=== assets + sprite_meta ===")
    conn = sqlite3.connect(str(db_path))
    try:
        for row in conn.execute(
            "SELECT a.path, a.kind, m.frame_w, m.frame_h, m.frame_count, "
            "       m.animations_json "
            "FROM assets a LEFT JOIN sprite_meta m ON m.asset_id=a.id "
            "WHERE a.kind IN ('sprite','spritesheet') ORDER BY a.id"
        ):
            print(row)

        print("\n=== labels (category/palette/mood/animation) ===")
        for row in conn.execute(
            "SELECT a.path, l.axis, l.label "
            "FROM asset_labels l JOIN assets a ON a.id=l.asset_id "
            "WHERE l.axis IN ('category','palette','mood','animation') "
            "ORDER BY a.path, l.axis"
        ):
            print(row)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/drive_live_batch.py <data_dir>")
        sys.exit(1)
    sys.exit(main(Path(sys.argv[1])))
