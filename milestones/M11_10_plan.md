# M11.10 Plan — Batch 완성 (text_embed + chat_spritesheet)

- **Spec**: [`docs/superpowers/specs/2026-05-22-m11-10-batch-completion.md`](../docs/superpowers/specs/2026-05-22-m11-10-batch-completion.md)
- **Branch**: `feat/m11-10-batch-completion` (v0.2.9 candidate)
- **추정 작업 시간**: 2~4h

## 목표

26 sprite 분석에 53 Gemini API 호출 → **≤5 호출** (10× 감소).  text_embed multi-input batch + chat_spritesheet sync 분기 통합.

## Phase 분할

### Phase 0 — Investigation (0.5h)

- [ ] Baseline 재현 — fresh data-dir + 26 sprite + 로그 카운트 53 확인
- [ ] text_embed sync trace — `EmbeddingManager` / `BackendChain` / `GeminiBackend.embed` 호출 stack
- [ ] chat_spritesheet sync trace — 단일 sprite (sheet 아님) sprite_meta 의 sync 호출 위치
- [ ] 결정 doc — Phase 2 옵션 (1 prompt 확장 vs 2 별도 batch) 선택

### Phase 1 — text_embed batch wiring (1h)

#### Phase 1-A — Red

- [ ] `tests/test_m11_10_batch_completion.py` 신설
- [ ] `test_text_embed_uses_batch_when_threshold_met` — batch_embed spy 1회 + embed spy 0회
- [ ] `test_text_embed_falls_back_to_sync_when_batch_unsupported`
- [ ] `test_text_embed_batch_threshold_respect`

→ 3 red 확인 (`pytest tests/test_m11_10_batch_completion.py -v`)

#### Phase 1-B — Green

- [ ] `EmbeddingManager.run_for_pending_assets` (또는 신규 wrapper) 에 batch_embed 분기 추가
- [ ] `BackendChain.batch_embed(texts: list[str]) -> tuple[list[list[float]], str]` 시그니처 신설
- [ ] Analyzer 진입점에서 pending text 모은 후 batch 호출
- [ ] 3 red → green

### Phase 2 — chat_spritesheet sync 통합 (1h)

#### Phase 2-A — Investigation 결과 적용

Phase 0 의 옵션 선택:
- 옵션 1 (chat_image prompt 확장 — sprite_meta 동봉): chat_image 1 batch 호출에 sprite_meta 포함
- 옵션 2 (chat_spritesheet 단일 sprite path): sheet=False 도 chat_spritesheet batch 로 묶기

#### Phase 2-B — Red

- [ ] `test_single_sprite_meta_goes_to_batch` — 26 단일 sprite 분석 시 sync `generateContent` 호출 0회 + `batchGenerateContent` 1~2회

#### Phase 2-C — Green

- [ ] 옵션 1 또는 2 구현
- [ ] payload_parser / messages 동기화 (옵션 1 인 경우)
- [ ] 1 red → green

### Phase 3 — LIVE 검증 (0.5h)

- [ ] Fresh data-dir + `pixel_food_items_fruits` (26 sprite) + helper script
- [ ] 로그 `httpx.*POST.*google` 카운트 ≤ 5 확인
- [ ] DB 검증 — 26 ok + 26 embedding + 26 sprite_meta + label rows ≥ 4500

### Phase 4 — Verification + PR (0.5h)

- [ ] `milestones/M11_10_verification.md` 작성 — 자동 + 옵트인 + LIVE + 한계
- [ ] HANDOFF.md 갱신
- [ ] Commit + push + PR draft (`feat/m11-10-batch-completion`)
- [ ] v0.2.9 candidate (publish 보류, 사용자 명시 시)

## 회귀 기준

- `pytest -q` baseline: `1560 passed + 1 skipped + 57 deselected` (M11.9 + CLIP fix PR #32 가정)
- 신규 red→green: 4~5 케이스 → green 후 `1564~1565 passed`
- 옵트인: `pytest -m llm_integration -v` 6 PASSED 유지

## 의존성

- ✅ M11.9 PR #31 main 머지 완료 (`1c85eaf`)
- ⚠️ CLIP fix PR #32 머지 후 본 작업 진입 — PR #32 의 변경분 (`clip_labeler.py:138` + 4 doc files) 이 main 에 있어야 함
- 트레이 부팅 LIVE 검증 시 `scripts/launch-tray-test.ps1` (chore PR #33 머지 완료, main `5bffaa4`)

## 비 목표

본 spec 의 §3.3 그대로:
- OpenAI / Ollama batch 화
- Async / concurrent submit
- Batch 결과 streaming
- Description 자체 LLM 생성 비용 (description-level dedup)
