# M2 todo

[M2_plan.md](./M2_plan.md) 에서 도출한 TDD 순서 체크리스트. 작업 단위 번호(§3.x)는 plan 의 절을 그대로 가리킨다.

체크박스 진행 규칙은 M1 과 동일 — A(스캐폴딩) → B(red, 테스트 먼저 모두 작성·실행) → C(green, 모듈 의존 순서대로 통과) → D(검증) → E(M3 인계).

## A. 스캐폴딩 / 의존성

- [ ] `pyproject.toml` — 다음 의존성을 `dependencies` 에 추가
  - `Pillow>=10`
  - `numpy>=1.26`
  - `librosa>=0.10`
  - `soundfile>=0.12`
  - `httpx>=0.27`
  - `pydantic>=2.6`
  - `open_clip_torch>=2.24`
  - `torch>=2.2`
  - `matplotlib>=3.8`
- [ ] `pyproject.toml` — `optional-dependencies.dev` 에 추가
  - `pytest-asyncio>=0.23`
  - `respx>=0.20`
- [ ] `pyproject.toml [tool.pytest.ini_options]` — `markers = ["clip_integration: requires real CLIP model download"]` + `addopts = "-ra -m 'not clip_integration'"`
- [ ] `src/gah/core/analyzer/__init__.py` 빈 패키지 마커
- [ ] `tests/conftest.py` — M2 픽스처 추가
  - `fixture_dir` — `tests/fixtures/` 경로 + 결정적 PRNG 로 fixture 파일 자동 생성
  - `mock_ollama` — `respx` 컨텍스트 + OpenAI/네이티브 라우트 헬퍼
  - `fake_clip_backend` — `FakeBackend` (sha256 → fake 임베딩)
  - `analyzer_inputs` — `AnalyzerInput` 빌더 헬퍼
- [ ] `tests/fixtures/` — 결정적 픽스처 (Pillow + numpy + soundfile 로 생성):
  - `tiny_pixel_32.png` (32×32 4색)
  - `tiny_vector_256.png` (256×256 그라디언트)
  - `transparent_alpha.png` (64×64 알파)
  - `short_sfx_1s.wav` (16kHz mono 1s)
  - `medium_sfx_5s.wav` (16kHz mono 5s)
  - `long_bgm_45s.wav` (16kHz mono 45s)
  - `mel_sample.png` (멜 스펙트로그램 모킹용)
- [ ] 의존성 설치 확인 — PowerShell 에서 `pip install -e D:\ClaudeCowork\game-asset-helper\game-asset-helper[dev]` 한 줄. torch wheel ≈ 800 MB 다운로드 인내.

## B. 테스트 작성 (red phase)

먼저 모든 테스트 파일을 작성하고 `pytest -q` 한 번 돌려서 **새로 추가된 테스트들이 모두 fail** 하는지 확인. M0/M1 의 67 케이스는 그대로 PASS.

### B.1 `tests/test_store_m2.py` (17 케이스)

- [ ] `test_initialize_creates_m2_tables` — sprite_meta/sound_meta/assets_fts/asset_embeddings/asset_labels/clip_label_cache/labels 모두 존재
- [ ] `test_initialize_is_idempotent_with_m1_tables`
- [ ] `test_save_sprite_meta_replaces`
- [ ] `test_save_sound_meta_replaces`
- [ ] `test_save_asset_labels_overwrites_per_asset`
- [ ] `test_save_embedding_roundtrip`
- [ ] `test_update_fts_can_be_searched` — `assets_fts MATCH 'pixel'` 동작
- [ ] `test_next_pending_asset_returns_oldest_first`
- [ ] `test_mark_asset_state_sets_analyzed_at_when_ok`
- [ ] `test_mark_asset_state_failed_keeps_analyzed_at_null`
- [ ] `test_pending_assets_for_pack_filters_correctly`
- [ ] `test_update_pack_aggregate_stores_json`
- [ ] `test_clip_label_cache_get_put`
- [ ] `test_save_asset_labels_with_dup_axis_label_different_source`
- [ ] `test_delete_asset_cascades_m2_tables`
- [ ] `test_labels_table_enforces_unique_axis_label`
- [ ] `test_labels_table_keeps_disabled_rows`

### B.2 `tests/test_labels.py` (19 케이스, 시드 + LabelRegistry)

- [ ] `test_seed_has_expected_axes` — `SEED_LABELS` 키 24개 정확히 일치(시각 14 + 사운드 10)
- [ ] `test_seed_no_duplicates_within_axis`
- [ ] `test_total_seed_count_in_range_290_to_340`
- [ ] `test_seed_animation_axis_matches_design_doc` — DESIGN §4.2.2 의 9개 포함
- [ ] `test_bootstrap_inserts_seed_on_empty_db_then_noop_on_second_call`
- [ ] `test_bootstrap_includes_description_for_every_seed_label`
- [ ] `test_list_labels_returns_only_enabled_by_default`
- [ ] `test_list_labels_returns_stable_sorted_order`
- [ ] `test_list_labels_with_description_true_returns_descriptions`
- [ ] `test_list_labels_with_description_false_omits_descriptions`
- [ ] `test_add_label_rejects_invalid_token` — `"Pixel Art"`/한글/공백/대문자 모두 거부
- [ ] `test_add_label_accepts_valid_user_token_with_source_user_and_null_description`
- [ ] `test_add_label_with_description_persists_string`
- [ ] `test_set_label_description_updates_row_and_updated_at`
- [ ] `test_add_label_existing_pair_returns_was_new_false_and_activates`
- [ ] `test_set_enabled_false_excludes_from_list_labels_default`
- [ ] `test_invalidate_clears_in_memory_cache`
- [ ] `test_label_catalog_signature_changes_on_add_disable_describe`
- [ ] `test_label_catalog_signature_stable_when_no_changes`

### B.3 `tests/test_labels_admin_ui.py` (7 케이스, offscreen)

- [ ] `test_dialog_lists_seed_axes`
- [ ] `test_table_shows_labels_with_source_and_state_and_description_columns`
- [ ] `test_add_label_input_writes_to_registry`
- [ ] `test_invalid_token_input_shows_inline_error_and_does_not_call_registry`
- [ ] `test_toggle_enable_writes_to_registry_and_refreshes_table`
- [ ] `test_edit_description_inline_writes_to_registry`
- [ ] `test_user_label_with_empty_description_shows_warning_icon`

### B.4 `tests/test_ollama_client.py` (16 케이스, respx 모킹)

- [ ] `test_chat_uses_openai_endpoint_first`
- [ ] `test_chat_falls_back_to_native_on_openai_4xx`
- [ ] `test_chat_falls_back_to_native_on_connect_error`
- [ ] `test_native_payload_packs_image_and_audio_into_single_images_field`
- [ ] `test_openai_payload_uses_image_url_data_uri`
- [ ] `test_openai_payload_uses_input_audio_dict`
- [ ] `test_chat_force_json_retries_on_invalid_json`
- [ ] `test_chat_gives_up_after_max_retries`
- [ ] `test_chat_raises_typed_error_on_total_failure`
- [ ] `test_embed_uses_openai_first_then_native`
- [ ] `test_embed_returns_floats_unchanged`
- [ ] `test_chat_passes_num_ctx_to_native`
- [ ] `test_chat_passes_format_json_to_native`
- [ ] `test_chat_uses_timeout_from_config`
- [ ] `test_encode_image_helper_base64`
- [ ] `test_encode_audio_clip_helper_outputs_wav_base64`

### B.5 `tests/test_embedding.py` (5 케이스)

- [ ] `test_encode_text_returns_bytes_and_dim`
- [ ] `test_encode_text_uses_configured_model_name`
- [ ] `test_decode_vector_roundtrips_through_blob`
- [ ] `test_first_call_determines_dim` — 응답 길이 768 → 이후 dim 강제
- [ ] `test_encode_text_propagates_ollama_error`

### B.6 `tests/test_clip_labeler.py` (8 케이스, 마지막 2개는 `clip_integration` 마크)

- [ ] `test_warmup_populates_cache_only_for_missing_labels`
- [ ] `test_score_image_returns_scores_per_label_in_zero_one_range`
- [ ] `test_score_image_clamps_negative_cosine_to_zero`
- [ ] `test_score_image_uses_cached_label_vectors_after_warmup`
- [ ] `test_label_added_after_warmup_is_computed_lazily`
- [ ] `test_disabled_clip_returns_empty_dict` — `config.clip_enable=False` 일 때
- [ ] `test_open_clip_backend_init_does_not_download_until_called` *(clip_integration)*
- [ ] `test_open_clip_backend_actual_inference` *(clip_integration)*

### B.7 `tests/test_searchable.py` (9 케이스)

- [ ] `test_for_fts_includes_label_prefixed_tokens` — `label:pixel_art`
- [ ] `test_for_fts_includes_axis_prefixed_tokens` — `category:character` (콜론 분리 이슈 발견 시 `_` 폴백)
- [ ] `test_for_fts_includes_label_descriptions_in_quotes`
- [ ] `test_for_fts_includes_path_and_size_meta`
- [ ] `test_for_embed_truncates_to_short_summary` — 공백 단위 ≤ 256
- [ ] `test_for_embed_uses_top_n_labels_by_score`
- [ ] `test_for_embed_includes_asset_description`
- [ ] `test_for_embed_excludes_path_and_low_score_labels`
- [ ] `test_for_fts_and_for_embed_are_distinct_strings`

### B.8 `tests/test_analyzer_sprite.py` (11 케이스)

- [ ] `test_analyze_pixel_art_classifies_as_pixel_art_via_heuristic`
- [ ] `test_analyze_vector_classifies_as_not_pixel_art`
- [ ] `test_analyze_extracts_alpha_correctly`
- [ ] `test_analyze_extracts_5_dominant_colors`
- [ ] `test_analyze_calls_ollama_with_resampled_image` — base64 디코드 후 긴 변 ≤ 768
- [ ] `test_analyze_validates_response_against_whitelist`
- [ ] `test_analyze_falls_back_to_other_after_max_retries`
- [ ] `test_analyze_integrates_clip_scores_as_separate_source_labels`
- [ ] `test_analyze_searchable_for_embed_includes_korean_description`
- [ ] `test_analyze_searchable_for_fts_uses_english_enum_regardless_of_language`
- [ ] `test_analyze_searchable_for_fts_includes_label_descriptions_from_registry`

### B.9 `tests/test_analyzer_sound.py` (13 케이스)

- [ ] `test_analyze_short_sfx_uses_native_path`
- [ ] `test_analyze_long_bgm_with_smart_chunks_merges_results`
- [ ] `test_analyze_falls_back_to_spectrogram_when_native_times_out`
- [ ] `test_analyze_marks_audio_path_used_spectrogram_when_fallback_succeeds`
- [ ] `test_analyze_falls_back_to_heuristic_when_both_paths_fail`
- [ ] `test_analyze_extracts_loudness_db_from_librosa`
- [ ] `test_analyze_detects_loopable_from_gemma_response`
- [ ] `test_analyze_does_not_call_clip_labeler`
- [ ] `test_analyze_emits_labels_for_all_ten_sound_axes`
- [ ] `test_analyze_omits_voice_type_when_category_not_voice`
- [ ] `test_analyze_omits_genre_when_category_not_music`
- [ ] `test_analyze_rejects_genre_when_category_is_sfx_and_retries`
- [ ] `test_analyze_persists_new_sound_meta_columns` — tempo/intensity/genre/voice_type 컬럼

### B.10 `tests/test_analysis_queue.py` (8 케이스, FakeAnalyzer)

- [ ] `test_enqueue_asset_processes_via_correct_analyzer`
- [ ] `test_enqueue_pack_drains_all_pending_in_pack`
- [ ] `test_drain_pending_picks_up_existing_pending_rows_on_boot`
- [ ] `test_concurrency_one_processes_serially`
- [ ] `test_failed_analyzer_marks_state_failed_without_killing_worker`
- [ ] `test_signal_emitted_for_each_finished_asset`
- [ ] `test_stop_waits_for_in_flight_analyzer_to_finish`
- [ ] `test_pack_completion_triggers_aggregate_update`

### B.11 `tests/test_analysis_progress.py` (9 케이스, 주입 clock)

- [ ] `test_progress_eta_is_none_when_fewer_than_3_samples`
- [ ] `test_progress_eta_uses_recent_window_average`
- [ ] `test_progress_eta_window_caps_at_10_samples`
- [ ] `test_progress_includes_in_flight_path_during_analysis`
- [ ] `test_progress_in_flight_path_cleared_after_completion`
- [ ] `test_progress_pending_count_combines_queue_and_db`
- [ ] `test_progress_signal_emitted_at_start_and_end_of_each_asset`
- [ ] `test_failed_analysis_still_contributes_to_duration_window`
- [ ] `test_format_duration_kor_handles_none_seconds_minutes_hours`

### B.12 `tests/test_progress_statusbar.py` (4 케이스, offscreen)

- [ ] `test_statusbar_initially_shows_idle_label`
- [ ] `test_statusbar_updates_on_progress_signal`
- [ ] `test_statusbar_shows_completed_then_idle_after_queue_drains`
- [ ] `test_tray_tooltip_reflects_current_progress`

### B.13 `tests/test_config_m2.py` (5 케이스)

- [ ] `test_new_fields_have_documented_defaults`
- [ ] `test_from_mapping_ignores_unknown_keys_still`
- [ ] `test_toml_roundtrip_preserves_new_fields`
- [ ] `test_description_language_validates_known_values` — `"ko"`/`"en"` 만, 외에는 기본값 폴백 + 경고 로그
- [ ] `test_clip_enable_can_be_disabled`

### B.14 `tests/test_ui_smoke_m2.py` (3 케이스, offscreen)

- [ ] `test_main_window_constructs_with_translated_strings`
- [ ] `test_library_view_renders_label_and_description_columns`
- [ ] `test_pack_view_renders_aggregate_column`

빠진 회귀 방지 — `tests/test_config.py`/`test_imports.py` 가 M2 모듈 추가 후 그대로 통과해야 한다. `test_imports.py` 는 새 모듈 목록(`gah.core.labels`, `gah.core.ollama_client`, `gah.core.embedding`, `gah.core.clip_labeler`, `gah.core.searchable`, `gah.core.analysis_queue`, `gah.core.analyzer.base`, `gah.core.analyzer.sprite`, `gah.core.analyzer.sound`, `gah.ui.labels_admin`) 추가 후 그대로 PASS.

**테스트 작성 후 한 번 돌려 확인** — `pytest -q` 결과가 M0/M1 **67 PASS** + M2 신규 **134 FAILED** 가 되어야 한다(B.6 의 `clip_integration` 마크 2개는 기본 실행에서 제외라 활성 FAILED 는 132). 새 테스트가 PASS 라고 표시되면 그건 테스트가 잘못 통과한다는 신호 — fixture 누락이나 import 우회 점검.

## C. 구현 (green phase)

의존 순서대로 모듈을 작성하고, 해당 모듈 단위 테스트만 좁혀 돌려 통과 확인 (`pytest tests/test_<x>.py -v`). 한 묶음이 끝나면 인접 묶음 회귀가 없는지 `pytest -q` 한 번.

### C.1 데이터 계층 (Config + Store + Labels)

- [ ] `src/gah/config.py` — M2 필드 9개 추가
  - `analysis_timeout_seconds: float = 30.0`
  - `analysis_concurrency: int = 1`
  - `analysis_max_retries: int = 3`
  - `description_language: str = "ko"`
  - `clip_model: str = "ViT-B-32"`
  - `clip_pretrained: str = "openai"`
  - `clip_enable: bool = True`
  - `audio_max_seconds: int = 30`
  - `audio_chunk_strategy: str = "smart"`
- [ ] `src/gah/core/store.py` 수정 — `_M2_SCHEMA` 상수 + `initialize()` 가 M1·M2 둘 다 실행
  - 신규 테이블: sprite_meta / sound_meta / assets_fts(FTS5) / asset_embeddings / asset_labels / clip_label_cache / labels
  - 신규 데이터클래스: `SpriteMeta`, `SoundMeta` (tempo/intensity/genre/voice_type 포함), `LabelScore`, `LabelRow`
  - 신규 메서드: `mark_asset_analyzing` / `save_sprite_meta` / `save_sound_meta` / `save_asset_labels` / `save_embedding` / `update_fts` / `next_pending_asset` / `mark_asset_state` / `update_pack_aggregate` / `pending_assets_for_pack` / `clip_label_cache_get` / `clip_label_cache_put`
  - labels 관련: `list_labels` / `add_label` / `set_label_description` / `set_label_enabled` / `seed_labels` / `label_catalog_signature`
  - `AssetRow` 에 `analysis_error: str | None` 필드 추가
- [ ] `src/gah/core/labels.py` — `SEED_LABELS` (24축 ≈ 316개 `(label, description)` 튜플) + `LabelRegistry` 클래스
  - 토큰 정규식 `^[a-z][a-z0-9_]{0,31}$` 검증
  - in-memory 캐시 + 변경 메서드 자동 invalidate
  - `bootstrap()` / `list_labels(axis, enabled_only, with_description)` / `list_axes()` / `add_label` / `set_enabled` / `set_description` / `invalidate`

### C.2 HTTP 백엔드 (Ollama + 임베딩)

- [ ] `src/gah/core/ollama_client.py` — `OllamaClient` + `ChatMessage` dataclass
  - `chat(messages, force_json=True, num_ctx=8000) -> dict` — OpenAI 호환 1차 → Ollama 네이티브 폴백
  - `embed(text, model=None) -> list[float]` — 동일 폴백
  - base64 헬퍼: `encode_image(path) -> str`, `encode_audio_clip(samples, sample_rate) -> str`
  - 에러: `OllamaError(stage, path, cause)`
- [ ] `src/gah/core/embedding.py` — `EmbeddingEncoder`
  - `encode_text(text) -> (bytes, dim)` — float32 LE 직렬화
  - `decode_vector(blob, dim) -> np.ndarray`
  - dim 은 첫 호출 응답 길이로 확정

### C.3 CLIP 백엔드 + 검색 텍스트 빌더

- [ ] `src/gah/core/clip_labeler.py` — `ClipBackend(Protocol)` + `OpenClipBackend` + `ClipLabeler`
  - `OpenClipBackend.device = "cuda" if torch.cuda.is_available() else "cpu"` — 로그 명시
  - 모델 가중치 cache_dir = `paths.cache_dir / "clip"` (lazy 다운로드)
  - `warmup(labels=None)` — None 이면 registry 의 시각 14축 자동 수집
  - `score_image(path, labels=None) -> dict[label, 0..1]`
  - `FakeBackend` 도 같이 export (테스트용)
- [ ] `src/gah/core/searchable.py` — `build_searchable(meta, labels, label_descriptions, description, rel_path) -> SearchableTexts`
  - `for_fts` — 라벨/축 prefix 토큰 + 라벨 description (인용부호) + 경로 + 기술 메타
  - `for_embed` — 상위 N=5 라벨 + 그 description + 에셋 description, ≤ 256 토큰

### C.4 분석기

- [ ] `src/gah/core/analyzer/base.py` — `AnalyzerResult`, `SearchableTexts`, `AnalyzerInput`, `AnalyzerError`, `ResponseModel` (Pydantic 베이스)
- [ ] `src/gah/core/analyzer/sprite.py` — `SpriteAnalyzer`
  - Pillow + numpy 기술 특성(픽셀아트 휴리스틱, 도미넌트 5색 k-means)
  - 768px 리샘플 + base64 → Gemma 호출 → Pydantic 검증 → CLIP 점수 통합
  - 시스템 프롬프트 enum 슬롯을 `registry.list_labels(axis)` 로 동적 주입
  - 화이트리스트 위반 3회 → `state='partial'` + `style='other'`
- [ ] `src/gah/core/analyzer/sound.py` — `SoundAnalyzer`
  - librosa + soundfile 기술 특성 (duration/SR/channels/loudness/BPM)
  - 30s 클립 전략 (`smart` / `first` / `rms_peak`)
  - 1차 네이티브 → 2차 멜 스펙트로그램 비전 → 3차 휴리스틱 폴백, `audio_path_used` 마킹
  - 시스템 프롬프트가 10축 enum + 조건부 null 규칙(voice_type/genre)
  - 응답 → `LabelScore` 10축 INSERT + `sound_meta` 4개 새 컬럼 저장

### C.5 분석 큐 + 진행 표시

- [ ] `src/gah/core/pack_aggregate.py` (또는 `pack_manager.py` 확장) — `compute_aggregate(store, pack_id) -> dict`
  - main_style / category_dist / palette / avg_dim / avg_duration_ms
- [ ] `src/gah/core/analysis_queue.py` — `AnalysisQueue(QObject)`, `AnalysisProgress` dataclass
  - `ThreadPoolExecutor(max_workers=concurrency)` + `queue.Queue[int]`
  - `_recent_durations: deque[float]` (maxlen=eta_window=10)
  - `analysisFinished(int)` + `progressChanged(object)` 시그널
  - `enqueue_asset` / `enqueue_pack` / `drain_pending` / `progress` / `start` / `stop`
  - 팩 pending 0 도달 시 `compute_aggregate` 호출

### C.6 UI (라벨 관리 + 상태바 + 컬럼)

- [ ] `src/gah/ui/labels_admin.py` — `LabelsAdminDialog(QDialog)`
  - 축 콤보 + 라벨 테이블(라벨/상태/출처/description 컬럼) + 추가/토글/edit 액션
  - 토큰 정규식 인라인 검증 + 빈 description 경고 아이콘
  - 모든 변경은 `LabelRegistry` 직접 호출, 테이블 즉시 refresh
- [ ] `src/gah/ui/main_window.py` 수정
  - 메뉴/탭/컬럼 헤더 모두 `tr()` 래핑
  - `QStatusBar` 영구 위젯 — `QProgressBar` + ETA 라벨
  - `_format_duration_kor(seconds) -> str` 헬퍼
  - 슬롯 `update_progress(snapshot)` / `on_asset_analyzed(asset_id)` — 워커 시그널을 QueuedConnection 으로 받음
  - `set_label_registry(registry)` — 라벨 관리 다이얼로그가 참조
  - `Ctrl+L` 단축키로 라벨 관리 다이얼로그
- [ ] `src/gah/ui/library_view.py` 수정 — `라벨`/`설명` 컬럼 추가, `tr()` 래핑, 배치 조회로 N+1 회피
- [ ] `src/gah/ui/pack_view.py` 수정 — `집계` 컬럼 추가 (`packs.aggregate_meta` JSON 한 줄 요약), `tr()` 래핑
- [ ] `src/gah/tray.py` 수정 — `"라벨 관리…"` 액션 추가 + `setToolTip()` 으로 진행 상태 짧은 형식

### C.7 통합 + MCP 인계 stub

- [ ] `src/gah/app.py` 수정 — 부팅 흐름
  ```
  store.initialize()
  registry = LabelRegistry(store); registry.bootstrap()
  reconcile_library(store, library_root)
  ollama = OllamaClient(...); embedder = EmbeddingEncoder(ollama, ...)
  clip = ClipLabeler(OpenClipBackend(...), store, registry) if config.clip_enable else None
  sprite = SpriteAnalyzer(ollama, clip, embedder, registry)
  sound  = SoundAnalyzer(ollama, embedder, registry, spectrogram_cache_dir=...)
  queue  = AnalysisQueue(store, sprite, sound, concurrency=config.analysis_concurrency)
  queue.start(); queue.drain_pending()
  watcher = LibraryWatcher(on_pack_changed=lambda name: _on_pack_changed(...))
  queue.analysisFinished.connect(main_window.on_asset_analyzed)
  queue.progressChanged.connect(main_window.update_progress)
  queue.progressChanged.connect(lambda s: tray.setToolTip(...))
  main_window.set_label_registry(registry)
  ```
  종료 시 `queue.stop()` → `watcher.stop()` → `store.close()`.
- [ ] `docs/MCP_USAGE_GUIDE.md` — M3 인계용 stub (1페이지)
  - 라벨 어휘는 자기 기술 (`list_labels` 응답에 description)
  - `label_catalog_signature` 캐시 정책
  - 자연어 쿼리 + `labels_any` / `labels_all` / `labels_none` 권고
  - `matched_labels` / `score_breakdown` 응답 활용
  - DESIGN.md §13 워크플로 참조 링크

각 묶음 마지막에 `pytest -q` 로 회귀 점검. 전체 묶음이 다 끝나면 합계 ≈ **201 passed** (활성 199 + `clip_integration` 마크 2 옵트인).

## D. 검증

- [ ] `pytest -q` 전체 통과 (M0/M1 회귀 없음 + M2 신규 모두 PASS) — 약 201 passed
- [ ] PowerShell 트레이 실행 → 상태바에 `"분석 대기 중"` 보임 *(사용자 수동)*
- [ ] `library\kenney_test\` 만들고 PNG + WAV 드롭 → 5~30초 후 `분석 상태` 가 `pending → analyzing → ok` *(사용자 수동)*
- [ ] 라이브러리 탭 `라벨` / `설명` 컬럼 채워짐 *(사용자 수동)*
- [ ] 트레이 메뉴 `"라벨 관리…"` → 24축 다이얼로그, 사용자 라벨 추가/비활/description 편집 *(사용자 수동)*
- [ ] 분석 진행 상태바에 `"분석 중 n/m — 약 X 남음"` + 트레이 툴팁 동기화 *(사용자 수동)*
- [ ] `sqlite3 ...\metadata.db "SELECT axis, label, description FROM labels WHERE axis='style' LIMIT 5"` → 시드 description 표시 *(사용자 수동)*
- [ ] `sqlite3 ...\metadata.db "SELECT asset_id FROM assets_fts WHERE searchable_text MATCH 'label:pixel_art'"` → 라벨 매칭 동작 *(사용자 수동)*
- [ ] CUDA 가용 PC: 로그에 `"CLIP backend initialized on device=cuda"` / CPU PC: `device=cpu` *(사용자 수동)*

수동 검증 절차 전체는 [`M2_verification.md`](./M2_verification.md) §3 에 PowerShell 한 줄씩 풀어 작성한다.

## E. M3 인계

- [ ] `milestones/M2_verification.md` 작성 — `pytest -v` 출력, 환경 한계, 사용자 수동 검증 결과
- [ ] `HANDOFF.md` 갱신 — §1 한 줄 요약 / §2 검증 사실 / §5 M3 시작 절차 (M3 plan 작성·MCP 도구·통일성 스코어러 안내)
- [ ] `CLAUDE.md` §2 진행 현황 표의 M2 상태 ✅ + §8 을 M3 안내로 교체
- [ ] `milestones/README.md` 의 마일스톤 표 갱신
- [ ] `docs/MCP_USAGE_GUIDE.md` 가 존재하는지 확인 (M3 가 본격 풀어쓸 stub)
