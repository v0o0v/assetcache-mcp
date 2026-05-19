# v0.1.1 — v0.0.1 compat yagni-clean (design)

## 1. 배경

v0.0.1 (Game Asset Helper / `gah`) 은 [`docs/RELEASE_NOTES_v0.0.1.md`](../../RELEASE_NOTES_v0.0.1.md) 에 따라 [GitHub release v0.0.1](https://github.com/v0o0v/assetcache-mcp/releases/tag/v0.0.1) 이 published 되었으나, **실 외부 사용자·다운로드 0** (사용자 2026-05-26 확인).

따라서 M10 Phase 1 에서 만든 v0.0.1 데이터 폴더 마이그레이션 helper (`core/migration.py` + `web/routers/migration.py` + `_migration_banner.html` + `--migrate=copy|move` + 관련 +21 테스트 + i18n msgid 3건 + README/CLAUDE/HANDOFF 안내) 는 dead code. 같은 PR 에 M10 rename 누락 2건 (`mcp/server.py` 의 `FastMCP("game-asset-helper", ...)`, `tools/setup_m6_test.py` 의 `%APPDATA%\GameAssetHelper\` 경로 안내) 도 묶어 정리한다. v0.0.1 / `gah` / `GameAssetHelper` 잔재를 한 번에 제거하는 "yagni-clean v0.0.1 compat" patch.

이 patch 는 v0.1.1 publish 로 끝나며, Trusted Publishing (OIDC) 의 첫 자동 publish 검증도 겸한다.

## 2. 목표 / 비-목표

**목표**
1. 사용자 0 인 v0.0.1 호환 코드/테스트/문서/i18n msgid 일괄 제거
2. M10 rename 누락 2건 fix (FastMCP server name, M6 테스트 도구 경로 안내)
3. v0.1.1 tag push 로 Trusted Publishing 첫 자동 publish 검증

**비-목표**
- M10 Phase 2 의 PyPI 알림 helper (`core/updater/*`, `web/routers/updates.py`, `_pypi_update_banner.html`, tray `TrayController`) — 보존
- M10 historical 문서 (`milestones/M10_*`, `docs/superpowers/specs/2026-05-19-m10-*`, `docs/superpowers/plans/2026-05-19-m10-*`) 의 본문 — 보존 (마이그레이션이 v0.1.1 에서 yagni-clean 되었다는 짧은 후기만 추가)
- `docs/RELEASE_NOTES_v0.0.1.md` — historical, 그대로 유지
- 새 마일스톤 디렉터리 (`milestones/M11_*`) — 안 만듦. v0.1.1 은 patch 단위, spec/plan 만 작성

## 3. 범위

### 3.1 Dead code (완전 삭제)

| 경로 | 비고 |
|---|---|
| `src/assetcache/core/migration.py` | 전체 (197 lines) |
| `src/assetcache/web/routers/migration.py` | 전체 (101 lines) |
| `src/assetcache/web/templates/_migration_banner.html` | 전체 |
| `tests/test_migration_detect.py` | 전체 (6 tests) |
| `tests/test_migration_runner.py` | 전체 (6 tests) |
| `tests/test_migration_path_rewrite.py` | 전체 (3 tests) |
| `tests/test_migration_router.py` | 전체 (3 tests) |
| `tests/test_cli_migrate.py` | 전체 (2 tests) |

합계 **-20 테스트** (Task 2 collect-only 실측 = 5 파일 본체 20 tests, plan 초안의 -21 가정 정정).

### 3.2 부분 축소 (live 코드)

| 파일 | 변경 |
|---|---|
| `src/assetcache/__main__.py` | `--migrate`/`--legacy-data-dir` argparse 옵션 + `_run_migration_cli` 함수 + `EXIT_MIGRATION_FAILED` 상수 + `main()` 의 `if args.migrate:` 분기 제거 |
| `src/assetcache/config.py` | `AppPaths.legacy_data_dir` field + `default_app_paths` 의 legacy 자동 탐지 로직 제거. `user_data_dir("GameAssetHelper", ...)` 호출도 제거 |
| `src/assetcache/web/app.py` | `migration as migration_router` import + `app.include_router(migration_router.router)` 1줄 제거 |
| `src/assetcache/web/templates/base.html` | `{% include "_migration_banner.html" %}` 1줄 제거 (line 71) |
| `src/assetcache/web/locale/{ko,en}/LC_MESSAGES/messages.po` | Phase 1.7 msgid 3건 (`"v0.0.1 data detected"`, `"Copy"`, `"Migrating..."`) 제거. PyPI 알림 2건 (`"available"`, `"Upgrade command copied to clipboard"`) 유지 |
| `src/assetcache/web/locale/messages.pot` | `pybabel extract` 재추출 |
| `src/assetcache/web/locale/{ko,en}/LC_MESSAGES/messages.mo` | `pybabel compile` 재컴파일 |
| `tests/test_locale_assetcache_msgid.py` | `NEW_MSGIDS` 의 마이그레이션 3건 제거. parametrize 10 → 4 case (-6 실 회귀) |

### 3.3 M10 rename 누락 fix

| 파일 | 변경 |
|---|---|
| `src/assetcache/mcp/server.py:96` | `FastMCP("game-asset-helper", ...)` → `FastMCP("assetcache-mcp", ...)`. MCP client (Claude Code/Desktop) 가 보는 서버 이름. 도구 prefix `mcp__assetcache-mcp__*` 로 변경됨 — release notes 에 reconnect 안내 |
| `tools/setup_m6_test.py` | line 7 docstring + line 57/62 `_appdata_library_dir()` 함수의 `"GameAssetHelper"` → `"AssetCacheMCP"` 치환 |

### 3.4 live 문서 (완전 제거)

| 파일 | 변경 |
|---|---|
| `README.md` | 마이그레이션 안내 섹션 + 진행 현황 표의 v0.0.1 마이그레이션 row + `--migrate` 명령 |
| `CLAUDE.md` | §1 v0.0.1 마이그레이션 helper 언급, §5 디렉터리 구조의 `migration/`, §6 진행 현황 표의 M10 description, §7 `--migrate=copy|move`, §8 v0.0.1 사용자 데이터, §9 알려진 이슈의 v0.0.1 관련 |
| `HANDOFF.md` | §2 Phase 1 row, §3 마이그레이션 소스 row + `legacy_data_dir`, §4 `--migrate`, §7 후속 정리거리의 v0.0.1 관련 |
| `DESIGN.md` | 마이그레이션 관련 언급 (있는 경우) |

### 3.5 historical 문서 (후기 노트만 추가, 본문 보존)

다음 파일들은 시점의 결정 기록이므로 본문 보존, 끝에 한 줄 후기만 추가:

| 파일 | 후기 |
|---|---|
| `milestones/M10_plan.md` | "Phase 1 데이터 폴더 마이그레이션 helper 는 v0.1.1 (2026-05-26) 에서 yagni-clean — v0.0.1 외부 사용자 0 확인 후" |
| `milestones/M10_todo.md` | 동일 |
| `milestones/M10_verification.md` | 동일 + 시나리오 1~5 (마이그레이션 검증) 옆에 "v0.1.1 에서 dead code 제거 — 본 검증은 historical" 노트 |
| `docs/superpowers/specs/2026-05-19-m10-pypi-and-rename-design.md` | 동일 |
| `docs/superpowers/plans/2026-05-19-m10-pypi-and-rename.md` | 동일 |

### 3.6 release / 버전

| 파일 | 변경 |
|---|---|
| `pyproject.toml` | `version = "0.1.0"` → `"0.1.1"` |
| `src/assetcache/__init__.py` | `__version__ = "0.1.0"` → `"0.1.1"` |

## 4. 작업 순서 (TDD-friendly)

1. main 동기화 (`git pull`) → 회귀 baseline 확인 (`pytest -q` → **1103 passed + 1 skipped + 40 deselected**)
2. branch checkout `chore/v011-yagni-clean` (이미 완료)
3. 이 spec commit
4. **삭제 phase** — test 5 파일 일괄 삭제 + i18n test 갱신 → `pytest -q` → **1077 passed** (회귀 정확히 -26 신호)
5. **부분 축소 phase** — commit 단위 (each ≤ 1 file group):
   - CLI: `__main__.py` cleanup
   - Config: `config.py` cleanup
   - Web app: `app.py` router unregister
   - Template: `base.html` include 제거
   - Migration module 삭제: `core/migration.py`
   - Router module 삭제: `web/routers/migration.py`
   - Banner template 삭제: `_migration_banner.html`
   - 각 commit 후 `pytest -q` 회귀 확인
6. **i18n phase** — msgid 3건 제거 + `pybabel extract` + `pybabel compile` → `pytest -q`
7. **M10 rename fix phase** — `mcp/server.py` + `tools/setup_m6_test.py` → `pytest -q` + `pytest -m mcp_integration` (FastMCP name 변경 영향 확인)
8. **문서 phase** — live 완전 제거 (한 commit) + historical 후기 추가 (한 commit)
9. **version bump** — `pyproject.toml` + `__init__.py` → commit
10. **회귀 최종** — `pytest -q` → 1077 passed + 1 skipped + 40 deselected; `pytest -m mcp_integration` 통과
11. **PR 준비** — push, PR 생성, merge, tag v0.1.1 push 는 사용자가 직접 수행 (사용자 메모: 수동 검증·푸시·머지는 사용자 책임)

## 5. 위험 / 주의사항

- **FastMCP server name 변경**: Claude Code/Desktop 에 이미 등록된 MCP 도구의 prefix 가 `mcp__game-asset-helper__*` → `mcp__assetcache-mcp__*` 로 바뀐다. 단 v0.0.1 사용자 0, v0.1.0 publish 1일째라 외부 영향 거의 0. release notes 에 "MCP 클라이언트 reconnect 필요" 명시.
- **`tools/setup_m6_test.py` 경로 안내 갱신**: 사용자만 사용하는 도구. 갱신 후 사용자가 새 경로 (`%APPDATA%\AssetCacheMCP\library`) 로 다시 작업 폴더 선택.
- **Babel 재추출**: `babel.cfg` 변경 0 이라 새 문자열 추출 0. 단순 cleanup.
- **회귀 목표 -26**: baseline 1077 가 새 baseline. 다음 patch 가 이 baseline 기준이라 정확히 떨어져야.
- **historical 문서 후기 노트**: 짧게, 본문 보존. 검증 시점의 사실을 왜곡하지 않음.

## 6. 검증

**자동** — `pytest -q` → **1077 passed + 1 skipped + 40 deselected**. `pytest -m mcp_integration` → 2 cases pass (FastMCP name `assetcache-mcp` 인식 + 20 도구 카운트 유지).

**수동** (사용자):
1. 트레이 부팅 (`python -m assetcache --tray`) → 마이그레이션 배너 안 보임 + PyPI 알림 배너만 정상
2. 웹 (`http://127.0.0.1:9874`) 진입 → 배너 영역 PyPI 만
3. CLI `python -m assetcache --version` → `assetcache-mcp 0.1.1`
4. CLI `python -m assetcache --migrate=copy` → `unrecognized arguments: --migrate=copy` (예상 에러)
5. Claude Code/Desktop 에서 reconnect → 도구 prefix `mcp__assetcache-mcp__*` (또는 사용자 `mcpServers` key 그대로)
6. PR 머지 후 `git tag v0.1.1 && git push origin v0.1.1` → GitHub Actions Trusted Publishing 자동 publish → [PyPI v0.1.1](https://pypi.org/project/assetcache-mcp/) 확인 + `pipx upgrade assetcache-mcp` 검증

## 7. 다음

v0.1.1 publish 후:
- M11 후보 (Mac/Linux 정식 검증) — 사용자 환경 준비 시 별도 마일스톤
- v0.1.2 patch — 사용자 피드백 누적 시
