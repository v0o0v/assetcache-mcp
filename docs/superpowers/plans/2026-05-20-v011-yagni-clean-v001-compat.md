# v0.1.1 — v0.0.1 compat yagni-clean Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v0.0.1 외부 사용자 0 확인 후 M10 Phase 1 의 데이터 폴더 마이그레이션 helper + 관련 +21 테스트 + i18n msgid 3건 + 문서 안내 일괄 제거. 같은 PR 에 M10 rename 누락 2건 (FastMCP server name + `tools/setup_m6_test.py` 경로 안내) 정리. v0.1.1 publish 로 Trusted Publishing 첫 자동 publish 도 검증.

**Architecture:** TDD-역방향 (회귀 -21) 패턴 — 먼저 test 5 파일 삭제 → 회귀 기준선이 1103 → 1082 로 떨어지는 신호 확인 후, live 코드를 commit 단위로 부분 축소. dead module 본체는 의존성이 모두 제거된 뒤 마지막에 삭제 (import error 회피). i18n / rename fix / 문서 / version bump 는 그 뒤 별도 commit. 각 commit 후 `pytest -q` 회귀 1082 passed 유지.

**Tech Stack:** Python 3.12, pytest, Babel (`pybabel compile`), FastMCP, FastAPI, Jinja2, argparse, semver.

**Branch:** `chore/v011-yagni-clean` (이미 `db43d1a` spec commit 됨)
**Baseline:** `1103 passed + 1 skipped + 40 deselected` on `chore/v011-yagni-clean db43d1a`
**Target:** `1082 passed + 1 skipped + 40 deselected` (회귀 -21)
**Spec:** [`docs/superpowers/specs/2026-05-20-v011-yagni-clean-v001-compat-design.md`](../specs/2026-05-20-v011-yagni-clean-v001-compat-design.md)

**커밋 메시지 규칙** — 한글, conventional commits 스타일 prefix (`refactor` / `test` / `docs` / `fix` / `chore`), scope `(v011)`. 본문은 짧게 (1~2줄). 모든 commit 끝에 `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` 푸터.

---

## Task 1: 환경 확인 — baseline 회귀 검증

**Files:** (확인만)
- `chore/v011-yagni-clean` branch HEAD
- venv `%USERPROFILE%\.venvs\gah\`

- [ ] **Step 1: venv 활성화 + main repo 이동**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```

```powershell
cd D:\ClaudeCowork\game-asset-helper\game-asset-helper
```

- [ ] **Step 2: 현재 branch / HEAD 확인**

```powershell
git branch --show-current
git log --oneline -3
```

Expected:
```
chore/v011-yagni-clean
db43d1a docs(v011): v0.0.1 호환 코드 yagni-clean spec 작성
16ba2df chore(m10/cleanup): Phase 0/5 todo 마크 정합성 + CLAUDE/HANDOFF M10 완료 반영 (#13)
7ba6551 ci: workflow actions Node.js 24 호환 버전으로 갱신 (#12)
```

- [ ] **Step 3: baseline 회귀 (Task 2 이전)**

```powershell
pytest -q
```

Expected: `1103 passed, 1 skipped, 40 deselected`

회귀가 1103 이 아니면 plan 의 모든 target 수치도 비례 조정. 다른 patch 가 main 에 들어왔는지 `git fetch origin && git log origin/main..main --oneline` 으로 추가 확인.

---

## Task 2: 마이그레이션 테스트 5 파일 일괄 삭제 (-21)

**Files (delete):**
- `tests/test_migration_detect.py`
- `tests/test_migration_runner.py`
- `tests/test_migration_path_rewrite.py`
- `tests/test_migration_router.py`
- `tests/test_cli_migrate.py`

- [ ] **Step 1: 각 파일의 테스트 개수 사전 카운트**

```powershell
pytest tests\test_migration_detect.py tests\test_migration_runner.py tests\test_migration_path_rewrite.py tests\test_migration_router.py tests\test_cli_migrate.py --collect-only -q
```

Expected: 합계 21 tests collected. 21 이 아니면 spec 의 `-21` 가정이 깨졌다는 신호 — 정지 후 사용자 확인.

- [ ] **Step 2: 5 파일 git rm**

```powershell
git rm tests\test_migration_detect.py tests\test_migration_runner.py tests\test_migration_path_rewrite.py tests\test_migration_router.py tests\test_cli_migrate.py
```

Expected: `rm 'tests/test_migration_detect.py'` 등 5줄 출력.

- [ ] **Step 3: 회귀 확인 — 1082 신호**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`. 21 이 정확히 빠지지 않으면 — 다른 파일이 마이그레이션 모듈을 import 해 ImportError 가 누적 fail 로 잡힘 → 출력 살펴 누락 파일 식별.

- [ ] **Step 4: commit**

```bash
git commit -m "$(cat <<'EOF'
test(v011): v0.0.1 마이그레이션 테스트 5 파일 삭제

회귀 1103 → 1082 (-21). detect/runner/path_rewrite/router/cli_migrate
모듈 본체는 다른 코드의 의존성이 모두 정리된 후 Task 8 에서 삭제.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: i18n msgid 정합성 테스트 갱신

**Files:**
- Modify: `tests/test_locale_assetcache_msgid.py` (`NEW_MSGIDS` list)

- [ ] **Step 1: 현재 파일 확인**

`NEW_MSGIDS` 가 다음 5건이라는 사실을 확인 (이미 spec 매핑에 명시):

```python
NEW_MSGIDS = [
    # Phase 1.7 (마이그레이션 배너) — 영어 msgid 3건
    "v0.0.1 data detected",
    "Copy",
    "Migrating...",
    # Phase 2.7 (PyPI 신버전 알림) — 영어 msgid 2건
    "available",
    "Upgrade command copied to clipboard",
]
```

- [ ] **Step 2: 마이그레이션 3건 제거, PyPI 2건만 유지**

`tests/test_locale_assetcache_msgid.py` 의 module docstring + `NEW_MSGIDS` 둘 다 갱신.

Edit `tests/test_locale_assetcache_msgid.py`:

old:
```python
"""ko/en .po catalog 의 M10 신규 msgid 정합성 검사.

Phase 1.7 (마이그레이션 배너) + Phase 2.7 (PyPI 신버전 알림) 의 신규 msgid 가
ko + en 양쪽 .po 카탈로그에 모두 존재하는지 보장한다. 신규 msgid 가 한쪽에만
추가되거나 컴파일이 누락된 회귀를 빠르게 잡는다.
"""
```

new:
```python
"""ko/en .po catalog 의 M10 Phase 2.7 (PyPI 신버전 알림) msgid 정합성 검사.

신규 msgid 가 한쪽 언어에만 추가되거나 컴파일이 누락된 회귀를 빠르게 잡는다.
Phase 1.7 (마이그레이션 배너) msgid 3건은 v0.1.1 yagni-clean 에서 제거됨.
"""
```

old:
```python
NEW_MSGIDS = [
    # Phase 1.7 (마이그레이션 배너) — 영어 msgid 3건
    "v0.0.1 data detected",
    "Copy",
    "Migrating...",
    # Phase 2.7 (PyPI 신버전 알림) — 영어 msgid 2건
    "available",
    "Upgrade command copied to clipboard",
]
```

new:
```python
NEW_MSGIDS = [
    # Phase 2.7 (PyPI 신버전 알림) — 영어 msgid 2건
    "available",
    "Upgrade command copied to clipboard",
]
```

또한 단순 파서 docstring 의 "M10 의 신규 msgid 5건" 표현도 갱신:

old:
```python
    """Single-line `msgid "..."` 항목만 추출.

    M10 의 신규 msgid 5건은 모두 single-line 이라 본 단순 파서로 충분하다.
    multi-line msgid 가 필요한 시점에는 babel.messages.pofile 로 보강한다.
    """
```

new:
```python
    """Single-line `msgid "..."` 항목만 추출.

    검사 대상 msgid 는 모두 single-line 이라 본 단순 파서로 충분하다.
    multi-line msgid 가 필요한 시점에는 babel.messages.pofile 로 보강한다.
    """
```

- [ ] **Step 3: 회귀 확인**

```powershell
pytest tests\test_locale_assetcache_msgid.py -v
```

Expected: `test_msgid_present_in_locale[en-Upgrade command copied to clipboard] PASSED` 등 4 case 통과 (2 lang × 2 msgid).

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected` (변화 없음 — 같은 test 함수가 parametrize 만 10 → 4 case 로 줄어듦. 모두 통과하므로 회귀 count 영향 0).

- [ ] **Step 4: commit**

```bash
git commit -am "$(cat <<'EOF'
test(v011): i18n msgid 정합성 테스트의 마이그레이션 3건 제거

NEW_MSGIDS 5 → 2 (Phase 2.7 PyPI 알림만 유지). parametrize 10 → 4 case.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: CLI cleanup — `__main__.py`

**Files:**
- Modify: `src/assetcache/__main__.py`

- [ ] **Step 1: 현재 파일 인지 (이미 컨텍스트에 있음)**

`_build_parser` 의 `--migrate` (line 63-69) + `--legacy-data-dir` (line 70-77) 옵션, `_run_migration_cli` 함수 (line 80-126), `main()` 의 `if args.migrate:` 분기 (line 143-149), `EXIT_MIGRATION_FAILED = 3` 상수 (line 39).

- [ ] **Step 2: `EXIT_MIGRATION_FAILED` 상수 제거**

Edit:

old:
```python
EXIT_OK = 0
EXIT_ALREADY_RUNNING = 0  # benign — second launch should be silent
EXIT_NOT_IMPLEMENTED = 2
EXIT_MIGRATION_FAILED = 3
EXIT_USAGE = 64
```

new:
```python
EXIT_OK = 0
EXIT_ALREADY_RUNNING = 0  # benign — second launch should be silent
EXIT_NOT_IMPLEMENTED = 2
EXIT_USAGE = 64
```

- [ ] **Step 3: `--migrate` + `--legacy-data-dir` argparse 옵션 제거**

Edit `_build_parser`:

old:
```python
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="로그 레벨 (DEBUG/INFO/WARNING/ERROR)",
    )
    parser.add_argument(
        "--migrate",
        choices=["copy", "move"],
        default=None,
        help="v0.0.1 (GameAssetHelper) 데이터 폴더를 헤드리스로 마이그레이션. "
             "copy 는 원본 보존, move 는 원본 제거.",
    )
    parser.add_argument(
        "--legacy-data-dir",
        type=Path,
        default=None,
        help="--migrate 와 함께 — legacy(구 v0.0.1) data_dir 명시. "
             "지정하지 않으면 platformdirs(GameAssetHelper) 로 자동 검출.",
    )
    return parser
```

new:
```python
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="로그 레벨 (DEBUG/INFO/WARNING/ERROR)",
    )
    return parser
```

- [ ] **Step 4: `_run_migration_cli` 함수 전체 제거**

Edit (function 전체 line 80-126):

old:
```python
def _run_migration_cli(
    paths,
    mode: str,
    legacy_override: Path | None,
) -> int:
    """헤드리스 마이그레이션 — `python -m assetcache --migrate=copy|move`.

    detect_v001_candidate 가 후보를 못 찾으면 EXIT_OK + 안내 메시지로 종료한다
    (사용자가 이미 마이그레이션 완료했거나 v0.0.1 데이터가 없는 정상 시나리오).
    legacy_override 가 주어지면 paths.legacy_data_dir 을 강제로 교체해 검출에
    사용한다 — explicit --data-dir 흐름에서 default_app_paths 가 legacy 를
    None 으로 두는 동작을 우회하기 위함.
    """
    from dataclasses import replace
    from assetcache.core.migration import (
        MigrationRunner,
        MigrationState,
        detect_v001_candidate,
    )

    if legacy_override is not None:
        paths = replace(paths, legacy_data_dir=legacy_override.expanduser().resolve())

    candidate = detect_v001_candidate(paths)
    if candidate is None:
        print(
            "마이그레이션 후보가 없습니다 — v0.0.1 데이터 폴더가 발견되지 "
            "않았거나 이미 마이그레이션이 완료되었습니다.",
        )
        return EXIT_OK

    print(
        f"마이그레이션 시작 (mode={mode}): "
        f"{candidate.source} → {candidate.target} "
        f"({candidate.total_files} 파일, {candidate.total_bytes:,} bytes)"
    )

    import asyncio
    runner = MigrationRunner()
    asyncio.run(runner.run(candidate, mode=mode))  # type: ignore[arg-type]

    if runner.state == MigrationState.DONE:
        print("마이그레이션 완료.")
        return EXIT_OK

    print(f"마이그레이션 실패: {runner.error}", file=sys.stderr)
    return EXIT_MIGRATION_FAILED


def main(argv: Sequence[str] | None = None) -> int:
```

new:
```python
def main(argv: Sequence[str] | None = None) -> int:
```

- [ ] **Step 5: `main()` 의 `if args.migrate:` 분기 + 사이 주석 제거**

Edit:

old:
```python
    if args.version:
        print(f"assetcache-mcp {__version__}")
        return EXIT_OK

    if args.migrate:
        # 헤드리스 마이그레이션 — single_instance lock 안 잡음 (1회성 단독 실행).
        # setup_logging 보다 먼저 분기 — 그래야 logs/assetcache.log 가
        # data_dir 안에 file handle 로 잡힌 상태에서 _do_transfer 의
        # rmtree(target) 가 Windows file lock 으로 깨지지 않는다.
        # 진행 출력은 stdout/stderr 만 사용 (1회성 헤드리스 흐름).
        return _run_migration_cli(paths, args.migrate, args.legacy_data_dir)

    level = getattr(logging, str(args.log_level).upper(), logging.INFO)
```

new:
```python
    if args.version:
        print(f"assetcache-mcp {__version__}")
        return EXIT_OK

    level = getattr(logging, str(args.log_level).upper(), logging.INFO)
```

- [ ] **Step 6: 회귀 확인**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`. Task 2 의 cli_migrate 테스트는 이미 제거됐으니 이 시점에 import error 없음.

```powershell
python -m assetcache --migrate=copy
```

Expected (stderr): `assetcache: error: unrecognized arguments: --migrate=copy` → exit code != 0.

```powershell
python -m assetcache --version
```

Expected: `assetcache-mcp 0.1.0` (Task 14 이전이라 0.1.0).

- [ ] **Step 7: commit**

```bash
git commit -am "$(cat <<'EOF'
refactor(v011): __main__.py 의 --migrate 옵션 + _run_migration_cli 제거

argparse 옵션 2개 (--migrate, --legacy-data-dir) + 함수 1개
(_run_migration_cli) + 상수 1개 (EXIT_MIGRATION_FAILED) + main()
분기 1건 제거. CLI 표면 단순화.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Config cleanup — `config.py`

**Files:**
- Modify: `src/assetcache/config.py`

- [ ] **Step 1: 현재 파일 확인**

`AppPaths.legacy_data_dir: Path | None = None` field (line 44) + `default_app_paths` 안의 legacy 자동 탐지 로직 (line 70-77, 86).

- [ ] **Step 2: `AppPaths.legacy_data_dir` field 제거**

Edit:

old:
```python
    log_path: Path
    lock_path: Path
    legacy_data_dir: Path | None = None  # %APPDATA%\GameAssetHelper\ — v0.0.1 마이그레이션용

    def ensure_dirs(self) -> None:
```

new:
```python
    log_path: Path
    lock_path: Path

    def ensure_dirs(self) -> None:
```

- [ ] **Step 3: `default_app_paths` 의 legacy 자동 탐지 로직 + AppPaths 생성자 인자 제거**

Edit:

old:
```python
def default_app_paths(data_root: str | os.PathLike[str] | None = None) -> AppPaths:
    root = _resolve_data_root(data_root)
    legacy = None
    if data_root is None and not os.environ.get("GAH_DATA_DIR"):
        # 실 사용자 흐름에서만 legacy 검출 — explicit override 면 미사용
        legacy_root = Path(user_data_dir("GameAssetHelper", appauthor=False, roaming=True)).resolve()
        if legacy_root != root:
            legacy = legacy_root
    return AppPaths(
        data_dir=root,
```

new:
```python
def default_app_paths(data_root: str | os.PathLike[str] | None = None) -> AppPaths:
    root = _resolve_data_root(data_root)
    return AppPaths(
        data_dir=root,
```

old (AppPaths 생성 마지막 인자 + 사용 안 하는 import 정리):
```python
        log_path=root / "logs" / "assetcache.log",
        lock_path=root / "assetcache.lock",
        legacy_data_dir=legacy,
    )
```

new:
```python
        log_path=root / "logs" / "assetcache.log",
        lock_path=root / "assetcache.lock",
    )
```

- [ ] **Step 4: `user_data_dir` import 가 다른 곳에서 쓰이는지 확인**

```powershell
Select-String -Pattern "user_data_dir" -Path "src\assetcache\config.py"
```

남아있으면 (예: `_resolve_data_root` 안에서) 그대로 두기. legacy 호출만 제거했음.

- [ ] **Step 5: 회귀 확인**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`.

```powershell
pytest tests\test_config.py -v
```

Expected: 모두 통과. `legacy_data_dir` 가 사라졌으므로 그 field 를 검사하는 테스트가 있었으면 깨졌을 텐데, Task 2 에서 이미 마이그레이션 관련 테스트는 모두 삭제됐으므로 회귀 0.

- [ ] **Step 6: commit**

```bash
git commit -am "$(cat <<'EOF'
refactor(v011): config.py 의 legacy_data_dir 제거

AppPaths.legacy_data_dir field + default_app_paths 의 v0.0.1
GameAssetHelper 자동 탐지 로직 제거. 외부 사용자 0 확인 후 dead code.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Web app cleanup — `app.py`

**Files:**
- Modify: `src/assetcache/web/app.py`

- [ ] **Step 1: 현재 import + 등록 확인**

```python
# line 28-32
    labels_admin,
    library,
    migration as migration_router,
    packs,
    pages,
```

```python
# line 155-159
    app.include_router(projects_pages_router)       # M7 Phase 6 — 프로젝트 HTML 페이지
    app.include_router(settings_router.router)       # M8 — 설정 페이지
    app.include_router(migration_router.router)      # M10 — 마이그레이션 API
    app.include_router(updates_router.router)        # M10 — PyPI 업데이트 알림 API
```

- [ ] **Step 2: import 제거**

Edit:

old:
```python
    labels_admin,
    library,
    migration as migration_router,
    packs,
    pages,
```

new:
```python
    labels_admin,
    library,
    packs,
    pages,
```

- [ ] **Step 3: include_router 줄 제거**

Edit:

old:
```python
    app.include_router(settings_router.router)       # M8 — 설정 페이지
    app.include_router(migration_router.router)      # M10 — 마이그레이션 API
    app.include_router(updates_router.router)        # M10 — PyPI 업데이트 알림 API
```

new:
```python
    app.include_router(settings_router.router)       # M8 — 설정 페이지
    app.include_router(updates_router.router)        # M10 — PyPI 업데이트 알림 API
```

- [ ] **Step 4: 회귀 확인**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`.

- [ ] **Step 5: commit**

```bash
git commit -am "$(cat <<'EOF'
refactor(v011): web/app.py 의 migration router 등록 제거

routers import 1줄 + include_router 1줄 제거. /api/migration/*
endpoint 전면 비활성화.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Template cleanup — `base.html`

**Files:**
- Modify: `src/assetcache/web/templates/base.html`

- [ ] **Step 1: include 줄 확인**

Line 71: `{% include "_migration_banner.html" %}`

- [ ] **Step 2: 줄 제거**

Edit:

old:
```html
<body>
  {% include "_migration_banner.html" %}
  {% include "_pypi_update_banner.html" %}
  {% include "_nav.html" %}
```

new:
```html
<body>
  {% include "_pypi_update_banner.html" %}
  {% include "_nav.html" %}
```

- [ ] **Step 3: 회귀 확인**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`.

- [ ] **Step 4: commit**

```bash
git commit -am "$(cat <<'EOF'
refactor(v011): base.html 의 migration banner include 제거

Task 8 에서 _migration_banner.html 자체를 삭제하기 전에 참조부터
끊는다.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Dead module 3 파일 삭제

**Files (delete):**
- `src/assetcache/core/migration.py`
- `src/assetcache/web/routers/migration.py`
- `src/assetcache/web/templates/_migration_banner.html`

- [ ] **Step 1: 다른 곳에서 import 잔존 확인**

```powershell
Select-String -Pattern "from assetcache.core.migration|core\.migration|routers\.migration|_migration_banner" -Path "src\","tests\" -Include "*.py","*.html" -Recurse
```

Expected: 출력 0. Task 4/6/7 이후 모든 참조가 정리됐으면 여기는 안전.

만약 잔존 import 가 있으면 Task 2~7 중 빠뜨린 위치 → 정지 후 보강.

- [ ] **Step 2: 3 파일 git rm**

```powershell
git rm src\assetcache\core\migration.py src\assetcache\web\routers\migration.py src\assetcache\web\templates\_migration_banner.html
```

Expected: `rm 'src/assetcache/core/migration.py'` 등 3줄.

- [ ] **Step 3: 회귀 확인**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`. ImportError 가 나오면 Step 1 의 grep 이 놓친 참조 → 출력 살펴 보강.

- [ ] **Step 4: 부팅 smoke test (선택)**

```powershell
python -c "from assetcache.web.app import create_app; from assetcache.config import default_app_paths, load_config; p = default_app_paths(); p.ensure_dirs(); c = load_config(p.config_path); create_app(paths=p, config=c)"
```

Expected: stdout 출력 없음, exception 없음. FastAPI 앱이 정상 인스턴스화되면 OK.

- [ ] **Step 5: commit**

```bash
git commit -m "$(cat <<'EOF'
refactor(v011): migration/router/banner 모듈 3 파일 삭제

core/migration.py + web/routers/migration.py + templates/_migration_banner.html
일괄 삭제. 의존성은 Task 4~7 에서 모두 정리됨.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: i18n msgid 3건 제거 + .mo 재컴파일

**Files:**
- Modify: `src/assetcache/web/locale/ko/LC_MESSAGES/messages.po` (line 778-805 부근)
- Modify: `src/assetcache/web/locale/en/LC_MESSAGES/messages.po` (line 788-815 부근)
- Modify (regenerate): `src/assetcache/web/locale/messages.pot`
- Modify (regenerate): `src/assetcache/web/locale/{ko,en}/LC_MESSAGES/messages.mo`

- [ ] **Step 1: ko messages.po 의 3개 msgid 블록 제거**

각 블록은 다음 형식 (4-5줄):

```
#: src/assetcache/web/templates/_migration_banner.html:66
msgid "v0.0.1 data detected"
msgstr "v0.0.1 데이터를 발견했습니다"
```

Read `src/assetcache/web/locale/ko/LC_MESSAGES/messages.po`, 다음 3 블록 (각 `msgid` 와 `msgstr` 페어 + 앞의 `#:` reference comment 줄 + 빈 줄 1개) 제거:

1. msgid `"v0.0.1 data detected"`
2. msgid `"Copy"`
3. msgid `"Migrating..."`

Edit 시 정확한 reference comment + msgid + msgstr 3줄 + 직후 빈 줄을 함께 제거 (그렇지 않으면 빈 줄이 누적).

old (예시 — 첫 블록):
```

#: src/assetcache/web/templates/_migration_banner.html:66
msgid "v0.0.1 data detected"
msgstr "v0.0.1 데이터를 발견했습니다"

```

new (앞뒤 blank line 그대로, 본문 4 줄만 제거):
```

```

같은 방식으로 3 블록 모두 제거.

- [ ] **Step 2: en messages.po 의 동일 3 블록 제거**

같은 방식 — line 788~ 부근.

- [ ] **Step 3: messages.pot 재추출**

```powershell
pybabel extract -F babel.cfg -o src\assetcache\web\locale\messages.pot src\assetcache
```

Expected: stdout 마지막 줄 `extracting messages from src\assetcache\web\templates\... (skipping ...)` 또는 `writing PO template file to src\assetcache\web\locale\messages.pot`.

`_migration_banner.html` 는 이미 삭제됐으므로 pot 에 그 msgid 가 자동 빠짐.

- [ ] **Step 4: .mo 재컴파일**

```powershell
pybabel compile -d src\assetcache\web\locale -l ko -l en
```

Expected: stdout `compiling catalog src\assetcache\web\locale\ko\LC_MESSAGES\messages.po to src\assetcache\web\locale\ko\LC_MESSAGES\messages.mo` 등 2줄.

- [ ] **Step 5: 회귀 확인**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`.

```powershell
pytest tests\test_locale_assetcache_msgid.py -v
```

Expected: 4 case 모두 PASSED (Task 3 의 NEW_MSGIDS 2건 × 2 lang).

- [ ] **Step 6: commit**

```bash
git add src\assetcache\web\locale
git commit -m "$(cat <<'EOF'
i18n(v011): 마이그레이션 msgid 3건 제거 + .mo 재컴파일

ko/en messages.po 에서 'v0.0.1 data detected' / 'Copy' / 'Migrating...'
3 블록 제거. messages.pot pybabel extract 재생성. .mo pybabel compile
재생성.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: M10 rename 누락 fix — `mcp/server.py` FastMCP name

**Files:**
- Modify: `src/assetcache/mcp/server.py:96`

- [ ] **Step 1: 현재 줄 확인**

Line 96: `server = FastMCP("game-asset-helper", instructions=INSTRUCTIONS)`

- [ ] **Step 2: 이름 변경**

Edit:

old:
```python
    server = FastMCP("game-asset-helper", instructions=INSTRUCTIONS)
```

new:
```python
    server = FastMCP("assetcache-mcp", instructions=INSTRUCTIONS)
```

- [ ] **Step 3: 회귀 확인 — mcp_integration 포함**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`.

```powershell
pytest -m mcp_integration -v
```

Expected: 2 case (실 `python -m assetcache --mcp` subprocess + JSON-RPC 핸드셰이크 + 20 도구 응답) 모두 PASSED. server name 이 응답 metadata 에 포함되면 그 케이스에서 새 이름 `assetcache-mcp` 가 보임 — 다만 기존 테스트가 server name 을 검증하는지 확인. 검증 안 하면 PASSED 그대로.

만약 server name 을 hard-code 검증하는 테스트가 있으면 — 테스트도 함께 갱신 (`old "game-asset-helper"` → new `"assetcache-mcp"`) 후 commit. 

- [ ] **Step 4: commit**

```bash
git commit -am "$(cat <<'EOF'
fix(v011): mcp/server.py FastMCP server name → assetcache-mcp

M10 rename 누락 — Claude Code/Desktop 이 보는 MCP server 이름.
v0.1.1 publish 후 사용자는 클라이언트 reconnect 필요.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: M10 rename 누락 fix — `tools/setup_m6_test.py` 경로 안내

**Files:**
- Modify: `tools/setup_m6_test.py` (line 7, 57, 62)

- [ ] **Step 1: 현재 줄 확인**

```
line 7:  4. `%APPDATA%\\GameAssetHelper\\library\\<pack>\\` 에 PNG + JSON + pack.json 배치
line 57:    """%APPDATA%\\GameAssetHelper\\library 경로 반환."""
line 62:    return Path(base) / "GameAssetHelper" / "library"
```

- [ ] **Step 2: 3 줄 모두 갱신**

Edit (line 7 docstring):

old:
```
  4. `%APPDATA%\\GameAssetHelper\\library\\<pack>\\` 에 PNG + JSON + pack.json 배치
```

new:
```
  4. `%APPDATA%\\AssetCacheMCP\\library\\<pack>\\` 에 PNG + JSON + pack.json 배치
```

Edit (line 57):

old:
```python
    """%APPDATA%\\GameAssetHelper\\library 경로 반환."""
```

new:
```python
    """%APPDATA%\\AssetCacheMCP\\library 경로 반환."""
```

Edit (line 62):

old:
```python
    return Path(base) / "GameAssetHelper" / "library"
```

new:
```python
    return Path(base) / "AssetCacheMCP" / "library"
```

- [ ] **Step 3: 회귀 확인**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`. (tools 디렉터리는 test 에 포함 안 됨 — 영향 0)

- [ ] **Step 4: commit**

```bash
git commit -am "$(cat <<'EOF'
fix(v011): tools/setup_m6_test.py 경로 안내 → AssetCacheMCP

M10 rename 누락 — docstring + _appdata_library_dir() 의
%APPDATA%\GameAssetHelper\library 안내 3 군데 갱신.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: live 문서 v0.0.1 안내 제거 — README / CLAUDE / HANDOFF / DESIGN

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `HANDOFF.md`
- Modify: `DESIGN.md`

- [ ] **Step 1: README.md — 마이그레이션 안내 섹션 + 진행 현황 표 갱신**

README.md line 77 부근 `## 이전 v0.0.1 사용자 — 마이그레이션` 섹션 전체 제거. 끝 위치는 다음 `## ...` 헤더 직전.

Read `README.md` 로 정확한 구간 (line 77 부터 다음 헤더까지) 확인 후 Edit 으로 통째 제거.

또한 진행 현황 표 (line 46 부근) 의 M10 row 갱신:

old:
```
| **M10 — PyPI + AssetCacheMCP rename** | **🚧 in-flight** | `pipx install assetcache-mcp` + 마이그레이션 helper + PyPI 신버전 알림 |
```

new:
```
| M10 — PyPI + AssetCacheMCP rename | ✅ 완료 (main 머지) | `pipx install assetcache-mcp` + PyPI 신버전 알림 |
```

- [ ] **Step 2: README.md 회귀 — 다른 위치 잔존 grep**

```powershell
Select-String -Pattern "마이그레이션|--migrate|GameAssetHelper|legacy_data_dir" -Path README.md
```

Expected: 출력 0. 잔존이 있으면 그 줄도 함께 정리.

- [ ] **Step 3: CLAUDE.md — 마이그레이션 관련 위치 갱신**

다음 위치들 — Read 로 확인 후 Edit:

1. §1 의 "이 프로젝트는 M10 에서 ... rename 되었다. v0.0.1 사용자는 자동 마이그레이션 배너 또는 `assetcache --migrate=copy` 사용." 문장 → "이 프로젝트는 M10 에서 ... rename 되었다." 까지만 (마이그레이션 사용자 안내 1문장 제거)
2. §5 의 디렉터리 구조에서 `migration/` 디렉터리 노드 (3-4줄) 제거
3. §6 의 venv·런타임 데이터 항의 "M10 이전 v0.0.1 사용자는 `%APPDATA%\GameAssetHelper\` 가 잔존" 부분 → "v0.0.1 사용자는 외부 0 — 잔존 없음." 또는 그 문장 자체 제거
4. §7 자주 쓰는 명령의 "마이그레이션 (v0.0.1 → AssetCacheMCP, 헤드리스)" 블록 + 두 PowerShell 명령 통째 제거
5. §8 의 8.1/8.3 항에서 v0.0.1 마이그레이션 helper 언급 갱신 (`마이그레이션 helper 제공` 부분 제거)
6. §9 의 "알려진 이슈" 에 v0.0.1 마이그레이션 관련 있으면 제거 (현재 없음, 단 확인)

Read 로 줄 단위 확인 후 각 Edit 적용.

- [ ] **Step 4: HANDOFF.md — Phase 1 / 마이그레이션 소스 / --migrate 갱신**

다음 위치:

1. §2 의 표 의 "Phase 1 — 마이그레이션 helper" row 통째 제거 (또는 "Phase 1 — yagni-clean (v0.1.1 에서 제거됨)" 로 노트)
2. §3 의 표 "마이그레이션 소스 | `%APPDATA%\GameAssetHelper\` (v0.0.1 사용자 잔존, ...)" row 제거
3. §4 의 PowerShell 명령에 `--migrate` 가 있으면 제거
4. §7 의 후속 정리거리에서 v0.0.1 마이그레이션 관련 항 제거

또한 §1 의 한 줄 요약에서 "사용자 데이터 폴더 `%APPDATA%\GameAssetHelper\` → `%APPDATA%\AssetCacheMCP\` 자동 마이그레이션 helper 제공 (배너 + CLI)." 문장 통째 제거.

§2 의 회귀 수치 1103 도 그대로 두기 — historical (M10 완료 시점). 또는 끝에 "v0.1.1 yagni-clean 후 baseline 1082" 짧은 노트 추가 (Task 15 에서 마지막에).

- [ ] **Step 5: DESIGN.md — 마이그레이션 관련 위치**

Grep 결과 (이미 확인):

1. line 367 — `M10 이전 키 이름은 GameAssetHelper` 부분 → historical 이므로 그대로 유지 또는 갱신. live 문서 정책상 갱신: "M10 이전 키 이름은 `GameAssetHelper`" 가 historical fact 인데 design 문서가 history 까지 명시. 일관성 위해 그대로 두기 (Microsoft Windows autostart key 이름의 변천사).
2. line 936 — `query_json _schema_version 1` 의 `M5+ 마이그레이션 시 신호` → 무관 (검색 schema 마이그레이션). 그대로.
3. line 1044 — 디렉터리 구조 안내의 `# CLI 엔트리포인트 (--tray / --mcp / --version / --migrate)` 에서 `--migrate` 제거.
4. line 1051-1053 — `migration/` 디렉터리 항목 3-4줄 통째 제거.
5. line 1310 — `M10 부터 PyPI 가 1차 배포 채널이고 exe 는 2차` 그대로 유지.
6. line 1318+ — `Milestone 10 — PyPI 배포 + AssetCacheMCP rename + 마이그레이션` 섹션 — title 갱신: "Milestone 10 — PyPI 배포 + AssetCacheMCP rename". Phase 1 내용은 historical 이므로 본문 보존, 끝에 "v0.1.1 에서 yagni-clean — v0.0.1 외부 사용자 0 확인 후" 한 줄 추가.

Edit (line 1044):

old:
```
│       ├── __main__.py        # CLI 엔트리포인트 (--tray / --mcp / --version / --migrate)
```

new:
```
│       ├── __main__.py        # CLI 엔트리포인트 (--tray / --mcp / --version)
```

Edit (line 1051-1053 — migration/ 디렉터리 항목):

old:
```
│       ├── migration/         # M10 Phase 1 — v0.0.1 → AssetCacheMCP
│       │   ├── detect.py      # GameAssetHelper 후보 탐지
│       │   └── migrate.py     # copy/move + .migrated_from_v001 마커
```

new:
```
```
(빈 — 3 줄 통째 제거. 위·아래 디렉터리 항목과 자연스러운 들여쓰기 유지)

Edit (line 1318):

old:
```
### Milestone 10 — PyPI 배포 + AssetCacheMCP rename + 마이그레이션 (1.5~2주) 🚧 in-flight
```

new:
```
### Milestone 10 — PyPI 배포 + AssetCacheMCP rename (1.5~2주) ✅ 완료
```

- [ ] **Step 6: 회귀 확인 (회귀 영향 0 이지만 build 깨짐 방지 차원)**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`.

- [ ] **Step 7: commit**

```bash
git commit -am "$(cat <<'EOF'
docs(v011): README/CLAUDE/HANDOFF/DESIGN v0.0.1 마이그레이션 안내 제거

live 문서 4 종에서 v0.0.1 마이그레이션 helper / --migrate 명령 /
GameAssetHelper 경로 안내 / Phase 1 row 일괄 제거. historical
문서는 Task 13 에서 후기 노트만 추가.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: historical 문서 후기 노트 추가

**Files:**
- Modify: `milestones/M10_plan.md` (끝)
- Modify: `milestones/M10_todo.md` (끝)
- Modify: `milestones/M10_verification.md` (끝)
- Modify: `docs/superpowers/specs/2026-05-19-m10-pypi-and-rename-design.md` (끝)
- Modify: `docs/superpowers/plans/2026-05-19-m10-pypi-and-rename.md` (끝)

- [ ] **Step 1: 후기 노트 wording 통일**

각 파일 끝에 다음 한 단락 (1-2줄) 추가 — wording 통일:

```markdown

---

**2026-05-20 후기**: M10 Phase 1 의 v0.0.1 (GameAssetHelper) 데이터 폴더 마이그레이션 helper 는 v0.1.1 (`chore/v011-yagni-clean`) 에서 yagni-clean 됐다. v0.0.1 외부 사용자·다운로드 0 확인 후, 관련 코드 + 테스트 21건 + i18n msgid 3건 + 문서 안내 일괄 제거. 본 문서의 Phase 1 본문은 historical record 로 보존.
```

각 파일을 Read 로 끝 확인 후 Edit 으로 위 한 단락 append.

- [ ] **Step 2: M10_verification.md 의 시나리오 1~5 (마이그레이션 검증) 표시**

`milestones/M10_verification.md` 안의 시나리오 1~5 (마이그레이션 관련 사용자 검증) 가 어느 §인지 Read 로 확인. 각 시나리오 헤더에 "(v0.1.1 에서 dead code 제거 — 본 검증은 historical)" 짧은 prefix 또는 끝 노트 추가. 본문은 보존.

- [ ] **Step 3: 회귀 확인 (영향 0)**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`.

- [ ] **Step 4: commit**

```bash
git commit -am "$(cat <<'EOF'
docs(v011): M10 historical 문서에 v0.1.1 yagni-clean 후기 추가

milestones/M10_{plan,todo,verification}.md + docs/superpowers/{specs,plans}
의 M10 문서 5 종에 짧은 후기 한 단락 append. 본문은 historical record
로 보존.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Version bump 0.1.0 → 0.1.1

**Files:**
- Modify: `pyproject.toml:7`
- Modify: `src/assetcache/__init__.py:3`

- [ ] **Step 1: pyproject.toml version 갱신**

Edit:

old:
```toml
version = "0.1.0"
```

new:
```toml
version = "0.1.1"
```

- [ ] **Step 2: __init__.py __version__ 갱신**

Edit:

old:
```python
__version__ = "0.1.0"
```

new:
```python
__version__ = "0.1.1"
```

- [ ] **Step 3: 두 곳 동기화 확인**

```powershell
Select-String -Pattern "0\.1\.0|0\.1\.1" -Path "pyproject.toml","src\assetcache\__init__.py"
```

Expected:
```
pyproject.toml:7:version = "0.1.1"
src\assetcache\__init__.py:3:__version__ = "0.1.1"
```

- [ ] **Step 4: 회귀 확인 — version 검증 테스트**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected`.

```powershell
python -m assetcache --version
```

Expected: `assetcache-mcp 0.1.1`

- [ ] **Step 5: commit**

```bash
git commit -am "$(cat <<'EOF'
chore(v011): version 0.1.0 → 0.1.1

pyproject.toml + src/assetcache/__init__.py 두 곳 동시. v0.1.1
publish 대상. tag v0.1.1 push 후 Trusted Publishing 자동 publish.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: 최종 회귀 + MCP integration 검증

**Files:** (검증만)

- [ ] **Step 1: pytest 전체 회귀**

```powershell
pytest -q
```

Expected: `1082 passed, 1 skipped, 40 deselected in <60s>`

- [ ] **Step 2: MCP integration 옵트인**

```powershell
pytest -m mcp_integration -v
```

Expected: 2 case PASSED (실 `python -m assetcache --mcp` subprocess + JSON-RPC 핸드셰이크 + 20 도구 응답). FastMCP server name 이 `"assetcache-mcp"` 로 응답하는지 추가 확인.

- [ ] **Step 3: 트레이 부팅 smoke (사용자 수동 — 자동화 한계)**

```powershell
python -m assetcache --tray
```

수동 검증 (사용자):
- 마이그레이션 배너 → 안 보임
- PyPI 알림 배너 → 정상 (24h 캐시)
- 웹 (`http://127.0.0.1:9874`) 진입 → 배너 영역 PyPI 만
- 트레이 아이콘 우클릭 → 메뉴 정상

- [ ] **Step 4: CLI 검증**

```powershell
python -m assetcache --version
```

Expected: `assetcache-mcp 0.1.1`

```powershell
python -m assetcache --migrate=copy
```

Expected stderr: `assetcache: error: unrecognized arguments: --migrate=copy`

- [ ] **Step 5: branch 상태 + commit 카운트**

```powershell
git log --oneline main..HEAD
```

Expected: 약 14-15 commit (Task 1 시작 baseline 부터 Task 14 까지). spec commit + Task 2~14 = 13~14.

- [ ] **Step 6: 사용자에게 PR 준비 안내**

다음 명령은 사용자가 직접:

```powershell
git push -u origin chore/v011-yagni-clean
```

```powershell
gh pr create --base main --head chore/v011-yagni-clean --title "v0.1.1 — v0.0.1 호환 코드 yagni-clean" --body "$(cat docs/superpowers/specs/2026-05-20-v011-yagni-clean-v001-compat-design.md)"
```

또는 GitHub UI 에서 PR 생성. body 는 spec 의 §1 + §3 요약. release notes 는 PR 머지 후:

1. `git checkout main && git pull`
2. `git tag v0.1.1 && git push origin v0.1.1`
3. GitHub Actions Trusted Publishing 자동 publish → PyPI v0.1.1 확인
4. `pipx upgrade assetcache-mcp` 또는 `pip install --upgrade assetcache-mcp` 으로 client 환경 갱신
5. Claude Code/Desktop reconnect (FastMCP name 변경)

---

## 자기-점검 (계획 작성자)

**Spec coverage:**
- spec §3.1 (Dead code 8 파일) → Task 2 + Task 8 ✓
- spec §3.2 (부분 축소 6 파일) → Task 3, 4, 5, 6, 7, 9 ✓
- spec §3.3 (M10 rename 누락 2건) → Task 10, 11 ✓
- spec §3.4 (live 문서 4 종) → Task 12 ✓
- spec §3.5 (historical 후기 5 종) → Task 13 ✓
- spec §3.6 (version bump) → Task 14 ✓
- spec §6 검증 (자동 + 수동) → Task 15 ✓

**Placeholder 0** — TBD/TODO/"적절한 에러 처리"/"비슷한 방식" 없음.

**Type consistency** — 외부 API 명칭 (`FastMCP("assetcache-mcp", ...)`, `--migrate`, `legacy_data_dir`, `MIGRATION_MARKER`, `_run_migration_cli` 등) 모든 task 에서 동일 spelling.

**회귀 일관성** — 모든 task 의 expected `1082 passed, 1 skipped, 40 deselected` (Task 1 만 baseline `1103`). 도구 카운트 20 그대로 유지.
