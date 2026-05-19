# HANDOFF — Cowork → Claude Code (또는 다음 세션)

**마지막 인계 시각**: 2026-05-19 (M9 implementation 완료 + path pivot — SignPath → PyPI 우선)
**마지막 완료 작업**: **M9 — 코드 서명 + 자동 업데이트** implementation (17 task, 1111 tests, code review APPROVED-AFTER-DOGFOOD) — 단 PyPI 채택으로 **머지 보류**
**v2 distribution 결정**: **PyPI 1순위** (`pipx install <pkg>` 무료 cross-platform), SignPath 는 Option B
**v2 앱 이름 변경**: Game Asset Helper / `gah` → **AssetCacheMCP** / `assetcache-mcp` (PyPI) / `assetcache` (CLI)
**현재 브랜치**: `feat/m9-code-signing-and-auto-update` (main 위 21 commits, **push 안 됨**, **main 머지 보류**)
**main 브랜치**: 마지막 commit `9069e55` (M9 plan + cover) — 그 이후 모든 변경은 feat/m9 위에만
**다음 세션 작업**: **새 마일스톤 (M10?) — PyPI + rename to AssetCacheMCP** spec/plan/implementation

이 문서는 작업이 중단될 때 다음 세션이 "현재 어디까지 와 있는가"를 한 번에 파악하도록 작성된 스냅샷이다.

## 1. 한 줄 요약

M9 implementation 완료 (`feat/m9-code-signing-and-auto-update` 21 commits, **1111 passed + 1 skipped + 40 deselected**, MCP 20 도구 그대로, 회귀 0). 코드 리뷰 결과 **APPROVED-AFTER-DOGFOOD** (Critical 0, Important 3, Minor 4). 그러나 직후 사용자가 **Mac 지원 의도 + SmartScreen 우회 + 비용 최소화** 관점에서 path 재고 → **PyPI 1순위** 결정. SignPath 신청은 보류 (신청 초안만 `docs/SIGNPATH_APPLICATION.md` + `docs/CODE_SIGNING_POLICY.md` 에 작성 — option B 보존). 다음 세션 = 새 마일스톤으로 **PyPI 배포 + AssetCacheMCP rename** 시작.

## 2. 검증된 사실 (M9 완료 시점)

자동 — `pytest -q` 결과 **1111 passed + 1 skipped + 40 deselected** (M9 +65, baseline 1046)

| Phase | 핵심 산출물 | 신규 테스트 |
|---|---|---:|
| 0 — SignPath 신청 + RELEASE_BUILD_GUIDE | `docs/RELEASE_BUILD_GUIDE.md` (7단계 절차) | 0 |
| 1 — Checker + Version | Config `[update]` + `version.py` semver-lite + `UpdateChecker.check_once` + `PollingLoop` | +24 |
| 2 — Downloader + Installer | `UpdateDownloader` (httpx stream + SHA256) + `UpdateInstaller` (STEP 1/2/3) + ctypes `wait_for_pid` + `__main__ --complete-update` | +24 |
| 3 — Web UI | `/api/updates/{check,start,status,install}` + SSE + `_update_banner.html` + i18n msgid +8 + base.html 통합 | +12 |
| 4 — 트레이 | `tray.py` 동적 메뉴 + Qt Signal cross-thread 마샬링 | +4 |
| 5 — 검증 + 문서 + dogfood prep | `M9_verification.md` (6 시나리오) + README §배포 갱신 + v0.0.2 version bump + RELEASE_NOTES_v0.0.2.md | 0 |
| 후속 — SignPath 신청 docs | `docs/SIGNPATH_APPLICATION.md` + `docs/CODE_SIGNING_POLICY.md` | 0 |
| **M9 전체** | **MCP 20 도구 그대로, 신규 의존성 1 (`respx>=0.20` dev)** | **+64~65** |

## 3. 환경 (재현용)

| 항목 | 값 |
|---|---|
| OS | Windows 10 (Mac/Linux 지원 v3 또는 별도 마일스톤에서) |
| Python | python.org 3.12 (`C:\Users\v0o0v\AppData\Local\Programs\Python\Python312\python.exe`) |
| venv | `C:\Users\v0o0v\.venvs\gah\` |
| 작업 폴더 | `D:\ClaudeCowork\game-asset-helper\game-asset-helper\` |
| 런타임 데이터 | `C:\Users\v0o0v\AppData\Roaming\GameAssetHelper\` (rename 후 `AssetCacheMCP\`) |
| 라이브러리 루트 | `%APPDATA%\GameAssetHelper\library\` |
| 메타 DB | `%APPDATA%\GameAssetHelper\metadata.db` (WAL, M7 에서 `unity_imports` / `projects` / `asset_usage` 확장) |
| **MCP 도구 수** | 20 도구 (M9 신규 0 — 업데이트는 사용자 UX 영역) |

**금기**: Microsoft Store Python, Cowork 작업 폴더 내부 venv.

M9 신규 의존성: `respx>=0.20` (dev — httpx mock).

## 4. 새 세션에서 바로 이어가는 방법

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```

```powershell
cd D:\ClaudeCowork\game-asset-helper\game-asset-helper
```

```powershell
git status
```

→ feat/m9 브랜치 상태. **main 으로 checkout 후 작업 시작 권장** (M9 는 보존, 신규 마일스톤은 main 위에 분기).

```powershell
git checkout main
```

```powershell
pytest -q
```

→ `1046 passed, 1 skipped, 40 deselected` (main 기준, M9 의 +65 는 feat/m9 에만).

## 5. 다음 세션 진입 절차 (v2 PyPI + rename)

### 5.1 환경 복원

위 §4 와 동일.

### 5.2 결정 (v2 distribution + rename)

✅ **확정** (다음 세션은 이 결정에서 시작):
- **PyPI 1순위** — `pipx install assetcache-mcp` 또는 `uv tool install assetcache-mcp` 로 cross-platform 배포
- **앱 이름** — `AssetCacheMCP` (display) / `assetcache-mcp` (PyPI) / `assetcache` (CLI)
- **Package dir** — `src/gah/` → `src/assetcache/`
- **데이터 폴더** — `%APPDATA%\GameAssetHelper\` → `%APPDATA%\AssetCacheMCP\` (v0.0.1 사용자 마이그레이션 helper 필요)
- **SignPath** — 보류 (option B). 신청 docs 는 feat/m9 에 보존 (`docs/SIGNPATH_APPLICATION.md` + `docs/CODE_SIGNING_POLICY.md`)
- **M9 코드** — feat/m9 보존. PyPI 흐름에 맞게 일부 모듈 (version / checker / web banner / tray Signal) 재사용, Installer / swap / --complete-update 는 drop. 자세한 retain/drop 표는 [memory project-m9-pivot-state](file://memory/project_m9_pivot_state.md)

### 5.3 다음 세션 첫 작업 (5~10분)

1. `git checkout main` (M9 branch 보존)
2. `pypi.org/project/assetcache-mcp` 점유 확인 (점유 시 변형: `assetcache`, `asset-cache-mcp`, `assetcachemcp`, etc.)
3. PyPI 계정 + 2FA 활성화 확인 (없으면 등록)
4. `superpowers:brainstorming` 으로 새 spec 시작 — 범위는 사용자와 합의:
   - PyPI 패키지 + entry point 셋업
   - 이름 rename 작업 (1~2일 mechanical)
   - v0.0.1 사용자 마이그레이션 helper (`%APPDATA%\GameAssetHelper\` → `%APPDATA%\AssetCacheMCP\`)
   - M9 모듈 cherry-pick / refactor / drop
   - Mac/Linux 지원 범위 (v2 에 포함 vs 별도 마일스톤)
5. spec → plan → subagent-driven-development 흐름

### 5.4 다음 세션이 자동 로드하는 메모리

- [`project_v2_distribution_strategy.md`](file://memory/project_v2_distribution_strategy.md) — **PyPI 1순위 결정 + Mac 지원 의도 + 비용 분석**
- [`project_v2_rename_to_assetcachemcp.md`](file://memory/project_v2_rename_to_assetcachemcp.md) — **AssetCacheMCP rename 범위 + 마이그레이션**
- [`project_m9_pivot_state.md`](file://memory/project_m9_pivot_state.md) — **M9 implementation 완료 + 어느 모듈 재사용 가능한지**
- `project_v001_release_published.md` — v0.0.1 release 컨텍스트
- `feedback_ask_via_popup.md` — 질문은 AskUserQuestion popup 으로 (2026-05-19 사용자 명시)
- `feedback_korean_for_pr_and_commits.md` — 한글 PR/commit/docs
- `feedback_run_commands_directly.md` — Claude 가 자동화 가능 명령은 직접 실행

## 6. 마일스톤 정렬 (v1 완료, v2 in progress)

| # | 이름 | 상태 |
|---:|---|---|
| M0~M8 | v1 (뼈대 ~ 패키징 + i18n) | ✅ 완료 (main 머지) |
| M9 | 코드 서명 + 자동 업데이트 | ⚠️ implementation 완료 / **머지 보류** (PyPI 채택으로 path pivot) |
| **다음** | **PyPI + AssetCacheMCP rename** (M10? 또는 v2.0) | 📋 spec 작성 대기 |

v1 release: [v0.0.1 on GitHub](https://github.com/v0o0v/game-asset-helper/releases/tag/v0.0.1) (서명 X, SmartScreen 차단 해제 안내).

## 7. v2 보류 항목 (PyPI / rename 외)

v2 backlog 의 다른 theme (UX 풍부화 / Unity import 확장 / 분석 정확도 등) 은 그대로 보류. PyPI + rename 끝나면 우선순위 재정렬.

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
- Mac/Linux 지원 (`sys.platform` 가드 + autostart/installer 분기)
- MSI/NSIS 인스톨러 (Windows 캐주얼 사용자용 — 단 PyPI 가 우선이라 우선순위 낮음)
- get_active_project / set_active_project / get_project_preferences MCP 도구
- M9 의 코드 서명 + 자동 업데이트 (option B — SignPath 신청 docs 보존)
