# M11.2 TDD 체크리스트

자세한 step 은 [`docs/superpowers/plans/2026-05-21-m11-2-batch-spritesheet-modality.md`](../docs/superpowers/plans/2026-05-21-m11-2-batch-spritesheet-modality.md) 참고. spec: [`docs/superpowers/specs/2026-05-21-m11-2-batch-spritesheet-modality.md`](../docs/superpowers/specs/2026-05-21-m11-2-batch-spritesheet-modality.md).

- [x] Phase 0 — env activate + branch checkout + baseline (1490)
- [x] Phase 1 — modality 분리 (store / config / chain / registry) — commit `f953417`
- [x] Phase 2 — sheet_classifier — commit `78ee90b`
- [x] Phase 3 — BATCH_SPRITESHEET_PROMPT + composite builder — commit `cd9e063`
- [x] Phase 4 — BatchManager chat_spritesheet 분기 + AnalysisQueue + Gemini backend — commit `8a1f006`
- [x] Phase 5 — BatchPoller _persist_spritesheet_payload — commit `2c3fdb1`
- [x] Phase 6 — UI / i18n / settings router — commit `3b6343c`
- [ ] Phase 7 — 통합 / 회귀 / 옵트인 / verification / PR

## 신규 테스트 카운트 (목표 ~+40)

| Phase | 파일 | 신규 |
|---|---|---:|
| 1 | test_store_modality_kind_filter.py | 5 |
| 1 | test_config.py (append) | 3 |
| 1 | test_llm_chain_spritesheet.py | 2 |
| 2 | test_batch_sheet_classifier.py | 7 |
| 3 | test_analyzer_messages_spritesheet.py | 5 |
| 4 | test_batch_manager_spritesheet.py | 7 |
| 4 | test_analysis_queue_batch_hook.py (append) | 1 |
| 4 | test_llm_backend_gemini_batch.py (append) | 1 |
| 5 | test_batch_poller_spritesheet_modality.py | 7 |
| **합계** | | **38** |

회귀 baseline 1490 → 약 **1528+** 예상 (Phase 7 옵트인 1 추가 시 1529).
