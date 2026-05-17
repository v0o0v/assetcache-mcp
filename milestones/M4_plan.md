# M4 — 검색 UX 풍부화 (구현 계획)

> **에이전트 작업자에게**: 이 plan 은 [`M3_plan.md`](./M3_plan.md) 와 같은 한국어 마일스톤 표준 형식이다. 본 plan 을 그대로 따라 [`milestones/M4_todo.md`](./M4_todo.md) 의 체크리스트를 만들고, **테스트를 먼저 작성한 뒤** 구현으로 넘어간다. 본 plan 은 [`HANDOFF.md §5`](../HANDOFF.md) 의 "M4 plan 작성 시 결정해야 할 항목" 4개 + 메모리 `project_search_ux_milestone.md` 의 책임 범위 + DESIGN.md §11 의 M4 정의를 합쳐 풀어 쓴 것이며, 결정된 5개 핵심 항목(라벨 부울 문법·가중치 슬라이더 노출·저장된 검색 테이블·다양성 알고리즘·페널티 학습)을 모듈·SQL·테스트 단위까지 1:1 로 옮긴다.

## 1. 목표

M3 가 깔아둔 `HybridSearcher` + 12 MCP 도구 + GUI 검색 박스 위에 **풍부한 검색·필터·정렬 UX + 자연어 라벨 파서 + 결과 다양성 + 페널티 학습**을 얹는다. M4 가 끝나면 다음 세 시나리오가 정상 동작한다.

1. **자연어 라벨 부울 쿼리 — GUI**

   라이브러리 탭 검색 박스에 `"orchestral AND dark NOT loop"` 입력 → 250ms 디바운스 후 파서가 `labels_all=[orchestral, dark]`, `labels_none=[loop]` 으로 분해 → `HybridSearcher.hybrid()` 호출. 결과 그리드에 매칭된 라벨이 칩으로 시각화되고, 5채널 점수 + 다양성 보정이 적용된 정렬 결과가 노출.

2. **MCP — `find_asset` 풍부 호출 + 저장된 검색**

   ```jsonc
   find_asset({
     query: "전투 BGM",
     label_query: "sound_mood:dark AND sound_use:combat NOT sound_genre:chiptune",
     project_id: "D:/Unity/MyGame",
     diversity: "mmr",
     diversity_lambda: 0.7,
     count: 10
   })
   ```

   → 같은 팩이 10개를 독점하지 않고 MMR 가 적용된 cross-pack 결과. 다음 호출:

   ```jsonc
   save_search({
     project_id: "D:/Unity/MyGame",
     name: "전투 BGM 다크",
     query: "전투 BGM",
     label_query: "sound_mood:dark AND sound_use:combat NOT sound_genre:chiptune",
     diversity: "mmr"
   })
   ```

   → 저장된 검색이 `saved_searches` 테이블에 박힘. 다음 세션에서 `list_saved_searches` → `run_saved_search(name="전투 BGM 다크")` 로 즉시 재호출.

3. **페널티 학습 — `report_feedback` 누적이 다음 검색에 반영**

   ```jsonc
   report_feedback({ query_id: 42, asset_id: 999, reason: "negative" })
   ```

   → `feedback_records` 에 `weight=-0.5` 기록. 다음 `find_asset` 응답의 `score_breakdown.feedback` 가 `-0.05` (가중치 0.10 적용 후) 로 반영되어 해당 자산이 후속 순위에서 밀림. 같은 팩에서 3 자산이상 negative 누적 시 pack-wide penalty 추가.

세부:

- **`label_query` 파서** — `AND`/`OR`/`NOT` 대문자 키워드 + `()` 그룹 + `axis:label` 명시 + bare label 자동 매칭. AST → DNF 정규화 → `labels_all`/`labels_any`/`labels_none` 매핑. 등록되지 않은 토큰은 free-text 로 분리. 모호한 bare label(여러 axis 후보) 은 `AmbiguousLabel` 에러 + 후보 제안.
- **HybridSearcher 확장** — 6번째 채널 `feedback` 추가 + 다양성 보정 단계 (`none`/`mmr`/`round_robin`). 가중치 재배분: `semantic 0.35 + keyword 0.10 + label_match 0.20 + consistency 0.20 + recency 0.05 + feedback 0.10 = 1.00`. M3 가중치는 Config 마이그레이션으로 자동 갱신.
- **`saved_searches` 테이블 + 4 MCP 도구** — `save_search`/`list_saved_searches`/`delete_saved_search`/`run_saved_search`. project_id 별 unique name, query_json 에 SearchRequest 직렬화.
- **`feedback_records` 테이블 + signed weight** — `negative=-0.5`/`positive=+0.3`/`irrelevant=-0.3`. project_id 별 asset-level + pack-level (≥3 negative → pack-wide -0.1).
- **`suggest_packs.samples` 풍부화** — `thumbnail_path` (sprite: lazy-generated 256×256 PNG, sound: None) + `preview_blurb` (Gemma description 의 한 줄 발췌 또는 top-2 라벨).
- **GUI 라이브러리 탭 풍부 UX**:
  - 좌측 사이드 패널 — axis 별 라벨 칩 다중 선택 (AND/OR/NOT 모드 토글)
  - 다축 필터 — 팩 다중 선택 콤보, kind/analysis_state/license/vendor 드롭다운, 해상도·길이 슬라이더
  - 상단 검색 박스 — 자연어 (free-text) + 파서가 라벨 부울 자동 추출
  - 우측 사이드 패널 — 가중치 슬라이더 5채널 (0..100) + 3 프리셋 + 저장된 검색 목록
  - 결과 그리드 — `matched_labels` 칩 + 점수 시각화 (5채널 stack bar 또는 단순 숫자)
  - 정렬 드롭다운 — score / 추가일 / 파일 크기 / 이름 (asc/desc)
- **DB 마이그레이션** — `saved_searches` + `feedback_records` 2 테이블 신설. M0/M1/M2/M3 의 21 객체 + 신규 2 테이블 + 인덱스 3 = 26 객체.

M4 가 끝나면 사용자는 GUI 에서 자연어 + 칩 + 슬라이더로 조합 검색을 하고, MCP 사용자는 `label_query` + `diversity` + 저장된 검색까지 활용한다. 페널티 학습이 켜져서 한 번 거부한 자산은 다음 검색에서 즉시 밀린다.

## 2. 산출물

### 2.1 코드 모듈

| 파일/디렉터리 | 책임 | 상태 |
|---|---|---|
| `src/gah/config.py` (수정) | M4 신규 필드 5 개 — `weight_feedback=0.10`, `diversity_default="none"`, `diversity_mmr_lambda=0.7`, `feedback_negative_weight=-0.5`, `feedback_positive_weight=0.3`, `feedback_irrelevant_weight=-0.3`, `feedback_pack_threshold=3`, `feedback_pack_penalty=-0.1`, `feedback_window_seconds=2_592_000` (30 일). 또 기본 가중치 재배분 — `weight_semantic 0.40→0.35`, `weight_keyword 0.15→0.10` (label_match/consistency/recency 동일, feedback 0.10 신규로 합 1.0 유지). `from_mapping` 의 가중치 합 검증 확장 (6채널). | 수정 |
| `src/gah/core/store.py` (수정) | `_M4_SCHEMA` 상수 추가 + `initialize()` 가 M1·M2·M3·M4 순차 실행. 신규 메서드: `save_search`/`list_saved_searches`/`delete_saved_search`/`update_saved_search_last_used`/`get_saved_search`/`insert_feedback_record`/`feedback_records_for_project`/`pack_feedback_count`. | 수정 |
| `src/gah/core/label_query.py` | `parse_label_query(text, registry) -> ParsedLabelQuery` — `AND`/`OR`/`NOT` + `()` + `axis:label` + bare label 매칭. AST 정규화 후 `labels_all`/`labels_any`/`labels_none` + `free_text` 4튜플 반환. 모호 → `AmbiguousLabel` 예외 with 후보 제안. 미지 토큰은 free_text. `ParsedLabelQuery(labels_all, labels_any, labels_none, free_text, original_expr)`. | 신규 |
| `src/gah/core/search.py` (수정) | `SearchRequest` 에 4 필드 추가 — `label_query: str|None`, `diversity: str = "none"` (`none|mmr|round_robin`), `diversity_lambda: float|None`, `weight_feedback_override: float|None`. `HybridSearcher.hybrid()` 6 단계 → 7 단계 (라벨 파서 적용 + 6채널 가중합 + 다양성 보정). 헬퍼: `_feedback_bonus(store, project_id, asset_id) -> float`, `_apply_diversity(ranked, method, lambda_) -> ranked`. `ResultRow.score_breakdown` 에 `feedback` 키 추가. | 수정 |
| `src/gah/core/thumbnails.py` | `ensure_thumbnail(asset_path, cache_dir, asset_id, max_size=256) -> Path | None` — sprite 자산만 PNG 256×256 생성 (Pillow `thumbnail`). 캐시 hit 시 즉시 반환. 사운드/시트는 None. 캐시 위치 `cache/thumbnails/<asset_id>.png`. | 신규 |
| `src/gah/core/suggest_packs.py` | M3 `mcp/tools.py::tool_suggest_packs` 의 핵심 알고리즘을 분리 + samples 풍부화. `enrich_sample(asset, cache_dir, store) -> dict` — `thumbnail_path` (sprite) + `preview_blurb` (Gemma description 한 줄 발췌 또는 top-2 라벨). | 신규 (`mcp/tools.py` 는 이 모듈로 위임) |
| `src/gah/mcp/models.py` (수정) | `FindAssetRequest` 에 4 필드 추가 (`label_query`, `diversity`, `diversity_lambda`, `weight_feedback_override`). `ReportFeedbackRequest.reason` 을 enum (`negative`/`positive`/`irrelevant`) 으로 제한. 신규 모델 4 개 — `SaveSearchRequest`/`SaveSearchResult`/`ListSavedSearchesResult`/`DeleteSavedSearchRequest`/`RunSavedSearchRequest`. `SuggestPacksResult.packs[].samples[]` 에 `thumbnail_path`/`preview_blurb` 추가. | 수정 |
| `src/gah/mcp/tools.py` (수정) | 4 도구 신규 — `tool_save_search`/`tool_list_saved_searches`/`tool_delete_saved_search`/`tool_run_saved_search`. `tool_find_asset` 가 `label_query` 파서 호출 후 SearchRequest 의 `labels_*` 와 병합 (구조화 입력 우선, 파서가 덧붙임). `tool_report_feedback` 가 `Config.feedback_*_weight` 로 signed weight 결정 후 `store.insert_feedback_record`. `tool_suggest_packs` 는 `suggest_packs.enrich_sample` 로 위임. | 수정 |
| `src/gah/mcp/server.py` (수정) | `register_all_tools` 가 신규 4 도구 등록 — 총 16 도구. `INSTRUCTIONS` 갱신 (저장된 검색 / 페널티 학습 / 다양성 옵션 한 문단 추가). | 수정 |
| `src/gah/ui/library_view.py` (수정) | M3 의 단순 표 → 풍부 UX. 좌측 라벨 칩 패널 (`LabelChipPanel`), 우측 가중치+저장 패널 (`SearchSidePanel`), 상단 검색 박스 + 정렬 드롭다운, 결과 행에 matched_labels 칩 표시 (간단한 텍스트 또는 작은 라벨 위젯), 다축 필터 (pack/kind/state/license/vendor 콤보), `apply_filter()` 가 SearchRequest 로 통합. | 대대적 수정 |
| `src/gah/ui/label_chip_panel.py` | `LabelChipPanel(registry, parent)` — axis 별 그룹 박스 + 라벨 체크박스. AND/OR/NOT 라디오 (라벨 단위는 같은 모드 가정 — 모드는 패널 전체 단위). `selected() -> dict[axis, list[label]]` + signal `selectionChanged`. | 신규 |
| `src/gah/ui/search_side_panel.py` | `SearchSidePanel(config, store, parent)` — 5 슬라이더 + 3 프리셋 버튼 + 저장된 검색 리스트 + "현재 검색 저장" 버튼. Config 양방향 바인딩 (`weight_*` 변경 시 슬라이더 갱신, 슬라이더 변경 시 Config 즉시 갱신 + `save_config` 호출). `currentSavedSearchActivated(name)` 시그널. | 신규 |
| `src/gah/ui/filter_bar.py` | `FilterBar(store, parent)` — 다축 필터 (pack 콤보 다중, kind/state/license/vendor 드롭다운, 정렬 드롭다운). `filterChanged` 시그널 + `current_filters() -> dict`. | 신규 |
| `docs/MCP_USAGE_GUIDE.md` (수정) | §1.1 신규 4 도구 (saved_searches) 의 실응답 JSON 추가. §3.2 `label_query` 문법과 파싱 시나리오. §4 `diversity` 옵션 / λ 튜닝 노트. §5 `report_feedback` reason enum + 페널티 학습 동작 설명. | 수정 |
| `DESIGN.md` (수정) | §5.1 SQL 스키마에 `saved_searches`/`feedback_records` 추가. §6.5 `suggest_packs.samples` 가 `thumbnail_path`/`preview_blurb` 채워진 응답으로 갱신 (이미 정의된 형태와 맞춤). §6.10 `report_feedback` 의 reason enum + 페널티 학습 방식 명시. §11 M4 항목에 본 마일스톤이 실제로 한 일 (defer 한 항목 명시) 정리. | 수정 |
| `milestones/M4_todo.md` | TDD 체크리스트 (이 plan §3 의 작업 단위를 1:1 매핑) | 신규 |
| `milestones/M4_verification.md` | M4 끝에 작성 — 자동 `pytest -v` 결과 + 사용자 수동 검증 항목 + 알려진 한계 | 신규 |

### 2.2 테스트

| 파일 | 케이스 수 | 핵심 검증 |
|---|---:|---|
| `tests/test_label_query.py` | ~16 | 빈 입력 → empty / 단일 bare label → labels_all 1개 / `axis:label` 명시 정확 매칭 / `AND` 두 atom → labels_all / `OR` 두 atom → labels_any / `NOT atom` → labels_none / `(a AND b) OR c` → DNF 정규화 / 우선순위 `NOT > AND > OR` / 미지 토큰 → free_text 로 분리 / 모호 bare label → `AmbiguousLabel` + 후보 제안 / 대소문자 보존 (label) vs 키워드 대문자만 / 한글 라벨 매칭 / 따옴표 안 토큰 1개 / 중첩 괄호 / 등록된 라벨 vs 미등록 분리 / 연산자 누락 시 묵시적 AND |
| `tests/test_store_m4.py` | ~12 | `_M4_SCHEMA` 두 테이블 idempotent / `save_search` 정상 + `UNIQUE(project_id, name)` 충돌 시 OperationalError / `list_saved_searches` 프로젝트별 + global / `delete_saved_search` 정상 + 미존재 시 noop / `update_saved_search_last_used` 갱신 / `get_saved_search` by name → row / `insert_feedback_record` 정상 + signed weight 저장 / `feedback_records_for_project` 윈도우 내 행만 / `pack_feedback_count` 집계 정확 / cascade — project 삭제 시 saved/feedback cascade / JSON roundtrip / migration idempotent with M1/M2/M3 |
| `tests/test_search_diversity.py` | ~9 | `diversity="none"` → M3 동작 그대로 / `mmr` λ=1.0 → score 만 (다양성 0) / `mmr` λ=0.0 → 같은 팩 절대 안 뽑힘 / `mmr` λ=0.7 → 상위 K 가 팩 다양화 / `round_robin` 5 결과 2 팩 → 교대 / `round_robin` 1 팩만 후보 → 그대로 / 후보 ≤ count → diversity 무관하게 모두 반환 / mmr 결과의 `score_breakdown` 변형 없음 (다양성은 순위만 영향) / `diversity_lambda=None` 시 Config default 적용 |
| `tests/test_feedback_penalty.py` | ~10 | `negative` 기록 후 다음 검색의 `score_breakdown.feedback` 음수 / `positive` 기록 후 양수 / 같은 자산에 양·음 동시 → 합산 / 윈도우 밖 (>30일) 기록 무시 / 다른 project 의 기록은 영향 없음 / pack 단위 ≥3 negative → 같은 팩 다른 자산도 penalty / pack penalty 임계 미달 시 미적용 / `Config.weight_feedback=0` 시 효과 없음 / `report_feedback` 가 알 수 없는 reason → ValidationError / `feedback_records` 누적 검증 |
| `tests/test_suggest_packs_samples_rich.py` | ~6 | sprite 자산 sample → `thumbnail_path` 존재 + 캐시 hit / 사운드 자산 sample → `thumbnail_path=None` + `preview_blurb` 채워짐 / Gemma description 가 길면 첫 한 줄만 / description 없으면 top-2 라벨 폴백 / `include_thumbnails=false` → `thumbnail_path` 안 채움 / 캐시 디렉터리 자동 생성 |
| `tests/test_library_search_ui_rich.py` | ~14 | offscreen Qt. `LabelChipPanel` 24 axis 그룹 모두 노출 / 칩 선택 시 `selectionChanged` 발화 / AND/OR/NOT 라디오 전환 / `SearchSidePanel` 5 슬라이더 초기값 = Config / 슬라이더 변경 → Config 즉시 갱신 / 프리셋 버튼 클릭 → 슬라이더 + Config 동시 갱신 / 저장된 검색 리스트 초기 로드 / "저장" 버튼 → store insert / 저장 리스트 클릭 → searcher 호출 / `FilterBar` pack 다중 선택 / kind 드롭다운 / 정렬 변경 → 검색 재호출 / 결과 행 matched_labels 칩 노출 / 디바운스 250ms 유지 |
| `tests/test_mcp_tools_m4.py` | ~14 | `find_asset` 에 `label_query` 전달 → 파서 호출 결과가 SearchRequest 에 주입 / 구조화 `labels_all` + `label_query` 동시 → 병합 (둘 다 적용) / 파서 모호 토큰 → `400_invalid_input` + 후보 제안 / `diversity="mmr"` 전달 → SearchRequest 에 그대로 / `report_feedback(reason="negative")` → `feedback_records` insert / unknown reason → ValidationError / `save_search` 정상 → 저장 + ID 반환 / `save_search` 중복 name → `400_invalid_input` / `list_saved_searches` 정렬 (last_used desc) / `delete_saved_search` 정상 / `run_saved_search` 가 저장된 query_json → `tool_find_asset` 위임 / `run_saved_search` 미존재 name → `404_not_found` / `suggest_packs` samples 풍부화 (`thumbnail_path`+`preview_blurb`) / 16 도구 모두 등록 회귀 |
| `tests/test_search_m4.py` | ~8 | 6채널 가중합 합 = score (±1e-4) / `weight_feedback_override` 적용 / feedback 채널 후보 없을 때 0 / `label_query` 가 free_text 분리 후 semantic 쿼리에 그대로 전달 / `apply_diversity` 가 mmr 시 same-pack 점수 감산 / round_robin 라운드 정확 / 6번째 채널 추가가 M3 회귀 0 / `weight_feedback=0` 시 분해에 키 존재하되 값 0 |
| `tests/test_config_m4.py` | ~6 | `weight_feedback` 기본 0.10 / 6채널 가중치 합 = 1.0 ±1e-6 / `diversity_default="none"` 기본 / `diversity_mmr_lambda=0.7` 기본 / `feedback_*_weight` 부호 검증 (negative<0, positive>0) / TOML 왕복 |
| `tests/test_thumbnails.py` | ~5 | 첫 호출 → 캐시 파일 생성 + 256×256 / 캐시 hit → 재생성 안 함 (mtime 동일) / 사운드/시트 → None / 캐시 디렉터리 자동 생성 / 잘못된 path → None + 로그 |
| `tests/test_mcp_integration.py` (수정 — 옵트인 `mcp_integration` 마크) | 0 신규 (기존 2 갱신) | `tools/list` 응답 12 → 16 도구 (saved_search 4 신규 포함) |

**합계 ~100 신규 active 케이스** + 옵트인 0 신규 (M3 의 2 옵트인 케이스 갱신만). 기존 M0(18) + M1(49) + M2(134) + M2.1(16) + M3(112) = 329 active (M3 가중치 변경 회귀 1 발생 가능 — `test_config_m3::test_weight_sum_equals_one_within_tolerance` 가 5채널 가정으로 작성됨. M4 가 갱신: 6채널로 확장). 합 ≈ **329 + 100 = 429 active** + 4 deselected.

## 3. 작업 단위와 책임

작업은 순서대로 진행한다 (앞 단위가 뒤 단위의 빌딩 블록). 각 단위는 **테스트 먼저 → 구현 → 통과 → 커밋** 사이클을 지킨다.

### 3.1 Config 마이그레이션 + Store M4 스키마 (0.5일)

`src/gah/config.py` — M4 신규 필드 + 가중치 재배분:

```python
# weight 기본값 재배분 (5채널 → 6채널)
weight_semantic: float = 0.35       # M3 0.40 → 0.35
weight_keyword: float = 0.10        # M3 0.15 → 0.10
weight_label_match: float = 0.20    # 동일
weight_consistency: float = 0.20    # 동일
weight_recency: float = 0.05        # 동일
weight_feedback: float = 0.10       # 신규 — 합 1.00

# 다양성
diversity_default: str = "none"     # "none" | "mmr" | "round_robin"
diversity_mmr_lambda: float = 0.7   # 0..1, score ↔ 다양성 trade-off

# 페널티 학습
feedback_negative_weight: float = -0.5
feedback_positive_weight: float = 0.3
feedback_irrelevant_weight: float = -0.3
feedback_pack_threshold: int = 3
feedback_pack_penalty: float = -0.1
feedback_window_seconds: int = 2_592_000  # 30 일
```

`from_mapping` 의 가중치 합 검증 확장 — 6채널 합 1.0 ±1e-6 아니면 경고 + 기본값 폴백.

`src/gah/core/store.py` — `_M4_SCHEMA` 추가:

```sql
-- _M4_SCHEMA
CREATE TABLE IF NOT EXISTS saved_searches (
  id              INTEGER PRIMARY KEY,
  project_id      INTEGER REFERENCES projects(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  query_json      TEXT NOT NULL,          -- SearchRequest 직렬화 (project_id 제외)
  created_at      INTEGER NOT NULL,
  last_used_at    INTEGER,
  UNIQUE(project_id, name)                 -- project_id NULL 도 같은 name 1개만
);
CREATE INDEX IF NOT EXISTS idx_saved_searches_project ON saved_searches(project_id, last_used_at);

CREATE TABLE IF NOT EXISTS feedback_records (
  id              INTEGER PRIMARY KEY,
  project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  asset_id        INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  query_id        INTEGER REFERENCES search_queries(id) ON DELETE SET NULL,
  reason          TEXT NOT NULL,           -- 'negative' | 'positive' | 'irrelevant'
  weight          REAL NOT NULL,           -- signed; Config.feedback_*_weight 적용 결과
  created_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_project_asset
  ON feedback_records(project_id, asset_id, created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_project_pack
  ON feedback_records(project_id, asset_id);
```

Store 신규 메서드 (모두 write 는 `write_lock` 안):

write:
- `save_search(project_id: int|None, name: str, query_json: str) -> int` — 중복 name 시 OperationalError
- `delete_saved_search(project_id: int|None, name: str) -> bool` — 삭제된 행 ≥1 이면 True
- `update_saved_search_last_used(saved_search_id: int) -> None`
- `insert_feedback_record(project_id, asset_id, query_id, reason, weight) -> int`

read:
- `list_saved_searches(project_id: int|None) -> list[SavedSearchRow]` — `last_used_at DESC NULLS LAST, created_at DESC`
- `get_saved_search(project_id: int|None, name: str) -> SavedSearchRow | None`
- `feedback_records_for_project(project_id: int, asset_ids: list[int]|None, within_seconds: int) -> dict[int, float]` — `{asset_id: sum(weight)}` (윈도우 내)
- `pack_feedback_count(project_id: int, pack_ids: list[int], within_seconds: int) -> dict[int, int]` — 음수 가중치 행 카운트

신규 데이터클래스 `SavedSearchRow(id, project_id, name, query_json, created_at, last_used_at)`.

테스트(`tests/test_store_m4.py`): §2.2 의 12 케이스.

### 3.2 `core/label_query.py` 파서 (1.5일)

데이터클래스:

```python
@dataclass(frozen=True)
class ParsedLabelQuery:
    labels_all: list[LabelFilter]
    labels_any: list[LabelFilter]
    labels_none: list[LabelFilter]
    free_text: str                   # 파서가 매칭 못한 토큰 join 결과
    original_expr: str               # 디버깅용 원본
```

문법 (EBNF 근접):

```
expr     = or_expr
or_expr  = and_expr ('OR' and_expr)*
and_expr = not_expr (('AND' | implicit_and) not_expr)*
not_expr = 'NOT'? atom
atom     = '(' or_expr ')'
         | axis_label
         | bare_label
         | free_token
axis_label = IDENT ':' IDENT
bare_label = IDENT     -- LabelRegistry 에서 axis 자동 매칭
free_token = QUOTED_STRING | TOKEN  -- 미지 토큰
```

- `AND`/`OR`/`NOT` 은 **대문자 전체 일치** 만 키워드 (사용자가 `and`/`or` 를 라벨로 쓸 가능성 보호).
- bare label 매칭: `LabelRegistry.list_labels(enabled_only=True)` 에서 `label == token` 인 row 들. 1개면 자동 axis. 2개 이상이면 `AmbiguousLabel(token, candidates=[axis...])` 예외.
- 0개면 `free_token` 으로 분류 — `free_text` 에 join.
- 미지 토큰 처리: AND/OR/NOT 트리에 들어가지 않고 별도 `free_text` 누적.

알고리즘:

1. **토크나이저** — 공백 분리 + 따옴표/괄호/콜론 처리. 결과: `Token(text, kind={'LPAREN','RPAREN','AND','OR','NOT','AXIS','LABEL','FREE'})`.
2. **분류기** — 각 LABEL 토큰을 registry 로 분류 → AXIS_LABEL / FREE.
3. **재귀하강 파서** — `expr/or/and/not/atom` 5 함수. 출력은 AST.
4. **DNF 정규화** — `(a AND b) OR c` → `[(a AND b), c]`. 각 disjunct 가 conjunction 으로 구성되면 정상 매핑:
   - 단일 conjunction (OR 없음) → 모든 atom 을 `labels_all` (NOT 은 `labels_none`).
   - 여러 conjunctions (OR 존재) → 각 conjunction 의 atom 들을 `labels_any` 로 평탄화 (단, 같은 disjunct 안에서 AND 조건 보존 안 됨 — 한계). 한계가 부담스러우면 `UnsupportedExpression` 예외.

   M4 v1 한계: AST 가 다음 두 형태 중 하나면 정확 매핑:
   - **순수 AND** — `a AND b AND NOT c` → `labels_all=[a,b]`, `labels_none=[c]`.
   - **순수 OR** — `a OR b OR NOT c` → `labels_any=[a,b]`, `labels_none=[c]`.
   - **혼합** — `(a AND b) OR c` 는 v1 에서 `UnsupportedExpression(hint="순수 AND 또는 순수 OR 만 지원")` 예외. 자주 쓰는 케이스는 모두 순수형으로 풀리므로 v1 한계 수용.

5. **free_text 모으기** — `free_token` 들을 원래 순서대로 join.

API:

```python
def parse_label_query(text: str, registry: LabelRegistry) -> ParsedLabelQuery:
    """텍스트 → ParsedLabelQuery. 빈 입력 또는 라벨 0개 → 빈 ParsedLabelQuery (free_text=text)."""

class LabelQueryError(ValueError):
    """파서 베이스."""

class AmbiguousLabel(LabelQueryError):
    def __init__(self, label: str, candidates: list[str]) -> None: ...

class UnsupportedExpression(LabelQueryError):
    """AND/OR 혼합 표현 (v1 한계)."""
```

테스트(`tests/test_label_query.py`): §2.2 의 16 케이스.

### 3.3 `core/search.py` 확장 (1일)

`SearchRequest` 4 필드 추가:

```python
@dataclass(frozen=True)
class SearchRequest:
    # ... 기존 ...
    label_query: str | None = None
    diversity: str = "none"               # "none" | "mmr" | "round_robin"
    diversity_lambda: float | None = None # None → Config.diversity_mmr_lambda
    weight_feedback_override: float | None = None
```

`HybridSearcher.hybrid()` 단계 확장 (M3 의 1~7 → M4 의 1~8):

```
1. project upsert + summary  (M3 그대로)
2. label_query 파싱 (있다면) — ParsedLabelQuery 와 SearchRequest 의 labels_* 병합:
      merged.labels_all = req.labels_all + parsed.labels_all
      merged.labels_any = req.labels_any + parsed.labels_any
      merged.labels_none = req.labels_none + parsed.labels_none
      effective_query = (req.query + " " + parsed.free_text).strip()
3. 후보 추출 (FTS + semantic) — M3 그대로, effective_query 사용
4. scope 필터 (force/blocked/kind/labels/filters) — M3 그대로
5. 채널 점수 산출 — M3 5 채널 + 신규 feedback 채널:
      feedback_raw[a] = store.feedback_records_for_project(pid, [a], window).get(a, 0.0)
      pack_neg_count[a] = store.pack_feedback_count(pid, [pack_of(a)], window).get(pack_of(a), 0)
      if pack_neg_count[a] >= config.feedback_pack_threshold:
          feedback_raw[a] += config.feedback_pack_penalty
      feedback[a] = clamp(feedback_raw[a], -1.0, 1.0)
6. 가중합 (6채널) — M3 의 5채널 합산에 feedback 항 추가:
      final[i] = w_sem*sem + w_kw*kw + w_label*label_match + w_cons*cons
               + w_rec*rec + w_fb*feedback
      (w_fb 는 req.weight_feedback_override 우선, 없으면 Config.weight_feedback)
      breakdown[i] = {..., "feedback": s_fb}
7. prefer/force/pinned 보정 — M3 그대로
8. 다양성 보정 (req.diversity != "none") — sorted 결과를 재정렬:
      _apply_diversity(ranked, method="mmr", lambda_=...) -> ranked
      _apply_diversity(ranked, method="round_robin") -> ranked
9. top-N + 응답 빌드 + insert_search_query — M3 그대로
```

`_apply_diversity` 구현:

```python
def _apply_diversity(ranked: list[tuple[int, float, int]], method: str,
                     lambda_: float, count: int) -> list[int]:
    """ranked = [(asset_id, score, pack_id), ...] sorted desc by score.
    count = 반환 자산 수.
    """
    if method == "round_robin":
        # 팩 단위 큐 → 라운드별 1개씩 pop. 팩 소진 시 다음 팩으로.
        by_pack: dict[int, list[tuple[int,float]]] = {}
        for aid, s, pid in ranked:
            by_pack.setdefault(pid, []).append((aid, s))
        # 팩 순서: 각 팩의 top score 내림차순
        pack_order = sorted(by_pack.keys(),
                            key=lambda p: by_pack[p][0][1], reverse=True)
        picked: list[int] = []
        while len(picked) < count and any(by_pack[p] for p in pack_order):
            for p in pack_order:
                if not by_pack[p]:
                    continue
                picked.append(by_pack[p].pop(0)[0])
                if len(picked) >= count:
                    break
        return picked
    elif method == "mmr":
        # mmr_i = lambda*score_i - (1-lambda)*max_sim_to_picked
        # sim(i, j) = 1.0 if same_pack else 0.0
        picked: list[tuple[int, int]] = []  # (asset_id, pack_id)
        remaining = list(ranked)
        while remaining and len(picked) < count:
            best_idx, best_mmr = -1, float("-inf")
            for idx, (aid, s, pid) in enumerate(remaining):
                if picked:
                    max_sim = 1.0 if any(pp == pid for _, pp in picked) else 0.0
                else:
                    max_sim = 0.0
                mmr = lambda_ * s - (1.0 - lambda_) * max_sim
                if mmr > best_mmr:
                    best_mmr, best_idx = mmr, idx
            aid, _, pid = remaining.pop(best_idx)
            picked.append((aid, pid))
        return [aid for aid, _ in picked]
    else:  # "none"
        return [aid for aid, _, _ in ranked[:count]]
```

`ResultRow.score_breakdown` 에 `feedback` 키 항상 포함 (값 0 가능).

테스트:
- `tests/test_search_m4.py` — §2.2 의 8 케이스
- `tests/test_search_diversity.py` — §2.2 의 9 케이스
- `tests/test_feedback_penalty.py` — §2.2 의 10 케이스 (HybridSearcher 통합 + store 호출 spy)

### 3.4 `core/thumbnails.py` + `core/suggest_packs.py` (0.5일)

`core/thumbnails.py`:

```python
def ensure_thumbnail(
    asset_path: Path, kind: str, cache_dir: Path, asset_id: int,
    *, max_size: int = 256,
) -> Path | None:
    """sprite 자산만 256×256 PNG 생성. 이미 존재하면 즉시 반환. sound/spritesheet → None."""
    if kind not in ("sprite",):
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{asset_id}.png"
    if out.exists():
        return out
    try:
        from PIL import Image
        with Image.open(asset_path) as img:
            img.thumbnail((max_size, max_size))
            img.save(out, "PNG")
        return out
    except Exception:
        log.exception("thumbnail generation failed: %s", asset_path)
        return None
```

`core/suggest_packs.py`:

```python
def enrich_sample(
    asset_row: AssetRow, store: Store, cache_dir: Path,
    *, include_thumbnails: bool,
) -> dict:
    """asset_row → {asset_id, path, score, thumbnail_path, preview_blurb}."""
    thumb = None
    if include_thumbnails:
        thumb = ensure_thumbnail(Path(asset_row.path), asset_row.kind,
                                  cache_dir, asset_row.id)
    # preview_blurb: Gemma description 첫 한 줄 또는 top-2 라벨 폴백
    blurb = _extract_blurb(asset_row, store)
    return {
        "asset_id": asset_row.id, "path": asset_row.path,
        "thumbnail_path": str(thumb) if thumb else None,
        "preview_blurb": blurb,
    }


def _extract_blurb(asset_row: AssetRow, store: Store) -> str | None:
    # 1) sprite_meta.description (Gemma) 또는 sound_meta.description.
    # 2) 첫 한 줄만 (\n split), 80자 컷.
    # 3) 없으면 top-2 라벨로 폴백: "axis=label · axis=label"
    ...
```

`mcp/tools.py::tool_suggest_packs` 의 samples 채움 로직을 위 헬퍼로 교체.

테스트:
- `tests/test_thumbnails.py` — §2.2 의 5 케이스
- `tests/test_suggest_packs_samples_rich.py` — §2.2 의 6 케이스

### 3.5 MCP 모델 + 도구 + 서버 확장 (1일)

`mcp/models.py` 수정:

```python
# FindAssetRequest 에 4 필드 추가
class FindAssetRequest(BaseModel):
    # ... 기존 ...
    label_query: str | None = None
    diversity: Literal["none", "mmr", "round_robin"] = "none"
    diversity_lambda: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_feedback_override: float | None = None

# ReportFeedbackRequest.reason 을 Literal 로 제한
class ReportFeedbackRequest(BaseModel):
    query_id: int
    asset_id: int
    reason: Literal["negative", "positive", "irrelevant"]

# 신규 모델 4 개
class SaveSearchRequest(BaseModel):
    project_id: str | None = None
    name: str = Field(min_length=1, max_length=100)
    query: str = ""
    label_query: str | None = None
    kind: Literal["sprite", "spritesheet", "sound"] | None = None
    labels_all: list[AxisLabel] = []
    labels_any: list[AxisLabel] = []
    labels_none: list[AxisLabel] = []
    filters: Filters | None = None
    diversity: Literal["none", "mmr", "round_robin"] = "none"
    diversity_lambda: float | None = None
    count: int = 5
    model_config = ConfigDict(extra="forbid")

class SaveSearchResult(BaseModel):
    ok: bool
    saved_search_id: int

class ListSavedSearchesResult(BaseModel):
    saved_searches: list[dict]  # {id, name, query_json, created_at, last_used_at}

class DeleteSavedSearchRequest(BaseModel):
    project_id: str | None = None
    name: str

class RunSavedSearchRequest(BaseModel):
    project_id: str | None = None
    name: str
    overrides: dict = Field(default_factory=dict)  # SearchRequest 필드 일부 덮어쓰기

# SuggestPacksResult.packs[].samples[] 에 thumbnail_path / preview_blurb 추가
# (모델 자체는 dict 라 변경 없음; docs 갱신)
```

`mcp/tools.py` 신규 4 도구:

```python
def tool_save_search(deps, req: SaveSearchRequest) -> SaveSearchResult:
    """SearchRequest 형식 JSON 으로 직렬화 + store.save_search.
    project_id 가 string 이면 upsert_project 로 ID 매핑.
    중복 name → McpToolError("400_invalid_input", ...).
    """
    ...

def tool_list_saved_searches(deps, project_id: str | None) -> ListSavedSearchesResult:
    pid = None
    if project_id:
        pid = deps.store.upsert_project(project_id).id
    rows = deps.store.list_saved_searches(pid)
    return ListSavedSearchesResult(saved_searches=[
        {"id": r.id, "name": r.name, "query_json": r.query_json,
         "created_at": r.created_at, "last_used_at": r.last_used_at}
        for r in rows
    ])

def tool_delete_saved_search(deps, req: DeleteSavedSearchRequest) -> dict:
    with deps.store.write_lock:
        pid = None
        if req.project_id:
            pid = deps.store.upsert_project(req.project_id).id
        ok = deps.store.delete_saved_search(pid, req.name)
    if not ok:
        raise McpToolError("404_not_found", f"saved search {req.name!r} 없음")
    return {"ok": True}

def tool_run_saved_search(deps, req: RunSavedSearchRequest) -> FindAssetResult:
    pid = None
    if req.project_id:
        pid = deps.store.upsert_project(req.project_id).id
    row = deps.store.get_saved_search(pid, req.name)
    if row is None:
        raise McpToolError("404_not_found", f"saved search {req.name!r} 없음")
    payload = json.loads(row.query_json)
    payload.update(req.overrides)  # 호출 시 일부 override 허용
    # FindAssetRequest 재구성 후 tool_find_asset 위임
    find_req = FindAssetRequest(**payload, project_id=req.project_id)
    with deps.store.write_lock:
        deps.store.update_saved_search_last_used(row.id)
    return tool_find_asset(deps, find_req)
```

`tool_find_asset` 확장 — `label_query` 파싱:

```python
def tool_find_asset(deps, req: FindAssetRequest) -> FindAssetResult:
    parsed_all = list(req.labels_all)
    parsed_any = list(req.labels_any)
    parsed_none = list(req.labels_none)
    effective_query = req.query
    if req.label_query:
        try:
            parsed = parse_label_query(req.label_query, deps.registry)
        except AmbiguousLabel as e:
            raise McpToolError(
                "400_invalid_input",
                f"라벨 '{e.label}' 모호 — 가능한 axis: {', '.join(e.candidates)}",
            )
        except UnsupportedExpression as e:
            raise McpToolError("400_invalid_input", str(e))
        parsed_all.extend([AxisLabel(axis=l.axis, label=l.label) for l in parsed.labels_all])
        parsed_any.extend([AxisLabel(axis=l.axis, label=l.label) for l in parsed.labels_any])
        parsed_none.extend([AxisLabel(axis=l.axis, label=l.label) for l in parsed.labels_none])
        if parsed.free_text:
            effective_query = (req.query + " " + parsed.free_text).strip()

    sreq = SearchRequest(
        query=effective_query,
        # ... 기존 매핑 ...
        labels_all=_ax(parsed_all), labels_any=_ax(parsed_any), labels_none=_ax(parsed_none),
        diversity=req.diversity,
        diversity_lambda=req.diversity_lambda,
        weight_feedback_override=req.weight_feedback_override,
    )
    # ... 기존 결과 빌드 ...
```

`tool_report_feedback` 확장:

```python
def tool_report_feedback(deps, req: ReportFeedbackRequest) -> dict:
    weight = {
        "negative": deps.config.feedback_negative_weight,
        "positive": deps.config.feedback_positive_weight,
        "irrelevant": deps.config.feedback_irrelevant_weight,
    }[req.reason]
    # query_id → project_id 매핑 — search_queries.project_id
    row = deps.store.conn.execute(
        "SELECT project_id FROM search_queries WHERE id = ?", (req.query_id,),
    ).fetchone()
    if row is None:
        raise McpToolError("404_not_found", f"query_id={req.query_id} 없음")
    project_id = int(row[0]) if row[0] is not None else None
    if project_id is None:
        # global query — 페널티 학습 비활성 (프로젝트 없는 호출)
        log.info("feedback skipped (no project): %s", req)
        return {"ok": True, "skipped": True}
    with deps.store.write_lock:
        deps.store.insert_feedback_record(
            project_id=project_id, asset_id=req.asset_id,
            query_id=req.query_id, reason=req.reason, weight=weight,
        )
    return {"ok": True}
```

`mcp/server.py::register_all_tools` 에 4 도구 등록 추가. `INSTRUCTIONS` 갱신:

```
Recommended workflow (M4 update):
1. Session start: call list_labels(with_description=true) once; cache by `signature`.
2. User request: call suggest_packs(query, project_id, kind). Use `samples[].thumbnail_path`
   and `preview_blurb` to show preview to the user.
3. Pick: call find_asset(query, project_id, label_query="axis:label AND ...",
   diversity="mmr", force_pack_id=<picked>, count=N).
4. Adoption: after copying a file to the project, call record_asset_use.
5. Rejection: call report_feedback(query_id, asset_id, reason="negative") — this
   penalizes the asset/pack for the next search in this project.
6. Save reusable queries: call save_search(project_id, name, ...) and re-run later
   with run_saved_search(project_id, name).
```

테스트 (`tests/test_mcp_tools_m4.py` 의 14 케이스).

### 3.6 GUI 라이브러리 탭 풍부 UX (2일)

가장 큰 단위. 3 위젯 신규 + library_view 대대적 수정.

**`src/gah/ui/label_chip_panel.py`** — axis 별 라벨 칩 패널:

```python
class LabelChipPanel(QWidget):
    selectionChanged = Signal()

    def __init__(self, registry: LabelRegistry, parent: QWidget|None=None):
        super().__init__(parent)
        self._registry = registry
        self._checks: dict[tuple[str, str], QCheckBox] = {}
        self._mode_radios: dict[str, QRadioButton] = {}  # 'all'/'any'/'none'
        layout = QVBoxLayout(self)
        # 상단 — 모드 라디오
        mode_box = QGroupBox(_tr("매칭 모드"))
        mb_layout = QHBoxLayout(mode_box)
        for key, label in [("all", _tr("AND")), ("any", _tr("OR")),
                           ("none", _tr("NOT"))]:
            r = QRadioButton(label)
            self._mode_radios[key] = r
            mb_layout.addWidget(r)
        self._mode_radios["all"].setChecked(True)
        layout.addWidget(mode_box)
        # 본문 — axis 별 그룹
        self._build_axis_groups(layout)

    def selected(self) -> tuple[str, list[LabelFilter]]:
        """('all'|'any'|'none', [LabelFilter, ...])."""
        ...

    def _build_axis_groups(self, layout: QVBoxLayout) -> None: ...
```

**`src/gah/ui/search_side_panel.py`** — 가중치 + 저장된 검색:

```python
class SearchSidePanel(QWidget):
    weightsChanged = Signal()
    savedSearchActivated = Signal(str)        # name
    saveCurrentRequested = Signal(str)        # name

    def __init__(self, config: Config, store: Store, parent: QWidget|None=None):
        super().__init__(parent)
        self._config = config
        self._store = store
        layout = QVBoxLayout(self)

        # 가중치 슬라이더 5 채널 (실제 6 채널 중 feedback 은 별도 토글)
        self._sliders: dict[str, QSlider] = {}
        for name, label in [
            ("weight_semantic", _tr("의미")),
            ("weight_keyword", _tr("키워드")),
            ("weight_label_match", _tr("라벨")),
            ("weight_consistency", _tr("통일성")),
            ("weight_recency", _tr("최신")),
            ("weight_feedback", _tr("피드백")),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            s = QSlider(Qt.Horizontal)
            s.setRange(0, 100)
            s.setValue(int(getattr(config, name) * 100))
            s.valueChanged.connect(self._on_slider_changed)
            self._sliders[name] = s
            row.addWidget(s)
            layout.addLayout(row)

        # 프리셋 버튼
        preset_box = QGroupBox(_tr("프리셋"))
        pl = QHBoxLayout(preset_box)
        for key, label, weights in [
            ("balanced", _tr("균형"), DEFAULT_M4_WEIGHTS),
            ("consistency_first", _tr("통일성 우선"), CONSISTENCY_FIRST_WEIGHTS),
            ("novelty_first", _tr("참신성 우선"), NOVELTY_FIRST_WEIGHTS),
        ]:
            b = QPushButton(label)
            b.clicked.connect(lambda _, w=weights: self.apply_weights(w))
            pl.addWidget(b)
        layout.addWidget(preset_box)

        # 저장된 검색 리스트
        self._saved_list = QListWidget()
        self._saved_list.itemDoubleClicked.connect(
            lambda it: self.savedSearchActivated.emit(it.text()))
        layout.addWidget(QLabel(_tr("저장된 검색")))
        layout.addWidget(self._saved_list)

        # 저장 버튼
        self._save_btn = QPushButton(_tr("현재 검색 저장…"))
        self._save_btn.clicked.connect(self._on_save_clicked)
        layout.addWidget(self._save_btn)

    def apply_weights(self, weights: dict[str, float]) -> None: ...
    def _on_slider_changed(self, _: int) -> None: ...  # Config 즉시 갱신
    def _on_save_clicked(self) -> None: ...           # 이름 입력 다이얼로그 → signal
    def reload_saved_searches(self, project_id: int|None) -> None: ...
```

**`src/gah/ui/filter_bar.py`** — 다축 필터 + 정렬:

```python
class FilterBar(QWidget):
    filterChanged = Signal()

    def __init__(self, store: Store, parent: QWidget|None=None):
        super().__init__(parent)
        self._store = store
        layout = QHBoxLayout(self)
        # pack 다중 선택 — 컴포넌트는 QListWidget(MultiSelection)
        # kind / analysis_state / license / vendor — QComboBox
        # sort — QComboBox (score desc, score asc, added_at desc, ..., name asc)
        ...

    def current_filters(self) -> dict:
        """SearchRequest.filters + sort 키."""
        ...
```

**`src/gah/ui/library_view.py`** — 대대적 수정:

```python
class LibraryView(QWidget):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store
        self._searcher: HybridSearcher | None = None
        self._registry: LabelRegistry | None = None
        self._config: Config | None = None
        self._current_project_id: int | None = None  # GUI 세션 단위 (or None)

        # 레이아웃: QSplitter — 왼쪽 LabelChipPanel + FilterBar, 가운데 테이블, 오른쪽 SearchSidePanel
        splitter = QSplitter(Qt.Horizontal, self)
        left = self._build_left_panel()
        center = self._build_center_panel()
        right = self._build_right_panel()
        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1); splitter.setStretchFactor(1, 4); splitter.setStretchFactor(2, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def set_searcher(self, searcher): self._searcher = searcher
    def set_label_registry(self, registry):
        self._registry = registry
        self._label_chip_panel.populate(registry)
    def set_config(self, config):
        self._config = config
        self._side_panel.bind_config(config)
    # ... 기존 _run_search 가 chip + slider + filter 결과를 SearchRequest 로 통합 ...
```

테스트 (`tests/test_library_search_ui_rich.py` 의 14 케이스). offscreen Qt.

### 3.7 `docs/MCP_USAGE_GUIDE.md` + `DESIGN.md` 갱신 (0.5일)

`docs/MCP_USAGE_GUIDE.md`:

- **§1.1** 신규 4 도구 (`save_search`/`list_saved_searches`/`delete_saved_search`/`run_saved_search`) 의 실응답 JSON 예시.
- **§3.2** `label_query` 문법:

  ```
  label_query = "sound_mood:dark AND sound_use:combat NOT sound_genre:chiptune"
  ```

  파서 규칙·DNF 한계·모호 토큰 에러 응답 예시.
- **§4** `diversity` 옵션 + λ 튜닝 노트 (0.0 → 다양성 only, 1.0 → score only, 0.7 권장).
- **§5** `report_feedback` reason enum + 페널티 학습 동작 (asset-level / pack-level threshold).
- **§6** 에러 코드 표에 `400_invalid_input` 의 새 변형 (`label_query` 모호 / `UnsupportedExpression`) 추가.

`DESIGN.md`:

- **§5.1** SQL 스키마 끝에 `saved_searches` + `feedback_records` 2 블록 추가.
- **§6.5** `suggest_packs.samples` 응답이 `thumbnail_path`/`preview_blurb` 채워진 형태 (이미 DESIGN 정의대로) 명시.
- **§6.10** `report_feedback` 의 reason enum + 페널티 학습 알고리즘 한 문단 (asset-level + pack-level).
- **§6.x 신규 §6.12** — `save_search`/`list_saved_searches`/`delete_saved_search`/`run_saved_search` 4 도구 명세.
- **§11 Milestone 4** — 실제 한 일 정리 (defer 한 항목: 그리드↔리스트 토글·hover preview·사운드 인라인 재생·결과 비교 보기·키보드 단축키는 M7).

## 4. 외부 의존성

| 패키지 | 용도 | 비고 |
|---|---|---|
| (없음) | — | M4 는 기존 의존성만 사용. Pillow (M2), PySide6 (M0), mcp SDK (M3) 가 그대로 충분. |

기존 의존성 변화 없음. 새 wheel 추가 없음.

## 5. 테스트 전략

### 5.1 테스트 fixture

새 fixture (`tests/conftest.py` 확장):

- `m4_store` — M3 `populated_store` 확장. `saved_searches`/`feedback_records` 비어 있는 상태로 초기화 + 2~3 자산에 라벨 매칭 가능하도록 axis/label 분포 확보.
- `populated_label_registry` — M2/M3 의 24 axis 316 라벨 시드를 fake registry 로 빠르게 빌드. 파서 테스트가 외부 DB 의존 없이 결정적.
- `make_search_request` — `SearchRequest` 빌더 헬퍼 (테스트별 일부 필드만 채움).
- `tmp_thumbnail_cache` — 임시 디렉터리 + 1 sprite PNG 셋업.
- `qtbot` 대용 직접 위젯 픽스처 — `offscreen` 모드로 `LabelChipPanel`/`SearchSidePanel`/`FilterBar` 인스턴스 빠르게 생성.

### 5.2 단위 테스트 목록 (요약 — §2.2 표가 단일 출처)

§2.2 표가 케이스 수 + 핵심 검증을 그대로 담는다. 총 ~100 active.

### 5.3 테스트 인프라

- `pyproject.toml [tool.pytest.ini_options]` — `markers` 변경 없음. M4 의 mcp_integration 갱신은 기존 마크 그대로 사용.
- `tests/test_mcp_integration.py` — 기존 2 케이스의 `tools/list` 12 → 16 단언 갱신.
- `populated_store` 픽스처 (M3) 는 M4 의 신규 두 테이블이 비어 있는 상태로 호환 — `initialize()` 가 M1+M2+M3+M4 4 스키마를 동시에 만들면서 빈 테이블만 생성.
- 가중치 검증 픽스처 — M3 의 5채널 합 1.0 단언이 6채널 합 1.0 으로 갱신 (`test_config_m3::test_weight_sum_equals_one_within_tolerance` 회귀 갱신 1 건).

### 5.4 검증 기준 (Definition of Done)

1. `pytest -q` 전체 통과 — M0(18) + M1(49) + M2(134) + M2.1(16) + M3(112) + 회귀 갱신(±0) + M4 신규 ~100 = 합계 **약 429 active**. `clip_integration` 2 + `mcp_integration` 2 = 4 deselected.
2. M0/M1/M2/M2.1 회귀 0 건. M3 회귀는 `test_config_m3::test_weight_sum_equals_one_within_tolerance` 1 건 갱신 (6채널 합 1.0 단언으로 수정).
3. PowerShell 수동 검증 (§5.5):
   - `python -m gah --mcp` 의 `tools/list` 가 16 도구 반환 (4 신규 포함).
   - `find_asset` 에 `label_query="sound_mood:dark AND sound_use:combat"` 전달 → 응답 `matched_labels` 에 두 라벨 포함.
   - `report_feedback(reason="negative")` 호출 후 같은 자산이 다음 `find_asset` 응답에서 순위 하락 (`score_breakdown.feedback` 음수).
   - `save_search` → `list_saved_searches` → `run_saved_search` 라운드트립 정상.
   - GUI 라이브러리 탭에 좌측 칩 패널 + 우측 슬라이더 패널 + 상단 검색 박스 + 정렬 드롭다운 모두 노출. 칩 선택 후 검색 → 결과 행에 matched_labels 노출.
4. `docs/MCP_USAGE_GUIDE.md` 가 신규 4 도구 + `label_query` 문법 + `diversity`/`report_feedback` 새 동작 모두 문서화.
5. `DESIGN.md` 가 §5.1/§6.5/§6.10/§6.12/§11 갱신 — 신규 테이블·새 응답·페널티 학습·4 신규 도구·M4 실제 한 일.

### 5.5 수동 검증 시나리오 (요약)

`milestones/M4_verification.md` 가 끝에 자세히 작성. plan 차원에선 다음만 둔다.

1. **자동 — `pytest -q` 약 429 통과**.
2. **MCP `tools/list` 16 도구** — `pytest -m mcp_integration -v` 자동.
3. **`label_query` 파서 e2e** — Claude 가 직접 `tool_find_asset` 호출 후 응답 검증.
4. **페널티 학습 e2e** — 같은 query 두 번 + 사이에 `report_feedback("negative")` 호출 → 두 번째 응답의 `score_breakdown.feedback` 음수.
5. **저장된 검색 라운드트립** — `save_search` → `list` → `run_saved_search` → `tool_find_asset` 결과와 동일.
6. **GUI 풍부 UX** — 사용자가 트레이의 메인 윈도우 라이브러리 탭에서 칩 다중 선택 + 슬라이더 조작 + 저장된 검색 활용 시각 확인.

## 6. 위험 요소와 완화

- **`label_query` 파서의 모호성 vs 사용자 친화** — `AND`/`OR`/`NOT` 대문자 키워드는 영어권 사용자에겐 자연스럽지만 한국어 사용자는 불편할 수 있다. M4 v1 은 영어 키워드만 — 한국어 키워드 (`그리고`/`또는`/`제외`) 는 M5+ 가 사용자 피드백 기반으로 결정. GUI 검색 박스 placeholder 에 짧은 안내 + ⓘ 툴팁으로 문법 가이드.
- **DNF 정규화 한계 — 혼합 AND/OR 미지원** — v1 은 순수 AND 또는 순수 OR 만 정확 매핑. `(a AND b) OR c` 같은 혼합은 `UnsupportedExpression` 예외. 사용 빈도 분석은 verification 단계 — 자주 쓰이면 M5+ 가 OR-of-AND 매핑 추가.
- **bare label 의 모호 매칭** — 같은 label 텍스트가 여러 axis 에 등록될 수 있다 (예: "dark" 가 `sound_mood`/`sprite_palette` 양쪽). `AmbiguousLabel` 예외 + 후보 axis 제안 — 사용자가 `axis:label` 명시로 재시도. 24 axis 316 라벨 시드에서 실측 모호 케이스 0~3 개 예상 (verification 에서 수집).
- **6번째 가중 채널 추가의 회귀** — `test_score_breakdown_sums_to_score_within_tolerance` (M3) 가 5 키 합산 단언. M4 가 6 키로 확장하면서 `feedback` 키 항상 포함 (값 0 가능) 으로 회귀 흡수. M3 의 가중치 합 1.0 단언 1 건만 6채널로 갱신.
- **MMR λ 선택** — 너무 작으면 score 낮은 자산이 다양성만으로 끌려옴. 너무 크면 다양성 효과 없음. 0.7 기본 — IR 표준 권장값. GUI 슬라이더로 사용자가 미세 조절 가능 (M5+ 토글 위치 결정).
- **`feedback_records` 누적의 stale risk** — 30일 윈도우 (`feedback_window_seconds`) 로 자동 만료. 사용자가 라이브러리 재구성 후 옛 페널티가 남아 새 자산을 부당하게 밀지 않게. `cleanup_feedback_records` 잡은 M5+ 가 추가 (M4 는 윈도우 필터만).
- **pack-level penalty 의 과민 반응** — 3 negative 자산이 같은 팩이면 pack-wide -0.1. 임계가 너무 낮으면 한두 번의 실수로 팩 전체가 페널티. Config 노출 (`feedback_pack_threshold=3` 기본) + GUI 설정 슬라이더로 사용자 조절.
- **`saved_searches.query_json` 의 스키마 진화** — M4 의 SearchRequest 구조가 M5+ 에서 바뀌면 저장된 검색이 깨짐. v1 은 `query_json` 에 `_schema_version: 1` 필드 박음 — M5+ 가 마이그레이션 시그널로 사용.
- **GUI 풍부 UX 의 성능** — 칩 패널 24 axis × ~15 라벨 = ~360 체크박스. Qt 가 그 정도는 즉시 렌더. 단 라벨 추가/제거 시 패널 전체 재구성이 100ms+ 걸릴 수 있음 — `LabelRegistry` 변경 시그널을 받아 변경된 axis 만 부분 갱신.
- **저장된 검색의 동시 수정 충돌** — 트레이 GUI + `--mcp` 두 프로세스가 같은 name 으로 save 시 SQLite UNIQUE 위반. `OperationalError` → `400_invalid_input` 변환. 사용자에게 "이미 존재" 안내 + GUI 는 "덮어쓰기?" 다이얼로그.
- **MCP `run_saved_search` 의 overrides 부작용** — overrides 가 잘못된 필드 키를 보내면 `FindAssetRequest(**payload, **overrides)` 가 ValidationError. typed error 반환 — 사용자가 어떤 필드가 잘못됐는지 확인.
- **GUI 풍부 UX 의 수동 검증 부담 증가** — M3 는 검색 박스 1 항목만 사용자 시각 확인이었으나 M4 는 칩/슬라이더/저장된 검색/정렬 4 항목이 시각 단계. `feedback_milestone_manual_verification_format.md` 에 따라 단계별 체크리스트로 사용자 응답 본문에 별도 제시.
- **`tool_report_feedback` 의 query_id 가 없는 호출** — 저장된 검색 모드에서 `find_asset` 가 새 query_id 를 발급 → 같은 query_id 로 `report_feedback` 호출 가능. 단 `save_search` 자체는 query_id 발급 안 함 (저장만). MCP 클라이언트는 항상 `find_asset` 또는 `run_saved_search` 응답의 `query_id` 를 캐시 후 `report_feedback` 에 전달.

## 7. M5 인계점

M4 가 끝나면 M5 (시트 분석 + 애니메이션) 이 다음을 그대로 받는다.

- **`LabelRegistry` + `label_query` 파서** — M5 의 시트 분석이 추가하는 새 axis (`sheet_animation`, `sheet_grid` 등) 도 같은 파서로 검색 가능.
- **`HybridSearcher` 6채널 + 다양성** — M5 의 새 자산 (시트 frame 단위 splitting 결과) 도 같은 검색 알고리즘으로 즉시 노출.
- **`saved_searches`** — M5 가 시트 관련 검색 패턴 ("walk 애니메이션 시트") 을 저장된 검색으로 노출.
- **`feedback_records`** — M5 의 frame 추정 결과에 대한 사용자 피드백도 같은 메커니즘으로 누적.
- **GUI 풍부 UX** — M5 가 시트 frame 미리보기 패널을 라이브러리 탭에 추가할 때 칩 패널/슬라이더 패널이 그대로 컨테이너 역할.

또 M4 안에서 **의도적으로 남겨두는** 자리 (M5+ 가 채움):

- 결과 그리드 ↔ 리스트 토글 — v1 은 표 형태만. M7 GUI 마감이 그리드 뷰 추가.
- hover 미리보기 — v1 미포함. M7.
- 사운드 인라인 재생 — v1 미포함. M7 (PySide6 `QMediaPlayer`).
- 결과 비교 보기 — v1 미포함. M7.
- 키보드 단축키 — v1 미포함 (Tab/Enter 기본 동작만). M7.
- `cleanup_feedback_records` 잡 (윈도우 만료 행 삭제) — v1 은 검색 시 윈도우 필터만. M5+ 가 주기적 정리.
- `label_query` 의 한국어 키워드 (`그리고`/`또는`/`제외`) — v1 영어만. M5+ 사용자 피드백 기반 결정.
- `label_query` 의 혼합 AND/OR (OR-of-AND DNF) — v1 순수형만. M5+ 가 사용 빈도 기반.
- 가중치 슬라이더 + 페널티 학습의 사용자 가시화 — v1 은 슬라이더 + Config 만. 페널티 학습이 실제로 결과를 어떻게 바꿨는지 GUI 차트 노출은 M7.

---

## 자기 검토 메모

- §1 가중치 공식 합 = `0.35 + 0.10 + 0.20 + 0.20 + 0.05 + 0.10 = 1.00`. ✓
- §2.1 의 모듈 14 개 ↔ §3 의 작업 단위 7 묶음 — 매핑:
  - 3.1 (Config + Store) ↔ config.py + store.py
  - 3.2 (parser) ↔ label_query.py
  - 3.3 (search 확장) ↔ search.py
  - 3.4 (thumbnails + suggest_packs) ↔ thumbnails.py + suggest_packs.py
  - 3.5 (MCP) ↔ mcp/models.py + mcp/tools.py + mcp/server.py
  - 3.6 (GUI) ↔ library_view.py + label_chip_panel.py + search_side_panel.py + filter_bar.py
  - 3.7 (문서) ↔ MCP_USAGE_GUIDE.md + DESIGN.md
  매핑 일관 ✓
- §2.2 표 합 = 16+12+9+10+6+14+14+8+6+5 = **100 신규 active**. ✓ (mcp_integration 갱신 0 신규)
- 의존성 변화 없음 — 위험도 낮음. ✓
- 위험 요소 §6 — 파서 한계 + 가중 채널 추가 회귀 + GUI 성능 + 저장된 검색 동시 수정 모두 완화책 명시. ✓
- M5 인계점 §7 — `LabelRegistry`/`HybridSearcher`/`saved_searches`/`feedback_records`/GUI 컨테이너 모두 그대로 활용 ✓
- 한국어 plan / 영어 파일·폴더명 — 준수 ✓
- 메모리 `feedback_run_commands_directly.md` — 자동 측정 가능한 것은 Claude 가 PowerShell 로 직접 (MCP `tools/list` 16 + 페널티 학습 e2e + 저장된 검색 라운드트립), GUI 풍부 UX 4 항목만 사용자 시각. ✓
- 메모리 `feedback_milestone_manual_verification_format.md` — M4 끝 응답 본문에 단계별 체크리스트 (GUI 4 항목) 별도 제시 예정. ✓
- 메모리 `project_search_ux_milestone.md` — 라벨 칩 다중 선택 + 가중치 슬라이더 + 저장된 검색 + 다축 필터 + 정렬 모두 포함. 그리드↔리스트 토글·hover preview·사운드 인라인 재생·결과 비교 보기·키보드 단축키는 M7 으로 명시 미룸 (§7). ✓
- 메모리 `project_label_scoring_clip_inclusion.md` — `label_match` 채널 가중치 동일 0.20 보존. ✓

검증 끝.
