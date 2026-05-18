# M8 — 검증 결과

## 자동 검증

| 항목 | 결과 |
|---|---|
| `pytest -q` | **1046 passed + 1 skipped + 40 deselected** (M7 1002 baseline + M8 +44) |
| `pytest -m mcp_integration -v` | 2/2 (MCP 20 도구 그대로) |
| `pytest -m e2e -v` | (M8 범위 외 — skip) |

## 수동 검증 시나리오 (사용자 단계)

각 단계를 사용자가 실제 실행하며 결과를 ✅ / ❌ 로 표기.

### 1. PyInstaller 빌드 + 단일 exe 동작

- [ ] `pyinstaller gah.spec` 빌드 성공 (10분 내, 메모리 4 GB+ 권장)
- [ ] `dist/GameAssetHelper.exe` 가 ~1.5~2 GB 크기로 산출
- [ ] `dist/GameAssetHelper.exe --version` → "0.0.1" 출력
- [ ] `dist/GameAssetHelper.exe --tray` → 트레이 등장 + 브라우저 자동 열림
- [ ] 첫 검색 시 CLIP 가중치 자동 다운로드 (~5분, 이미 캐시됐으면 skip)

### 2. i18n 동작

- [ ] 브라우저 기본 (ko) → UI 한국어 표시
- [ ] `?lang=en` 쿼리 파라미터 → UI 영어 전환 확인
- [ ] `/settings` → 언어 라디오 "English" 선택 → 저장 → reload 후 영어 유지
- [ ] 쿠키 `gah_locale` 가 set 되어 있음 (브라우저 dev tools 확인)

### 3. 다크 모드 토글

- [ ] 헤더에 ☀️/🌙/🌗 버튼 보임
- [ ] 클릭 사이클: auto → light → dark → auto
- [ ] 페이지 reload 후 토글 상태 유지 (localStorage)
- [ ] 시스템 다크 모드일 때 auto 모드가 시스템 따라감

### 4. 자동 시작

- [ ] `/settings` 토글 on → `regedit` `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\GameAssetHelper` 값 존재 확인
- [ ] 토글 off → 값 삭제 확인
- [ ] 트레이 우클릭 → "자동 시작 (Windows)" 체크박스 동기 동작
- [ ] PC 재부팅 → 자동 시작 켠 상태라면 GAH 자동 실행 (선택적 검증)

### 5. 기존 기능 회귀 없음

- [ ] M5 — 라이브러리 / 검색 / 채택 정상 동작
- [ ] M6 — 시트 분석 / `suggest_animation_frames` 정상
- [ ] M7 — Unity Asset Store 스캔 / 임포트 / 프로젝트 페이지 정상

## DRY 정리

Task 3 의 code reviewer 가 발견한 `SUPPORTED` 중복 (`i18n.SUPPORTED_LOCALES` + `locale_middleware.SUPPORTED`) 을 Task 14 에서 통합.

변경 내용:
- `src/gah/web/locale_middleware.py` 의 `SUPPORTED = ("ko", "en")` 줄 제거
- `from .i18n import SUPPORTED_LOCALES as SUPPORTED` 로 교체
- 회귀 0 확인 (1046 passed 유지)

## 알려진 한계 / v2 보류 항목

- **SmartScreen 경고** — 코드 서명 없음. 사용자 "추가 정보 → 실행" 필요 (v2 에서 서명 검토)
- **exe 크기** — CLIP 가중치 포함 시 ~1.5~2 GB (GitHub release 2 GB 제한 근접)
- **WAL 잔존** — SQLite WAL 파일, 다음 부팅 시 자동 정리
- **Qt 트레이 메뉴 i18n 한국어 고정** — Qt i18n 은 v2
- **Pack/프로젝트 풍부 UX** — v2 (메타 수정, manual_override, 프로젝트 pin/block, 사용 분포 차트)
- **Playwright E2E** — v2
- **모바일/태블릿 최적화** — v2
- **추가 언어 (ja/zh)** — v2
- **인스톨러 (MSI/NSIS)** — v2
- **자동 업데이트** — v2
- **자동 동기화 스케줄러** — v2
- **트레이 알림** — v2
