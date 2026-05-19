# HANDOFF — Cowork → Claude Code (또는 다음 세션)

**마지막 인계 시각**: 2026-05-19 (M10 Phase 3 완료 — docs + i18n catalog + verification)
**마지막 완료 작업**: **M10 Phase 0~3** — rename mechanical + 마이그레이션 helper + PyPI 알림 (cherry-pick) + docs/i18n 정합성 + M10_verification.md
**M10 distribution 결정**: **PyPI 1순위** (`pipx install assetcache-mcp` 무료 cross-platform), SignPath 는 Option B
**M10 앱 이름 변경**: Game Asset Helper / `gah` → **AssetCacheMCP** / `assetcache-mcp` (PyPI) / `assetcache` (CLI) — Phase 0 에서 완료
**현재 worktree**: `D:\ClaudeCowork\game-asset-helper\game-asset-helper\.claude\worktrees\brave-tesla-80fb0e\`
**현재 브랜치**: `claude/brave-tesla-80fb0e` (main 위 31+ commits, **push 안 됨**)
**main 브랜치**: 마지막 commit `9069e55` (M9 plan + cover) — M9 이후 모든 변경은 worktree 위에만
**다음 세션 작업**: **M10 Phase 4 — PyPI 빌드 + 배포** (pyproject 최종 확정 + entry point + `python -m build` + TestPyPI + 정식 PyPI)

이 문서는 작업이 중단될 때 다음 세션이 "현재 어디까지 와 있는가"를 한 번에 파악하도록 작성된 스냅샷이다.

## 1. 한 줄 요약

M10 Phase 0~3 완료 (`claude/brave-tesla-80fb0e` worktree, **1103 passed + 1 skipped + 40 deselected**, MCP 20 도구 그대로). Phase 0 (rename `gah` → `assetcache` mechanical) + Phase 1 (`%APPDATA%\GameAssetHelper\` → `%APPDATA%\AssetCacheMCP\` 마이그레이션 helper: detect / copy / move + 웹 배너 + CLI `--migrate=copy|move` + i18n 10건) + Phase 2 (M9 cherry-pick: version / checker PyPI JSON API / pip_command 환경 분기 / web banner / tray Signal + i18n 4건) + Phase 3 (README/CLAUDE/HANDOFF/DESIGN 표기 일괄 갱신 + locale catalog 정합성 test + M10_verification.md). 다음 = Phase 4 (PyPI 빌드 + 배포).

## 2. 검증된 사실 (M10 Phase 0~3 완료 시점)

자동 — `pytest -q` 결과 **1103 passed + 1 skipped + 40 deselected** (M10 +57, baseline 1046)

| Phase | 핵심 산출물 | 신규 테스트 |
|---|---|---:|
| 0 — rename mechanical | `src/gah/` → `src/assetcache/` + 모든 import / config / babel.cfg / spec / docs 경로 | 0 (회귀만) |
| 1 — 마이그레이션 helper | `migration/detect.py` + `migration/migrate.py` (copy/move + `.migrated_from_v001` 마커) + 웹 배너 + SSE 진행률 + CLI `--migrate=copy|move` + i18n msgid 10건 | +37 |
| 2 — PyPI 알림 (M9 cherry-pick) | `updater/version.py` + `updater/checker.py` (PyPI JSON API + 캐시) + `updater/pip_command.py` (pipx/uv/pip 분기) + `web/routers/updates.py` 단순화 + `_pypi_update_banner.html` + tray 동적 메뉴 + i18n msgid 4건 | +10 |
| 3 — docs + i18n catalog + verification | README/CLAUDE/HANDOFF/DESIGN 표기 일괄 갱신 + `tests/test_locale_assetcache_msgid.py` (5 msgid × 2 lang = 10 instance) + `milestones/M10_verification.md` (수동 시나리오 7건) | +10 |
| **M10 Phase 0~3 전체** | **MCP 20 도구 그대로, 신규 의존성 0** | **+57** |

## 3. 환경 (재현용)

| 항목 | 값 |
|---|---|
| OS | Windows 10 (Mac/Linux 지원 M11 또는 별도 마일스톤에서) |
| Python | python.org 3.12 (`C:\Users\v0o0v\AppData\Local\Programs\Python\Python312\python.exe`) |
| venv | `C:\Users\v0o0v\.venvs\gah\` (이름은 그대로 유지) |
| 작업 폴더 | `D:\ClaudeCowork\game-asset-helper\game-asset-helper\.claude\worktrees\brave-tesla-80fb0e\` |
| 런타임 데이터 | `C:\Users\v0o0v\AppData\Roaming\AssetCacheMCP\` (M10 rename 후) |
| 라이브러리 루트 | `%APPDATA%\AssetCacheMCP\library\` |
| 메타 DB | `%APPDATA%\AssetCacheMCP\metadata.db` (WAL, M7 `unity_imports` / `projects` / `asset_usage` 확장 유지) |
| 마이그레이션 소스 | `%APPDATA%\GameAssetHelper\` (v0.0.1 사용자 잔존, `.migrated_from_v001` 마커로 idempotent) |
| **MCP 도구 수** | 20 도구 (M10 신규 0) |

**금기**: Microsoft Store Python, Cowork 작업 폴더 내부 venv.

M10 신규 의존성: 0 (Phase 2 의 httpx 는 M7 부터 기존).

## 4. 새 세션에서 바로 이어가는 방법

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```

```powershell
cd D:\ClaudeCowork\game-asset-helper\game-asset-helper\.claude\worktrees\brave-tesla-80fb0e
```

```powershell
git status
```

→ `claude/brave-tesla-80fb0e` 브랜치 상태. main 위 31+ commits.

```powershell
pytest -q
```

→ `1103 passed, 1 skipped, 40 deselected` (M10 Phase 0~3 누적).

## 5. 다음 세션 진입 절차 (M10 Phase 4 — PyPI 빌드 + 배포)

### 5.1 환경 복원

위 §4 와 동일.

### 5.2 Phase 4 진행 (`docs/superpowers/plans/2026-05-19-m10-pypi-and-rename.md §Phase 4`)

✅ **확정** (Phase 3 까지 완료, Phase 4 부터):
- **Task 4.1** — `pyproject.toml` 최종 확정 (name = `assetcache-mcp`, version = `0.1.0`, classifiers, deps, entry_points)
- **Task 4.2** — `assetcache-mcp` console_script entry point (`[project.scripts]` 또는 `[project.gui-scripts]`)
- **Task 4.3** — `python -m build` 로 sdist + wheel 생성 + 새 venv 에서 smoke
- **Task 4.4** — TestPyPI 업로드 (`twine upload --repository testpypi dist/*`) + `pipx install --index-url https://test.pypi.org/simple/ assetcache-mcp` 검증
- **Task 4.5** — 정식 PyPI 업로드 (`twine upload dist/*`)
- **Task 4.6** — GitHub Actions workflow (`.github/workflows/publish.yml`) — tag push → 자동 빌드 + 업로드

### 5.3 Phase 4 첫 작업 (5~10분)

1. `pypi.org/project/assetcache-mcp` 점유 확인 (점유 시 변형 검토 — 현재 plan 은 `assetcache-mcp` 가정)
2. PyPI 계정 + 2FA 활성화 확인 (없으면 등록)
3. TestPyPI 계정 별도 등록 + token 생성
4. `pyproject.toml` 작성 후 `python -m build` 로 wheel/sdist smoke
5. wheel local 설치 검증 (`pipx install ./dist/assetcache_mcp-0.1.0-py3-none-any.whl`) → `assetcache --version` 확인

### 5.4 다음 세션이 자동 로드하는 메모리

- [`project_m10_inflight_phase2_task21.md`](file://memory/project_m10_inflight_phase2_task21.md) — M10 Phase 0~2 in-flight 스냅샷
- [`project_v2_distribution_strategy.md`](file://memory/project_v2_distribution_strategy.md) — **PyPI 1순위 결정 + Mac 지원 의도 + 비용 분석**
- [`project_v2_rename_to_assetcachemcp.md`](file://memory/project_v2_rename_to_assetcachemcp.md) — **AssetCacheMCP rename 범위 + 마이그레이션**
- [`project_m9_pivot_state.md`](file://memory/project_m9_pivot_state.md) — **M9 implementation 완료 + 어느 모듈 재사용 가능한지**
- `project_v001_release_published.md` — v0.0.1 release 컨텍스트
- `feedback_ask_via_popup.md` — 질문은 AskUserQuestion popup 으로
- `feedback_korean_for_pr_and_commits.md` — 한글 PR/commit/docs
- `feedback_run_commands_directly.md` — Claude 가 자동화 가능 명령은 직접 실행
- `feedback_manual_verification_fixes.md` — 수동 검증 중 발견 fix 는 브랜치 누적

## 6. 마일스톤 정렬

| # | 이름 | 상태 |
|---:|---|---|
| M0~M8 | v1 (뼈대 ~ 패키징 + i18n) | ✅ 완료 (main 머지) |
| M9 | 코드 서명 + 자동 업데이트 | ⚠️ implementation 완료 / **머지 보류** (PyPI 채택으로 path pivot) |
| M10 | **PyPI + AssetCacheMCP rename** | 🚧 Phase 0~3 완료, Phase 4 (배포) 대기 |
| M11+ | Mac/Linux 검증 + 추후 | 📋 미정 |

v1 release: [v0.0.1 on GitHub](https://github.com/v0o0v/game-asset-helper/releases/tag/v0.0.1) (서명 X, SmartScreen 차단 해제 안내).

## 7. M10 보류 항목 / 후속

M10 backlog 의 다른 theme (UX 풍부화 / Unity import 확장 / 분석 정확도 등) 은 그대로 보류. Phase 4 끝나면 우선순위 재정렬.

- Pack/프로젝트 풍부 UX (메타 수정, manual_override, pin/block, 사용 분포 차트)
- 라이브러리 카드 직접 피드백 입력 UI
- 트레이 알림
- Pack/라벨 페이지 내 검색
- 새 axis 추가 UI
- 다중 Asset Store 캐시 경로
- UPM `.tgz` / scoped registry 임포트
- PSD/TGA 임포트
- publisher 패널 실제 HTTP 구현
- 자동 동기화 스케줄러
- 캐시에서 사라진 `.unitypackage` 자동 제거
- 사운드 임베딩 보조 (CLAP/PANNs)
- Ollama 오디오 안정성 모니터링
- 비균일 atlas 시트 지원
- 시트 frame size 입력 GUI
- Playwright E2E 테스트
- 추가 언어 (ja / zh)
- Mac/Linux 지원 (`sys.platform` 가드 + autostart 분기) — M11 후보
- MSI/NSIS 인스톨러 (Windows 캐주얼 사용자용 — PyPI 가 1차라 우선순위 낮음)
- get_active_project / set_active_project / get_project_preferences MCP 도구
- M9 의 코드 서명 (option B — SignPath 신청 docs 보존)
