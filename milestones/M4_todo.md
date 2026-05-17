# M4 todo

[M4_plan.md](./M4_plan.md) 에서 도출한 TDD 순서 체크리스트. 작업 단위 번호(§3.x) 는 plan 의 절을 그대로 가리킨다.

체크박스 진행 규칙 (M3 와 동일) — A(스캐폴딩) → B(red, 테스트 먼저 모두 작성·실행) → C(green, 모듈 의존 순서대로 통과) → D(검증) → E(M5 인계).

## A. 스캐폴딩 / 의존성 / 분기

`milestones/M4_plan.md` §2.1 의 의존성·테스트 인프라.

- [ ] **브랜치** — `main` 에서 `feat/m4-search-ux` (또는 사용자 결정 다른 이름) 분기 후 작업.
- [ ] `pyproject.toml` — 추가 의존성 **없음**. 변경 사항 없음 확인.
- [ ] `src/gah/mcp/` / `src/gah/ui/` / `src/gah/core/` 디렉터리 그대로 — 새 모듈만 추가.
- [ ] `tests/conftest.py` — M4 fixture 추가
  - `m4_store` — M3 `populated_store` 위에 `saved_searches`/`feedback_records` 비어 있는 초기 상태 + 2~3 자산이 axis/label 매칭 가능한 시드
  - `populated_label_registry` — 외부 DB 없이 결정적 라벨 시드 (axis 5~6개 × label 10개 정도) 로 파서 테스트 빠르게 실행
  - `make_search_request` — `SearchRequest` 빌더 헬퍼
  - `tmp_thumbnail_cache` — 임시 디렉터리 + 1 sprite PNG seed
  - `mcp_tool_deps_m4` — `ToolDeps` 빌더 (M3 의 `mcp_tool_deps` 위에 `usage`/`registry` 같은 정상 컴포넌트 주입 + queue=None)

## B. 테스트 작성 (red phase)

먼저 모든 테스트 파일을 작성하고 `pytest -q` 한 번 돌려서 **새로 추가된 테스트들이 모두 fail** 하는지 확인. M0/M1/M2/M2.1/M3 의 333 케이스는 그대로 PASS 단, M3 의 `test_config_m3::test_weight_sum_equals_one_within_tolerance` 1 케이스는 6채널 가정으로 갱신 (red 단계에서 fail → green 단계에서 6채널 합 1.0 단언으로 수정).

### B.1 `tests/test_label_query.py` (16 케이스)

- [ ] `test_empty_input_returns_empty_parsed`
- [ ] `test_single_bare_label_resolves_to_axis`
- [ ] `test_axis_label_explicit_form_matches_exact`
- [ ] `test_and_two_atoms_to_labels_all`
- [ ] `test_or_two_atoms_to_labels_any`
- [ ] `test_not_atom_to_labels_none`
- [ ] `test_implicit_and_between_adjacent_atoms`
- [ ] `test_nested_parens_pure_and`
- [ ] `test_nested_parens_pure_or`
- [ ] `test_mixed_and_or_raises_unsupported_expression`
- [ ] `test_unknown_token_goes_to_free_text`
- [ ] `test_ambiguous_bare_label_raises_with_candidates` — 같은 label 이 axis 2개에 등록된 경우
- [ ] `test_uppercase_only_keywords` — `and` (소문자) 는 라벨로 취급
- [ ] `test_korean_label_matches` — UTF-8 라벨 매칭 검증
- [ ] `test_quoted_string_token_preserved` — `"dark cave"` 는 단일 free_token
- [ ] `test_precedence_not_then_and_then_or` — `a OR b AND NOT c` → `(a) OR (b AND NOT c)` 형식, 혼합이지만 단순 케이스 처리 (이 경우 v1 한계 — `UnsupportedExpression` 예외도 OK; 테스트는 raises 형태로 작성)

### B.2 `tests/test_store_m4.py` (12 케이스)

- [ ] `test_initialize_creates_m4_tables` — saved_searches/feedback_records 존재
- [ ] `test_initialize_is_idempotent_with_m1_m2_m3_tables` — 두 번 호출해도 OK
- [ ] `test_save_search_returns_id`
- [ ] `test_save_search_duplicate_name_raises_operational_error`
- [ ] `test_list_saved_searches_orders_by_last_used_desc`
- [ ] `test_delete_saved_search_returns_true_when_present`
- [ ] `test_delete_saved_search_returns_false_when_missing`
- [ ] `test_update_saved_search_last_used_sets_timestamp`
- [ ] `test_insert_feedback_record_persists_signed_weight`
- [ ] `test_feedback_records_for_project_filters_window`
- [ ] `test_pack_feedback_count_aggregates_negative_only`
- [ ] `test_delete_project_cascades_saved_and_feedback`

### B.3 `tests/test_search_diversity.py` (9 케이스)

- [ ] `test_diversity_none_preserves_m3_order`
- [ ] `test_mmr_lambda_1_equals_pure_score_order`
- [ ] `test_mmr_lambda_0_forces_different_packs`
- [ ] `test_mmr_lambda_07_balances_score_and_diversity`
- [ ] `test_round_robin_alternates_packs`
- [ ] `test_round_robin_single_pack_falls_back_to_score`
- [ ] `test_candidates_below_count_returns_all_regardless_of_diversity`
- [ ] `test_mmr_does_not_alter_score_breakdown` — diversity 는 순위만 변경, 점수는 변경 없음
- [ ] `test_diversity_lambda_none_uses_config_default`

### B.4 `tests/test_feedback_penalty.py` (10 케이스)

- [ ] `test_negative_feedback_lowers_next_search_feedback_channel`
- [ ] `test_positive_feedback_raises_next_search_feedback_channel`
- [ ] `test_positive_and_negative_for_same_asset_sums`
- [ ] `test_feedback_outside_window_is_ignored`
- [ ] `test_feedback_in_other_project_does_not_affect_this_project`
- [ ] `test_pack_level_penalty_when_three_negatives_in_same_pack`
- [ ] `test_pack_level_penalty_not_applied_below_threshold`
- [ ] `test_weight_feedback_zero_means_no_effect`
- [ ] `test_unknown_reason_rejected_by_mcp_model` — Pydantic Literal 검증
- [ ] `test_feedback_records_accumulate_across_calls`

### B.5 `tests/test_suggest_packs_samples_rich.py` (6 케이스)

- [ ] `test_sprite_sample_has_thumbnail_path`
- [ ] `test_sound_sample_has_null_thumbnail_with_blurb`
- [ ] `test_gemma_description_truncated_to_first_line_and_80_chars`
- [ ] `test_blurb_falls_back_to_top2_labels_when_no_description`
- [ ] `test_include_thumbnails_false_skips_thumbnail_generation`
- [ ] `test_thumbnail_cache_directory_auto_created`

### B.6 `tests/test_library_search_ui_rich.py` (14 케이스, offscreen)

- [ ] `test_label_chip_panel_renders_all_24_axes`
- [ ] `test_label_chip_panel_emits_selection_changed_on_check`
- [ ] `test_label_chip_panel_radio_mode_toggle_changes_emit_meta`
- [ ] `test_search_side_panel_slider_initial_values_match_config`
- [ ] `test_search_side_panel_slider_change_updates_config_immediately`
- [ ] `test_search_side_panel_preset_button_applies_weights`
- [ ] `test_search_side_panel_saved_searches_load_on_open`
- [ ] `test_search_side_panel_save_button_emits_save_signal_with_name`
- [ ] `test_search_side_panel_saved_search_double_click_emits_activated`
- [ ] `test_filter_bar_pack_multi_select_changes_emit`
- [ ] `test_filter_bar_kind_dropdown_filters_search`
- [ ] `test_filter_bar_sort_change_triggers_re_search`
- [ ] `test_library_view_result_row_shows_matched_labels`
- [ ] `test_library_view_debounce_remains_250ms_after_rich_ux_added`

### B.7 `tests/test_mcp_tools_m4.py` (14 케이스)

- [ ] `test_find_asset_label_query_parses_and_injects`
- [ ] `test_find_asset_structured_labels_plus_label_query_merge`
- [ ] `test_find_asset_ambiguous_label_returns_400_with_candidates`
- [ ] `test_find_asset_diversity_mmr_propagates_to_searcher`
- [ ] `test_report_feedback_negative_inserts_signed_weight`
- [ ] `test_report_feedback_unknown_reason_validation_error`
- [ ] `test_save_search_persists_and_returns_id`
- [ ] `test_save_search_duplicate_name_returns_400`
- [ ] `test_list_saved_searches_sorted_last_used_desc`
- [ ] `test_delete_saved_search_returns_ok_when_present`
- [ ] `test_delete_saved_search_404_when_missing`
- [ ] `test_run_saved_search_delegates_to_find_asset`
- [ ] `test_run_saved_search_404_when_name_missing`
- [ ] `test_register_all_tools_count_is_16` — 12 → 16 회귀 가드

### B.8 `tests/test_search_m4.py` (8 케이스)

- [ ] `test_six_channel_score_breakdown_sums_to_score_within_tolerance`
- [ ] `test_weight_feedback_override_applied`
- [ ] `test_feedback_channel_zero_when_no_feedback_records`
- [ ] `test_label_query_free_text_appended_to_semantic_query`
- [ ] `test_apply_diversity_mmr_picks_different_packs`
- [ ] `test_apply_diversity_round_robin_balances_packs`
- [ ] `test_six_channel_does_not_break_m3_baseline_search`
- [ ] `test_weight_feedback_zero_keeps_breakdown_key_with_value_zero`

### B.9 `tests/test_config_m4.py` (6 케이스)

- [ ] `test_weight_feedback_default_is_010`
- [ ] `test_six_channel_weights_sum_equals_one_within_tolerance`
- [ ] `test_diversity_default_is_none`
- [ ] `test_diversity_mmr_lambda_default_is_07`
- [ ] `test_feedback_weights_have_expected_signs` — negative<0, positive>0
- [ ] `test_toml_roundtrip_preserves_all_m4_fields`

### B.10 `tests/test_thumbnails.py` (5 케이스)

- [ ] `test_first_call_generates_256_png`
- [ ] `test_second_call_returns_cached_file_without_regeneration`
- [ ] `test_sound_kind_returns_none`
- [ ] `test_cache_directory_auto_created`
- [ ] `test_invalid_path_returns_none_and_logs`

### B.11 회귀 갱신

- [ ] `tests/test_config_m3.py::test_weight_sum_equals_one_within_tolerance` — 5채널 합 1.0 단언을 6채널 합 1.0 으로 갱신 (test 코드를 수정 — green 단계에서 M4 Config 가 6 weight 노출하면 자동 통과)
- [ ] `tests/test_mcp_integration.py` (옵트인) — `tools/list` 응답이 12 → 16 도구 단언 갱신 (가능 시 `expected = {12개 + 4 saved_search}`)

빠진 회귀 방지 — `tests/test_imports.py` 가 M4 신규 모듈 (`gah.core.label_query`, `gah.core.thumbnails`, `gah.core.suggest_packs`, `gah.ui.label_chip_panel`, `gah.ui.search_side_panel`, `gah.ui.filter_bar`) 추가 후 그대로 PASS.

**테스트 작성 후 한 번 돌려 확인** — `pytest -q` 결과가 M0/M1/M2/M2.1 **221 PASS** + M3 **111 PASS** + 갱신 **1 FAILED** (`test_weight_sum_equals_one_within_tolerance`) + M4 신규 **~100 FAILED** 가 되어야 한다. 새 테스트가 PASS 라고 표시되면 fixture 누락이나 import 우회 점검.

> 케이스 합: B.1(16) + B.2(12) + B.3(9) + B.4(10) + B.5(6) + B.6(14) + B.7(14) + B.8(8) + B.9(6) + B.10(5) = **100 신규 active**. B.11 갱신 (회귀 흡수).

## C. 구현 (green phase)

의존 순서대로 모듈을 작성하고, 해당 모듈 단위 테스트만 좁혀 돌려 통과 확인 (`pytest tests/test_<x>.py -v`). 한 묶음이 끝나면 인접 묶음 회귀가 없는지 `pytest -q` 한 번.

### C.1 Config 마이그레이션 + Store M4 스키마

- [ ] `src/gah/config.py` 수정
  - 가중치 기본값 재배분 — `weight_semantic 0.40 → 0.35`, `weight_keyword 0.15 → 0.10`, `weight_feedback 0.10` 신규 (합 1.00)
  - `diversity_default = "none"`, `diversity_mmr_lambda = 0.7` 신규
  - `feedback_negative_weight = -0.5`, `feedback_positive_weight = 0.3`, `feedback_irrelevant_weight = -0.3` 신규
  - `feedback_pack_threshold = 3`, `feedback_pack_penalty = -0.1`, `feedback_window_seconds = 2_592_000` 신규
  - `from_mapping` 의 가중치 합 검증을 6채널로 확장 (경고 + 기본값 폴백)
- [ ] `src/gah/core/store.py` 수정
  - `_M4_SCHEMA` 상수 + `initialize()` 가 M1·M2·M3·M4 순차 실행
  - 신규 데이터클래스 `SavedSearchRow(id, project_id, name, query_json, created_at, last_used_at)`
  - write: `save_search` / `delete_saved_search` / `update_saved_search_last_used` / `insert_feedback_record`
  - read: `list_saved_searches` / `get_saved_search` / `feedback_records_for_project` / `pack_feedback_count`
  - 모든 write 는 `with self.write_lock:` 안
- [ ] 회귀 갱신 — `tests/test_config_m3.py::test_weight_sum_equals_one_within_tolerance` 를 6채널 합 1.0 단언으로 수정 (`assert (config.weight_semantic + config.weight_keyword + ... + config.weight_feedback) == pytest.approx(1.0, abs=1e-6)`)
- [ ] 테스트 좁혀 돌리기 — `pytest tests/test_config_m4.py tests/test_store_m4.py tests/test_config_m3.py -v`

### C.2 `core/label_query.py` 파서

- [ ] `src/gah/core/label_query.py` 신규
  - `ParsedLabelQuery(labels_all, labels_any, labels_none, free_text, original_expr)` dataclass
  - 예외 — `LabelQueryError(ValueError)` / `AmbiguousLabel(label, candidates)` / `UnsupportedExpression(hint)`
  - 토크나이저 — 공백 + 따옴표/괄호/콜론 처리, `Token(text, kind)`. kind ∈ `{LPAREN, RPAREN, AND, OR, NOT, AXIS, LABEL, FREE}`. `AND`/`OR`/`NOT` 은 대문자 전체 일치만.
  - 분류기 — 각 LABEL/AXIS_LABEL 토큰을 LabelRegistry 매칭. `AmbiguousLabel` 시 후보 axis 리스트 동봉.
  - 재귀하강 파서 — `or_expr`/`and_expr`/`not_expr`/`atom` 4 함수. AST 노드 `OrNode`/`AndNode`/`NotNode`/`AtomNode(LabelFilter)`.
  - DNF 정규화 — 순수 AND 또는 순수 OR 만 정확 매핑. 혼합 → `UnsupportedExpression`.
  - `parse_label_query(text, registry) -> ParsedLabelQuery` 공개 API
  - 빈 입력 또는 라벨 0개 → 빈 `ParsedLabelQuery(free_text=text)`
- [ ] `src/gah/core/__init__.py` — 신규 모듈 export (선택)
- [ ] 테스트 — `pytest tests/test_label_query.py -v`

### C.3 `core/thumbnails.py` + `core/suggest_packs.py`

- [ ] `src/gah/core/thumbnails.py` 신규
  - `ensure_thumbnail(asset_path, kind, cache_dir, asset_id, *, max_size=256) -> Path | None`
  - sprite 만 처리, sound/spritesheet → None
  - 캐시 hit 시 즉시 반환 (mtime 비교는 v1 미포함 — 단순 존재 체크)
  - Pillow `Image.open().thumbnail((256,256)).save(out, "PNG")`
  - 실패 시 `log.exception` + None
- [ ] `src/gah/core/suggest_packs.py` 신규
  - `enrich_sample(asset_row, store, cache_dir, *, include_thumbnails) -> dict`
  - `_extract_blurb(asset_row, store) -> str | None` — Gemma description 첫 한 줄 (80자 컷) 또는 top-2 라벨 폴백 (`"axis=label · axis=label"`)
- [ ] 테스트 — `pytest tests/test_thumbnails.py tests/test_suggest_packs_samples_rich.py -v`

### C.4 `core/search.py` 6 채널 + 다양성 + label_query 통합

- [ ] `src/gah/core/search.py` 수정
  - `SearchRequest` 4 필드 추가 — `label_query`, `diversity`, `diversity_lambda`, `weight_feedback_override`
  - `HybridSearcher.hybrid()` 단계 확장 (M3 5채널 → M4 6채널 + diversity)
  - 신규 헬퍼:
    - `_feedback_bonus(store, project_id, ordered, asset_meta, config) -> dict[int, float]` — asset-level + pack-level 합산, [-1, +1] 클램프
    - `_apply_diversity(ranked, method, lambda_, count) -> list[int]` — none/mmr/round_robin 분기
  - `ResultRow.score_breakdown` 에 항상 `feedback` 키 포함 (값 0 가능)
  - `label_query` 가 있으면 `parse_label_query` 호출 후 SearchRequest 의 `labels_*` 와 병합. AmbiguousLabel / UnsupportedExpression 은 그대로 raise (caller 가 처리)
- [ ] 테스트 — `pytest tests/test_search_m4.py tests/test_search_diversity.py tests/test_feedback_penalty.py tests/test_search.py -v` (M3 회귀 같이)

### C.5 MCP 모델 + 도구 + 서버

- [ ] `src/gah/mcp/models.py` 수정
  - `FindAssetRequest` 4 필드 추가 — `label_query`/`diversity`/`diversity_lambda`/`weight_feedback_override`
  - `ReportFeedbackRequest.reason` 을 `Literal["negative", "positive", "irrelevant"]`
  - 신규 모델 — `SaveSearchRequest`/`SaveSearchResult`/`ListSavedSearchesResult`/`DeleteSavedSearchRequest`/`RunSavedSearchRequest`
  - 모든 신규 모델 `model_config = ConfigDict(extra="forbid")`
- [ ] `src/gah/mcp/tools.py` 수정
  - `tool_find_asset` — `label_query` 파서 호출 + AmbiguousLabel/UnsupportedExpression → `400_invalid_input`
  - `tool_report_feedback` — Config 의 `feedback_*_weight` 로 signed weight 결정 + `store.insert_feedback_record` (project 없는 query 는 skipped=True 반환)
  - `tool_suggest_packs` — `suggest_packs.enrich_sample` 로 위임
  - 신규 4 도구 — `tool_save_search`/`tool_list_saved_searches`/`tool_delete_saved_search`/`tool_run_saved_search` (모두 write 는 write_lock)
- [ ] `src/gah/mcp/server.py` 수정
  - `register_all_tools` 가 신규 4 도구 등록 — 총 16 도구
  - `INSTRUCTIONS` 갱신 (저장된 검색 / 페널티 학습 / 다양성 옵션 한 문단)
- [ ] 테스트 — `pytest tests/test_mcp_tools_m4.py tests/test_mcp_models.py tests/test_mcp_tools.py tests/test_mcp_server_stdio.py -v`

### C.6 GUI 라이브러리 탭 풍부 UX

- [ ] `src/gah/ui/label_chip_panel.py` 신규
  - `LabelChipPanel(registry, parent)` — axis 별 QGroupBox + QCheckBox 다중 선택
  - 상단 QRadioButton 그룹 — AND/OR/NOT 모드 (패널 전체 단위)
  - `selectionChanged` 시그널
  - `selected() -> tuple[str, list[LabelFilter]]`
  - `populate(registry)` — registry 변경 시 재구성 (axis 단위 partial 갱신 v1 은 단순 clear+rebuild)
- [ ] `src/gah/ui/search_side_panel.py` 신규
  - `SearchSidePanel(config, store, parent)` — 6 슬라이더 (`weight_*`) + 3 프리셋 버튼 + 저장된 검색 QListWidget + "저장" 버튼
  - Config 양방향 바인딩 (`bind_config`/`reload_from_config`)
  - 시그널 — `weightsChanged`, `savedSearchActivated(name)`, `saveCurrentRequested(name)`
  - 프리셋 상수 — `DEFAULT_M4_WEIGHTS` / `CONSISTENCY_FIRST_WEIGHTS` / `NOVELTY_FIRST_WEIGHTS`
- [ ] `src/gah/ui/filter_bar.py` 신규
  - `FilterBar(store, parent)` — pack 다중 선택 + kind/state/license/vendor 드롭다운 + 정렬 드롭다운
  - `filterChanged` 시그널
  - `current_filters() -> dict` (SearchRequest.filters + sort_key + sort_order)
- [ ] `src/gah/ui/library_view.py` 대대적 수정
  - QSplitter — 왼쪽 LabelChipPanel + FilterBar / 가운데 검색 박스 + 테이블 / 오른쪽 SearchSidePanel
  - `set_label_registry(registry)` / `set_config(config)` 신규 setter (`app.py` 가 주입)
  - `_run_search` 가 chip + slider + filter + 검색박스 입력을 통합 → SearchRequest 빌드 후 `HybridSearcher.hybrid()` 호출
  - 결과 행에 `matched_labels` 칩 텍스트 노출 (`axis=label · axis=label` 형식)
  - 디바운스 250ms 유지
- [ ] `src/gah/app.py` 수정 — 신규 위젯/setter 호출
  - `main_window.library_view.set_label_registry(registry)`
  - `main_window.library_view.set_config(config)`
- [ ] 테스트 — `pytest tests/test_library_search_ui_rich.py tests/test_library_search_ui.py -v`

### C.7 `docs/MCP_USAGE_GUIDE.md` + `DESIGN.md` 갱신

- [ ] `docs/MCP_USAGE_GUIDE.md` — 신규 섹션
  - §1.1 신규 4 도구 (`save_search`/`list_saved_searches`/`delete_saved_search`/`run_saved_search`) 실응답 JSON
  - §3.2 `label_query` 문법 + DNF 한계 + 모호 토큰 에러 예시
  - §4 `diversity` 옵션 + λ 튜닝 노트
  - §5 `report_feedback` reason enum + 페널티 학습 동작
  - §6 에러 코드 표 갱신 (`400_invalid_input` 의 새 변형)
- [ ] `DESIGN.md` — 갱신
  - §5.1 SQL 스키마 끝에 `saved_searches`/`feedback_records` 2 블록 추가
  - §6.5 `suggest_packs.samples` 풍부화 명시
  - §6.10 `report_feedback` reason enum + 페널티 학습 알고리즘
  - §6.12 (신규) — 4 저장된 검색 도구 명세
  - §11 M4 실제 한 일 정리 + defer 한 항목 명시

각 묶음 마지막에 `pytest -q` 로 회귀 점검. 전체 묶음이 다 끝나면 합계 ≈ **429 passed** + 4 deselected (`clip_integration` 2 + `mcp_integration` 2).

## D. 검증

자동:

- [ ] `pytest -q` 전체 통과 (M0/M1/M2/M2.1/M3 회귀 없음 + 갱신 1 + M4 신규 모두 PASS) — 약 429 passed, 4 deselected
- [ ] `pytest -m mcp_integration -v` (옵트인) — `tools/list` 가 16 도구 (갱신 후) 통과
- [ ] `pytest -m clip_integration -v` (옵트인, M2 회귀 보존) — 2 케이스 통과

수동 (메모리 `feedback_run_commands_directly.md` — 자동화 가능한 것은 Claude 가 PowerShell 로 직접 측정, GUI 시각 확인만 사용자):

- [ ] `python -m gah --mcp` 의 `tools/list` 가 16 도구 — *Claude 가 직접*
- [ ] `find_asset` 에 `label_query="sound_mood:dark AND sound_use:combat"` 전달 → `matched_labels` 정확 — *Claude 가 직접*
- [ ] `report_feedback(reason="negative")` 호출 후 같은 자산의 다음 검색 `score_breakdown.feedback` 음수 — *Claude 가 직접*
- [ ] `save_search` → `list_saved_searches` → `run_saved_search` 라운드트립 — *Claude 가 직접*
- [ ] `sqlite3 ...\metadata.db ".tables"` 가 `saved_searches`/`feedback_records` 포함 — *Claude 가 직접*
- [ ] **GUI 풍부 UX 4 항목 시각 확인** — *사용자 수동* (응답 본문에 단계별 체크리스트로 별도 제시)
  1. 라이브러리 탭 좌측에 라벨 칩 패널 (axis 별 그룹 + AND/OR/NOT 라디오) 노출
  2. 우측에 가중치 슬라이더 6채널 + 프리셋 버튼 3개 + 저장된 검색 리스트 + "저장" 버튼 노출
  3. 상단 검색 박스에 `"sound_mood:dark AND sound_use:combat"` 입력 → 250ms 후 결과 행에 `matched_labels` 칩 노출
  4. "저장" 버튼 → 이름 다이얼로그 → 저장된 검색 리스트에 추가 → 더블클릭하면 재호출

수동 검증 절차 전체는 [`M4_verification.md`](./M4_verification.md) 에 PowerShell 한 줄씩 풀어 작성.

## E. M5 인계

- [ ] `milestones/M4_verification.md` 작성 — `pytest -v` 출력, 환경 한계, Claude 가 직접 측정한 자동 검증 결과 + 사용자 수동 검증 4 항목 결과
- [ ] `HANDOFF.md` 갱신
  - §1 한 줄 요약 — M4 완료 + 다음 M5 (시트 분석 + 애니메이션)
  - §2 검증된 사실 — 429 passed 표
  - §3 환경 — 의존성 변화 없음 명시
  - §5 M5 시작 절차 — M4 plan/todo 를 템플릿 삼아 M5 작성 가이드 (격자 분할 / Aseprite·TexturePacker JSON / `suggest_animation_frames`)
  - §6 의도적으로 남겨둔 자리 — 그리드↔리스트 토글 / hover preview / 사운드 인라인 재생 / 결과 비교 보기 / 키보드 단축키 / `cleanup_feedback_records` 잡 / 한국어 키워드 파서 / 혼합 AND/OR DNF 모두 M7 (또는 M5+)
- [ ] `CLAUDE.md` §2 진행 현황 표의 M4 상태 ✅ + §8 을 M5 안내로 교체
- [ ] `milestones/README.md` 의 마일스톤 표 갱신
- [ ] `docs/MCP_USAGE_GUIDE.md` 본격 가이드 확인 — 신규 4 도구 + `label_query` + `diversity` + 페널티 학습 모두 채워짐
- [ ] PR 머지 후 `feat/m4-search-ux` 브랜치 삭제 (또는 사용자 결정 대기)
