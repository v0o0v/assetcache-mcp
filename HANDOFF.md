# HANDOFF — Cowork → Claude Code (또는 다음 세션)

**마지막 인계 시각**: 2026-05-17 (M5 Phase 0~2 완료 시점)
**마지막 완료 마일스톤**: M4 (검색 UX 풍부화) — ✅ 머지됨 ([PR #5](https://github.com/v0o0v/game-asset-helper/pull/5))
**진행 중 마일스톤**: **M5 — 웹 GUI 전환 + 라이브러리 리디자인 + Claude pick** (~5.5주, 약 38% 진행)
**현재 브랜치**: `feat/m5-web-gui` (main 위 **25 commit**, 미머지)
**다음 작업**: **Phase 3 (우측 사이드 패널 B/C/D 탭) — [`milestones/M5_plan.md`](milestones/M5_plan.md) §4.3 의 18 task, ~1.5주**

이 문서는 작업이 중단될 때 다음 세션이 "현재 어디까지 와 있는가" 를 한 번에 파악하도록 작성된 스냅샷이다. 마일스톤 또는 phase 가 하나 끝날 때마다 이 문서를 갱신한다.

## 1. 한 줄 요약

M4 가 main 으로 머지된 후 M5 spec ([`docs/superpowers/specs/2026-05-17-m5-web-gui-and-library-redesign.md`](docs/superpowers/specs/2026-05-17-m5-web-gui-and-library-redesign.md)) + plan ([`milestones/M5_plan.md`](milestones/M5_plan.md), 2097 줄 6 phase 75 task) + todo 작성 → `feat/m5-web-gui` 브랜치 분기 후 `superpowers:subagent-driven-development` 스킬로 **Phase 0 (의존성/Config/vendoring) + Phase 1 (FastAPI 스캐폴딩 + WebServer + 트레이 통합 + SSE bus) + Phase 2 (라이브러리 페이지: 검색 + 결과 + 카드 + 상세 모달 + 사운드 + 페이지네이션) 완료**. 누적 25 commit, **506 passed + 7 skipped + 4 deselected**. Qt UI 위젯 7 파일 + 테스트 4 파일은 Phase 5 폐기 예정이라 임시 module-level skip 적용. 다음 세션 = Phase 3 (B/C/D 사이드 패널) → Phase 4 (`request_user_pick` + SSE push) → Phase 5 (Qt 폐기 + Pack/라벨 관리 웹 이식) → Phase 6 (마감 + verification).

## 2. 검증된 사실 (M5 Phase 0~2 시점)

자동 — `pytest -q` 결과 **506 passed + 7 skipped + 4 deselected** (Phase 0 시작 시 460 baseline 대비 +46 신규 + Phase 5 폐기 예정 7 파일 ~50 케이스 skip → 순 합계 506).

| 영역 | 새 케이스 | 비고 |
|---|---:|---|
| M0~M4 베이스라인 | 452 | M4 PR #5 머지 시점 |
| Phase 0 — Config M5 + UsageSource | 8 | `test_config_m5.py` |
| Phase 1A — web/url + pending + deps | 15 | `test_web_url.py` + `test_web_pending.py` |
| Phase 1B — FastAPI app + WebServer | 14 | `test_web_app.py` + `test_web_server.py` |
| Phase 1C — tray + run_tray + health.actual_port | 13 | `test_tray_m5.py` + `test_app_m5.py` + `test_health_actual_port.py` |
| Phase 2A — 검색 백엔드 + 카드 partial | 14 | `test_web_routers_library_search.py` + `test_web_routers_thumbnail.py` |
| Phase 2B — 라이브러리 페이지 베이스 | 10 | `test_web_pages.py` |
| Phase 2C — 결과 툴바 + 페이지네이션 + 디폴트 | 13 | toolbar/pagination/default 보강 |
| Phase 2D — 상세 모달 + 사운드 + 통합 | 19 | `test_web_asset_detail.py` + `test_web_audio.py` + integration |
| Phase 2 fix — pagination toolbar 중복 | 2 | toolbar/cards-only 분리 |
| **합계** | **+ 108 신규** | Phase 5 폐기 예정 7 파일 ~50 케이스 skip |

`pytest -m mcp_integration -v` — 2/2 (16 도구, Phase 4 가 17 도구로 갱신 예정).

수동 — Phase 2 끝 시점부터 사용자가 시각 검증 가능:

```powershell
python -m gah --tray
```

→ 트레이 아이콘 + 브라우저 자동 열림 (http://127.0.0.1:9874/library). 검색 / 정렬 / 그리드↔리스트 / 카드 크기 S/M/L / 카드 클릭 모달 / 사운드 ▶ 재생 / 다크 모드 (OS prefers-color-scheme) 시각 확인 가능. Phase 3 이전엔 ⚙ 고급 클릭 시 사이드 패널이 placeholder ("Phase 3 에서 채워집니다") 만 표시.

## 3. 환경 (재현용)

| 항목 | 값 |
|---|---|
| OS | Windows 10 |
| Python | python.org 3.12 (`C:\Users\v0o0v\AppData\Local\Programs\Python\Python312\python.exe`) |
| venv | `C:\Users\v0o0v\.venvs\gah\` |
| 작업 폴더 | `D:\ClaudeCowork\game-asset-helper\game-asset-helper\` |
| 런타임 데이터 | `C:\Users\v0o0v\AppData\Roaming\GameAssetHelper\` |
| 라이브러리 루트 | `%APPDATA%\GameAssetHelper\library\` |
| 메타 DB | `%APPDATA%\GameAssetHelper\metadata.db` (WAL, 21+5=26 객체) |
| CLIP 캐시 | `%APPDATA%\GameAssetHelper\cache\clip\` |
| 스펙트로그램 캐시 | `%APPDATA%\GameAssetHelper\cache\spectrograms\` |
| **신규 M5: web.port 파일** | `%APPDATA%\GameAssetHelper\web.port` (MCP server ↔ FastAPI 포트 공유) |

**금기**: Microsoft Store Python, Cowork 작업 폴더 내부 venv.

M5 신규 의존성 (`pyproject.toml`):

- `fastapi>=0.110`, `uvicorn[standard]>=0.27` (transitive `websockets`, `httptools`, `watchfiles`)
- `jinja2>=3.1`, `python-multipart>=0.0.9`, `sse-starlette>=2`

vendoring (`src/gah/web/static/vendor/`):

- `htmx.min.js` 1.9.12
- `htmx-sse.min.js` 1.9.12
- `alpine.min.js` 3.13.10

기존 venv 그대로 사용 시:

```powershell
pip install -e D:\ClaudeCowork\game-asset-helper\game-asset-helper[dev]
```

→ `pyproject.toml` 의 신규 5 의존성 + transitives 자동 설치.

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

→ `On branch feat/m5-web-gui` + 25 (또는 그 이상 — 본 인계 커밋 포함) commits ahead of main + clean.

```powershell
git log --oneline -10
```

→ 최상단 본 인계 커밋 + 그 아래 Phase 2 fix + Phase 2D 의 통합 / 사운드 / 모달 / 디폴트 / 페이지네이션 / toolbar / 베이스 / Phase 2A 의 thumbnail/search-results/search 등.

```powershell
pytest -q
```

→ `506 passed, 7 skipped, 4 deselected` (또는 본 인계 커밋이 추가한 doc-only 케이스로 ±2). m4 GUI 7 파일은 Phase 5 폐기 예정이라 module-level skip.

선택 — 사용자 직접 시각 검증:

```powershell
python -m gah --tray
```

→ 브라우저로 라이브러리 페이지 진입. 검색 + 결과 + 카드 + 모달 + 사운드 시각 확인.

## 5. 다음 세션 진입 절차 (Phase 3 시작)

### 5.1 환경 복원 + 회귀 검증

§4 의 4 명령 (Activate.ps1 / cd / git status / pytest -q) 실행. 506 passed 확인.

### 5.2 Phase 3 작업 진입

[`milestones/M5_plan.md`](milestones/M5_plan.md) §4.3 = **Phase 3 (우측 사이드 패널 B/C/D 탭, ~1.5주, 18 task)**. 핵심:

- **Task 3.1**: ⚙ 토글 + 슬라이드 인 transition (사실 Phase 2B 의 `library.html` 에 이미 `x-show` + `x-transition` 적용 — 검증 + 보강만)
- **Task 3.2**: 사이드 패널 리사이즈 핸들 (마우스 드래그)
- **Task 3.3**: B/C/D 탭 헤더 + 컨테이너
- **Task 3.4-3.9**: B 탭 (매칭 모드 / 라벨 검색 / 종류 탭 / axis 칩 FlowLayout / 다축 필터 / `/api/search` 의 selectedLabels + matchMode 통합)
- **Task 3.10-3.13**: C 탭 (표시 옵션 양방향 바인딩 + 카드 메타 토글)
- **Task 3.14-3.17**: D 탭 (프리셋 3개 + 슬라이더 펼침 + 저장된 검색 + 통일성/페널티 요약 + 반응형)
- **Task 3.18**: 수동 시각 검증

권장 sub-phase 분할 (Phase 2 패턴):

- **Phase 3A**: Task 3.1-3.3 + 패널 컨테이너 + 탭 헤더 (스캐폴딩, ~3 commit)
- **Phase 3B**: Task 3.4-3.9 + B 탭 (칩 패널 + 다축 필터, ~6 commit)
- **Phase 3C**: Task 3.10-3.13 + C 탭 (표시 옵션, ~4 commit)
- **Phase 3D**: Task 3.14-3.17 + D 탭 + 반응형 (~6 commit)

각 sub-phase 마다 implementer (sonnet) + spec/quality reviewer (sonnet or haiku) 패턴.

### 5.3 Phase 3 시작 전 빠른 cleanup (옵션 — 코드 리뷰 잔여)

Phase 2 review 에서 합의된 follow-up:

1. **`populated_deps` / `populated_client` fixture 통합** — 현재 `tests/test_web_routers_library_search.py`, `test_web_asset_detail.py`, `test_web_audio.py` 3 파일에 동일 fixture 중복. `tests/conftest.py` 로 이동 + 3 파일 정리. ~30 분.

2. **자산 상세 모달 [채택]/[거부] 버튼 endpoint stub** — 현재 `POST /api/record-use` 와 `POST /api/feedback` 호출이 404 silent. Phase 3 의 feedback 라우터 채울 때 같이 처리. 또는 Phase 4 의 자동 record_asset_use 와 통합. **결정**: Phase 3 D 탭 (feedback 라우터 채움) 시점에 처리.

3. **`pack_ids` 필터** — `SearchBody` 가 받지만 `SearchRequest` 에 미전달 (M4 SearchRequest 가 `pack_ids` 필드 없음). Phase 3 B 탭 다축 필터 시점에 `SearchRequest` 확장 또는 store-level filtering 추가 필요. **Phase 3B 의 Task 3.8 (다축 필터 드롭다운) 작업 안에서 처리**.

4. **`Store.get_pack_by_id` 헬퍼** — `asset_detail.html` 의 pack 이름 조회를 위해 라우터에서 raw SQL 사용 중. Phase 5 (Pack 페이지) 시점에 Store 메서드 추가 권장.

5. **`_card_wide.html` div 의 keyboard accessibility** — `hx-trigger="click"` 만 — `role="button"` + `tabindex="0"` 부재. Phase 6 마감 단계 흡수.

### 5.4 새 세션이 자동 로드하는 메모리

다음 메모리가 자동 컨텍스트 로드:

- 마일스톤 수동 검증 항목 표시 방식 (feedback)
- PR/커밋 한글 (feedback)
- 가능한 한 직접 실행 (feedback)
- M2 분석 클라이언트 백엔드 추상화 (project)
- Ollama 멀티모달 API 형식 실측 (project)
- 모델 출력 듀얼 언어 + GUI i18n (project)
- 라벨 가중치 + CLIP v1 편입 (project)
- 검색 UX 전용 마일스톤 M4 신설 (project)
- GAH 배포 전략 — torch CUDA/CPU 통합 빌드 (project)
- M2.1 분석 큐 병렬화 패치 (project)
- M5 신규 — 웹 GUI 전환 결정 (project)
- **M5 Phase 0~2 진행 상태 (신규)** (project)
- **M5 subagent-driven-development 워크플로 (신규)** (project)

### 5.5 M5 진행 현황 (한눈에)

| Phase | 상태 | 핵심 산출물 | commit |
|---|---|---|---:|
| plan/todo | ✅ | spec → plan 2097 줄 + todo | 1 |
| Phase 0 (의존성/Config/vendoring) | ✅ | FastAPI 5 의존성 + Config 7 필드 + UsageSource enum + HTMX/Alpine 정적 자원 | 3 |
| Phase 1A (web/url + pending + deps) | ✅ | `web.port` R/W, PendingPickQueue (asyncio.Future + lock + TTL), WebDeps | 4 (race fix 1 포함) |
| Phase 1B (FastAPI factory + WebServer) | ✅ | `build_app` lifespan, uvicorn 별 스레드, 포트 폴백 9874→9883 | 2 |
| Phase 1C (tray + run_tray + health) | ✅ | 트레이 메뉴 → 브라우저, MainWindow 의존성 0, SSE bus, m4 GUI 7 파일 skip | 3 |
| Phase 2A (검색 백엔드 + 카드) | ✅ | `/api/search`, `/ui/search-results`, `/api/thumbnail`, 와이드/리스트 카드 partial | 4 (bug fix 1 포함) |
| Phase 2B (페이지 베이스 + 검색 바) | ✅ | base/library/nav, CSS 변수 light/dark, 검색 바 300ms 디바운스, ⚙ 토글 | 1 |
| Phase 2C (결과 툴바 + 페이지네이션 + 디폴트) | ✅ | view/size/sort 툴바, 더 보기 버튼, 빈 검색 → 라이브러리 추가일↓ 폴백 | 3 |
| Phase 2D (모달 + 사운드 + 통합) | ✅ | `/ui/asset-detail`, `/api/audio`, `/ui/audio-player`, 모달 CSS | 3 |
| Phase 2 fix (toolbar 중복) | ✅ | `_results_grid.html` ↔ `_results_cards_only.html` 분리 + library.html dead x-data 정리 | 1 |
| **Phase 3** (B/C/D 사이드 패널) | **다음** | 우측 사이드 패널 + 칩 패널 + 슬라이더 + 저장된 검색 | 0 |
| Phase 4 (`request_user_pick` + SSE) | 대기 | MCP 17번째 도구, SSE push, Claude 요청 카드 | 0 |
| Phase 5 (Qt 폐기 + Pack/라벨 이식) | 대기 | 7 파일 삭제 + Pack/labels admin 웹 페이지 | 0 |
| Phase 6 (마감 + verification) | 대기 | 다크모드 토글 / 에러 페이지 / WEB_UI_GUIDE / verification | 0 |
| Final review | 대기 | 전체 변경 review | 0 |

## 6. 마일스톤 재정렬 (변경 없음)

| 신규 # | 이름 | 일정 | 상태 |
|---:|---|---:|---|
| M0~M3 | (변경 없음) | — | ✅ 완료 (main) |
| M4 | 검색 UX 풍부화 (Qt 위젯) | 1.5주 | ✅ 완료 (main, M5 가 Qt 위젯 폐기 예정) |
| **M5** | **웹 GUI 전환 + 라이브러리 리디자인 + Claude pick** | **5.5주** | **🔄 진행 중 (~38%)** |
| M6 | 시트 분석 + 애니메이션 | 1주 | 대기 |
| M7 | Unity Asset Store 임포트 | 1주 | 대기 |
| M8 | 패키징 + i18n | 1주 | 대기 |

## 7. M5 spec §13 의 5 열린 질문 — 결정 적용 결과

| # | spec 질문 | plan §3 결정 | Phase 0~2 적용 결과 |
|---|---|---|---|
| Q1 | FastAPI 같은 프로세스 vs subprocess | 같은 프로세스 + 별 스레드 | ✅ `WebServer` 가 `threading.Thread` 로 uvicorn 별 스레드 실행. Qt main thread 와 충돌 X. |
| Q2 | WebSocket vs SSE | SSE (sse-starlette) | ✅ `web/sse_bus.py` thread-safe broadcast 구현. SSE 라우터는 Phase 4 가 채움 (Phase 1B 스텁만 등록). |
| Q3 | Qt 폐기 시점 | M5 안 (Phase 5) | 🔄 진행 중 — Phase 1C 가 m4 7 파일 모듈 skip + Phase 5 가 삭제. |
| Q4 | 자동 `record_asset_use` | 자동 호출 (source='claude_pick') | 🔄 Phase 4 가 구현 — `UsageSource.CLAUDE_PICK` enum 은 Phase 0 에서 정의 완료. |
| Q5 | i18n 백엔드 | v1 placeholder `_t()`, 본격은 M8 | ✅ `web/i18n.py` 의 `_t()` passthrough + Jinja2 `_` 글로벌 등록. 모든 사용자 노출 문자열은 `{{ _("...") }}` 로 감싸 둠. |

신규 결정 적용 결과:

- **MCP↔FastAPI HTTP loopback** — `/internal/user-pick` long-poll (Phase 4 가 구현). `web.port` 파일 R/W (Phase 1A) 가 인프라.
- **포트 폴백** — `web_port` 부터 `web_port_max_attempts` (10) 회 시도. ✅ `WebServer._find_available_port` 구현 완료.
- **PendingPick TTL/한도** — TTL = `claude_pick_timeout_seconds + 60s`, max_pending = 20. ✅ `PendingPickQueue.cleanup_expired` (Phase 1A) + lifespan 의 cleanup 잡 (Phase 1B). API 라우터는 Phase 4 가 등록.

## 8. M5 Phase 0~2 의 의도적으로 미룬 항목

Phase 3~6 가 채움:

- **B/C/D 사이드 패널 UI** — Phase 3
- **SSE 라우터 실 구현 (`/sse/notifications`)** — Phase 4 (현재 빈 stub 라우터만)
- **Claude `request_user_pick` MCP 도구 + `/internal/user-pick` 라우터** — Phase 4 (PendingPickQueue 인프라는 Phase 1A 완료)
- **자동 `record_asset_use(source='claude_pick')`** — Phase 4 (UsageSource enum 은 Phase 0 완료)
- **Pack 페이지 (`/packs`) + 라벨 관리 페이지 (`/labels/admin`)** — Phase 5 (현재 빈 stub 라우터만 + nav 의 링크는 404)
- **Qt UI 파일 7개 + 테스트 4 파일 실 삭제** — Phase 5 (현재 module-level skip)
- **다크모드 사용자 토글** — Phase 6 (현재 OS prefers-color-scheme 자동만)
- **반응형 모바일 최적화** — Phase 6 (현재 ≤768px 사이드 자동 닫힘만)
- **`WEB_UI_GUIDE.md` 작성** — Phase 6
- **`M5_verification.md`** — Phase 6 끝

## 9. 알려진 한계 / 주의사항 (Phase 3 흡수 가능)

§5.3 의 5 follow-up 사항 (fixture 중복 / adopt 버튼 404 / pack_ids 미전달 / Store 헬퍼 부재 / keyboard accessibility) + Phase 5 폐기 예정 7 파일 skip 마크 유지.

또한:

- **`SearchRequest.offset` 미지원** — M4 가 만든 SearchRequest 에 offset 필드 없음. `_do_search` 가 `count = body.count + body.offset` 으로 fetch 후 Python 슬라이싱. 큰 offset 에선 비효율 — M6 또는 후속 phase 에서 SearchRequest 확장 권장.
- **`store.list_assets(limit=10_000)`** — 디폴트 상태 폴백에서 사용. 매우 큰 라이브러리 (1만+) 에선 비효율 — M6 또는 후속 phase 에서 `count_assets` 기반 동적 limit 으로 개선.
- **m4 7 파일 skip** — Phase 5 가 파일 자체 삭제 시 skip 마크도 같이 사라짐. 이때 `pytest -q` 통과 카운트가 변동 (skip → 0, total 도 감소).
- **autoplay** — `_audio_player.html` 의 `<audio autoplay>` 는 사용자 클릭 후라 브라우저 정책 통과.

## 10. 문서 맵

- [`README.md`](./README.md) — 사용자용 시작 안내
- [`CLAUDE.md`](./CLAUDE.md) — Claude 작업 가이드 (§2 진행 현황 표 + §8 다음 작업)
- [`HANDOFF.md`](./HANDOFF.md) — 이 파일, 마일스톤/phase 경계 인계
- [`DESIGN.md`](./DESIGN.md) — 전체 아키텍처·스키마·MCP 명세
- [`milestones/M5_plan.md`](./milestones/M5_plan.md) — M5 의 6 phase 75 task plan
- [`milestones/M5_todo.md`](./milestones/M5_todo.md) — TDD 체크리스트
- [`milestones/`](./milestones/) — 이전 마일스톤들의 plan/todo/verification
- [`docs/MCP_USAGE_GUIDE.md`](./docs/MCP_USAGE_GUIDE.md) — Phase 4 가 17번째 도구로 갱신 예정
- [`docs/superpowers/specs/2026-05-17-m5-web-gui-and-library-redesign.md`](./docs/superpowers/specs/2026-05-17-m5-web-gui-and-library-redesign.md) — M5 spec 원본

## 11. 갱신 규칙

이 문서는 다음 시점에 반드시 업데이트한다.

1. Phase 또는 마일스톤이 완료될 때 (§1 한 줄 요약, §2 검증 결과, §5 다음 작업).
2. 환경 결정이 바뀔 때 (§3).
3. 새 금기·주의사항이 발견될 때 (§9).

내용을 누적하기보다 **현재 시점의 진실만** 적는다. 과거 이력은 git log 에 맡긴다.
