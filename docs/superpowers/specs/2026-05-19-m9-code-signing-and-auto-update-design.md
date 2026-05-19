# M9 — 코드 서명 + 자동 업데이트 design

**작성일**: 2026-05-19
**대상 마일스톤**: M9 (v2 첫 마일스톤, M0~M8 다음)
**선행 마일스톤**: M8 (패키징 + i18n, v0.0.1 release published)
**예상 일정**: ~3주 + SignPath 심사 대기 (수일~수주)
**예상 신규 테스트**: +50 (1046 → ~1096)
**예상 신규 의존성**: 0건

---

## 1. 동기

v0.0.1 첫 GitHub release ([release page](https://github.com/v0o0v/game-asset-helper/releases/tag/v0.0.1)) 가 publish 된 직후 사용자가 마주하는 두 가지 진입 장벽을 해결한다:

1. **Windows SmartScreen 경고** — 코드 서명 인증서 미적용 → "Windows에서 PC 보호" 경고. 현재 release notes 가 "추가 정보 → 실행" 우회 안내를 포함하지만, 사용자 신뢰도 ↓, 첫 onboarding 마찰 ↑.
2. **수동 업데이트** — 사용자가 매번 GitHub release 페이지를 방문해 새 버전 다운로드 + 재설치해야 함. 점진 release (v0.0.2 / v0.1.0) 가 이어질수록 누적 마찰.

두 문제는 결합되어 있다 — 서명된 빌드를 자동으로 받아야 자동 업데이트가 의미 있다 (서명 없는 새 버전을 받으면 또 SmartScreen). 한 spec 에 묶어 해결한다.

## 2. 핵심 결정사항 요약

| 결정 | 선택 | 근거 |
|---|---|---|
| 코드 서명 인증서 | **SignPath Foundation OSS 무료 프로그램** | MIT 라이선스 + 공개 repo 적격. 직접 비용 $0. Stellarium / Flameshot / GitExtensions 등 선례 |
| 업데이트 클라이언트 | **자체 구현** (GitHub Releases API + httpx + 기존 UI 통합) | GAH 의 FastAPI/Alpine/HTMX/PySide6 패턴과 일관. 의존성 0. WinSparkle/PyUpdater 비채택 |
| 업데이트 정책 | **알림만** (사용자 동의 후 진행) | 사용자 통제력 확보. v2 첫 iteration 에 적절. 백그라운드 자동 다운로드는 다음 iteration 검토 |
| 배포 채널 | **GitHub Releases** | bandwidth 무제한 + 무료, v0.0.1 이미 이 채널 사용 |
| swap 패턴 | **Self `--complete-update` mode + ctypes wait_for_pid** | 외부 stub 파일 0, 단일 exe 내 로직 격리. PowerShell stub / cmd stub 비채택 |
| 폴링 주기 | **24h** | API rate limit 안전 (60 req/hr unauthenticated 한도 안에서 사용자당 1/day) |
| 버전 비교 | **자체 구현 semver-lite** (~20줄) | `0.0.1` / `0.0.2` / `0.1.0` / `1.0.0` 처리 충분. `semver` lib 의존 안 만듦 |

**비채택 사유**:
- Azure Trusted Signing / EV 인증서 → 비용 발생, SignPath 무료로 충분
- WinSparkle → DLL 번들 필요, 네이티브 다이얼로그가 GAH 웹 UI 와 분리
- PyUpdater → 활성 개발 종료
- 외부 helper exe (gah-updater.exe) → 별도 binary ~50MB 추가, 첫 셋업 비용 큼
- 백그라운드 자동 다운로드 정책 → 사용자 통제력 약화, 첫 iteration 미적용

## 3. 아키텍처

```
GameAssetHelper.exe  (signed by SignPath Foundation OSS cert)
├─ Tray (PySide6 QSystemTrayIcon)
│   ├─ "메인 창 열기"
│   ├─ "업데이트 확인"                ← 신규 (수동 트리거)
│   ├─ "v0.0.2 업데이트 가능 →"        ← 신규 (동적, 새 버전 감지 시만 표시)
│   ├─ "윈도 시작 시 자동 실행"
│   └─ "종료"
│
├─ FastAPI web server (port 9874)
│   ├─ 기존: /library /packs /labels/admin /settings ...
│   └─ 신규:
│       /api/updates/check       (GET, HTMX poll, 상태 JSON 반환)
│       /api/updates/start       (POST, 다운로드 시작)
│       /api/updates/status      (GET, SSE 진행률 스트림)
│   └─ base.html 상단 _update_banner.html partial (Alpine x-show)
│
└─ src/gah/core/updater/        ← 신규 패키지
    ├─ __init__.py
    ├─ checker.py        (UpdateChecker, GitHub API + polling thread)
    ├─ version.py        (semver-lite 비교)
    ├─ downloader.py     (UpdateDownloader, httpx stream + SHA256)
    └─ installer.py      (UpdateInstaller, swap 패턴 + --complete-update 모드)

         │ (1) GET /repos/v0o0v/game-asset-helper/releases/latest
         ▼
   GitHub Releases API  (unauthenticated, 60 req/hr 한도)
         │
         │ (2) asset 다운로드: GameAssetHelper.exe + body 의 SHA256
         ▼
   %APPDATA%\GameAssetHelper\update\GameAssetHelper.new.exe
         │
         │ (3) swap + 새 exe 재시작 (--complete-update 모드)
         ▼
   서명된 새 버전 부팅 — 사용자 시점 끊김 없음
```

## 4. 모듈 / 컴포넌트

### 신규 / 수정 파일

| 파일 | 변경 | 비고 |
|---|---|---|
| `src/gah/core/updater/__init__.py` | **신규** | 패키지 entry |
| `src/gah/core/updater/checker.py` | **신규** | `UpdateChecker` 클래스 + polling thread |
| `src/gah/core/updater/version.py` | **신규** | semver-lite 파싱 + 비교 (~20줄) |
| `src/gah/core/updater/downloader.py` | **신규** | `UpdateDownloader` (httpx stream, SHA256, 진행률 콜백) |
| `src/gah/core/updater/installer.py` | **신규** | `UpdateInstaller` (swap 패턴 STEP 1~3, `--complete-update` 모드) |
| `src/gah/__main__.py` | 수정 | `--complete-update --old-pid <pid>` 인자 처리 |
| `src/gah/web/routers/updates.py` | **신규** | `/api/updates/{check,start,status}` |
| `src/gah/web/templates/_update_banner.html` | **신규** | Alpine partial — 배너 + "지금 업데이트" / "나중에" |
| `src/gah/web/templates/base.html` | 수정 | `{% include "_update_banner.html" %}` 상단 추가 |
| `src/gah/tray.py` | 수정 | "업데이트 확인" 액션 + 동적 "vX.X.X 업데이트 가능" 메뉴 |
| `src/gah/config.py` | 수정 | 신규 `[update]` 섹션 (release_repo / check_interval_hours / enabled) |
| `src/gah/app.py` | 수정 | 부팅 시 UpdateChecker thread 시작 (`update.enabled=true` 일 때) |
| `src/gah/web/locale/{ko,en}/LC_MESSAGES/messages.po` | 수정 | 신규 msgid ~10건 (배너 / 트레이 / 진행률 / 에러) |
| `gah.spec` | 변경 없음 | SignPath 는 빌드된 exe 를 post-build 외부 서명 (클라우드 업로드) 흐름이라 spec 자체는 미변경. 만약 PyInstaller 의 `version_info` 메타데이터 (CompanyName 등) 가 SignPath 자격 심사에 필요하면 그때 추가 |
| `docs/RELEASE_BUILD_GUIDE.md` | **신규** | SignPath 클라우드 서명 + release 절차 단계별 |
| `README.md` | 수정 | §배포 갱신 (서명 흐름 포함) |

### 신규 Config 필드

```toml
[update]
release_repo = "v0o0v/game-asset-helper"   # GitHub <owner>/<repo>
check_interval_hours = 24                  # 폴링 주기 (1 이상)
enabled = true                             # /settings 에서 off 가능
```

**기본값 정책**: `enabled=true`, `check_interval_hours=24`. 사용자가 명시적으로 끄지 않는 한 부팅 시 폴링 thread 시작.

### 신규 의존성

**0건**. 활용 가능한 기존:
- `httpx` — GitHub API + asset 다운로드
- `FastAPI` + `sse-starlette`(M5) — `/api/updates/status` SSE
- `PySide6` — 트레이 동적 메뉴 (signal/slot)
- `ctypes` (Python 표준) — Windows `OpenProcess` + `WaitForSingleObject` (PID wait)
- 기존 logging / Config 인프라

## 5. Data flow

### 5.1 폴링 흐름 (정상 path)

```
부팅 시 (app.py) + check_interval_hours 주기
  ↓
UpdateChecker.run()  [QThread or threading.Thread, daemon=True]
  ↓
  httpx GET https://api.github.com/repos/{release_repo}/releases/latest
       Accept: application/vnd.github.v3+json
       (unauthenticated, no PAT)
  ↓
  parse: tag_name (예: "v0.0.2"), assets[].browser_download_url (.exe), body 에서 SHA256 추출
  ↓
  version.compare(parsed("0.0.2"), __version__("0.0.1"))
  ↓
       <= 0 (같거나 더 낮음) → 다음 주기까지 idle
       > 0 → AvailableUpdate state 저장
              ├─ Qt signal "updateAvailable" emit → 트레이 메뉴 갱신
              └─ 다음 /api/updates/check 호출에서 detected=True 응답
```

### 5.2 SHA256 출처

**채택**: release asset 으로 `GameAssetHelper.exe.sha256` 파일을 exe 와 함께 업로드. UpdateChecker 가 두 asset URL 호출 (exe + .sha256). 코드 명확, 파싱 정규식 불필요.

릴리즈 절차에서 `sha256sum dist/GameAssetHelper.exe > dist/GameAssetHelper.exe.sha256` 후 `gh release create v0.0.2 dist/GameAssetHelper.exe dist/GameAssetHelper.exe.sha256 ...`. `docs/RELEASE_BUILD_GUIDE.md` 에 명시.

**비채택 — release body 파싱**: body 에 `🤖 SHA256: <hash>` 추가 + 정규식 추출. 사람이 body 편집 시 깨질 위험 + 추출 코드 추가. 채택안이 단순.

### 5.3 사용자 알림 → 클릭 → 다운로드

```
[알림]
  - 트레이 메뉴: "v0.0.2 업데이트 가능 →" 항목 (클릭 시 웹 UI /library 로 이동 + 배너 강조)
  - 웹 UI base.html 상단 배너 (Alpine x-show, x-data updateBanner):
      "🎉 v0.0.2 가 나왔습니다. [지금 업데이트] [나중에]"

[클릭 → /api/updates/start]
  POST /api/updates/start
  ↓
  서버: UpdateDownloader.start() 별도 thread 로 비동기 시작
  응답: { "status": "started", "stream_url": "/api/updates/status" }
  ↓
  클라이언트: EventSource(/api/updates/status) 열기

[다운로드 + 검증]
  asset URL → httpx stream → %APPDATA%\GameAssetHelper\update\GameAssetHelper.new.exe
  SHA256 검증
       FAIL → .new.exe 삭제 + SSE { "phase": "error", "reason": "sha256_mismatch" }
       PASS → SSE { "phase": "ready_to_install" }
              → 클라이언트가 자동으로 install API 호출
              → UpdateInstaller.swap_and_restart()

[진행률 SSE 이벤트]
  data: {"phase":"download","bytes":12345678,"total":323020426}
  data: {"phase":"verify"}
  data: {"phase":"ready_to_install"}
  data: {"phase":"restarting"}
```

### 5.4 Swap 패턴 (가장 중요)

**Windows 제약**:
- 실행 중인 `.exe` 덮어쓰기 ❌
- 자기 자신 rename 은 ✅

**3-step 패턴** (외부 의존 0, 단일 exe 내 로직):

```
초기 상태:
  C:\App\GameAssetHelper.exe       ← 실행 중 (PID=1234)
  %APPDATA%\GameAssetHelper\update\GameAssetHelper.new.exe   ← 다운로드 + SHA 검증된 새 버전

STEP 1 — 메인이 본인 rename + 새 파일 자리잡기 (in-process, 동기)
  os.rename: "C:\App\GameAssetHelper.exe" → "C:\App\GameAssetHelper.old.exe"
                (Windows 가 실행 중인 exe 자체의 rename 은 허용)
  os.replace: "%APPDATA%\...\new.exe"     → "C:\App\GameAssetHelper.exe"

STEP 2 — 새 exe 를 "정리 모드" 로 spawn 후 메인 종료
  subprocess.Popen([
      "C:\\App\\GameAssetHelper.exe",
      "--complete-update",
      "--old-pid", "1234",
  ], creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
  메인 (PID=1234): Qt cleanup → web server stop → thread join → sys.exit(0)

STEP 3 — 새 exe 가 "정리 모드" 안에서
  a) PID 1234 종료 대기 (ctypes.windll.kernel32.OpenProcess + WaitForSingleObject, max 30s)
  b) os.unlink("C:\\App\\GameAssetHelper.old.exe")
  c) subprocess.Popen(["C:\\App\\GameAssetHelper.exe", "--tray"], detached)
  d) --complete-update 프로세스 sys.exit(0)

사용자 시점:
  트레이 아이콘 잠시 사라짐 (~3~5s)
  → 다시 등장 (새 버전, --tray 일반 모드)
  → 브라우저 탭은 그대로 유지 (포트 9874, 새 서버 재바인딩)
```

**PID wait 구현** (~25줄, `installer.py`):

```python
import ctypes

def wait_for_pid(pid: int, timeout_sec: int = 30) -> bool:
    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0
    INFINITE_TIMEOUT_MS = timeout_sec * 1000

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return True  # 이미 종료된 PID — OpenProcess 가 0 반환

    try:
        result = kernel32.WaitForSingleObject(handle, INFINITE_TIMEOUT_MS)
        return result == WAIT_OBJECT_0
    finally:
        kernel32.CloseHandle(handle)
```

### 5.5 "나중에" 케이스

- 사용자가 배너 "나중에" 누르면: AvailableUpdate state 유지 (트레이 + 배너 계속 표시)
- 다음 부팅 시 재폴링 → 같은 버전이면 같은 알림 유지
- /settings 에서 `update.enabled = false` 토글 시 폴링 thread 중단 + 알림 dismiss

## 6. Error handling 매트릭스

| 단계 | 실패 케이스 | 처리 |
|---|---|---|
| **폴링** | 네트워크 끊김 / DNS 실패 | 조용히 로그 + 다음 주기 재시도. 사용자 알림 X |
| **폴링** | GitHub API rate limit (60/hr 초과) | exponential backoff (다음 시도 +1h, +2h, +4h, max 24h) |
| **폴링** | 응답 JSON malformed / tag_name 누락 | 로그 warning + skip |
| **폴링** | `.sha256` asset 누락 | 다운로드 진입 안 함 (release 작성자 실수 → 다음 release 대기), 로그 warning |
| **버전 비교** | 현재 == latest | skip (정상) |
| **버전 비교** | 현재 > latest (다운그레이드) | skip + 로그 warning |
| **다운로드** | 중간 끊김 | 처음부터 재시작 (308MB 라 resume 미구현, 단순화) |
| **다운로드** | SHA256 mismatch | `.new.exe` 즉시 삭제 + SSE error "검증 실패" + 재시도 가능 |
| **다운로드** | 디스크 부족 | SSE error + 필요 용량 안내 |
| **swap STEP 1** | rename 실패 (권한 / lock) | 알림 "관리자 권한 필요" + `.new.exe` 보관 + 다음 부팅 시 재시도 |
| **swap STEP 2** | Popen 새 exe 실패 | rollback (`.old.exe` → `.exe` 원복) + 알림 |
| **swap STEP 3a** | 메인 30s 안에 안 죽음 | 강제 진행 → Move 실패 시 30s 추가 wait, 5분 누적 후 포기 + 사용자 안내 "수동 재시작 후 적용" |
| **swap STEP 3c** | 새 exe `--tray` 시작 실패 | `--complete-update` 가 로그 + 트레이 toast + `.old.exe` 보존 (사용자가 수동 복구 가능) |

## 7. 테스트 전략

### 7.1 신규 단위 테스트 (+50)

| 테스트 파일 | 대상 | 신규 |
|---|---|---:|
| `tests/test_updater_checker.py` | UpdateChecker (httpx-mock) — new/same/older 버전, rate limit, malformed JSON | +12 |
| `tests/test_updater_version.py` | semver-lite 비교 (`0.0.1` / `0.0.2` / `0.1.0` / `1.0.0` / `v` prefix / pre-release tag) | +8 |
| `tests/test_updater_download.py` | UpdateDownloader — SHA pass/fail, 부분 다운로드, 디스크 부족 모킹 | +8 |
| `tests/test_updater_swap.py` | UpdateInstaller — STEP 1~3 시뮬레이션 (tmp 디렉토리 + fake exe), ctypes `wait_for_pid` (실 subprocess spawn), rollback | +10 |
| `tests/test_web_updates.py` | `/api/updates/{check,start,status}` (TestClient + SSE) | +8 |
| `tests/test_tray_update.py` | 트레이 메뉴 동적 갱신 (PySide6 mock) | +4 |
| **합계** | | **+50** |

### 7.2 통합 테스트 (옵트인)

`pytest -m update_integration` (기존 `mcp_integration` 와 동일 패턴):
- 실 GitHub Releases API 호출 (`/repos/v0o0v/game-asset-helper/releases/latest`) 1 req
- 응답 파싱 + 버전 비교 검증
- CI 에서는 skip, 로컬에서 수동 검증

### 7.3 수동 검증 시나리오 (Phase 5)

1. v0.0.1 → v0.0.2 실제 swap 시연 (vm 또는 backup 폴더에서)
2. "나중에" 클릭 후 다음 부팅 → 알림 재표시 확인
3. /settings → `update.enabled = false` 토글 → 폴링 중단 확인
4. 네트워크 끊은 채 부팅 → 폴링 조용히 실패, 사용자 알림 없음 확인
5. SHA mismatch 시뮬레이션 (asset 다운로드 후 변조) → SSE error 표시 확인
6. STEP 3a 메인이 30s 안에 안 죽는 케이스 (Qt cleanup hang 시뮬레이션) → 폴백 흐름 확인

## 8. Phase 분할

| Phase | 범위 | 산출 | 신규 테스트 | 예상 |
|---:|---|---|---:|---:|
| **0** | SignPath 신청 + 빌드 가이드 정립 | `docs/RELEASE_BUILD_GUIDE.md`, signpath.org/apply 제출, 첫 서명 빌드 dry-run | 0 | 0.5주 + 심사 대기 (수일~수주) |
| **1** | Updater 백엔드 — Checker + Version | `core/updater/checker.py` + `version.py`, polling thread, Config 신규 필드 (`update.*`) | +20 | 0.7주 |
| **2** | Updater 백엔드 — Downloader + Installer | `core/updater/downloader.py` + `installer.py`, `--complete-update` 모드, ctypes `wait_for_pid` | +18 | 0.7주 |
| **3** | Web UI 통합 | `web/routers/updates.py`, `_update_banner.html` (Alpine), SSE 진행률, base.html 통합, gettext msgid ~10건 + ko/en .po | +8 | 0.4주 |
| **4** | 트레이 통합 | `tray.py` 동적 메뉴 (Qt signal/slot), "업데이트 확인" + "vX.X.X 업데이트 가능" | +4 | 0.2주 |
| **5** | 검증 + 문서 + 첫 서명 release | 수동 시나리오 6건, README §배포 갱신, **v0.0.2 실제 release 로 dogfood** (본 spec 의 첫 실사용) | 0 | 0.5주 |
| **합계** | | **MCP 20 도구 그대로, 신규 의존성 0** | **+50** | **~3주 + SignPath 심사 대기** |

**중요**: Phase 0 (SignPath 자격 심사) 는 인적 검토라 대기 시간 불확실. Phase 1~4 는 심사 결과와 무관하게 병행 가능 (서명 없이 빌드한 exe 로 swap 흐름 dry-run 까지 검증 가능). Phase 5 의 dogfood release 만 SignPath 승인 후 실행.

## 9. 메트릭 / 신규 의존성

- **신규 의존성**: 0건
- **신규 Config 필드**: 3건 (`update.release_repo`, `update.check_interval_hours`, `update.enabled`)
- **신규 MCP 도구**: 0건 (업데이트는 사용자 UX 영역, Claude 가 호출할 일 없음)
- **테스트 합계**: 1046 → ~1096 (+50)
- **신규 파일**: ~10건 (updater 패키지 5, web routers 1, templates 1, RELEASE_BUILD_GUIDE 1, 테스트 6)
- **수정 파일**: ~7건 (`__main__.py`, `app.py`, `base.html`, `tray.py`, `config.py`, ko/en .po, `gah.spec`, README.md)

## 10. 알려진 한계 / 다음 iteration 검토

- **부분 다운로드 resume 미구현** — 308MB 라 처음부터 재시작. 회선 불안정 사용자는 여러 번 시도 필요할 수 있음. v0.0.x 추후 검토.
- **stable/beta 채널 분리 없음** — GitHub `releases/latest` 가 pre-release 제외 표준. pre-release tag 는 자동 skip. 채널 분리는 다음 iteration.
- **백그라운드 자동 다운로드 미지원** — 첫 iteration 은 알림만. 추후 `update.policy = "notify"|"auto_download"|"auto_install"` 옵션 검토.
- **다국어 — ja/zh 미적용** — M8 i18n 인프라 활용해 다음 iteration 추가 가능.
- **rollback UI 없음** — 새 버전 부팅 실패 시 `.old.exe` 보존만 함. 사용자가 직접 rename 으로 복구. 자동 rollback 은 watchdog timer 필요해 복잡도 ↑, 다음 iteration.
- **DB schema migration 정책** — 본 spec 범위 외. v0.0.1 → v0.0.2 schema 변경 없다고 가정 (현재 GAH 의 SQLite schema 가 안정). 이후 schema 변경 발생 시 별도 spec 에서 마이그레이션 흐름 (auto-migrate on first boot vs export/import) 설계.
- **GitHub Actions CI 자동화 미포함** — 별도 spec. 현재는 로컬 빌드 + SignPath 클라우드 서명 수동 절차.

## 11. 출처 / 참고

- [SignPath Foundation Open Source Program](https://signpath.org/) — "no cost for open-source projects"
- [SignPath Foundation Apply](https://signpath.org/apply)
- [Stellarium 코드 서명 사례](https://stellarium.org/) — SignPath Foundation 참여 OSS 선례
- [GitHub Releases API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)
- [Windows `MoveFileEx` / replace-on-reboot](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw) — swap 패턴 백업 (현재 spec 은 self-restart 로 우회)
- [Win32 `OpenProcess` + `WaitForSingleObject`](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject) — PID wait
- [CLAUDE.md §4.4](../../../CLAUDE.md) — 모르는 정보는 웹 확인 후 반영
- [project_v001_release_published 메모리](file://memory/project_v001_release_published.md) — v0.0.1 release 컨텍스트
