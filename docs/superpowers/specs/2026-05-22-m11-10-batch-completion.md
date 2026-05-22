# M11.10 — Batch 완성 (text_embed + chat_spritesheet)

- **Spec ID**: `m11-10-batch-completion-2026-05-22`
- **Trigger**: M11.9 머지 + CLIP fix PR #32 LIVE 검증 중 발견 — 26 sprite 분석에 Gemini API ~53 호출 (chat_image 만 batch, 나머지 sync).  사용자 질문 "일괄로 할 방법은?"
- **Severity**: medium — 기능 정상 동작.  비용 (Gemini API token 과금) + latency 증가.  대규모 라이브러리 (수천 sprite) 에서는 비용 폭발 + rate limit 위험
- **Branch**: `feat/m11-10-batch-completion` (v0.2.9 candidate, M11.9 PR #31 + CLIP PR #32 머지 후)
- **추정 작업 시간**: 2~4h (TDD red→green + LIVE 검증 포함)

## 1. 배경 (관측 사실)

CLIP fix LIVE 검증 (PR #32) 중 `pixel_food_items_fruits` 팩 26 sprite 분석 시 로그 호출 카운트:

| 호출 종류 | 횟수 | Modality | 비고 |
|---|:-:|---|---|
| `batchGenerateContent` | **1** | chat_image | ✅ 25 sprite 동시 (job_id=1, succeeded) |
| `generateContent` (sync) | ~26 | chat_spritesheet 또는 leftover | ⚠️ sprite_meta enrichment.  batch path 있는데 분기에서 sync 떨어짐 |
| `batchEmbedContents` (endpoint, 단일 input) | ~26 | text_embed | ⚠️ SDK 의 `embed_content(contents=str)` 단일 호출.  multi-input batch 미사용 |
| CLIP scoring | 0 | (로컬) | ✅ 4368 label rows, API 0 호출 |

**총**: 1 batch + ~52 sync ≈ **53 호출 / 26 sprite ≈ 2.04 호출/sprite**.

대규모 라이브러리 예상 비용:
- 1,000 sprite → ~2,040 호출
- 10,000 sprite → ~20,400 호출 (Gemini rate limit 충돌 가능성)

목표 도달 시:
- 1,000 sprite → **~40 호출** (batch 1개에 25 sprite 가정).  **50× 감소**

## 2. Root Cause (추정 → 검증 Phase 0 에서 확정)

### 2.1 text_embed 가 sync 떨어진 이유

코드 흐름 (`src/assetcache/core/`):

- `embedding.py:58` — `EmbeddingManager` 가 `self.client.embed(text)` 호출 (single text).
- `core/llm/backends/gemini.py:153-158` — `GeminiBackend.embed()` 가 `self._client.models.embed_content(contents=text)` (single string).
- `core/batch/manager.py:183` — `backend.batch_embed(texts=texts)` 호출 (multi-input batch 함수 **존재**) — BatchManager 의 batch submit path 에서만 호출됨.

**의심**: text_embed modality 가 batch submit path 진입을 안 함.  가능한 원인:
- (A) Analyzer 가 batch 등록 전에 sync `embed()` 직접 호출 (`EmbeddingManager` 단독 호출 경로)
- (B) text_embed batch 가 chat_image batch 결과 도착 후 따라가야 하는데, 트리거 wiring 누락
- (C) text_embed modality 의 `fetch_pending_by_modality(modality='text_embed')` 가 0 행 반환 (assets 가 text_embed 용 pending 상태로 마크 안 됨)

### 2.2 chat_spritesheet 가 sync 떨어진 이유

- `core/batch/manager.py:128-149` — `classify_image_assets` 호출 후 sheet hits 만 chat_spritesheet batch.  **sheet 가 아닌 단일 sprite 의 sprite_meta enrichment** 은 어디서 처리되는가?
- 의심: 단일 sprite 의 sprite_meta 추출이 별도 sync analyzer path 로 떨어짐 (`core/analyzer/spritesheet_meta.py` 의 sync 진입점).

### 2.3 sync 26 호출 카운트 ≠ 26 sprite 의 1:1

가능: 26 sprite × (chat_spritesheet 1번 + text_embed 1번) = 52 sync ≈ 사용자 로그의 ~52 sync 합.

## 3. 목표 (Acceptance Criteria)

### 3.1 정량 목표

- [ ] AC #1: `pixel_food_items_fruits` (26 sprite) **재분석 시** Gemini API 호출 ≤ **5** (chat_image 1 + chat_spritesheet 1 + text_embed 1 + 안전 마진 2).  현재 53.  **10× 감소**.
- [ ] AC #2: 비용 (token usage) 측면에서 chat_image batch 가 sync 와 동등 (이미 검증됨 — M11.1).  text_embed multi-input batch 가 동등.
- [ ] AC #3: latency — 1000 sprite 라이브러리 분석 wall-clock time `<` 현재 sync chain (목표 3× 이상 단축).  옵트인 LIVE 측정.

### 3.2 정성 목표

- [ ] AC #4: text_embed batch 진입 경로 명확 — Analyzer 가 description 모은 후 `batch_embed(texts=[...])` 1회 호출.  BatchManager 의 submit path 거치든 직접 호출 wrapper 든 OK.
- [ ] AC #5: chat_spritesheet sync 분기 → batch 통합 — 단일 sprite 의 sprite_meta enrichment 도 batch_image_chat (또는 chat_spritesheet batch) 로 묶임.
- [ ] AC #6: 회귀 `pytest -q` PASSED, 신규 red→green 케이스 모두 green.

### 3.3 비 목표 (Out of Scope)

- 다른 backend (OpenAI / Ollama) 의 batch 화 — Gemini 만 우선.  OpenAI batch 는 M11.x patches backlog item D 로 기록.
- Async / concurrent submit — 현재 단일 thread 의 sequential batch 로 충분.
- Batch 결과 streaming — 1회 poll → 1회 결과 그대로.
- Description 자체 LLM 생성 비용 (어떻게 description 을 적게 부르는가) — 본 spec 은 "이미 생성된 description 의 embedding 만" 다룸.

## 4. 구현 단계

### Phase 0 — Investigation (0.5h)

1. **재현 + measure baseline** — fresh data-dir 에 sprite 1 팩 (26 sprite) drop, helper script `.\scripts\launch-tray-test.ps1 m11-10-baseline`, 로그에서 `httpx | HTTP Request: POST .*google` 카운트 53 확인.
2. **text_embed sync 호출 trace** — `EmbeddingManager.run_for_pending_assets` (또는 동급) 호출 stack 추적.  어디서 `client.embed(text)` 호출되는지 + 왜 batch 안 가는지 파일·라인 명시.
3. **chat_spritesheet sync 호출 trace** — sprite_meta enrichment 의 sync 진입점 명시.
4. **결정 doc** — `docs/superpowers/specs/2026-05-22-m11-10-rca.md` 또는 본 spec 의 §2 update.

### Phase 1 — text_embed batch wiring (1h)

#### Phase 1-A — Red

신규 test (`tests/test_m11_10_batch_completion.py`):

1. `test_text_embed_uses_batch_when_threshold_met` — Mock GeminiBackend with `batch_embed` spy + `embed` spy.  Analyzer 가 26 text 처리 시 `batch_embed` 호출 1회 + `embed` 호출 0 회 검증.
2. `test_text_embed_falls_back_to_sync_when_batch_unsupported` — Mock backend.supports_batch=False → `embed` 단일 호출 N회.
3. `test_text_embed_batch_threshold_respect` — `batch.threshold=10` + 5 pending → batch 안 가고 sync.  `batch.threshold=3` + 5 pending → batch submit.

→ 3 red.

#### Phase 1-B — Green

1. `EmbeddingManager.run_for_pending_assets` (또는 신규 wrapper) 가 chain.batch_embed() 호출 분기 추가.  ChainBackend 의 `batch_embed(texts: list[str]) -> tuple[list[list[float]], str]` 시그니처 신설.
2. BackendChain (`core/llm/chain.py:97` 참조) 의 batch_embed 가 primary backend 위임.
3. Analyzer 진입점에서 pending text 모은 후 batch 호출.

→ 3 green.

### Phase 2 — chat_spritesheet sync 분기 통합 (1h)

#### Phase 2-A — Investigation (Phase 0 의 결과 활용)

단일 sprite (sheet 아님) 의 sprite_meta 가 어디서 호출되는지 명시.  현재 코드의 `chat_spritesheet` batch path 가 sheet hit 가 0 일 때 어떻게 동작하는지 추적.

#### Phase 2-B — Red

- `test_single_sprite_meta_goes_to_batch` — 26 단일 sprite (sheet 아님) 분석 시 sync `generateContent` 호출 0회 + `batchGenerateContent` 1~2회 검증.

#### Phase 2-C — Green

가능 옵션:
- 옵션 1: chat_image batch 의 응답에 sprite_meta 필드 동봉 (현재 chat_image 가 라벨만, sprite_meta 는 별도) — prompt 확장
- 옵션 2: chat_spritesheet modality 의 단일 sprite path 추가 — sheet=False sprite 들도 묶어 batch

옵션 1 이 호출 절감 효과 큼 (chat_image 1회 batch 안에 sprite_meta 포함).  옵션 2 는 별도 batch 추가 (1 batch → 2 batch).

Phase 0 결과 보고 선택.

### Phase 3 — LIVE 검증 (0.5h)

- Fresh data-dir + `pixel_food_items_fruits` 팩 (26 sprite) + helper script 부팅
- 로그 grep `httpx.*POST.*google` 카운트 ≤ 5 확인
- DB 검증: 26 ok + 26 embedding + 26 sprite_meta + label rows ≥ 4500 (현재 baseline)

### Phase 4 — PR (0.5h)

- `feat/m11-10-batch-completion` 브랜치 commit + push + PR draft
- verification doc `milestones/M11_10_verification.md` 작성
- v0.2.9 candidate

## 5. 테스트 전략

### 5.1 자동 (pytest)

신규 케이스:
- `tests/test_m11_10_batch_completion.py` — Phase 1 + Phase 2 red→green 케이스 (5~8 케이스)

옵트인 (`@pytest.mark.llm_integration`):
- 실 Gemini API 호출 카운트 측정 (현재 baseline 53 → 목표 ≤5)

### 5.2 LIVE

- `scripts/launch-tray-test.ps1 m11-10-live` + `pixel_food_items_fruits` drop
- 로그 카운트 검증
- DB 검증

### 5.3 회귀

- `pytest -q` 1560 + 신규 = 1568~1572 예상 (band 미정 — Phase 1-A red 의 정확한 케이스 수 따라)
- 옵트인 `pytest -m llm_integration` 6 PASSED 유지

## 6. 위험 / 의존성

- **Gemini batchEmbedContents endpoint 의 multi-input 한계**: 최대 100 input / call.  26 sprite 는 안전 — 1000 sprite 라이브러리도 10 batch 로 처리 (chunk).  문서: https://ai.google.dev/api/embeddings
- **batch_embed 응답 순서**: input 순서와 결과 순서 매칭 보장 (Gemini API 보장).  test 에서 명시 검증.
- **chat_image batch + sprite_meta 동봉 (Phase 2 옵션 1)**: prompt 변경 + 응답 schema 확장.  M11.4 의 BATCH_IMAGE_PROMPT 영향 — payload_parser 동기화 필수.
- **CLIP fix PR #32 머지 의존**: M11.10 작업은 CLIP fix 완료 후.  순서: PR #32 → main → 본 spec branch off main.

## 7. 후속 (별도 trigger)

- v0.2.9 publish (M11.9 backend 정리 + CLIP fix + M11.10 batch 완성 동시 deliver)
- M11.x patches backlog item D — OpenAI Batch API 지원 (Anthropic 백엔드는 M11.9 에서 제거 — SDK 재도입 시점에 재평가)
- M11.x patches backlog item E — file destination batch (>20MB inline 우회) — 매우 큰 라이브러리에서 유의미

## 8. References

- Gemini Batch API docs: https://ai.google.dev/api/batch
- Gemini Embeddings API: https://ai.google.dev/api/embeddings
- `src/assetcache/core/batch/manager.py` — BatchManager 본체
- `src/assetcache/core/llm/backends/gemini.py:218` — `batch_embed()` 함수 (현재 호출 안 됨)
- `src/assetcache/core/embedding.py:58` — sync `client.embed(text)` 호출 위치
- M11.1 v0.2.1 — Gemini Batch API 첫 도입 (chat_image 만)
- M11.2 v0.2.2 — chat_spritesheet modality 신설
- CLIP fix PR [#32](https://github.com/v0o0v/assetcache-mcp/pull/32) — 본 spec 의 LIVE 발견 기원
