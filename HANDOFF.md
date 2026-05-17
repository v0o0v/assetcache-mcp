# HANDOFF — Cowork → Claude Code (또는 다음 세션)

**마지막 인계 시각**: 2026-05-17 (M4 + M5 spec 머지 후)
**마지막 완료 마일스톤**: M4 (검색 UX 풍부화) — ✅ **머지됨** ([PR #5](https://github.com/v0o0v/game-asset-helper/pull/5), main 위 fast-forward)
**다음 작업**: **사용자 spec 검토 → writing-plans 로 `milestones/M5_plan.md` 작성**
**M5 spec**: [docs/superpowers/specs/2026-05-17-m5-web-gui-and-library-redesign.md](docs/superpowers/specs/2026-05-17-m5-web-gui-and-library-redesign.md) — 웹 GUI 전환 + 라이브러리 리디자인 + Claude pick 인터랙션 (~5.5주)
**마일스톤 재정렬**: 신규 M5 (웹 GUI) / 기존 M5 시트분석 → M6 / 기존 M6 Unity → M7 / 기존 M7 패키징 → M8

이 문서는 작업이 중단될 때 다음 세션이 "현재 어디까지 와 있는가"를 한 번에 파악하도록 작성된 스냅샷이다. 마일스톤이 하나 끝날 때마다 이 문서를 갱신한다.

## 1. 한 줄 요약

설계(`DESIGN.md`) 위에 M0(뼈대) → M1(워처 + 팩 매니저 + SQLite 4테이블 + GUI 팩/라이브러리 탭) → M2(분석 파이프라인 + CLIP 라벨러 + 24축 316 시드 + 라벨 관리 다이얼로그 + 분석 큐/ETA 상태바) → M2.1(분석 큐 동시성 1 → 3 + Ollama semaphore + CLIP lock + SQLite write_lock + GUI 250ms 디바운스) → M3(HybridSearcher 가중합 0.40·sem + 0.15·kw + 0.20·label + 0.20·cons + 0.05·rec + MCP stdio 12 도구 + ConsistencyScorer + UsageTracker + GUI 검색 박스 + `docs/MCP_USAGE_GUIDE.md` 본격화 + 회귀 가드 2건) → **M4**(label_query 파서 AND/OR/NOT + axis:label + bare 자동매칭, HybridSearcher 6 채널 재배분 0.35/0.10/0.20/0.20/0.05/**0.10 feedback**, diversity none/mmr/round_robin, saved_searches 4 신규 MCP 도구 (12 → 16), feedback_records signed weight 페널티 학습 asset/pack-level, suggest_packs samples 풍부화 thumbnail+blurb, GUI 풍부 UX LabelChipPanel/SearchSidePanel/FilterBar) 까지 자동 452 테스트 + 2 mcp_integration 통과. 이후 사용자 GUI 검증 보고로 4 페인 (정보 과부하 / 좌우 스크롤 / 섹션 불명 / 가중치 불가해) 도출 + 브레인스토밍 10 결정 → **M5 spec (웹 GUI 전환 + 라이브러리 리디자인 + Claude pick) 작성 완료**. 다음 세션 = 사용자 spec 검토 → 승인 시 writing-plans 스킬로 `milestones/M5_plan.md` 작성 → red/green TDD.

## 2. 검증된 사실 (M4 시점, follow-up 후)

자동 — `pytest -q` 결과 **452/452 통과** (35s, Windows 10 / Python 3.12, `clip_integration` 2 + `mcp_integration` 2 = 4 옵트인 deselected). M3 의 333 + M4 의 100 신규 + M4 follow-up 의 19 신규 (회귀 갱신 3건 동일 카운트 유지).

`pytest -m mcp_integration -v` — 실제 `python -m gah --mcp` subprocess + JSON-RPC `initialize`/`tools/list` 핸드셰이크 **2/2 통과** — **16 도구** 모두 정상 응답 (M3 12 + M4 saved_searches 4).

수동 — M4 의 GUI 풍부 UX 시각 검증 (좌측 칩 패널 + 우측 슬라이더/저장 패널 + label_query 입력 + 저장된 검색 4 기능 라운드트립) 은 [`milestones/M4_verification.md`](./milestones/M4_verification.md) §4. 이 검증 중 4 페인 (정보 과부하 / 좌우 스크롤 가림 / 섹션 불명 / 가중치 불가해) 도출 → M5 spec 작성.

```
M0 회귀:        18 passed
M1 회귀:        49 passed
M2 회귀+신규:  134 passed
M1 추가 회귀:    3 passed
M2.1 신규:      16 passed
M2.1 회귀 보존:  +1 passed
M3 신규:       112 passed
M4 신규:       100 passed  (label_query 16 + store_m4 12 + search_diversity 9 +
                            feedback_penalty 10 + suggest_packs_samples 6 +
                            library_search_ui_rich 14 + mcp_tools_m4 14 +
                            search_m4 8 + config_m4 6 + thumbnails 5)
M4 follow-up:   19 passed  (LibraryView QSplitter 통합 3 + 저장된 검색 4 기능
                            12 + LabelChipPanel 종류별 탭 4 + 회귀 갱신)
─────────────────────────────────────────────
합계 452 passed (active) + 4 deselected (clip_integration 2 + mcp_integration 2)
```

M4 수동 검증 단계는 [`milestones/M4_verification.md`](./milestones/M4_verification.md) §4. M2.1/M3 의 수동 검증 단계도 그대로 유효. **M5 가 이 Qt UI 위젯들을 모두 폐기하고 웹 UI 로 대체할 예정** — verification 의 수동 단계도 함께 폐기.

## 3. 환경 (재현용)

| 항목 | 값 |
|---|---|
| OS | Windows 10 |
| Python | python.org 3.12 (`C:\Users\v0o0v\AppData\Local\Programs\Python\Python312\python.exe`) |
| venv | `C:\Users\v0o0v\.venvs\gah\` |
| 작업 폴더 | `D:\ClaudeCowork\game-asset-helper\game-asset-helper\` |
| 런타임 데이터 | `C:\Users\v0o0v\AppData\Roaming\GameAssetHelper\` |
| 라이브러리 루트 | `%APPDATA%\GameAssetHelper\library\` |
| 메타 DB | `%APPDATA%\GameAssetHelper\metadata.db` (WAL 모드, 14 객체) |
| CLIP 캐시 | `%APPDATA%\GameAssetHelper\cache\clip\` (첫 분석 시 ~600 MB 다운로드) |
| 스펙트로그램 캐시 | `%APPDATA%\GameAssetHelper\cache\spectrograms\` (사운드 2차 폴백) |

**금기**: Microsoft Store Python(`%APPDATA%` 가상화), Cowork 작업 폴더 내부 venv(권한 충돌).

M2 에서 새로 추가된 의존성 (`pyproject.toml`):

- `Pillow>=10`, `numpy>=1.26`, `librosa>=0.10`, `soundfile>=0.12`
- `httpx>=0.27`, `pydantic>=2.6`
- `open_clip_torch>=2.24`, `torch>=2.2` (단일 wheel — GPU/CPU 통합, 런타임 자동 감지)
- `matplotlib>=3.8` (사운드 2차 폴백의 스펙트로그램 PNG 렌더)
- dev: `pytest-asyncio>=0.23`, `respx>=0.20`

M3 에서 새로 추가된 의존성:

- `mcp>=1.27,<2` (Anthropic 공식 Python SDK — FastMCP 데코레이터 + stdio transport).

**M4 는 의존성 변화 없음** — Pillow (M2) 가 lazy thumbnail 캐시에, PySide6 (M0) 이 풍부 UX 위젯에, mcp SDK (M3) 가 saved_searches 4 신규 도구에 그대로 재사용.

기존 venv 를 그대로 쓰는 경우 다음 한 줄로 추가 설치:

```powershell
pip install -e D:\ClaudeCowork\game-asset-helper\game-asset-helper[dev]
```

(편집 가능 설치라 `pyproject.toml` 의 새 의존성이 자동 따라온다. torch wheel ≈ 800 MB + librosa numba 약 200 MB.)

## 4. 새 세션에서 바로 이어가는 방법

이미 venv 가 설치된 PC 라면:

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```

```powershell
cd D:\ClaudeCowork\game-asset-helper\game-asset-helper
```

```powershell
pytest -q
```

→ `452 passed, 4 deselected` 확인 (현재 브랜치 `feat/m4-search-ux` 기준). 그러면 M0~M4 기준점이 유지되고 있다는 뜻.

venv 가 없는 새 PC 라면 [`CLAUDE.md §6`](./CLAUDE.md) 의 셋업 절차 그대로.

## 5. 다음 세션 진입 절차 (M5 spec 검토 → plan 작성)

**현재 상태**: M4 + M5 spec 이 main 으로 머지됨 ([PR #5](https://github.com/v0o0v/game-asset-helper/pull/5)). 새 세션의 첫 작업:

### 5.1 환경 복원

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```

```powershell
cd D:\ClaudeCowork\game-asset-helper\game-asset-helper
```

```powershell
git status
```

→ `On branch main` + `Your branch is up to date with 'origin/main'` + clean 확인.

```powershell
git log --oneline -10
```

→ 최상단 머지 commit + 8 작업 커밋:
```
64ad166 Merge pull request #5 from v0o0v/feat/m4-search-ux
8075de8 docs: 세션 인계 — M5 신규 마일스톤 + 로드맵 재정렬 반영
a3b9782 docs(m5): spec — 웹 GUI 전환 + 라이브러리 리디자인 + Claude pick 인터랙션
e691273 feat(m4): 저장된 검색 4 기능 + LabelChipPanel 종류별 탭
209455d fix(m4): LibraryView 3-panel QSplitter 통합 누락 fix + app.py wiring
b165088 docs(m4): verification + HANDOFF/CLAUDE/README — M4 완료 인계
157889e feat(m4): 검색 UX 풍부화 — 6채널 + 다양성 + 페널티 학습 + 16 MCP + GUI 풍부
b2879e1 test(m4): red phase — 100 신규 케이스 + 회귀 갱신 2건
d19346c docs(m4): plan + todo — 검색 UX 풍부화 (1.5주 분량)
```

```powershell
pytest -q
```

→ `452 passed, 4 deselected`.

### 5.2 다음 작업 (우선순위 순)

1. **새 브랜치 생성** — `git checkout -b feat/m5-web-gui` (또는 적당한 이름).
2. **M5 spec 검토** — [`docs/superpowers/specs/2026-05-17-m5-web-gui-and-library-redesign.md`](docs/superpowers/specs/2026-05-17-m5-web-gui-and-library-redesign.md) 읽고 수정사항 있으면 사용자에게 확인.
3. **사용자 승인 시 writing-plans 스킬 호출** — `milestones/M5_plan.md` 를 M3/M4 plan 템플릿으로 작성. spec §10 의 5.5주 일정 + §13 의 5 열린 질문을 plan 단계 §3.x 에서 확정.
4. **M5 plan/todo 작성 → red phase 테스트 → green phase 구현 → verification** (M3/M4 cycle 동일).

### 5.3 새 세션이 자동 로드하는 메모리

다음 11 메모리가 자동 컨텍스트:

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
- **M5 신규 — 웹 GUI 전환 결정 (project, 2026-05-17)**

### 5.4 M5 spec 핵심 (요약)

10 결정사항:
1. 페인 = 정보 과부하 / 좌우 스크롤 / 섹션 불명 / 가중치 불가해
2. 레이아웃 = 옵션 C (상단 자연어 검색 + ⚙ 고급 + 우측 슬라이드 B/C/D)
3. B 탭 = 평탄 + 칩 검색 + FlowLayout wrap (좌우 스크롤 금지)
4. C 탭 = 결과 표시 옵션 (그리드/리스트 토글 + 카드 크기 + 정렬 + 메타)
5. 결과 카드 = 와이드 (썸네일 60×60 좌 + 텍스트 우, 사운드 인라인 ▶)
6. D 탭 = 프리셋 우선 (슬라이더 접힘) + 저장된 검색 + 통일성/페널티 요약
7. 호스팅 = FastAPI + 시스템 브라우저 (로컬 웹서버 9874, localhost 바인딩)
8. Claude pick = 동기 long-poll (5분 timeout, `request_user_pick` 신규 MCP 도구)
9. 프런트엔드 = HTMX + Alpine.js (빌드 X, ~30KB)
10. M4 그대로 머지 → M5 가 Qt 위젯 4개 + 테스트 폐기 + 웹 신규

신규 의존성: `fastapi` `uvicorn[standard]` `jinja2` `python-multipart` `websockets`.

폐기 대상 (M5): `library_view.py` + `label_chip_panel.py` + `search_side_panel.py` + `filter_bar.py` + `test_library_search_ui*.py` 2개. 추가 검토 (`main_window.py` / `pack_view.py` — M5 plan §3.x).

보존: 모든 백엔드 (store / search / consistency / usage / label_query / labels / thumbnails / suggest_packs / analysis 파이프라인 / mcp 16 도구).

### 5.5 마일스톤 재정렬

| 신규 # | 이름 | 일정 | 기존 # |
|---:|---|---:|---:|
| M0~M3 | (변경 없음) | — | — |
| M4 | 검색 UX 풍부화 (Qt 위젯) | (완료, 머지 후 폐기 예정) | M4 |
| **M5** | **웹 GUI 전환 + 라이브러리 리디자인 + Claude pick 인터랙션** | **~5.5주** | **신규** |
| M6 | 시트 분석 + 애니메이션 | 1주 | 기존 M5 |
| M7 | Unity Asset Store 임포트 | 1주 | 기존 M6 |
| M8 | 패키징 + i18n | 1주 | 기존 M7 |

## 6. M4 에서 의도적으로 남겨둔 자리 (M5 에서 처리 / 폐기)

대부분 항목이 M5 의 웹 UI 가 처음부터 다시 디자인하므로 자동 흡수.

- **그리드 ↔ 리스트 뷰 토글 / hover 미리보기 / 사운드 인라인 재생 / 결과 비교 보기 / 키보드 단축키** — **M5 스펙에 모두 포함**.
- **`cleanup_feedback_records` 잡** — 그대로 M6+ (백엔드 운영).
- **`label_query` 한국어 키워드** (`그리고`/`또는`/`제외`) — 그대로 M6+ (파서 확장).
- **`label_query` 혼합 AND/OR (OR-of-AND DNF)** — 그대로 M6+ (파서 확장).
- **`preview_blurb` 의 Gemma description 통합** — 그대로 M6+ (`assets.description` 컬럼 + 분석 파이프라인 확장 필요).
- **MMR 의 vector cosine similarity** — 그대로 M6+ (검색 알고리즘 튜닝).
- **pack-level penalty 임계 GUI 노출** — **M5 스펙에 포함** (D 탭 슬라이더 추가).

M3 에서 미뤘던 자리 중 M4 가 채운 것 (참고):

- `suggest_packs.samples` 풍부화 → 채움 (sprite thumbnail_path + top-2 라벨 blurb).
- `find_asset` 자연어 라벨 부울 파서 → 채움 (label_query 필드).
- 결과 다양성 부스터 (`cross_pack_filter`) → 채움 (`diversity` 필드, none/mmr/round_robin).
- `report_feedback` 페널티 학습 → 채움 (signed weight + asset/pack-level).

여전히 M3 에서 미룬 것:

- 암묵 top1 추정 (`implicit_top1_enabled`) — Config 기본 OFF. M4 도 그대로.
- `request_rescan` 의 워커 없음 케이스 — `--mcp` 단독 실행 시 `mark_pending` 만 + warnings. M4 도 그대로.

## 7. 문서 맵

- [`README.md`](./README.md) — 사용자용 시작 안내
- [`CLAUDE.md`](./CLAUDE.md) — Claude(코드 에이전트)용 작업 가이드
- [`HANDOFF.md`](./HANDOFF.md) — 이 파일, 마일스톤 경계의 인계 스냅샷
- [`DESIGN.md`](./DESIGN.md) — 전체 아키텍처·스키마·MCP 명세
- [`milestones/`](./milestones/) — 마일스톤별 plan/todo/verification
- [`docs/MCP_USAGE_GUIDE.md`](./docs/MCP_USAGE_GUIDE.md) — Claude Code 가 MCP 도구를 어떻게 활용하는지 가이드 (M3 가 본격화)

## 8. 갱신 규칙

이 문서는 다음 시점에 반드시 업데이트한다.

1. 마일스톤이 완료될 때 (§2 검증 결과, §1 한 줄 요약, "다음 작업").
2. 환경 결정이 바뀔 때 (§3).
3. 새 금기·주의사항이 발견될 때 (§3 또는 별도 섹션).

내용을 누적하기보다 **현재 시점의 진실만** 적는다. 과거 이력은 git log 에 맡긴다.
