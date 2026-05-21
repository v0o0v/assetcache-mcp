# M11.2 Plan — Batch Spritesheet Modality (v0.2.2 candidate)

## 0. 본 plan 의 위치

- 상위 spec: [`docs/superpowers/specs/2026-05-21-m11-2-batch-spritesheet-modality.md`](../docs/superpowers/specs/2026-05-21-m11-2-batch-spritesheet-modality.md)
- 전제: [PR #18](https://github.com/v0o0v/assetcache-mcp/pull/18) v0.2.x patches (main `12ebc42`), 회귀 1490
- 다음 산출물: `M11_2_todo.md` (TDD red→green 체크리스트) + 본 plan 의 Phase 별 detailed task

본 plan 은 **starter** — 다음 세션 시작 시 `superpowers:writing-plans` 또는 동등한 단계로 확장.

## 1. 목표

`chat_spritesheet` modality 신설로 PR #18 의 한계 (batch 에서 grid-only 시트가 animation 라벨 비어 있음) 해결. sync `SpritesheetAnalyzer` 와 batch 가 동등한 분석 결과 생성.

## 2. 산출물

| # | 산출물 | 비고 |
|---:|---|---|
| 1 | `core/store.py` — `_MODALITY_KIND_FILTER` 갱신 (sprite/spritesheet 분리) | 마이그레이션 0 |
| 2 | `core/llm/registry.py` 또는 `chain.py` — `chat_spritesheet` chain 자동 fallback to `chat_image` | 기존 사용자 영향 0 |
| 3 | `core/analyzer/messages.py` — `BATCH_SPRITESHEET_PROMPT` + `build_spritesheet_chat_messages` | sync `SpritesheetAnalyzer._call_gemma` 와 동일 schema |
| 4 | `core/batch/sheet_classifier.py` (신규) — `classify_image_assets(rows, library_dir, store)` | detect_sheet + kind promote |
| 5 | `core/batch/manager.py` — `_MODALITIES` 확장 + `try_submit("chat_image")` 가 classify 후 두 modality 각각 try | 임계값 분리 카운트 |
| 6 | `core/batch/poller.py` — `_handle_succeeded` modality switch 에 `chat_spritesheet` + 신규 `_persist_spritesheet_payload` | sync 와 동등 라벨/메타 |
| 7 | `web/routers/analyzing.py` + partial template — modality 4행 dashboard | i18n msgid 신규 |
| 8 | i18n `assetcache.po` (ko/en) — 신규 msgid | "Spritesheet batch", "spritesheet" |
| 9 | 옵트인 integration test 1건 — 실 Gemini batch chat spritesheet submit/cancel | `GEMINI_API_KEY` 필요 |
| 10 | `M11_2_verification.md` — 자동 + 수동 시나리오 5~7건 | sync 동등성 시각 검증 포함 |

## 3. Phase 분할 (얇은 starter)

다음 세션이 writing-plans / TDD cycle 로 확장.

### Phase 1 — modality 분리 (DB / config / chain)

- store `_MODALITY_KIND_FILTER` 갱신 + 회귀 (분리 후 chat_image 가 spritesheet 안 잡는지)
- chain.py — chat_spritesheet 자동 fallback
- 신규 테스트 (~5건): store/chain 단위

### Phase 2 — 시트 분류 helper

- `core/batch/sheet_classifier.py` 신설 — detect_sheet + kind promote
- 신규 테스트 (~10건): JSON 사이드카 / grid-only / 비-시트 / I/O 오류 fixture

### Phase 3 — 시트 전용 prompt + composite builder

- `BATCH_SPRITESHEET_PROMPT` (animation_hint enum 동적 주입)
- `build_spritesheet_chat_messages(abs_path, detection, prompt)` (make_preview_composite 재사용)
- 신규 테스트 (~5건): prompt 형식 + composite 생성

### Phase 4 — BatchManager 분기

- `_MODALITIES` 확장
- `try_submit("chat_image")` 가 classify 결과로 두 modality try
- `_build_chat_requests` modality 별 builder 선택
- 신규 테스트 (~10건): 시트/sprite 혼합 → 두 job 분리 검증

### Phase 5 — BatchPoller spritesheet handler

- `_handle_succeeded` modality switch 확장
- `_persist_spritesheet_payload` 신설 — validate + labels + animation_hint 추가 + sprite_meta enrichment + kind 보존
- 신규 테스트 (~10건): payload → 라벨/메타/promote 검증

### Phase 6 — UI / i18n / docs

- /settings + /analyzing modality 4행
- i18n msgid 신규 (ko/en)
- README / DESIGN 갱신 (필요 시)
- 신규 테스트 (~3건): UI render / i18n msgid 등록

### Phase 7 — 통합 / 회귀 / publish

- 전체 회귀 `pytest -q` 통과 (1490 + ~40)
- 옵트인 integration test 1건 (실 Gemini batch chat spritesheet)
- 수동 검증 (Aseprite 시트 batch → DB SELECT 로 animations_json + animation 라벨 확인)
- PR → main 머지 → tag v0.2.2 → Trusted Publishing 자동 publish (5회째)

## 4. 작업 시간 추정

- Phase 1~5: 1~1.5일
- Phase 6: 0.5일
- Phase 7 (검증/publish): 0.5일
- **합계 ~2~3일** (옵트인 integration 검증 비용 별도)

## 5. 시작 명령

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```

```powershell
cd D:\ClaudeCowork\game-asset-helper\game-asset-helper
```

```powershell
git checkout -b feat/m11-2-batch-spritesheet-modality
```

```powershell
pytest -q
```

→ 1490 passed 확인 후 Phase 1 부터.
