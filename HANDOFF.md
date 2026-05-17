# HANDOFF — Cowork → Claude Code (또는 다음 세션)

**마지막 인계 시각**: 2026-05-17
**마지막 완료 마일스톤**: M4 (검색 UX 풍부화)
**다음 작업**: M5 (시트 분석 + 애니메이션)

이 문서는 작업이 중단될 때 다음 세션이 "현재 어디까지 와 있는가"를 한 번에 파악하도록 작성된 스냅샷이다. 마일스톤이 하나 끝날 때마다 이 문서를 갱신한다.

## 1. 한 줄 요약

설계(`DESIGN.md`) 위에 M0(뼈대) → M1(워처 + 팩 매니저 + SQLite 4테이블 + GUI 팩/라이브러리 탭) → M2(분석 파이프라인 + CLIP 라벨러 + 24축 316 시드 + 라벨 관리 다이얼로그 + 분석 큐/ETA 상태바) → M2.1(분석 큐 동시성 1 → 3 + Ollama semaphore + CLIP lock + SQLite write_lock + GUI 250ms 디바운스) → M3(HybridSearcher 가중합 0.40·sem + 0.15·kw + 0.20·label + 0.20·cons + 0.05·rec + MCP stdio 12 도구 + ConsistencyScorer + UsageTracker + GUI 검색 박스 + `docs/MCP_USAGE_GUIDE.md` 본격화 + 회귀 가드 2건) → **M4**(label_query 파서 AND/OR/NOT + axis:label + bare 자동매칭, HybridSearcher 6 채널 재배분 0.35/0.10/0.20/0.20/0.05/**0.10 feedback**, diversity none/mmr/round_robin, saved_searches 4 신규 MCP 도구 (12 → 16), feedback_records signed weight 페널티 학습 asset/pack-level, suggest_packs samples 풍부화 thumbnail+blurb, GUI 풍부 UX LabelChipPanel/SearchSidePanel/FilterBar) 까지 자동 433 테스트 + 2 mcp_integration 통과. 다음은 M5 (시트 분석 + 애니메이션 + `suggest_animation_frames`) 를 같은 TDD 사이클로 시작한다.

## 2. 검증된 사실 (M4 시점)

자동 — `pytest -q` 결과 **433/433 통과** (30s, Windows 10 / Python 3.12, `clip_integration` 2 + `mcp_integration` 2 = 4 옵트인 deselected). M3 의 333 + M4 의 100 신규 (회귀 갱신 3건은 동일 카운트 유지).

`pytest -m mcp_integration -v` — 실제 `python -m gah --mcp` subprocess + JSON-RPC `initialize`/`tools/list` 핸드셰이크 **2/2 통과** — **16 도구** 모두 정상 응답 (M3 12 + M4 saved_searches 4).

수동 — M4 의 GUI 풍부 UX 4 단계 (좌측 칩 패널 + 우측 슬라이더/저장 패널 + label_query 입력 + 저장된 검색 라운드트립) 는 [`milestones/M4_verification.md`](./milestones/M4_verification.md) §4. 트레이+MCP 동시 기동 + 실 Claude Code 클라이언트 연결은 선택 검증으로 §4.3~§4.4.

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
─────────────────────────────────────────────
합계 433 passed (active) + 4 deselected (clip_integration 2 + mcp_integration 2)
```

M4 수동 검증 단계는 [`milestones/M4_verification.md`](./milestones/M4_verification.md) §4. M2.1/M3 의 수동 검증 단계도 그대로 유효.

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

→ `433 passed, 4 deselected` 확인. 그러면 M0~M4 기준점이 유지되고 있다는 뜻.

venv 가 없는 새 PC 라면 [`CLAUDE.md §6`](./CLAUDE.md) 의 셋업 절차 그대로.

## 5. M5 시작 절차

M5 범위: **시트 분석 + 애니메이션** — 격자 자동 분할, Aseprite/TexturePacker JSON 지원, `suggest_animation_frames` MCP 도구. 일정 1주 (DESIGN §11).

다음 세션 진입 시:

1. **새 브랜치 생성** — M4 머지 후 `main` 에서 `feat/m5-sheet-animation` (또는 적당한 이름).
2. **MEMORY.md 자동 로드 확인** — 새 세션은 다음 9개 메모리를 자동 컨텍스트로 받는다:
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
3. **DESIGN.md 참조 섹션** — §4.2.2 (스프라이트 시트), §6.6 (`suggest_animation_frames`), §11 Milestone 5.
4. **M5 plan 작성** — [`milestones/M4_plan.md`](./milestones/M4_plan.md) 또는 M3_plan 을 템플릿으로 `M5_plan.md`. 핵심 산출물:
   - `src/gah/core/sheet_splitter.py` — 격자 자동 감지 (uniform grid / non-uniform JSON manifest) + frame bounding box 추출.
   - Aseprite JSON / TexturePacker JSON 파서 — `pack/<sheet>.json` 동봉이 있으면 우선 사용, 없으면 격자 휴리스틱.
   - `assets.sprite_meta.frame_w/frame_h/frame_count/animation_tags` 4 컬럼 활용 — M2 가 이미 스키마 잡아둠.
   - `suggest_animation_frames(asset_id, animation)` MCP 도구 — frame_indices + fps_hint 반환.
   - GUI 라이브러리 탭의 시트 자산 미리보기 패널 (옵션, M7 로 미룰 수 있음).
5. **M5_todo.md** — TDD 순서 체크리스트.
6. **테스트 먼저** — `tests/test_sheet_splitter.py`, `tests/test_animation_frames.py`, `tests/test_mcp_tools_m5.py` 등.
7. **구현 → 통과 → `M5_verification.md`** (사용자 수동 검증 항목은 마일스톤 끝 응답 본문에 단계별 체크리스트로 별도 제시).

**M5 plan 작성 시 결정해야 할 항목**:

- 격자 자동 감지 알고리즘 — 빈 픽셀 열/행 검출 vs FFT 기반 주기성 vs 사용자 명시 우선.
- Aseprite JSON 의 frame name 규칙 vs `animation_tags` 매핑 (예: `walk_001`/`walk_002` → animation="walk").
- 시트 자산이 검색 결과에 frame 단위로 노출될지 (분할 후 N 자산) vs 단일 자산 + meta 만 (M4 와 호환).
- `suggest_animation_frames` 의 `fps_hint` 산출 — 시트 dpi/dimension 기반 휴리스틱 vs 사용자 입력.

## 6. M4 에서 의도적으로 남겨둔 자리

- **그리드 ↔ 리스트 뷰 토글 / hover 미리보기 / 사운드 인라인 재생 / 결과 비교 보기 / 키보드 단축키** — M4 는 표 형태만. M7 GUI 마감.
- **`cleanup_feedback_records` 잡** — v1 은 검색 시 윈도우 필터만 (윈도우 밖 행은 DB 에 남음). 주기적 정리는 M5+.
- **`label_query` 한국어 키워드** (`그리고`/`또는`/`제외`) — v1 영어 `AND`/`OR`/`NOT` 만. 사용자 피드백 기반으로 M5+ 가 추가 결정.
- **`label_query` 혼합 AND/OR (OR-of-AND DNF)** — v1 은 순수 AND 또는 순수 OR 만. `(a AND b) OR c` 는 `UnsupportedExpression`. 사용 빈도 분석은 시각 검증.
- **`preview_blurb` 의 Gemma description 통합** — v1 은 top-2 라벨만. `assets.description` 컬럼 추가 후 M5+ 가 첫 한 줄 (80자 컷) 통합.
- **MMR 의 vector cosine similarity** — v1 은 binary same-pack indicator (0/1). 더 정교한 sim 은 사용자 피드백 기반.
- **pack-level penalty 임계 GUI 노출** — v1 은 Config TOML 만. M7 슬라이더 추가.

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
