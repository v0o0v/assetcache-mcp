# M2 — 분석 파이프라인 + CLIP 라벨 스코어러 (구현 계획)

> **에이전트 작업자에게**: 이 plan은 한국어 마일스톤 표준 형식이다. 본 plan을 그대로 따라 [`milestones/M2_todo.md`](./M2_todo.md) 의 체크리스트를 만들고, **테스트를 먼저 작성한 뒤** 구현으로 넘어간다. M1 사이클(red → green → verification)을 그대로 답습한다.

## 1. 목표

M1이 깔아둔 워처·팩 매니저·SQLite 위에 **분석 파이프라인**을 얹는다. M2가 끝나면 `assets.analysis_state='pending'` 인 행 하나가 다음 단계를 거쳐 `'ok'`(혹은 일부 실패 시 `'partial'`/`'failed'`)로 전이된다.

- **스프라이트** — Pillow + numpy 로 기술 특성(해상도·알파·도미넌트 컬러·픽셀아트 여부) 추출 → Gemma 4 멀티모달로 듀얼 언어 라벨(영어 enum + 호출 언어 자연어) → CLIP zero-shot 으로 라벨별 객관 0~1 점수 → 라벨 + 메타 + 임베딩을 DB 에 저장.
- **사운드** — librosa + soundfile 로 기술 특성(길이·SR·채널·loudness·BPM) 추출 → Gemma 4 네이티브 오디오 호출 → 실패 시 멜 스펙트로그램 비전 폴백 → 그래도 실패면 휴리스틱 분류. 사운드 라벨링은 Gemma only(CLIP 안 함, v2 검토).
- **임베딩** — Ollama `nomic-embed-text` 로 "검색 가능한 텍스트"(파일명 + 카테고리 + 라벨 상위 + description) 768차원을 BLOB 으로 저장.
- **백엔드 추상화** — `ollama_client` 는 OpenAI 호환 `/v1/chat/completions` 우선 + Ollama 네이티브 `/api/chat` 폴백. base URL 한 줄로 LM Studio·llama-server 로 교체 가능 (`DESIGN.md §4.2.4`).
- **분석 큐** — M1 `LibraryWatcher.on_pack_changed` 콜백 + 부팅 시 풀스캔에서 발견된 `pending` 행을 단일 큐로 모아 워커가 순차 처리. 동시성 1 기본(`Config.analysis_concurrency`).
- **DB 마이그레이션** — `sprite_meta`, `sound_meta`, `assets_fts`(FTS5), `asset_embeddings`, `asset_labels` 5개 테이블을 신설. 기존 4개와 합쳐 총 9개. `assets.analysis_state` 전이(`pending → analyzing → ok / partial / failed`) 가 분석기에서 일어난다.
- **i18n 준비** — 메모리 `project_output_language_strategy.md` 결정에 따라 M1 GUI 의 사용자 노출 문자열을 일괄 `tr()` 래핑. M7 마감의 Qt 번역 도입을 한 단계로 줄인다.

M2 가 끝나면 사용자가 라이브러리에 팩을 떨어뜨렸을 때 GUI 라이브러리 탭의 `analysis_state` 컬럼이 `pending → analyzing → ok` 로 변하고, 같은 행에 라벨 칩 한두 개와 한국어 description 한 줄이 보인다(라벨·description 컬럼은 M2에서 새로 추가). 검색·통일성·MCP 도구는 M3 이후의 일이라 M2 GUI 는 여전히 단순 표.

## 2. 산출물

| 파일/디렉터리 | 책임 | 상태 |
|---|---|---|
| `pyproject.toml` (수정) | M2 의존성 추가 — `Pillow>=10`, `numpy>=1.26`, `librosa>=0.10`, `soundfile>=0.12`, `httpx>=0.27`, `pydantic>=2.6`, `open_clip_torch>=2.24`, `torch>=2.2` (CPU wheels). dev 그룹에 `pytest-asyncio>=0.23`, `respx>=0.20` (httpx 모킹) 추가 | 수정 |
| `src/gah/config.py` (수정) | `Config` 에 M2 필드 9개 추가 — `analysis_timeout_seconds`, `analysis_concurrency`, `analysis_max_retries`, `description_language`, `clip_model`, `clip_pretrained`, `clip_enable`, `audio_max_seconds`, `audio_chunk_strategy` | 수정 |
| `src/gah/core/store.py` (수정) | `_M2_SCHEMA` 상수 추가 + `initialize()` 에서 M1·M2 스키마 둘 다 실행. 신규 메서드: `mark_asset_analyzing`, `save_sprite_meta`, `save_sound_meta`, `save_asset_labels`, `save_embedding`, `update_fts`, `next_pending_asset`, `mark_asset_state`, `update_pack_aggregate` | 수정 |
| `src/gah/core/labels.py` | 시드 라벨 정의(`SEED_LABELS: dict[str, list[str]]`, 8축 × 평균 10개 ≈ 80개) + `LabelRegistry` — DB(`labels` 테이블) 기반 동적 라벨 조회·추가·비활성화. 부팅 시 빈 DB 면 시드 자동 적재. in-memory 캐시 + 변경 시 invalidate. | 신규 |
| `src/gah/ui/labels_admin.py` | 라벨 관리 다이얼로그(`QDialog`) — 축별 라벨 목록 + "추가"/"비활성화"/"활성화" 액션. 추가 즉시 `LabelRegistry.add_label` 호출, CLIP 라벨 임베딩은 다음 분석 때 lazy 계산. 트레이 메뉴 "라벨 관리…" 에서 호출. | 신규 |
| `src/gah/core/ollama_client.py` | `OllamaClient` 클래스. `chat(...)` — OpenAI 호환 1차 → Ollama 네이티브 폴백. 이미지/오디오 base64 페이로드 어댑터. `embed(text) -> list[float]`. `format="json"` 강제 + 재시도(지수 백오프). 모든 base URL·모델·타임아웃은 `Config` 주입. | 신규 |
| `src/gah/core/embedding.py` | `EmbeddingEncoder.encode(text) -> bytes` (float32 LE 직렬화). 검색 쿼리도 같은 인코더로 임베딩. 768차원 가정은 모델 호출 후 첫 응답 길이로 확정해 BLOB 저장. | 신규 |
| `src/gah/core/clip_labeler.py` | `ClipLabeler` 클래스. `open_clip` 모델 lazy 로딩, 라벨 텍스트 임베딩 사전 계산 + DB 캐시(`asset_labels` 와 별개 KV 캐시: `clip_label_cache(label, model, vector BLOB)`). `score_image(path) -> dict[label, score 0..1]`. 모델 가중치는 첫 실행 시 `%APPDATA%/GameAssetHelper/cache/clip/` 에 다운로드. | 신규 |
| `src/gah/core/analyzer/__init__.py` | 패키지 마커 | 신규 |
| `src/gah/core/analyzer/base.py` | `AnalyzerResult` / `SearchableTexts` / `AnalyzerInput` 데이터클래스, `AnalyzerError`(분기별 sub 에러), `ResponseModel` Pydantic 베이스 | 신규 |
| `src/gah/core/searchable.py` | `build_searchable(meta, labels, label_descriptions, description, rel_path) -> SearchableTexts` — FTS용 풍부 텍스트 + 임베딩용 단순 텍스트 빌더(분석기 2개가 공유). 토큰 prefix(`label:`/`category:`/`style:`/...) 규칙도 여기 집중. | 신규 |
| `src/gah/core/analyzer/sprite.py` | `SpriteAnalyzer.analyze(path, language) -> AnalyzerResult` — Pillow 기술 특성 + 이미지 리샘플(긴 변 768px) + Gemma 호출 + Pydantic 검증 + CLIP 점수 통합 | 신규 |
| `src/gah/core/analyzer/sound.py` | `SoundAnalyzer.analyze(path, language) -> AnalyzerResult` — librosa 기술 특성 + 30s 클립 선택 + 1차 네이티브 → 2차 스펙트로그램 → 3차 휴리스틱 폴백 | 신규 |
| `src/gah/core/analysis_queue.py` | `AnalysisQueue` — `enqueue_asset(asset_id)`/`enqueue_pack(pack_id)`/`drain_pending(store)`/`progress()`. `ThreadPoolExecutor(max_workers=config.analysis_concurrency)` 워커가 한 항목씩 꺼내 `route_analyzer(kind)` → DB 업데이트. Qt 시그널 `analysisFinished(int)` + `progressChanged(AnalysisProgress)` 노출. ETA 트래커(최근 10건 평균) 내장. | 신규 |
| `src/gah/app.py` (수정) | `AnalysisQueue` 인스턴스 생성, `LibraryWatcher.on_pack_changed` 안에서 `queue.enqueue_pack` 호출, 부팅 시 `queue.drain_pending(store)` 1회. `LabelRegistry.bootstrap()` 호출. 종료 시 큐 graceful stop. | 수정 |
| `src/gah/ui/main_window.py` (수정) | 분석 큐 시그널을 받아 `refresh()` 디스패치. `QStatusBar` 에 `QProgressBar` + ETA 라벨 영구 위젯. 메뉴/탭/컬럼 헤더의 사용자 노출 문자열을 모두 `tr("...")` 로 감싸기. 라이브러리 탭 컬럼에 `labels`, `description` 두 줄 추가. `_format_duration_kor` 헬퍼. | 수정 |
| `src/gah/tray.py` (수정) | `"라벨 관리…"` 메뉴 액션 추가. `setToolTip()` 으로 분석 진행 상황 짧은 형식 표시(시그널로 갱신). | 수정 |
| `src/gah/ui/pack_view.py` (수정) | `aggregate_meta` 열(주 스타일·도미넌트 팔레트 요약)을 표시. `tr()` 래핑. | 수정 |
| `src/gah/ui/library_view.py` (수정) | `labels`(상위 3개 칩 텍스트)·`description` 열 추가. `tr()` 래핑. | 수정 |
| `tests/fixtures/` | M2 테스트용 작은 PNG/WAV (모두 OSS·CC0 또는 직접 생성) 6~10 파일 (§5.2) | 신규 디렉터리 |
| `tests/test_store_m2.py` | M2 신규 테이블 생성·idempotent·새 메서드 단위 테스트 (≈ 18 케이스, `labels`/`clip_label_cache` 포함) | 신규 |
| `tests/test_labels.py` | 시드 라벨 일관성(중복 없음·축별 키 존재·총 개수 80~100 범위) + `LabelRegistry` 시드 적재·추가·비활성화·캐시 무효화·CLIP 캐시 영향 (≈ 12 케이스) | 신규 |
| `tests/test_labels_admin_ui.py` | 라벨 관리 다이얼로그 — 축별 목록 표시·추가 입력·비활성화 토글이 `LabelRegistry` 와 양방향 (≈ 5 케이스, offscreen) | 신규 |
| `tests/test_ollama_client.py` | `respx` 로 OpenAI/네이티브 양 경로 모킹 — JSON 응답 파싱·재시도·이미지 base64·오디오 base64·임베딩 (≈ 15 케이스) | 신규 |
| `tests/test_embedding.py` | float32 LE 직렬화 왕복·차원 확정·`OllamaClient` 모킹 (≈ 5 케이스) | 신규 |
| `tests/test_clip_labeler.py` | CLIP 백엔드를 인터페이스로 추상화해 fake 임베딩으로 검증 (실모델 다운로드는 옵트인 통합 마크). 라벨 점수 정렬·top-k·라벨 추가 시 캐시 무효화 (≈ 8 케이스) | 신규 |
| `tests/test_analyzer_sprite.py` | fixture PNG + 모킹된 Gemma JSON 응답 → 메타·라벨·임베딩 입력 문자열 어셈블 검증 (≈ 10 케이스) | 신규 |
| `tests/test_analyzer_sound.py` | fixture WAV + 1차/2차/3차 폴백 분기 — `audio_path_used` 가 `'native'`/`'spectrogram'`/`'heuristic'` 으로 정확히 마킹되는지 (≈ 8 케이스) | 신규 |
| `tests/test_analysis_queue.py` | 가짜 analyzer 와 가짜 clock 으로 큐·동시성 1·재시도·실패 격리 (≈ 8 케이스) | 신규 |
| `tests/test_analysis_progress.py` | `AnalysisProgress` 빌더·ETA 계산·진행 시그널·`_format_duration_kor` 헬퍼 (≈ 9 케이스) | 신규 |
| `tests/test_progress_statusbar.py` | 상태바 진행 위젯 — `update_progress` 슬롯이 ProgressBar 와 라벨을 정확히 갱신, "완료" 표시 후 idle 전환 (≈ 4 케이스, offscreen) | 신규 |
| `tests/test_config_m2.py` | M2 신규 필드 9개 — 기본값·forward-compat·TOML 왕복 (≈ 5 케이스) | 신규 |
| `tests/test_ui_smoke_m2.py` | `tr()` 래핑 후에도 위젯 생성·`refresh()` 가 새 컬럼을 채우는지 (≈ 3 케이스) | 신규 |
| `milestones/M2_todo.md` | TDD 체크리스트(이 plan 의 §3 작업 단위를 1:1 매핑) | 신규 |
| `milestones/M2_verification.md` | M2 끝에 작성 — 자동 `pytest -v` 결과 + 사용자 수동 검증 항목 + 알려진 한계 | 신규 |
| `docs/MCP_USAGE_GUIDE.md` | M3 인계용 stub — Claude Code 가 라벨 어휘를 활용해 자연어 쿼리를 어떻게 보내는지, `label_catalog_signature` 캐시 정책, 표준 워크플로. M3 완료 시 실제 응답 예시로 풀어쓴다. | 신규 stub |

## 3. 작업 단위와 책임

작업은 순서대로 진행한다(앞 모듈이 뒤 모듈의 빌딩 블록). 각 단위는 **테스트 먼저 → 구현 → 통과 → 커밋** 사이클을 지킨다.

### 3.1 `core/store.py` 마이그레이션 (M2 신규 테이블)

기존 `_SCHEMA` 는 그대로 두고 `_M2_SCHEMA` 상수를 추가, `initialize()` 가 두 스크립트를 순차 실행한다. 모두 `IF NOT EXISTS`/`CREATE VIRTUAL TABLE IF NOT EXISTS` 라 M1 사용자 DB 에 적용해도 안전하다.

```sql
-- _M2_SCHEMA 의 핵심
CREATE TABLE IF NOT EXISTS sprite_meta (
  asset_id        INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
  width           INTEGER NOT NULL,
  height          INTEGER NOT NULL,
  has_alpha       INTEGER NOT NULL,
  is_pixel_art    INTEGER NOT NULL,
  dominant_colors TEXT,
  frame_w         INTEGER,
  frame_h         INTEGER,
  frame_count     INTEGER,
  animation_tags  TEXT
);

CREATE TABLE IF NOT EXISTS sound_meta (
  asset_id        INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
  duration_ms     INTEGER NOT NULL,
  sample_rate     INTEGER NOT NULL,
  channels        INTEGER NOT NULL,
  loudness_db     REAL,
  bpm             REAL,
  category        TEXT,              -- sfx/bgm/voice/ui_sound/ambient/...
  loopable        INTEGER,
  instruments     TEXT,              -- JSON array of instrument enum labels
  tempo           TEXT,              -- very_slow..very_fast/variable
  intensity       TEXT,              -- quiet..deafening/swelling/sudden_burst
  genre           TEXT,              -- bgm·jingle·cinematic 일 때만 채움 (orchestral/electronic/...)
  voice_type      TEXT,              -- voice 일 때만 채움 (male_adult/.../singing)
  audio_path_used TEXT               -- 'native' | 'spectrogram' | 'heuristic'
);

CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
  asset_id UNINDEXED,
  searchable_text,
  tokenize = 'porter unicode61'
);

CREATE TABLE IF NOT EXISTS asset_embeddings (
  asset_id INTEGER PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
  model    TEXT NOT NULL,
  dim      INTEGER NOT NULL,
  vector   BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_labels (
  asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  axis     TEXT NOT NULL,            -- 'category'/'style'/'mood'/...
  label    TEXT NOT NULL,            -- 'pixel_art' / 'heroic' / ...
  score    REAL NOT NULL,            -- 0..1
  source   TEXT NOT NULL,            -- 'gemma' | 'clip' | 'user'
  weight   TEXT,                     -- 'primary'/'secondary'/'tertiary' (Gemma 만, 메모리 라벨 가중치 결정 참조)
  PRIMARY KEY (asset_id, axis, label, source)
);
CREATE INDEX IF NOT EXISTS idx_labels_label ON asset_labels(label);
CREATE INDEX IF NOT EXISTS idx_labels_asset ON asset_labels(asset_id);

-- CLIP 라벨 텍스트 임베딩 캐시
CREATE TABLE IF NOT EXISTS clip_label_cache (
  label    TEXT NOT NULL,
  model    TEXT NOT NULL,   -- 'ViT-B-32:openai' 같은 식별자
  dim      INTEGER NOT NULL,
  vector   BLOB NOT NULL,
  PRIMARY KEY (label, model)
);

-- 라벨 어휘(시드 + 사용자 추가) 단일 출처 — Claude Code 가 라벨 의미를 알 수 있도록 description 동봉
CREATE TABLE IF NOT EXISTS labels (
  id          INTEGER PRIMARY KEY,
  axis        TEXT NOT NULL,        -- 'category'/'style'/'mood'/...
  label       TEXT NOT NULL,        -- 'pixel_art' 같은 영어 enum 토큰
  description TEXT,                 -- 영어 한 문장 — 라벨 의미. Claude Code 가 자연어 쿼리를 라벨로 매핑할 때 참조
  source      TEXT NOT NULL,        -- 'seed' | 'user'
  enabled     INTEGER NOT NULL DEFAULT 1,
  created_at  INTEGER NOT NULL,
  updated_at  INTEGER NOT NULL,
  UNIQUE (axis, label)
);
CREATE INDEX IF NOT EXISTS idx_labels_axis_enabled ON labels(axis, enabled);
```

`Store` 에 추가하는 메서드:

- `mark_asset_analyzing(asset_id) -> None` — 단일 UPDATE.
- `save_sprite_meta(asset_id, meta: SpriteMeta)` — REPLACE INTO.
- `save_sound_meta(asset_id, meta: SoundMeta)` — REPLACE INTO.
- `save_asset_labels(asset_id, labels: list[LabelScore])` — 트랜잭션 안에서 `DELETE WHERE asset_id=?` 후 일괄 INSERT.
- `save_embedding(asset_id, model, vector_bytes, dim)` — REPLACE INTO.
- `update_fts(asset_id, searchable_text)` — `DELETE FROM assets_fts WHERE asset_id=?` 후 INSERT.
- `next_pending_asset() -> AssetRow | None` — 드레인 워커가 호출. `analysis_state='pending'` 중 `added_at ASC` 1행. (잠금 경합 회피: 단순 SELECT 후 `mark_asset_analyzing` 두 번 호출은 정상 — 워커가 1개라 race 없음.)
- `mark_asset_state(asset_id, state, error: str | None = None, analyzed_at: int | None = None)` — `state ∈ {'ok','partial','failed'}` 일 때 `analyzed_at` 설정.
- `update_pack_aggregate(pack_id, aggregate_json: str)` — `packs.aggregate_meta` 채움. PackManager 가 팩 전체 분석 종료 시 호출(M2 범위 안).
- `pending_assets_for_pack(pack_id) -> list[AssetRow]` — 큐 enqueue_pack 에서 사용.
- `clip_label_cache_get(label, model) -> bytes | None` / `clip_label_cache_put(label, model, dim, vector)`.
- `list_labels(axis: str | None = None, *, enabled_only: bool = True, with_description: bool = False) -> list[LabelRow]` — 라벨 조회. `with_description=True` 면 `LabelRow.description` 도 채움.
- `add_label(axis, label, *, source='user', description: str | None = None) -> int` — `UNIQUE(axis,label)` 충돌 시 기존 행 활성화로 폴백, id 반환. description 이 주어지면 같이 갱신.
- `set_label_description(axis, label, description: str | None)` — description 만 갱신, updated_at 도 같이.
- `set_label_enabled(axis, label, enabled: bool)` — 비활성화는 행 보존(추후 재활성화 가능). 비활성 라벨은 분석/검색 어휘 공간에서 제외.
- `seed_labels(initial: dict[str, list[tuple[str, str | None]]]) -> int` — 빈 `labels` 테이블에만 시드 INSERT(라벨 토큰 + 영어 description 묶음). 반환은 적재된 행 수. 두 번째 호출은 0행.
- `label_catalog_signature() -> str` — 활성 라벨 어휘의 전체 해시(`SELECT axis,label FROM labels WHERE enabled=1 ORDER BY ...` 의 sha256 16헥스). MCP 클라이언트가 라벨 카탈로그 캐시 무효화 여부를 결정할 때 사용. 변경 메서드가 호출되면 결과 해시도 바뀜.

`AssetRow` 에 `analysis_error: str | None` 필드 추가 (스토어 select 컬럼도 추가).

데이터클래스 신설(같은 파일에 두거나 `models.py` 분리는 plan 작성 시점 임의 — 같은 파일이 검색·이해 단순):

```python
@dataclass(frozen=True)
class SpriteMeta:
    width: int
    height: int
    has_alpha: bool
    is_pixel_art: bool
    dominant_colors: list[str]  # ["#aabbcc", ...]
    frame_w: int | None = None
    frame_h: int | None = None
    frame_count: int | None = None
    animation_tags: list[str] | None = None  # M5 가 채움. M2 는 None.

@dataclass(frozen=True)
class SoundMeta:
    duration_ms: int
    sample_rate: int
    channels: int
    loudness_db: float | None
    bpm: float | None
    category: str | None
    loopable: bool | None
    instruments: list[str] | None     # 화이트리스트 enum (sound_instrument 축)
    tempo: str | None                  # sound_tempo 축
    intensity: str | None              # sound_intensity 축
    genre: str | None                  # sound_genre 축, bgm/jingle/cinematic 일 때만
    voice_type: str | None             # sound_voice_type 축, voice 일 때만
    audio_path_used: str               # 'native' | 'spectrogram' | 'heuristic'

@dataclass(frozen=True)
class LabelScore:
    axis: str
    label: str
    score: float
    source: str  # 'gemma' | 'clip' | 'user'
    weight: str | None = None
```

### 3.2 `core/labels.py` — 시드 + `LabelRegistry`

**라벨 어휘 단일 출처는 `labels` 테이블**이고, `core/labels.py` 의 `SEED_LABELS` 는 부팅 시점에 **빈 DB 를 한 번 채우는 시드**다. 이후 사용자가 GUI(`ui/labels_admin.py`) 로 라벨을 추가/비활성화하면 그 변경은 즉시 다음 분석부터 반영된다.

시드는 **(label, description) 튜플 리스트** 로 박는다. description 은 영어 한 문장(≤ 15단어)이며, 라벨이 무엇을 의미하는지 명확히 적는다. 이 description 은:

1. **DB `labels.description` 컬럼에 저장** — `LabelRegistry.bootstrap()` 이 시드 적재 시 함께 INSERT.
2. **`assets_fts.searchable_text` 에 색인** — 라벨이 붙은 에셋의 검색 가능 텍스트에 라벨 description 도 추가 → 자연어 쿼리가 라벨 의미와 직접 매칭.
3. **M3 의 MCP 메타 도구(`describe_label`/`list_labels(with_description=true)`) 응답** — Claude Code 가 사용자 자연어 쿼리를 라벨로 풀어낼 때 참조.

```python
# 시드 — v1 시작 시 한 번 적재. 변경은 사용자/관리자가 GUI 로.
# 24축 ≈ 316개. 메모리 project_label_scoring_clip_inclusion.md 의 "목표 100~300개" 범위 살짝 초과(의도).
# 분류 기준:
#   * 시각 14축 (CLIP 점수 대상): category/style/mood/palette/color/view/material/lighting
#                                  /time_of_day/weather/theme/size_hint/domain/animation
#   * 사운드 전용 10축 (Gemma 만): sound_category/sound_mood/sound_timbre/sound_environment
#                                   /sound_instrument/sound_tempo/sound_intensity/sound_use
#                                   /sound_genre/sound_voice_type
# 모든 시드 라벨은 영어 description 한 줄(≤ 15 단어) 동봉. 사용자 추가 라벨은 description NULL 로 시작.
SEED_LABELS: dict[str, list[tuple[str, str]]] = {
    # ── 시각: 무엇/누구 ──────────────────────────────────────────────
    "category": [
        ("character",   "Animate or anthropomorphic entity such as a hero, enemy, or NPC."),
        ("creature",    "Non-humanoid living being: monster, animal, beast, alien."),
        ("tile",        "Repeatable terrain or floor block used for level construction."),
        ("background",  "Backdrop or scenery image not meant for direct interaction."),
        ("platform",    "Standable surface piece for platformer or jump-puzzle levels."),
        ("ui",          "User-interface graphic: button, panel, frame, HUD element."),
        ("icon",        "Small symbolic graphic representing a stat, item, or action."),
        ("effect",      "Visual effect such as explosion, particle, glow, or smoke."),
        ("projectile",  "Travelling object like bullet, arrow, magic bolt."),
        ("prop",        "Static decorative object placed inside a scene."),
        ("item",        "Pickup or inventory object: potion, coin, key, gem."),
        ("vehicle",     "Mode of transport: car, ship, mount, spaceship."),
        ("machine",     "Mechanical device or robot, often technological."),
        ("building",    "Architectural structure: house, tower, fortress."),
        ("furniture",   "Indoor furnishing: chair, table, bed, shelf."),
        ("plant",       "Vegetation: tree, bush, flower, grass."),
        ("terrain",     "Large-scale ground feature: hill, cliff, beach."),
        ("weapon",      "Tool used to attack or defend, melee or ranged."),
        ("food",        "Edible item or consumable resource."),
        ("portrait",    "Bust or headshot artwork of a character."),
        ("decoration",  "Ornamental detail with no gameplay function."),
        ("other",       "Falls outside the listed categories; see description."),
    ],  # 22

    # ── 시각: 어떻게(스타일) ────────────────────────────────────────
    "style": [
        ("pixel_art",     "Low-resolution sprite art with visible square pixels and limited palette."),
        ("vector_flat",   "Crisp flat shapes drawn with vector tools, no gradients."),
        ("hand_drawn",    "Artwork showing visible pencil, ink, or brush strokes."),
        ("painterly",     "Loose painted brushwork with soft edges and color blending."),
        ("sketch",        "Rough line drawing, often monochrome and unfinished."),
        ("anime",         "Japanese animation style with cel shading and large eyes."),
        ("comic",         "Western comic-book ink-and-color style with bold outlines."),
        ("cel_shaded",    "3D rendering with hard shading bands mimicking 2D animation."),
        ("3d_render",     "Image rendered from a 3D model with realistic shading."),
        ("low_poly",      "3D art with deliberately low polygon counts and flat facets."),
        ("voxel",         "3D art built from cubic voxels, similar to Minecraft."),
        ("photo",         "Photographic or photo-realistic imagery."),
        ("retro_8bit",    "Very limited palette evoking 8-bit consoles."),
        ("isometric_2d",  "2D art drawn from a fixed 30-degree isometric angle."),
    ],  # 14

    # ── 시각: 분위기 ────────────────────────────────────────────────
    "mood": [
        ("heroic",       "Bold, courageous, larger-than-life energy."),
        ("epic",         "Grand-scale, sweeping, momentous feel."),
        ("triumphant",   "Conveys victory or successful achievement."),
        ("hopeful",      "Optimistic, looking forward to a brighter outcome."),
        ("wholesome",    "Warm and family-friendly, comforting."),
        ("cute",         "Adorable and endearing, often round shapes and pastels."),
        ("playful",      "Light-hearted and fun, inviting interaction."),
        ("comic_relief", "Humorous or absurd, breaking tension."),
        ("romantic",     "Tender, affectionate, love-themed."),
        ("serious",      "Sober, grounded, without humor."),
        ("intense",      "Highly charged emotion or action."),
        ("tense",        "Suspenseful or anxious atmosphere."),
        ("dramatic",     "Theatrical, high-contrast emotional weight."),
        ("chaotic",      "Disorderly or frenetic energy."),
        ("mysterious",   "Hidden, unexplained, intriguing."),
        ("creepy",       "Unsettling, eerie, slightly horror-adjacent."),
        ("dark",         "Bleak, ominous, low-light atmosphere."),
        ("melancholic",  "Sad and reflective, gentle sorrow."),
        ("sad",          "Plainly downcast or sorrowful."),
        ("calm",         "Steady and unhurried, relaxing."),
        ("peaceful",     "Serene and conflict-free."),
        ("nostalgic",    "Evokes memory of past eras or childhood."),
    ],  # 22

    # ── 시각: 팔레트 톤 ─────────────────────────────────────────────
    "palette": [
        ("warm",         "Dominantly reds, oranges, yellows."),
        ("cool",         "Dominantly blues, greens, purples."),
        ("neutral",      "Balanced or grayscale-leaning palette."),
        ("monochrome",   "Single hue plus black/white variations."),
        ("vibrant",      "Highly saturated, energetic colors."),
        ("saturated",    "Rich color intensity throughout."),
        ("muted",        "Subdued, low-saturation palette."),
        ("desaturated",  "Almost grayscale with slight color tint."),
        ("dark",         "Overall low-luminance palette."),
        ("light",        "Overall high-luminance palette."),
        ("pastel",       "Soft, light, slightly washed-out tones."),
        ("earthy",       "Browns, tans, ochres, forest greens."),
    ],  # 12

    # ── 시각: 도미넌트 컬러 ─────────────────────────────────────────
    "color": [
        ("red_palette",     "Red is the dominant hue."),
        ("blue_palette",    "Blue is the dominant hue."),
        ("green_palette",   "Green is the dominant hue."),
        ("yellow_palette",  "Yellow is the dominant hue."),
        ("purple_palette",  "Purple/violet dominates."),
        ("orange_palette",  "Orange dominates."),
        ("pink_palette",    "Pink or magenta dominates."),
        ("teal_palette",    "Teal or cyan dominates."),
        ("crimson_palette", "Deep dark red dominates."),
        ("gold_palette",    "Metallic gold/yellow dominates."),
        ("silver_palette",  "Metallic silver/gray dominates."),
        ("black_palette",   "Black is dominant."),
        ("white_palette",   "White is dominant."),
        ("gray_palette",    "Neutral grays dominate."),
        ("earth_palette",   "Browns, ochres, and natural tones dominate."),
        ("sepia_palette",   "Warm brown-tinted monochrome."),
    ],  # 16

    # ── 시각: 시점 ─────────────────────────────────────────────────
    "view": [
        ("side_view",      "Viewed from the side, classic platformer angle."),
        ("top_down",       "Looking straight down from above."),
        ("isometric",      "Fixed 30-degree axonometric angle."),
        ("front_view",     "Facing the viewer head-on."),
        ("back_view",      "Subject's back faces the viewer."),
        ("three_quarter",  "Slightly angled view between front and side."),
        ("overhead",       "Bird's-eye perspective with slight angle."),
        ("perspective",    "True perspective projection with vanishing points."),
        ("orthographic",   "Parallel projection without perspective foreshortening."),
    ],  # 9

    # ── 시각: 재질 ─────────────────────────────────────────────────
    "material": [
        ("wood",    "Wood grain or planks visible."),
        ("metal",   "Reflective or matte metallic surface."),
        ("stone",   "Stone or rock texture."),
        ("cloth",   "Woven fabric, cloth, or tapestry."),
        ("leather", "Tanned hide or leather surface."),
        ("glass",   "Transparent or translucent glass."),
        ("water",   "Liquid water, lake, sea, or splash."),
        ("fire",    "Flame, ember, or burning element."),
        ("ice",     "Frozen surface, snow, or crystal."),
        ("organic", "Living tissue, plant matter, or flesh."),
        ("paper",   "Paper, parchment, or scroll."),
        ("plastic", "Synthetic glossy plastic surface."),
    ],  # 12

    # ── 시각: 조명 ─────────────────────────────────────────────────
    "lighting": [
        ("bright",     "Brightly and evenly lit scene."),
        ("dim",        "Subdued or low-intensity lighting."),
        ("neon",       "Glowing neon or fluorescent light sources."),
        ("candlelit",  "Warm flickering candle or torch light."),
        ("sunlit",     "Strong directional sunlight."),
        ("moonlit",    "Cool, soft moonlight."),
        ("shadowy",    "Heavy shadows, high contrast, low-key lighting."),
    ],  # 7

    # ── 시각: 시간대 ───────────────────────────────────────────────
    "time_of_day": [
        ("dawn",         "Just before sunrise, soft cool light."),
        ("day",          "Bright midday lighting."),
        ("dusk",         "Twilight after sunset, warm orange sky."),
        ("night",        "After dark, cool tones."),
        ("golden_hour",  "Warm-tinted hour just after sunrise or before sunset."),
    ],  # 5

    # ── 시각: 날씨 ─────────────────────────────────────────────────
    "weather": [
        ("clear",   "No precipitation, calm sky."),
        ("rainy",   "Active rainfall visible."),
        ("snowy",   "Snow falling or accumulated."),
        ("foggy",   "Heavy fog or mist reducing visibility."),
        ("stormy",  "Storm clouds, lightning, heavy weather."),
        ("sunny",   "Strong sun and clear sky."),
        ("windy",   "Visible wind effects on hair, cloth, foliage."),
    ],  # 7

    # ── 시각: 테마/배경 (장소·환경) ─────────────────────────────────
    "theme": [
        ("dungeon",     "Subterranean stone corridors, traps, treasure."),
        ("forest",      "Wooded outdoor environment."),
        ("ocean",       "Open sea or coastal water scene."),
        ("desert",      "Sandy arid landscape."),
        ("mountain",    "Rocky peaks or alpine terrain."),
        ("castle",      "Medieval fortified architecture."),
        ("village",     "Small rural human settlement."),
        ("cave",        "Natural underground cavern."),
        ("space",       "Outer space, stars, planets."),
        ("underwater",  "Below the water surface."),
        ("jungle",      "Dense tropical rainforest."),
        ("swamp",       "Wetland with murky water and twisted plants."),
    ],  # 12

    # ── 시각: 크기 힌트 ────────────────────────────────────────────
    "size_hint": [
        ("tiny",    "Extremely small asset, e.g. 8x8 to 16x16 sprite."),
        ("small",   "Compact asset, e.g. 32x32 sprite."),
        ("medium",  "Standard size, e.g. 64x64 to 128x128."),
        ("large",   "Big asset, e.g. boss sprite or 256+ px."),
        ("huge",    "Full-screen or backdrop-scale image."),
    ],  # 5

    # ── 의미: 장르/도메인 ──────────────────────────────────────────
    "domain": [
        ("fantasy",              "Magic, knights, dragons, classic high-fantasy tropes."),
        ("sci_fi",               "Futuristic technology, space, robotics."),
        ("cyberpunk",            "High tech meets low life, neon megacity dystopia."),
        ("steampunk",            "Victorian-era brass and steam-powered machinery."),
        ("modern",               "Contemporary real-world setting."),
        ("medieval",             "European Middle Ages aesthetics."),
        ("victorian",            "19th-century European elegance."),
        ("western",              "American old-west cowboy setting."),
        ("post_apocalyptic",     "Ruined civilization after a catastrophe."),
        ("mythological",         "Ancient myths and pantheons (Greek, Norse, etc.)."),
        ("prehistoric",          "Stone age, dinosaurs, primal humans."),
        ("futuristic",           "Near-future advanced civilization."),
        ("magical",              "Magic-saturated scene regardless of era."),
        ("military",             "Modern or near-future military equipment."),
        ("urban",                "Cityscape, streets, urban infrastructure."),
        ("rural",                "Countryside, farmland, small towns."),
        ("casual",               "Bright, simple casual-game aesthetic."),
        ("racing",               "Vehicles and racetrack imagery."),
        ("puzzle",               "Abstract block, gem, or board-game pieces."),
        ("horror",               "Frightening, gory, or supernatural-horror imagery."),
        ("japanese_traditional", "Edo-period Japan, kimono, samurai, sumi-e."),
        ("mecha",                "Giant piloted humanoid robots."),
    ],  # 22

    # ── 의미: 애니메이션 hint (DESIGN §4.2.2 시트 라벨 포함) ────────
    "animation": [
        ("idle",    "Resting or breathing loop while not acting."),
        ("walk",    "Steady walking cycle."),
        ("run",     "Faster running cycle."),
        ("jump",    "Take-off and airborne frames."),
        ("attack",  "Strike, swing, or shoot action."),
        ("hurt",    "Take-damage reaction frames."),
        ("death",   "Defeated or dying animation."),
        ("cast",    "Spell-casting or ability activation."),
        ("crouch",  "Lowered defensive stance."),
        ("dodge",   "Quick evasive sidestep or roll."),
        ("block",   "Defensive block or parry."),
        ("climb",   "Climbing ladder or wall."),
        ("swim",    "Swimming locomotion."),
        ("fly",     "Flying or hovering."),
        ("sleep",   "Resting or unconscious."),
        ("other",   "Animation that does not match the listed actions."),
    ],  # 16

    # ── 사운드 전용 10축 (CLIP 점수 없음, Gemma 만) ─────────────────
    "sound_category": [
        ("sfx",          "Discrete sound effect such as hit, jump, or pickup."),
        ("bgm",          "Background music track."),
        ("voice",        "Spoken voice line or narration."),
        ("ui_sound",     "Interface sound: click, hover, confirm."),
        ("ambient",      "Looping environmental ambience or atmosphere bed."),
        ("jingle",       "Short musical motif under ~5s such as victory/level-up cue."),
        ("stinger",      "Brief musical hit used as transition or emphasis."),
        ("foley",        "Realistic everyday sound: footsteps, cloth, object handling."),
        ("narration",    "Story-telling voice over multiple sentences."),
        ("loop",         "Sound explicitly designed to loop seamlessly."),
        ("oneshot",      "Single non-looping playback intended to fire once."),
        ("cinematic",    "Cutscene-grade music or sound design segment."),
    ],  # 12

    "sound_mood": [
        ("energetic",   "Upbeat, high-energy."),
        ("calm",        "Relaxing, low-energy."),
        ("eerie",       "Unsettling and atmospheric."),
        ("triumphant",  "Victorious fanfare."),
        ("sad",         "Sorrowful or downcast."),
        ("suspenseful", "Builds tension and unease."),
        ("cheerful",    "Happy and bouncy."),
        ("dark",        "Ominous and brooding."),
        ("mysterious",  "Curious, unresolved."),
        ("intense",     "Driving and powerful."),
        ("peaceful",    "Tranquil and gentle."),
        ("dramatic",    "Sweeping emotional weight."),
        ("heroic",      "Bold, courageous, larger-than-life."),
        ("melancholic", "Reflective, quietly mournful."),
        ("romantic",    "Tender, affectionate."),
        ("comedic",     "Funny, slapstick, lighthearted."),
        ("epic",        "Grand, momentous, sweeping scale."),
        ("hopeful",     "Optimistic and forward-looking."),
        ("ominous",     "Threat-suggesting, foreboding."),
        ("playful",     "Light-hearted, mischievous."),
        ("nostalgic",   "Evokes memory of past eras."),
        ("aggressive",  "Hostile, attacking energy."),
    ],  # 22

    "sound_timbre": [
        ("bright",     "Crisp, high-frequency-rich tone."),
        ("dark",       "Low-frequency-rich, warm tone."),
        ("harsh",      "Rough, abrasive, distorted edge."),
        ("soft",       "Gentle, mellow texture."),
        ("metallic",   "Ringing metal quality."),
        ("organic",    "Natural acoustic source feel."),
        ("electronic", "Synthesized or electronic origin."),
        ("acoustic",   "Played on real acoustic instruments."),
        ("distorted",  "Heavily processed, clipped, or fuzzed."),
        ("clean",      "Unprocessed, dry signal."),
        ("warm",       "Rich low-mids, friendly tonal feel."),
        ("sharp",      "Pointed, cutting high frequencies."),
        ("gritty",     "Textured, dirty, lo-fi character."),
        ("hollow",     "Resonant with notch in mids, tube-like."),
        ("percussive", "Transient-dominant, drum-like."),
        ("watery",     "Wet, modulated, chorus/flange-like."),
    ],  # 16

    "sound_environment": [
        ("indoor",            "Small reverberant room or interior space."),
        ("outdoor",           "Open air, minimal reverb."),
        ("underwater",        "Muffled, low-pass-filtered underwater feel."),
        ("cave",              "Long deep reverberation."),
        ("hall",              "Large hall reverb, concert-hall scale."),
        ("forest",            "Outdoor woodland ambience with foliage."),
        ("city",              "Urban traffic and crowd noise feel."),
        ("space",             "Vacuum-like sparse, alien feel."),
        ("dungeon",           "Cold stone corridors with dripping echoes."),
        ("ocean",             "Open water, waves, gulls."),
        ("vehicle_interior",  "Inside a moving vehicle, engine bed."),
        ("sewer",             "Damp tunnels with metallic drips."),
        ("sky",               "Open air, wind, altitude."),
        ("tavern",            "Indoor public house, crowd chatter."),
    ],  # 14

    "sound_instrument": [
        ("piano",       "Acoustic or electric piano."),
        ("strings",     "Bowed string section: violins, violas, cellos."),
        ("brass",       "Brass section: trumpets, trombones, horns."),
        ("woodwinds",   "Wind instruments: flute, clarinet, oboe."),
        ("percussion",  "Tuned or untuned percussion broadly."),
        ("drums",       "Drum kit or rhythm percussion."),
        ("synth",       "Electronic synthesizer."),
        ("choir",       "Vocal ensemble singing wordless or text."),
        ("guitar",      "Acoustic or electric guitar."),
        ("bass",        "Bass guitar or upright bass."),
        ("organ",       "Pipe organ or electric organ."),
        ("harp",        "Concert harp or small harp."),
        ("bell",        "Tuned bell or chime."),
        ("flute",       "Flute or recorder family solo."),
        ("vocal_solo",  "Single sung voice (wordless or lyrical)."),
        ("orchestra",   "Full symphonic ensemble."),
    ],  # 16

    "sound_tempo": [
        ("very_slow",  "Below ~60 BPM, ballad or atmospheric pacing."),
        ("slow",       "Roughly 60-90 BPM."),
        ("medium",     "Roughly 90-120 BPM, walking pace."),
        ("fast",       "Roughly 120-150 BPM, action pace."),
        ("very_fast",  "Above ~150 BPM, frantic pace."),
        ("variable",   "Tempo shifts or has no fixed tempo."),
    ],  # 6

    "sound_intensity": [
        ("quiet",         "Whisper-level, easy to overlook."),
        ("soft",          "Low background level."),
        ("moderate",      "Comfortable foreground level."),
        ("loud",          "Attention-grabbing, prominent."),
        ("deafening",     "Overwhelming, full mix dominator."),
        ("swelling",      "Gradually builds in volume."),
        ("sudden_burst",  "Quick spike with sharp attack."),
    ],  # 7

    "sound_use": [
        ("action",          "Fits action gameplay segments."),
        ("exploration",     "Fits exploration or traversal."),
        ("combat",          "Fits combat encounters."),
        ("victory",         "Plays on player success."),
        ("defeat",          "Plays on player failure."),
        ("level_complete",  "Marks stage completion."),
        ("game_over",       "Marks game-over state."),
        ("menu",            "Plays in menu/title screens."),
        ("dialogue",        "Plays under or as dialogue line."),
        ("cutscene",        "Plays in cinematic cutscene."),
        ("transition",      "Marks scene/area transition."),
        ("item_pickup",     "Plays when collecting an item."),
        ("achievement",     "Plays on achievement unlock."),
        ("alert",           "Warning or notification cue."),
        ("ambience_loop",   "Steady background loop without melody."),
        ("hit_impact",      "Plays on hit or impact event."),
    ],  # 16

    "sound_genre": [
        ("orchestral",       "Symphonic acoustic ensemble style."),
        ("electronic",       "Broad electronic / EDM-adjacent."),
        ("rock",             "Guitar-driven rock idiom."),
        ("jazz",             "Jazz harmony and swing/swing-adjacent rhythm."),
        ("classical",        "European classical period style."),
        ("ambient_music",    "Atmospheric music without strong beat."),
        ("chiptune",         "Retro 8/16-bit console synth music."),
        ("folk",             "Traditional folk instrumentation."),
        ("hip_hop",          "Hip-hop beat and production."),
        ("world",            "Non-Western folk or world-fusion style."),
        ("lofi",             "Lo-fi hip-hop/beats aesthetic."),
        ("cinematic_score",  "Hollywood-style film-score idiom."),
        ("synthwave",        "Retro 80s-inspired synth music."),
        ("metal",            "Heavy metal subgenres."),
    ],  # 14

    "sound_voice_type": [
        ("male_adult",     "Adult male voice."),
        ("female_adult",   "Adult female voice."),
        ("male_child",     "Boy or young male voice."),
        ("female_child",   "Girl or young female voice."),
        ("elderly",        "Old-sounding voice regardless of gender."),
        ("narrator",       "Even, story-telling narrator delivery."),
        ("monster_growl",  "Non-human growling or roaring."),
        ("robot",          "Robotic or vocoded voice."),
        ("alien",          "Otherworldly stylized voice."),
        ("whisper",        "Whispered or breathy delivery."),
        ("shouting",       "Yelled or projected delivery."),
        ("singing",        "Sung rather than spoken."),
    ],  # 12
}
# 합계 약 316개. 24축(시각 14축 + 사운드 10축).
# CLIP 점수 대상은 사운드 10축 제외한 14축.
```

```python
class LabelRegistry:
    """DB(`labels` 테이블) 기반 동적 라벨 어휘 관리자.

    분석기/CLIP labeler/검색 위젯이 모두 이 객체를 통해서만 라벨 목록을 본다.
    즉 라벨 어휘의 단일 출처(single source of truth)는 메모리 캐시가 아니라 DB.
    """

    def __init__(self, store: Store) -> None: ...

    def bootstrap(self, seed: dict[str, list[str]] = SEED_LABELS) -> int:
        """빈 `labels` 테이블에만 시드 INSERT. 이후 호출은 no-op."""

    def list_labels(self, axis: str | None = None, *, enabled_only: bool = True) -> list[str]:
        """순서는 (axis ASC, label ASC) 로 결정적. 테스트 안정성용."""

    def list_axes(self) -> list[str]: ...

    def add_label(self, axis: str, label: str) -> tuple[int, bool]:
        """반환: (id, was_new). 동일 (axis,label) 가 있으면 활성화로 폴백 후 (id, False).
        label 토큰은 ASCII lowercase + underscore 강제 (영어 enum 어휘 공간 통일)."""

    def set_enabled(self, axis: str, label: str, enabled: bool) -> None: ...

    def invalidate(self) -> None:
        """in-memory 캐시 비움. add_label/set_enabled 가 자동 호출하지만,
        외부 트랜잭션이 끝나고 수동 호출이 필요할 때(주로 테스트) 노출."""
```

내부 캐시: `_axis_to_labels: dict[str, list[str]] | None`. `list_labels` 첫 호출 시 `SELECT axis, label FROM labels WHERE enabled = 1 ORDER BY axis, label` 로 채우고, 변경 메서드가 None 으로 무효화. 분석 큐가 분석 직전 `list_labels` 를 한 번 호출하므로 캐시 hit 율 높다.

**부팅 흐름** (app.py): `store.initialize()` → `registry = LabelRegistry(store)` → `registry.bootstrap()`. 시드는 한 번만 들어가고, 이후 부팅에선 0행.

**라벨 토큰 검증**: `add_label` 은 `^[a-z][a-z0-9_]{0,31}$` 정규식 강제. 위반 시 `LabelValidationError`. 한글·공백·대문자 거부. 이는 검색·임베딩·CLIP 텍스트 인코딩의 어휘 공간을 영어 enum 으로 통일하기 위함(`project_output_language_strategy.md` 결정).

**라벨 비활성화의 의미**:
- 비활성 라벨은 `LabelRegistry.list_labels(enabled_only=True)` 에서 제외 → 새 분석에서 사용 안 됨.
- 이미 `asset_labels` 에 저장된 행은 **그대로 보존** (과거 분석 결과 손실 방지). 검색·필터에서도 그대로 보이지만, 사용자가 라벨 추가/제거 후 일관성을 원하면 GUI 의 "전체 재분석" 버튼(M3 의 `request_rescan` 백엔드, M2 에서는 단순 enqueue) 으로 다시 분석할 수 있다.
- CLIP 캐시(`clip_label_cache`) 의 비활성 라벨 행도 보존 (재활성화 시 즉시 사용 가능).

**분석기 사용 패턴**:
- `SpriteAnalyzer.analyze` 가 Gemma 프롬프트 생성 시 `registry.list_labels('category')` 를 enum 값으로 사용 → 동적 어휘. 스프라이트는 14개 시각 축 + 의미 축(domain/animation) = 약 200개 어휘.
- `ClipLabeler.score_image` 도 `labels=registry.list_labels(axis)` 로 14축 활성 라벨을 모두 받음(사운드 4축 제외).
- **사운드 라벨은 사운드 10축 모두 사용** — `sound_category`, `sound_mood`, `sound_timbre`, `sound_environment`, `sound_instrument`, `sound_tempo`, `sound_intensity`, `sound_use`, `sound_genre`, `sound_voice_type`. 시각 축(`category`/`style`/`color`/`view`/`material`/...)은 무시(축 자체를 안 보냄). 사운드 시스템 프롬프트의 enum 슬롯은 사운드 10축 만 채운다. `voice_type` 은 `category=voice` 일 때만, `genre` 는 `category` 가 음악 계열일 때만 채워지도록 Pydantic 검증.

**Gemma 응답이 화이트리스트 밖**일 때(예: 사용자가 `low_poly` 비활성화했는데 모델이 그걸 반환): 분석기는 `other` 강등(`category`/`animation`) 또는 라벨 누락(`mood`/`style` 등) 처리. 시스템 프롬프트의 enum 목록도 매 호출 시 `registry.list_labels(axis)` 로 동적 생성하므로 비활성 라벨은 애초에 모델에게 안 보임.

**테스트 결정성**: `list_labels` 정렬 보장 + `bootstrap` idempotent + `add_label` 의 race(동일 라벨 동시 추가)는 `UNIQUE` 제약으로 DB 가 흡수 → 두 번째 호출은 `was_new=False`.

### 3.3 `core/ollama_client.py` — HTTP 백엔드

설계는 메모리 `project_m2_analysis_backend.md` + `project_ollama_multimodal_api_shape.md` 그대로.

```python
@dataclass(frozen=True)
class ChatMessage:
    role: str              # 'system' | 'user'
    content: str
    images_b64: list[str] = field(default_factory=list)
    audio_b64: list[tuple[str, str]] = field(default_factory=list)  # (data, mime) e.g. ('AAA...', 'audio/wav')

class OllamaClient:
    def __init__(self, *, base_url: str, model: str,
                 timeout_seconds: float, max_retries: int) -> None: ...
    def chat(self, messages: list[ChatMessage], *, force_json: bool = True,
             num_ctx: int = 8000) -> dict: ...
    def embed(self, text: str, *, model: str | None = None) -> list[float]: ...
```

`chat()` 흐름:

1. OpenAI 호환 `POST {base_url}/v1/chat/completions` 시도 — 이미지: `image_url.url = "data:image/png;base64,..."`, 오디오: `input_audio.{data, format}` (OpenAI Realtime 스키마, LM Studio 이식 대비).
2. 응답이 4xx/5xx 또는 connect error 면 Ollama 네이티브 `POST {base_url}/api/chat` 폴백 — 이미지·오디오 모두 `messages[*].images` 단일 배열에 base64 만 넣음(메모리 실측 형식). `format: "json"` + `stream: false` + `options: {num_ctx}`.
3. 양 경로 모두 응답 본문에서 `choices[0].message.content` (OpenAI) 또는 `message.content` (네이티브) 를 추출, `json.loads`.
4. `force_json` 이면 JSON 파싱 실패 시 지수 백오프 재시도(`max_retries`).
5. 최종 실패는 `OllamaError(stage="chat", path="openai" | "native", cause=...)`.

`embed()` — `POST {base_url}/api/embeddings` (Ollama 네이티브). 응답 `embedding: [float, ...]` 반환. OpenAI 호환 `/v1/embeddings` 는 1차 시도, 실패 시 네이티브 폴백.

base64 헬퍼: `encode_image(path) -> str`, `encode_audio_clip(samples, sample_rate) -> str` — soundfile 로 WAV 직렬화 후 base64. 16kHz mono 가정.

### 3.4 `core/embedding.py` — 검색용 임베딩 인코더

```python
class EmbeddingEncoder:
    def __init__(self, client: OllamaClient, model: str = "nomic-embed-text") -> None: ...
    def encode_text(self, text: str) -> tuple[bytes, int]:
        """반환: (float32 LE 직렬화 bytes, dim). dim 은 첫 호출 시 결정."""
```

`bytes` 직렬화는 `numpy.asarray(vec, dtype=np.float32).tobytes()`. 디코딩 helper(`decode_vector(blob, dim) -> np.ndarray`)도 같이 둔다 — M3 검색이 사용. 모델·dim 은 BLOB 메타로 같이 저장(`save_embedding`).

### 3.5 `core/clip_labeler.py` — CLIP zero-shot 라벨 스코어러

설계는 메모리 `project_label_scoring_clip_inclusion.md` 결정 그대로. `open_clip_torch` 사용, 모델 기본 `ViT-B-32`/`openai` (≈ 600 MB).

```python
class ClipBackend(Protocol):
    """테스트에서 fake 로 갈아끼울 수 있게 인터페이스 분리."""
    model_id: str  # e.g. 'ViT-B-32:openai'
    dim: int
    def encode_text(self, texts: list[str]) -> np.ndarray: ...
    def encode_image(self, image_path: Path) -> np.ndarray: ...

class OpenClipBackend(ClipBackend):
    def __init__(self, model: str = "ViT-B-32", pretrained: str = "openai",
                 cache_dir: Path | None = None) -> None: ...
    # open_clip.create_model_and_transforms(...)
    # 첫 호출 시 cache_dir 에 가중치 다운로드. cache_dir 기본은 paths.cache_dir / "clip".

class ClipLabeler:
    def __init__(self, backend: ClipBackend, store: Store,
                 registry: LabelRegistry) -> None: ...
    def warmup(self, labels: list[str] | None = None) -> None:
        """라벨 텍스트 임베딩을 캐시(없는 것만 계산).
        labels 가 None 이면 registry 에서 CLIP 점수 대상 14축(category/style/mood/palette
        /color/view/material/lighting/time_of_day/weather/theme/size_hint/domain/animation)
        활성 라벨만 자동 수집. 사운드 전용 4축(sound_*)은 제외."""
    def score_image(self, image_path: Path,
                    labels: list[str] | None = None) -> dict[str, float]:
        """반환: { label: cosine 0..1 }. 음수 코사인은 0 으로 클램프.
        labels 가 None 이면 registry 에서 자동 수집."""
```

`score_image` 안에서:
1. 이미지 인코딩 1회 (긴 변 224px 리사이즈는 backend transform 이 담당).
2. `clip_label_cache` 에 없는 라벨만 모아 `encode_text` 1배치 → 캐시 저장.
3. 라벨 BLOB 들을 모아 `np.stack` → 코사인 = `(L @ img) / (||L|| ||img||)` → `dict` 반환.

테스트 전략:
- 단위 테스트는 `FakeBackend` 를 만들어 결정적 임베딩(예: 라벨 문자열 sha256 → 일정 차원 fake 벡터) 사용. 모델 다운로드 없음.
- 실모델은 `pytest -m clip_integration` 마크 옵트인. 기본 CI 에선 스킵.

GPU 사용은 v1 에서 강제하지 않음 — `OpenClipBackend` 가 `torch.cuda.is_available()` 시 자동으로 cuda 로 옮기되, 분석 큐 동시성 1 정책으로 GPU 메모리 경합 회피. CPU 추론 시 한 이미지당 ≈ 200ms 예상(ViT-B/32, M4 칩).

### 3.6 `core/analyzer/base.py`

`AnalyzerResult` — 분석기들이 동일 출력 형식으로 store 에 넘기는 데이터 컨테이너.

```python
@dataclass(frozen=True)
class SearchableTexts:
    """FTS5 와 임베딩 인코더가 보는 검색 텍스트는 분리한다.

    * for_fts — 길어도 좋다. 라벨 토큰·라벨 description·에셋 description·파일경로·기술 메타가 모두 들어가
      BM25 키워드 매칭이 풍부해진다. FTS5 는 길이 페널티가 거의 없음.
    * for_embed — nomic-embed-text 의 8K 토큰 한계 안에서 *의미 압축* 한 짧은 텍스트. 핵심 라벨(상위 N)
      + 라벨 description(상위 N) + 에셋 description 만 포함. 보통 ≤ 256 토큰.
    """
    for_fts: str
    for_embed: str


@dataclass(frozen=True)
class AnalyzerResult:
    kind: str                        # 'sprite' | 'sound' (시트는 M5)
    state: str                       # 'ok' | 'partial'
    error: str | None
    sprite_meta: SpriteMeta | None
    sound_meta: SoundMeta | None
    labels: list[LabelScore]
    searchable: SearchableTexts
    embedding_vector: bytes
    embedding_dim: int
    embedding_model: str
    description: str                 # 호출 언어 (기본 ko)

@dataclass(frozen=True)
class AnalyzerInput:
    asset_id: int
    pack_id: int
    abs_path: Path
    rel_path: str
    language: str = "ko"
```

`ResponseModel` Pydantic 베이스 (스프라이트·사운드 별로 상속) — `category`/`style`/`mood`/`palette`/`animation_hint` 은 `Literal[...]` 화이트리스트 강제. `extra="forbid"`. `description`/`subject`/`transcript` 는 `str`(언어 무관). `confidence: float = Field(ge=0, le=1)`.

화이트리스트 위반 시 `pydantic.ValidationError` → 재시도. 3회 실패 시 `state='failed'`.

### 3.7 `core/analyzer/sprite.py`

```python
class SpriteAnalyzer:
    def __init__(self, ollama: OllamaClient, clip: ClipLabeler | None,
                 embedder: EmbeddingEncoder, registry: LabelRegistry,
                 *, max_long_edge: int = 768) -> None: ...
    def analyze(self, inp: AnalyzerInput) -> AnalyzerResult: ...
```

`analyze()` 흐름:

1. **기술 특성**: Pillow 로 이미지 열기 → `width`/`height`/`has_alpha`. `numpy` 로 다운샘플 후 픽셀아트 판정(인접 픽셀 분산 임계 + 색상 유니크 카운트 ≤ 64). 도미넌트 컬러 5개는 K-Means(`sklearn` 없이 numpy 만으로 — 간단한 k-means++ 8 iter; 작은 이미지라 100ms 이내).
2. **이미지 리샘플**: 긴 변 768px (LANCZOS). 결과를 PNG 로 메모리 인코딩 → base64.
3. **Gemma 호출**: `OllamaClient.chat` 에 시스템 프롬프트(언어 인자 적용) + base64 이미지 1장. Pydantic 으로 검증.
4. **CLIP 점수**: `clip is not None and config.clip_enable` 이면 원본 파일을 그대로(또는 768 리사이즈본) `score_image(path, labels=LABEL_WHITELIST['style'] + ['palette'] + ['color'] + ['view'])` 호출. CLIP 비활성/실패 시 빈 dict (Gemma 라벨만 사용).
5. **라벨 통합**: Gemma 의 정규 enum 응답(예: `style: "pixel_art"`) 을 `LabelScore(axis='style', label='pixel_art', source='gemma', score=confidence, weight='primary')` 로 변환. `mood`/`palette`/`animation_hint` 는 다중이라 각각 primary/secondary/tertiary 배치(상위 1=primary, 2=secondary, 3+=tertiary). CLIP 점수는 같은 라벨에 대해 `source='clip', score=clip_score, weight=None` 으로 추가.
6. **검색 텍스트 빌드** — `SearchableTexts(for_fts=..., for_embed=...)`. 빌더는 `core/searchable.py` 의 `build_searchable(...)` 헬퍼(분석기 공유).
   - `for_fts` 예: `"path:kenney_hero/idle_03.png category:character style:pixel_art mood:heroic mood:serious palette:warm color:red_palette label:pixel_art label:heroic label:serious 'Low-resolution sprite art with visible square pixels...' 'Bold, courageous, larger-than-life energy.' '검을 든 중세 기사 캐릭터의 측면 도트 스프라이트' 32x32 alpha"` — 라벨 토큰에 `label:` prefix 를 붙여 FTS 쿼리가 라벨 단위로 가능하게(예: `assets_fts MATCH 'label:pixel_art AND label:heroic'`).
   - `for_embed` 예: `"character pixel_art heroic warm. Low-resolution sprite art with visible square pixels and limited palette. Bold, courageous, larger-than-life energy. 검을 든 중세 기사 캐릭터의 측면 도트 스프라이트."` — 256 토큰 안에서 의미 압축. 상위 라벨 5개 + 그 description + 에셋 description.
7. **임베딩**: `EmbeddingEncoder.encode_text(searchable.for_embed)`. FTS 텍스트는 임베딩에 안 씀.

시스템 프롬프트 템플릿(언어 변수 한 번에 반영, `description` 만 호출 언어). enum 목록은 매 호출 시 `registry.list_labels(axis)` 로 동적 생성한다 — 사용자가 라벨을 비활성화하면 그 토큰은 모델에게 보이지 않는다.

```
You are a game asset metadata generator. Respond ONLY with valid JSON, no prose.

JSON schema (strict):
- category: one of [{category_enum}]
- style: one of [{style_enum}]
- mood: array (1..3) from [{mood_enum}]
- palette: array (1..2) from [{palette_enum}]
- animation_hint: array (0..4) from [{animation_enum}]
- subject: short noun phrase describing the main subject. Write in {language}.
- description: one sentence (<= 30 words). Write in {language}.
- confidence: float 0..1

If unsure of an enum, pick "other". Never emit free-form enum values.
```

`{category_enum}` 같은 슬롯은 `", ".join(registry.list_labels("category"))` 로 채운다. `{language}` 는 `"ko"` 또는 `"en"`. 메모리 결정에 따라 v1 기본 `ko`.

### 3.8 `core/analyzer/sound.py`

```python
class SoundAnalyzer:
    def __init__(self, ollama: OllamaClient, embedder: EmbeddingEncoder,
                 *, max_clip_seconds: int = 30,
                 chunk_strategy: str = "smart",
                 spectrogram_cache_dir: Path) -> None: ...
    def analyze(self, inp: AnalyzerInput) -> AnalyzerResult: ...
```

`analyze()` 단계:

1. **기술 특성** — librosa.load 로 모노 다운믹스 + 16 kHz 리샘플. `duration_ms`, `channels` (원본), `sample_rate` (원본), `loudness_db` = RMS dB, `bpm` = `librosa.beat.beat_track` (안 잡히면 None). soundfile 로 원본 사양만 별도 조회(다운믹스 전).
2. **클립 선택** — 30s 이하면 그대로. 초과면 `chunk_strategy`:
   - `"smart"` (기본): 시작 5s + 중앙 15s + 끝 5s 세 청크, 각각 분석 후 머지(label union, mood/instruments 합집합, category 다수결).
   - `"first"`: 앞 30s.
   - `"rms_peak"`: 가장 큰 RMS 윈도우 30s.
3. **1차 — 네이티브 오디오 호출** — 각 청크를 WAV 16kHz mono 로 인코딩 → base64. `OllamaClient.chat` 에 메시지 1개(`audio_b64`). 30s wall-clock 타임아웃(`analysis_timeout_seconds`). 응답 Pydantic 검증. `audio_path_used='native'`.
4. **2차 — 멜 스펙트로그램 비전 폴백** — 1차가 타임아웃/GGML crash/JSON 실패시. librosa 로 멜 스펙트로그램(mels=128, hop=512) → matplotlib (Agg 백엔드) 로 PNG 저장 (`spectrogram_cache_dir / f"{asset_id}.png"`). 그 PNG 를 이미지 입력으로 다시 chat. 같은 Pydantic 스키마. `audio_path_used='spectrogram'`.
5. **3차 — 휴리스틱 폴백** — 둘 다 실패. 파일명/폴더명에 `bgm|loop|music` 포함 → `category='bgm'`; `voice|vo|line` → `voice`; `ui|click|hover` → `ui_sound`; 길이 ≥ 10s → `bgm` 후보; 그 외 `sfx`. `mood`/`instruments` 는 빈 리스트. `audio_path_used='heuristic'`. `state='partial'`.
6. **검색 텍스트 + 임베딩** — 스프라이트와 동일 방식으로 `build_searchable(...)` 호출.
   - `for_fts` 예: `"path:retro_synth/cave_loop.ogg sound_category:bgm sound_mood:dark sound_timbre:electronic sound_environment:cave label:bgm label:dark label:electronic 'Background music track.' 'Ominous and brooding.' '동굴 안에서 울리는 어둡고 신비로운 신스 루프 BGM' duration:47s loopable bpm:90"` (`bpm:90` 같은 수치도 키 prefix 와 결합해 FTS 쿼리에서 활용 가능).
   - `for_embed` 는 핵심 라벨 + description 만 — 256 토큰 안에서 의미 압축.

사운드 시스템 프롬프트(언어 변수 동일 적용, enum 은 `registry` 에서 동적 주입, 10축 모두 노출):

```
You are a game audio metadata generator. Respond ONLY with valid JSON.

Schema:
- category: one of [{sound_category_enum}]
- mood: array (0..3) from [{sound_mood_enum}]
- timbre: array (0..3) from [{sound_timbre_enum}]
- environment: array (0..2) from [{sound_environment_enum}]
- instruments: array (0..4) from [{sound_instrument_enum}]
- tempo: one of [{sound_tempo_enum}] or null if not applicable (e.g. ambient)
- intensity: one of [{sound_intensity_enum}]
- use: array (0..3) from [{sound_use_enum}]
- genre: one of [{sound_genre_enum}] or null if not music
- voice_type: one of [{sound_voice_type_enum}] or null if not voice
- loopable: boolean
- transcript: 발화 내용 in {language} if category=voice, else ""
- description: one sentence (<= 30 words) in {language}.
- confidence: float 0..1

Rules:
- If category != "voice", set voice_type to null.
- If category != "bgm" and category != "jingle" and category != "cinematic", set genre to null.
- Pick at most one label per single-value field. Multi-value fields stay within the listed count bounds.
```

10축 모두 화이트리스트 강제(Pydantic Literal). `instruments` 도 이제 enum(이전엔 자유 토큰). `tempo`/`genre`/`voice_type` 은 `Optional[Literal[...]]` 로 null 허용 — voice 가 아닌데 voice_type 채워 보내면 거부 → 재시도. 3회 실패 시 해당 단일 필드만 None 으로 강등하고 `state='partial'`.

저장 단계:
- 각 enum 응답을 `LabelScore(axis='sound_<axis>', label=<value>, source='gemma', score=confidence, weight='primary')` 로 변환해 `asset_labels` 에 INSERT.
- 다중 필드(`mood`/`timbre`/`environment`/`use`/`instruments`)는 순서대로 `primary`/`secondary`/`tertiary`(4번째부터는 추가 INSERT 안 함).
- `sound_meta` 테이블에 기존 컬럼(`category`/`loopable`/`instruments`/`audio_path_used`) 외 새 컬럼 추가: `tempo TEXT`, `intensity TEXT`, `genre TEXT`, `voice_type TEXT`. 새 컬럼은 §3.1 `_M2_SCHEMA` 의 `sound_meta` CREATE 문에 함께 둔다.

`SoundAnalyzer` 시그니처도 `registry: LabelRegistry` 를 받는다.

### 3.9 `core/analysis_queue.py` — 분석 큐 워커

```python
@dataclass(frozen=True)
class AnalysisProgress:
    completed_in_session: int       # 이번 부팅 후 완료한 분석 수 (성공·실패 모두 포함)
    pending: int                    # 큐 + 워커 in-flight + DB pending 합계
    in_flight_path: str | None      # 현재 분석 중인 에셋 상대 경로
    eta_seconds: float | None       # None 이면 표본 부족(< 3개)
    avg_duration_seconds: float | None  # 최근 N개 평균


class AnalysisQueue(QObject):
    analysisFinished = Signal(int)              # asset_id
    progressChanged  = Signal(object)           # AnalysisProgress (immutable)

    def __init__(self, store: Store, sprite: SpriteAnalyzer, sound: SoundAnalyzer,
                 *, concurrency: int = 1, eta_window: int = 10,
                 clock: Callable[[], float] = time.monotonic) -> None: ...
    def enqueue_asset(self, asset_id: int) -> None: ...
    def enqueue_pack(self, pack_id: int) -> None:
        """팩의 pending 에셋 모두 enqueue."""
    def drain_pending(self) -> int:
        """부팅 시 호출. 반환은 enqueue 한 개수."""
    def progress(self) -> AnalysisProgress:
        """현재 진행 상태 스냅샷. UI/툴팁이 임의 시점에 호출 가능."""
    def start(self) -> None: ...
    def stop(self, timeout: float = 5.0) -> None: ...
```

내부:

- `concurrent.futures.ThreadPoolExecutor(max_workers=concurrency)` + `queue.Queue[int]` (asset_id).
- ETA 트래커: `_recent_durations: deque[float] = deque(maxlen=eta_window)` (기본 maxlen=10). 분석 시작/종료 시점을 주입된 `clock` 으로 측정 → 종료 시 duration 추가. 평균은 산술 평균(이상치 보호용 trim 은 v2 검토). 표본이 3개 미만이면 `eta_seconds=None` (불확실 표시).
- 워커 본체:
  ```
  while running:
      asset_id = queue.get()
      asset = store.get_asset_by_id(asset_id)
      self._in_flight_path = asset.path
      self._emit_progress()                # in_flight 표시 + pending-1
      t0 = clock()
      try:
          store.mark_asset_analyzing(asset_id)
          analyzer = self.sprite if asset.kind == 'sprite' else self.sound
          inp = AnalyzerInput(...)
          result = analyzer.analyze(inp)
          self._persist(asset_id, result)
          store.mark_asset_state(asset_id, result.state, error=result.error, analyzed_at=now())
      except Exception as e:
          store.mark_asset_state(asset_id, 'failed', error=repr(e), analyzed_at=now())
          log.exception(...)
      finally:
          self._recent_durations.append(clock() - t0)
          self._completed_in_session += 1
          self._in_flight_path = None
          self._emit_progress()
          self.analysisFinished.emit(asset_id)
  ```
- `_emit_progress()` 가 `AnalysisProgress(...)` 빌드 후 `progressChanged.emit(snapshot)`.
- `pending` 계산: `queue.qsize() + (1 if in_flight else 0) + store.count_pending_assets()`. DB pending 까지 합산해 워처 인테이크가 미처 enqueue 하지 못한 항목까지 정확히 반영.
- `eta_seconds = avg * pending` (in_flight 포함). 0 이면 "분석 완료".
- `_persist` 가 sprite_meta/sound_meta + asset_labels + asset_embeddings + assets_fts 를 한 트랜잭션에 저장.
- 팩 완료 감지: 같은 팩의 pending 가 0 이 되면 `pack_manager.update_aggregate(store, pack_id)` 한 번 호출.
- 시그널이 GUI 스레드로 큐드 전달되면 `MainWindow.update_progress(snapshot)` + `MainWindow.refresh()` 호출.

ETA 결정성·신뢰도:

- 첫 분석 1~2건 동안은 `eta_seconds=None` 으로 표시("계산 중…"). 3건 이상부터 평균값 사용.
- 분석 시간이 자산 종류(sprite vs sound)/크기 차이로 분산이 크므로 v1 은 **단일 평균**으로 단순화. 종류별 분리 평균은 M3 이후 검토.
- 첫 CLIP 모델 다운로드 시간은 평균 표본을 크게 왜곡할 수 있다 → `OpenClipBackend` 가 download 시간을 별도 카운터로 빼고 첫 inference 부터만 ETA 표본에 반영(`_recent_durations` 첫 push 는 모델 다운로드 후 첫 완료부터).

테스트 전략 (분석 큐): `SpriteAnalyzer`/`SoundAnalyzer` 자리에 `FakeAnalyzer` (즉시 결정적 결과 반환). 시그널 전달은 콜백 리스트로 캡처. `clock` 픽스처 주입으로 ETA 계산이 결정적.

### 3.10 `core/pack_aggregate.py` (선택) 또는 `pack_manager.py` 확장

`packs.aggregate_meta` 채우는 로직. M1 의 `pack_manager.py` 에 함수 추가가 자연스럽다.

```python
def compute_aggregate(store: Store, pack_id: int) -> dict:
    """팩 전체 분석 결과를 집계.

    반환: { 'asset_count': N, 'main_style': 'pixel_art', 'palette': ['#...', ...],
            'category_dist': {'character': 0.4, ...}, 'avg_dim': [w,h],
            'avg_duration_ms': ... }
    """
```

분석 큐가 팩 완료 시 호출. JSON 으로 직렬화해 `store.update_pack_aggregate`. M3 통일성 스코어러가 이 값을 입력으로 사용.

M2 범위: `main_style` 은 sprite 의 가장 빈도 높은 style; `palette` 는 도미넌트 컬러 합집합 상위 5개; `category_dist` 는 라벨 axis='category' 의 정규화 분포.

### 3.11 `config.py` 확장

`Config` 에 추가:

```python
# M2 fields
analysis_timeout_seconds: float = 30.0
analysis_concurrency: int = 1
analysis_max_retries: int = 3
description_language: str = "ko"   # "ko" | "en"
clip_model: str = "ViT-B-32"
clip_pretrained: str = "openai"
clip_enable: bool = True
audio_max_seconds: int = 30
audio_chunk_strategy: str = "smart"  # "smart" | "first" | "rms_peak"
```

`from_mapping` 은 이미 forward-compat. M0/M1 의 11개 테스트는 그대로 통과해야 한다. M2 테스트(`test_config_m2.py`) 가 신규 필드 5~9개의 기본값·TOML 왕복을 추가 검증.

### 3.12 `app.py` 통합

```
qapp = ...
store.initialize()                           # M1 + M2 스키마
registry = LabelRegistry(store)
registry.bootstrap()                         # 빈 labels 테이블이면 시드 INSERT
reconcile_library(store, library_root)       # M1 그대로

ollama   = OllamaClient(base_url=config.ollama_url, model=config.model_image, ...)
embedder = EmbeddingEncoder(ollama, model=config.model_embed)
clip     = ClipLabeler(OpenClipBackend(...), store, registry) if config.clip_enable else None
sprite   = SpriteAnalyzer(ollama, clip, embedder, registry)
sound    = SoundAnalyzer(ollama, embedder, registry,
                         spectrogram_cache_dir=paths.cache_dir / "spectrograms")
queue    = AnalysisQueue(store, sprite, sound, concurrency=config.analysis_concurrency)
queue.start()
queue.drain_pending()                        # 부팅 시 1회

watcher = LibraryWatcher(
    window_seconds=config.watch_debounce_seconds,
    on_pack_changed=lambda name: _on_pack_changed(name, ...),
)
def _on_pack_changed(name):
    # 1. M1 인테이크 (GUI 스레드로 invoke)
    # 2. 인테이크 끝나면 queue.enqueue_pack(pack_id)
    # 3. main_window.packChanged.emit(name)

queue.analysisFinished.connect(main_window.on_asset_analyzed)  # refresh 일부

main_window.set_label_registry(registry)     # 라벨 관리 다이얼로그가 참조
```

종료 시 `queue.stop()` → `watcher.stop()` → `store.close()`.

### 3.13 UI `tr()` 래핑 + 새 컬럼

M1 위젯의 모든 사용자 노출 문자열을 `tr()` 로 감싼다. PySide6 에서는 `QObject` 메서드로 `self.tr("...")` 또는 `QCoreApplication.translate("Context", "...")`. 일관성을 위해 모듈 상단에 `_tr = QCoreApplication.translate` 헬퍼 임포트.

- 트레이 메뉴 — `"메인 창 열기"`, `"라벨 관리…"` (신규), `"종료"`
- 메인 윈도우 타이틀 — `"Game Asset Helper"` (그대로 두지만 `tr()` 래핑)
- 탭 이름 — `"팩"`, `"라이브러리"`
- 팩 탭 컬럼 — `"이름"`, `"벤더"`, `"라이선스"`, `"에셋 수"`, `"활성"`, `"집계"` (신규)
- 라이브러리 탭 컬럼 — `"팩"`, `"경로"`, `"종류"`, `"크기"`, `"분석 상태"`, `"라벨"` (신규), `"설명"` (신규)
- 라벨 관리 다이얼로그 — `"라벨 관리"` 타이틀, `"축"`, `"라벨"`, `"상태"`, `"출처"`(seed/user), `"추가"`, `"비활성화"`, `"활성화"` 버튼/컬럼
- **분석 진행 상태바** (신규) — `"분석 중 {n}/{total} — 현재: {path} — 약 {eta_label} 남음"` / `"분석 완료"` / `"분석 대기 중"`. `eta_label` 은 `_format_duration_kor(seconds)` 헬퍼가 `"6분"`/`"1시간 12분"`/`"45초"` 등으로 변환.

### 3.13b 분석 진행 표시 (`main_window.py` + `tray.py`)

분석 진행 정보를 사용자가 한눈에 보도록 두 위치에 노출.

**메인 윈도우 상태바** (`QMainWindow.statusBar()`):

- 영구 위젯 2개를 `addPermanentWidget`:
  - `QProgressBar` — `setRange(0, total)`, `setValue(completed)`. `total = completed + pending`. `pending==0` 이면 `setRange(0,1); setValue(1)` 으로 가득 찬 바.
  - `QLabel` — `"분석 중 47/132 — kenney_pack/hero.png — 약 6분 남음"`. 비활성 시 `"분석 대기 중"`.
- 슬롯 `update_progress(snapshot: AnalysisProgress)`:
  - `eta_seconds is None` 일 때 → `"… — 계산 중…"`
  - `pending == 0 and in_flight is None` → `"분석 완료"` 표시 후 5초 뒤 `"분석 대기 중"` 으로 전환(QTimer.singleShot).
  - in_flight path 가 너무 길면 우측 ellipsis(`hero_animation_run_07_a_very_long_filename.png` → `…long_filename.png`).
- 시그널 연결: `queue.progressChanged.connect(main_window.update_progress)` (QueuedConnection — 워커 스레드에서 emit 되므로 GUI 스레드로 마샬링).

**트레이 아이콘 툴팁** (`QSystemTrayIcon.setToolTip`):

- 메인 윈도우와 동일한 짧은 형식 (`"분석 중 47/132 — 약 6분 남음"`). 파일명은 길이 한계로 생략.
- 같은 시그널 슬롯 안에서 갱신.

**ETA 라벨 형식** (`_format_duration_kor`):

| 초 단위 | 라벨 |
|---|---|
| `< 60` | `"{n}초"` |
| `< 3600` | `"{m}분"` (반올림) |
| `>= 3600` | `"{h}시간 {m}분"` |
| `None` | `"계산 중…"` |

테스트 전략: `_format_duration_kor` 는 순수 함수 단위 테스트. 상태바 위젯은 offscreen 으로 라벨 텍스트 검증.

신규 컬럼:

- `라벨` 컬럼: 해당 에셋의 라벨 상위 3개를 `axis=label` 형식으로 띄어쓰기 join. M3 검색·M4 풍부 UX 의 사전 검증.
- `설명` 컬럼: Gemma 가 만든 `description` 한 줄 (호출 언어). 너무 길면 ellipsis.

`library_view.py` 의 `refresh()` 는 `Store.list_assets()` + `Store.labels_for_assets(asset_ids)` + `Store.descriptions_for_assets(asset_ids)` 배치 조회(N+1 회피)로 채운다.

### 3.14 라벨 관리 다이얼로그 (`ui/labels_admin.py`)

트레이 메뉴 `"라벨 관리…"` 또는 메인 윈도우의 `Ctrl+L` 단축키로 띄우는 `QDialog`.

레이아웃:

- 좌측 — 축 선택 콤보 (`category` / `style` / ... / `sound_category`). `LabelRegistry.list_axes()` 로 동적 채움.
- 중앙 — 선택 축의 라벨 테이블. 컬럼: `라벨` · `상태`(활성/비활성) · `출처`(`seed`/`user`).
- 하단 — `"라벨 추가"` 입력란(영문 lowercase + underscore 검증) + 추가 버튼, 행 선택 후 `"비활성화"`/`"활성화"` 토글.
- 모든 변경은 즉시 `LabelRegistry` 호출 후 테이블 새로고침. 분석 큐는 다음 분석부터 자동 반영(추가 신호 불필요).

검증 메시지:
- 토큰 정규식 위반 — "영문 소문자·숫자·`_` 만 가능 (예: `pixel_art`)" 인라인 표시.
- 이미 존재하는 라벨 추가 — 자동으로 활성화로 폴백하고 토스트 "이미 있는 라벨이라 활성화했습니다".

라벨 비활성화 후 영향 안내:
- 다이얼로그 푸터에 "비활성화한 라벨은 다음 분석부터 사용되지 않습니다. 기존 라벨 데이터는 보존됩니다." 안내 한 줄.

스레드 안전성:
- 다이얼로그는 메인 GUI 스레드에서만 살아 있고, `LabelRegistry` 의 모든 변경 메서드는 SQLite autocommit 으로 즉시 반영. 워커 스레드(분석 큐)는 다음 분석 시작 직전 `list_labels` 재호출로 최신 어휘를 본다.

### 3.15 M2 끝에서 `aggregate_meta` 와 GUI 가시화

팩 탭의 새 `집계` 컬럼은 `packs.aggregate_meta` JSON 에서 `main_style` + `category_dist` 상위 2개를 한 줄로 표시. 비어 있으면 `(분석 중)`.

### 3.16 MCP 활용을 위한 데이터 준비 (M3 인계 강화)

M2 가 분석 데이터를 만들 때, **M3 의 MCP 도구가 Claude Code 에게 "적당한 에셋"을 정확히 추천**할 수 있도록 다음을 보장한다. 이건 M2 책임 범위 안의 데이터 준비이며, MCP 도구 노출은 M3 가 한다.

**(a) 라벨 어휘를 자체적으로 자기 기술(self-describing) 하게**

- `labels.description` 에 영어 한 문장 설명을 박는다(시드 216개 모두). Claude Code 가 자연어 쿼리를 라벨로 풀어낼 때, `list_labels(axis=..., with_description=true)` 한 번이면 "이 라벨이 뭘 의미하는지" 알 수 있다.
- 사용자가 추가한 라벨은 description=NULL 로 시작. 라벨 관리 다이얼로그에서 채워 넣게 권장(빈 description 은 GUI에서 노란 경고 아이콘).
- `label_catalog_signature()` 가 어휘의 전체 해시를 돌려준다. MCP 클라이언트가 캐시 무효화 결정에 사용.

**(b) FTS5 검색이 라벨 단위·메타 단위로 가능하게**

- `searchable.for_fts` 가 토큰에 prefix 를 붙여 색인:
  - `label:pixel_art` — 라벨 직접 매칭
  - `category:character`, `style:pixel_art`, `mood:heroic` — 축별 매칭
  - `path:kenney_hero/idle.png` — 경로 매칭
  - 라벨 description 자체도 인용 부호 안에 넣어 BM25 가 자연어 쿼리와 매칭
- Claude Code 가 자연어 쿼리 `"어두운 동굴 BGM"` 을 받으면 M3 의 `find_asset` 백엔드가 다음을 실행:
  1. 자연어 → `nomic-embed-text` 임베딩 → 코사인 유사도 후보
  2. 라벨 추정(라벨 description 의 임베딩 코사인 또는 단순 토큰 매칭) → `assets_fts MATCH 'label:bgm AND label:dark'` 후보
  3. 두 후보 가중합 → top-N

**(c) 라벨 점수가 출처별로 분리 보존**

- `asset_labels.source ∈ {'gemma','clip','user'}` 가 분리되어 있어 M3/M4 의 검색 가중치 슬라이더에서 출처별 강도 조절 가능.
- `asset_labels.weight ∈ {'primary','secondary','tertiary'}`(Gemma 만) — 라벨 순위. M3 의 `find_asset` 응답 `matched_labels` 에 이 정보를 그대로 노출 가능.

**(d) `pack_aggregate` 가 팩 단위 요약을 제공**

- `packs.aggregate_meta` JSON 이 `main_style`, `category_dist`, `palette` 등을 포함 → M3 의 `suggest_packs` 가 "이 팩이 어떤 성격인지" 한 줄로 보여줄 수 있다.
- 사용자가 자연어로 "픽셀아트 RPG 팩 추천" 요청 → M3 가 `packs.aggregate_meta` 조회 + 통일성 가중치 + 라벨 점수로 정렬.

**(e) `searchable.for_embed` 가 짧고 의미 압축**

- 임베딩 차원이 라벨 description 노이즈에 휘둘리지 않게, 상위 라벨 5개 + 그 description + 에셋 description 만 임베딩. 라벨 토큰만 잔뜩 박은 텍스트는 의미 벡터를 단조롭게 만든다.

**(f) M2 plan 범위 안에서 만드는 stub 문서: `docs/MCP_USAGE_GUIDE.md`**

M3 가 본격화하지만 M2 끝에 짧은 stub 을 둔다. 내용은 1페이지로:
- 라벨 어휘는 자체 기술(`list_labels` 응답에 description 포함)
- 자연어 쿼리 → MCP 측에서 라벨 매핑·임베딩 검색 모두 수행. Claude Code 는 자연어 그대로 보내도 됨
- 응답에는 `matched_labels` 와 `score_breakdown` 이 들어와 Claude Code 가 사용자에게 추천 근거를 설명 가능
- 라벨 카탈로그는 캐시 가능 — `label_catalog_signature` 가 바뀌면 다시 받기
- 표준 워크플로는 DESIGN.md §13 참조(suggest_packs → 사용자 선택 → find_asset → record_asset_use)

이 문서는 M3 가 MCP 도구를 구현할 때 1차 가이드. M3 끝에 사용 예시·실제 응답 JSON 으로 본격 작성.

## 4. 외부 의존성

| 패키지 | 용도 | 비고 |
|---|---|---|
| `Pillow>=10` | 이미지 디코딩·리사이즈 | LANCZOS·도미넌트 컬러 추출 |
| `numpy>=1.26` | 픽셀아트 판정·도미넌트 컬러 k-means·임베딩 직렬화 | torch 와 호환 버전 |
| `librosa>=0.10` | 사운드 기술 특성·멜 스펙트로그램 | numba 의존성 가져옴 |
| `soundfile>=0.12` | WAV 인코딩(클립 → base64) | libsndfile wheel 포함 |
| `httpx>=0.27` | Ollama HTTP 클라이언트 | 동기 클라이언트 사용(asyncio 미도입) |
| `pydantic>=2.6` | LLM 응답 검증 | `Literal[...]` 화이트리스트 |
| `open_clip_torch>=2.24` | CLIP zero-shot | `torch` 의존 |
| `torch>=2.2` | CLIP 백본 | **CUDA 자동 감지, CPU 폴백** — 아래 "torch 설치 전략" 참고 |
| `matplotlib>=3.8` | 멜 스펙트로그램 PNG 저장 (Agg 백엔드) | 사운드 2차 폴백 |
| **dev** | | |
| `pytest-asyncio>=0.23` | (큐 테스트가 await 쓰면) | 시그널 동기 처리라 안 쓸 가능성 — 우선 추가 |
| `respx>=0.20` | httpx 모킹 | OpenAI/Ollama 양 경로 분기 검증 |

torch + open_clip 합쳐 ≈ 1.5 GB wheel + 모델 600 MB. M7 PyInstaller 패키징 시 부담은 인지하되 M2 plan 범위 밖.

대안 메모: `transformers` 의 `CLIPModel` 도 등가지만 `open_clip_torch` 가 더 가볍고 모델 라이브러리 풍부. v1 결정은 `open_clip_torch`.

### torch 설치 전략 (개발 + 배포)

배포 대상 사용자 PC 의 GPU 보유 여부가 다양하므로, **런타임에 자동 감지하고 어느 환경에서도 동작**해야 한다.

- **`pyproject.toml` 의존성**: 단순히 `torch>=2.2` 만 명시. `pip install` 은 기본 wheel 인덱스에서 받는데, PyPI 의 `torch` wheel 은 **CUDA 12.x 빌드가 기본 포함**되어 GPU 가 있으면 자동 사용, 없으면 자동으로 CPU 경로로 폴백한다. 별도 `extras_require` 분기 없음.
- **CPU 전용 wheel 옵션**: 사용자가 CUDA 가 없는 환경에서 wheel 사이즈를 줄이고 싶다면 `pip install torch --index-url https://download.pytorch.org/whl/cpu` 로 별도 설치 가능. README 에 안내. 우리 코드는 양쪽 모두 동일하게 동작.
- **런타임 감지**: `OpenClipBackend.__init__` 에서 `self.device = "cuda" if torch.cuda.is_available() else "cpu"`. 모델·이미지 텐서 모두 `.to(self.device)`. 로그에 `"CLIP backend initialized on device=cuda"` / `"...on device=cpu"` 명시.
- **M7 PyInstaller 배포**: 단일 exe 에는 PyPI 기본 wheel(GPU+CPU 통합)을 포함. 사용자 PC 에 GPU 가 있으면 자동 가속, 없어도 CPU 로 정상 동작. exe 크기 ≈ 1.5~2 GB 가 되지만 사용자 환경 분기 없음. (대안: GPU/CPU 두 빌드 따로 배포는 M7 결정.)
- **테스트 환경**: CI/단위 테스트는 `FakeBackend` 만 사용하므로 torch 설치 불필요. `clip_integration` 마크 통합 테스트만 실제 torch 필요(개발자 PC에서 옵트인).

## 5. 테스트 전략

### 5.1 테스트 fixture (`tests/fixtures/`)

생성 코드는 `tests/conftest.py` 의 fixture 함수로 두고 결정적 PRNG 로 생성(런타임 비용 무시 가능). 결과:

- `tiny_pixel_32.png` — 32×32 픽셀아트 (4색만 사용 → 픽셀아트 판정 양성)
- `tiny_vector_256.png` — 256×256 그라디언트(픽셀아트 판정 음성)
- `transparent_alpha.png` — 알파 채널 있는 64×64
- `short_sfx_1s.wav` — 16kHz mono 1s 사인파(440Hz)
- `medium_sfx_5s.wav` — 16kHz mono 5s 노이즈
- `long_bgm_45s.wav` — 16kHz mono 45s 멀티톤 (smart chunk 분기 검증)
- `mel_sample.png` — 사전 생성된 멜 스펙트로그램(2차 폴백 모킹용)

이미지 fixture 는 Pillow 로 생성, WAV 는 numpy + soundfile.

### 5.2 단위 테스트 목록

**store m2** — `tests/test_store_m2.py`
- `test_initialize_creates_m2_tables` — sprite_meta/sound_meta/assets_fts/asset_embeddings/asset_labels/clip_label_cache/**labels** 모두 존재
- `test_initialize_is_idempotent_with_m1_tables` — 두 번 호출해도 OK
- `test_save_sprite_meta_replaces` — 같은 asset_id 두 번 → 1행
- `test_save_sound_meta_replaces`
- `test_save_asset_labels_overwrites_per_asset` — 기존 라벨 제거 후 새 라벨만 남음
- `test_save_embedding_roundtrip` — bytes 저장 후 numpy 복원이 동일 벡터
- `test_update_fts_can_be_searched` — `assets_fts MATCH 'pixel'` 로 검색됨
- `test_next_pending_asset_returns_oldest_first`
- `test_mark_asset_state_sets_analyzed_at_when_ok` — 'analyzing' 으로 분석 중에는 analyzed_at NULL, 'ok' 시 채워짐
- `test_mark_asset_state_failed_keeps_analyzed_at_null` — 실패한 행은 재시도 가능하게 NULL 유지
- `test_pending_assets_for_pack_filters_correctly`
- `test_update_pack_aggregate_stores_json`
- `test_clip_label_cache_get_put`
- `test_save_asset_labels_with_dup_axis_label_different_source` — gemma 와 clip 같은 (axis,label) 가 공존 (source 컬럼이 PK 일부라 가능)
- `test_delete_asset_cascades_m2_tables` — 부모 assets 삭제 시 자식 5테이블 모두 사라짐
- `test_labels_table_enforces_unique_axis_label`
- `test_labels_table_keeps_disabled_rows`

**labels (시드 + Registry)** — `tests/test_labels.py`
- `test_seed_has_expected_axes` — `SEED_LABELS` 키 24개 정확히 일치 (시각 14축 + 사운드 10축. 참고: domain/animation 은 의미 강하지만 시각 축으로 분류)
- `test_seed_no_duplicates_within_axis`
- `test_total_seed_count_in_range_290_to_340`
- `test_seed_animation_axis_matches_design_doc` — DESIGN §4.2.2 의 9개와 정확히 일치
- `test_bootstrap_inserts_seed_on_empty_db_then_noop_on_second_call`
- `test_bootstrap_includes_description_for_every_seed_label` — 시드 약 316 개 모두 비어 있지 않은 영어 설명
- `test_list_labels_returns_only_enabled_by_default`
- `test_list_labels_returns_stable_sorted_order`
- `test_list_labels_with_description_true_returns_descriptions`
- `test_list_labels_with_description_false_omits_descriptions` — 응답 크기 절약
- `test_add_label_rejects_invalid_token` — `"Pixel Art"`/한글/공백 거부
- `test_add_label_accepts_valid_user_token_with_source_user_and_null_description`
- `test_add_label_with_description_persists_string`
- `test_set_label_description_updates_row_and_updated_at`
- `test_add_label_existing_pair_returns_was_new_false_and_activates` — 비활성 라벨을 같은 토큰으로 다시 추가하면 활성화로 폴백
- `test_set_enabled_false_excludes_from_list_labels_default`
- `test_invalidate_clears_in_memory_cache`
- `test_label_catalog_signature_changes_on_add_disable_describe` — 추가·비활성·description 변경 모두 해시 변동
- `test_label_catalog_signature_stable_when_no_changes`

**labels admin UI** — `tests/test_labels_admin_ui.py`
- `test_dialog_lists_seed_axes`
- `test_table_shows_labels_with_source_and_state_and_description_columns`
- `test_add_label_input_writes_to_registry`
- `test_invalid_token_input_shows_inline_error_and_does_not_call_registry`
- `test_toggle_enable_writes_to_registry_and_refreshes_table`
- `test_edit_description_inline_writes_to_registry`
- `test_user_label_with_empty_description_shows_warning_icon`

**searchable text builder** — `tests/test_searchable.py`
- `test_for_fts_includes_label_prefixed_tokens` — `label:pixel_art` 형태 색인
- `test_for_fts_includes_axis_prefixed_tokens` — `category:character` 등
- `test_for_fts_includes_label_descriptions_in_quotes` — BM25 가 자연어 쿼리와 매칭 가능
- `test_for_fts_includes_path_and_size_meta`
- `test_for_embed_truncates_to_short_summary` — ≤ 256 토큰 가정(공백 단위 카운트)
- `test_for_embed_uses_top_n_labels_by_score`
- `test_for_embed_includes_asset_description`
- `test_for_embed_excludes_path_and_low_score_labels` — 임베딩 의미 압축
- `test_for_fts_and_for_embed_are_distinct_strings`

**ollama client** — `tests/test_ollama_client.py`
- `test_chat_uses_openai_endpoint_first` — respx 가 `/v1/chat/completions` 200 응답 → 호출이 거기로 감
- `test_chat_falls_back_to_native_on_openai_4xx`
- `test_chat_falls_back_to_native_on_connect_error`
- `test_native_payload_packs_image_and_audio_into_single_images_field` — Ollama 네이티브 페이로드의 `messages[0].images` 가 이미지·오디오 base64 모두 포함
- `test_openai_payload_uses_image_url_data_uri`
- `test_openai_payload_uses_input_audio_dict`
- `test_chat_force_json_retries_on_invalid_json`
- `test_chat_gives_up_after_max_retries`
- `test_chat_raises_typed_error_on_total_failure`
- `test_embed_uses_openai_first_then_native`
- `test_embed_returns_floats_unchanged`
- `test_chat_passes_num_ctx_to_native`
- `test_chat_passes_format_json_to_native`
- `test_chat_uses_timeout_from_config`
- `test_encode_image_helper_base64`
- `test_encode_audio_clip_helper_outputs_wav_base64`

**embedding** — `tests/test_embedding.py`
- `test_encode_text_returns_bytes_and_dim`
- `test_encode_text_uses_configured_model_name`
- `test_decode_vector_roundtrips_through_blob`
- `test_first_call_determines_dim` — 첫 응답 길이 768 → 이후 같은 dim 강제
- `test_encode_text_propagates_ollama_error`

**clip labeler** — `tests/test_clip_labeler.py`
- `test_warmup_populates_cache_only_for_missing_labels` — 1차 warmup 후 2차에서 backend.encode_text 호출 없음
- `test_score_image_returns_scores_per_label_in_zero_one_range`
- `test_score_image_clamps_negative_cosine_to_zero`
- `test_score_image_uses_cached_label_vectors_after_warmup`
- `test_label_added_after_warmup_is_computed_lazily`
- `test_disabled_clip_returns_empty_dict` — clip_enable=false 일 때
- `test_open_clip_backend_init_does_not_download_until_called` — `clip_integration` 마크
- `test_open_clip_backend_actual_inference` — `clip_integration` 마크, 실모델 (CI 옵트인)

**analyzer sprite** — `tests/test_analyzer_sprite.py`
- `test_analyze_pixel_art_classifies_as_pixel_art_via_heuristic` — tiny_pixel_32 → SpriteMeta.is_pixel_art=True
- `test_analyze_vector_classifies_as_not_pixel_art`
- `test_analyze_extracts_alpha_correctly`
- `test_analyze_extracts_5_dominant_colors`
- `test_analyze_calls_ollama_with_resampled_image` — respx 로 본문 가로채 base64 디코드 → 긴 변 ≤ 768
- `test_analyze_validates_response_against_whitelist` — Gemma 가 `style: "anime_xyz"` 같은 위반 응답하면 분석기는 재시도
- `test_analyze_falls_back_to_other_after_max_retries` — 끝까지 위반이면 `state='partial'` + `style='other'` 강등
- `test_analyze_integrates_clip_scores_as_separate_source_labels` — gemma 와 clip 라벨이 axis 동일·source 다르게 양쪽 들어감
- `test_analyze_searchable_for_embed_includes_korean_description` — language='ko' 결과의 description 이 한글
- `test_analyze_searchable_for_fts_uses_english_enum_regardless_of_language`
- `test_analyze_searchable_for_fts_includes_label_descriptions_from_registry` — 라벨 description 이 FTS 텍스트에 포함

**analyzer sound** — `tests/test_analyzer_sound.py`
- `test_analyze_short_sfx_uses_native_path` — short_sfx_1s.wav → `audio_path_used='native'`
- `test_analyze_long_bgm_with_smart_chunks_merges_results` — long_bgm_45s.wav → 3청크 호출 + mood 합집합
- `test_analyze_falls_back_to_spectrogram_when_native_times_out` — respx 로 1차에 timeout → 2차 호출에 이미지 입력
- `test_analyze_marks_audio_path_used_spectrogram_when_fallback_succeeds`
- `test_analyze_falls_back_to_heuristic_when_both_paths_fail` — `category` 가 파일명 휴리스틱(`*bgm*` → `bgm`)으로 결정 + `state='partial'`
- `test_analyze_extracts_loudness_db_from_librosa`
- `test_analyze_detects_loopable_from_gemma_response`
- `test_analyze_does_not_call_clip_labeler` — 사운드 라벨링은 Gemma only
- `test_analyze_emits_labels_for_all_ten_sound_axes` — 응답에 10축 모두 들어오면 `asset_labels` 에 모든 축 행이 INSERT
- `test_analyze_omits_voice_type_when_category_not_voice` — Pydantic 강제 → voice_type=null 정상, 검증 실패 안 함
- `test_analyze_omits_genre_when_category_not_music` — bgm/jingle/cinematic 아니면 genre=null
- `test_analyze_rejects_genre_when_category_is_sfx_and_retries` — 모델이 잘못 genre 채우면 분석기가 재시도
- `test_analyze_persists_new_sound_meta_columns` — `tempo`/`intensity`/`genre`/`voice_type` 컬럼이 sound_meta 에 저장

**analysis queue** — `tests/test_analysis_queue.py`
- `test_enqueue_asset_processes_via_correct_analyzer`
- `test_enqueue_pack_drains_all_pending_in_pack`
- `test_drain_pending_picks_up_existing_pending_rows_on_boot`
- `test_concurrency_one_processes_serially`
- `test_failed_analyzer_marks_state_failed_without_killing_worker`
- `test_signal_emitted_for_each_finished_asset`
- `test_stop_waits_for_in_flight_analyzer_to_finish`
- `test_pack_completion_triggers_aggregate_update`

**analysis progress (ETA)** — `tests/test_analysis_progress.py`
- `test_progress_eta_is_none_when_fewer_than_3_samples`
- `test_progress_eta_uses_recent_window_average` — fake clock 으로 처리 시간 [1.0, 2.0, 3.0] 주입 → eta = 2.0 * pending
- `test_progress_eta_window_caps_at_10_samples` — 11개 주입해도 평균은 마지막 10개로
- `test_progress_includes_in_flight_path_during_analysis`
- `test_progress_in_flight_path_cleared_after_completion`
- `test_progress_pending_count_combines_queue_and_db`
- `test_progress_signal_emitted_at_start_and_end_of_each_asset` — 1 분석 당 progressChanged 2회
- `test_failed_analysis_still_contributes_to_duration_window` — 실패한 분석 시간도 ETA 표본에 포함
- `test_format_duration_kor_handles_none_seconds_minutes_hours` — `_format_duration_kor(45)=='45초'`, `(420)=='7분'`, `(4500)=='1시간 15분'`, `(None)=='계산 중…'`

**progress statusbar** — `tests/test_progress_statusbar.py`
- `test_statusbar_initially_shows_idle_label`
- `test_statusbar_updates_on_progress_signal`
- `test_statusbar_shows_completed_then_idle_after_queue_drains`
- `test_tray_tooltip_reflects_current_progress`

**config m2** — `tests/test_config_m2.py`
- `test_new_fields_have_documented_defaults`
- `test_from_mapping_ignores_unknown_keys_still`
- `test_toml_roundtrip_preserves_new_fields`
- `test_description_language_validates_known_values` — `"ko"`/`"en"` 만 허용 (warning 로그 + 기본값 폴백)
- `test_clip_enable_can_be_disabled`

**ui smoke m2** — `tests/test_ui_smoke_m2.py`
- `test_main_window_constructs_with_translated_strings`
- `test_library_view_renders_label_and_description_columns`
- `test_pack_view_renders_aggregate_column`

### 5.3 테스트 인프라

- `tests/conftest.py` 에 픽스처 추가:
  - `fixture_dir` — `Path(__file__).parent / "fixtures"`. 첫 호출 시 생성 함수(`_build_fixtures()`) 자동 호출.
  - `mock_ollama` — `respx.mock` 컨텍스트를 yield 하고 OpenAI/네이티브 양 엔드포인트 라우트 헬퍼 제공.
  - `fake_clip_backend` — `FakeBackend` 인스턴스(라벨/이미지 sha256 → 결정적 fake vec).
  - `analyzer_inputs` — 임의 fixture path 를 `AnalyzerInput` 으로 묶는 헬퍼.
- pytest mark: `@pytest.mark.clip_integration` — 실모델 다운로드 필요. 기본 실행에서 `-m "not clip_integration"` 으로 제외하도록 `pyproject.toml [tool.pytest.ini_options]` 의 `markers` + `addopts` 추가.
- 임시 SQLite 는 기존 `store` 픽스처 재사용. M2 마이그레이션도 같은 `initialize()` 안에 들어가 추가 픽스처 불필요.

### 5.4 검증 기준 (Definition of Done)

1. `pytest -q` 전체 통과 — M0(18) + M1(45 + 트레이 4) + M2 신규 **134** (store m2 17 / labels 19 / labels_admin_ui 7 / ollama_client 16 / embedding 5 / clip_labeler 8 / searchable 9 / analyzer_sprite 11 / analyzer_sound 13 / analysis_queue 8 / analysis_progress 9 / progress_statusbar 4 / config_m2 5 / ui_smoke_m2 3) = 합계 **약 201개**. `clip_integration` 마크된 2개는 기본 실행에서 제외라 활성 합계는 ≈ 199.
2. M0/M1 회귀 0건.
3. PowerShell 수동 검증 (§5.5):
   - Ollama 가 떠 있는 PC 에서 `python -m gah --tray` → 라이브러리에 떨어뜨린 팩의 pending 행이 `analyzing → ok` 로 전이.
   - GUI 라이브러리 탭 `라벨` 컬럼에 `category=character` 같은 표시 등장.
   - GUI 라이브러리 탭 `설명` 컬럼에 한국어 한 줄 표시.
   - `metadata.db` 의 `sprite_meta`/`sound_meta`/`asset_labels`/`asset_embeddings`/`assets_fts` 모두 행이 채워짐.
4. Ollama 미기동 환경 — 모든 분석 행이 결국 `failed` 가 되더라도 워커가 죽지 않고 큐가 빈다(다음 행 진행). GUI 가 노란 배너로 알린다(`MainWindow.set_ollama_unhealthy(True)`).
5. CLIP 모델 다운로드는 첫 실행 시 한 번만, 진행 표시는 trace 로그로 충분(GUI 표시는 M7 마감).

### 5.5 수동 검증 시나리오 (요약)

`milestones/M2_verification.md` 가 끝에 자세히 작성하지만 plan 차원에선 다음 6단계만 둔다.

1. Ollama 데몬 기동(`ollama serve`) + `ollama pull gemma4:e4b` + `ollama pull nomic-embed-text` 확인.
2. `pytest -q` → 약 201 passed.
3. `python -m gah --tray` → 트레이 + 메인 윈도우.
4. `library/` 에 PNG 1장 + WAV 1개 드롭 → 5~30초 후 라이브러리 탭의 `분석 상태` 컬럼이 `analyzing → ok`.
5. 라벨·설명 컬럼이 채워짐.
6. `sqlite3 ...\metadata.db "SELECT axis, label, score, source FROM asset_labels LIMIT 10"` → 10행 출력.
7. 트레이 메뉴 `"라벨 관리…"` → 다이얼로그에 시드 18축 노출. `style` 축에 사용자 라벨(예: `cell_shaded_kr_custom`) 추가 후, 같은 팩의 다른 PNG 를 드롭 → 새 분석 결과의 `asset_labels` 에 `source='clip'`/`'gemma'` 인 추가 라벨 행이 있을 수 있음. 비활성화 토글 후 라벨이 새 분석에서 빠지는지 확인.
8. **분석 진행 표시** — 라이브러리에 PNG/WAV 5~10개 한꺼번에 드롭. 메인 윈도우 상태바에 `"분석 중 3/10 — kenney_pack/hero_03.png — 약 15초 남음"` 형식이 보임. 트레이 아이콘 위에 마우스 hover → 같은 정보의 짧은 툴팁. 큐가 비면 `"분석 완료"` 5초 표시 후 `"분석 대기 중"` 으로 전환.
9. **CUDA 가속 (선택)** — `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"` 실행. `True`/디바이스명 출력되면 다음 분석부터 로그에 `"CLIP backend initialized on device=cuda"`. `False` 인 환경에서도 분석은 정상 진행, 로그에 `device=cpu`.
10. **라벨 카탈로그 (M3 인계 준비)** — `sqlite3 ...\metadata.db "SELECT axis, label, description FROM labels WHERE axis='style' LIMIT 5"` → 시드 라벨 5행이 영어 description 과 함께 출력. 모든 description 이 비어 있지 않아야 함. 라벨 관리 다이얼로그에서 description 한 줄 편집 후 같은 쿼리 → 변경 반영.
11. **FTS 라벨 매칭** — 분석 완료된 에셋 1개 이상 있는 상태에서 `sqlite3 ...\metadata.db "SELECT asset_id FROM assets_fts WHERE searchable_text MATCH 'label:pixel_art'"` → 픽셀아트로 라벨링된 에셋 ID 가 한 개 이상 반환. `... MATCH 'category:character AND mood:heroic'` 같은 축별 부울 쿼리도 동작해야 함. M3 의 `find_asset` 백엔드가 이걸 그대로 활용.

## 6. 위험 요소와 완화

- **Ollama `gemma4:e4b` 의 GGML assertion crash ([ollama#15333])** — 오디오 청크에서 간헐. 1·2·3차 폴백 체인이 이 시나리오를 흡수. 또한 워커는 단일 항목 실패가 큐를 멈추지 않게 처리(`failed` 마킹 + 다음 진행).
- **CLIP 모델 ~600 MB 첫 다운로드** — 캐시 위치를 `paths.cache_dir / "clip"` 로 명시. 다운로드 중 GUI 가 멈추지 않게 워커 스레드에서 lazy 로딩. 첫 분석에서만 지연.
- **CLIP + PyTorch 인스톨 사이즈** — wheel 합 ≈ 1.5 GB. dev 환경에선 OK, M7 PyInstaller 단일 exe 사이즈는 별도 마일스톤에서 다룬다. M2 는 패키지 사이즈 최적화 책임 없음.
- **librosa import 시간** — 첫 import 5~10초(numba JIT 캐시). 분석 워커는 lazy 로딩으로 분리, 메인 import 영향 없게 한다.
- **Pydantic v2 화이트리스트 위반 응답 처리** — Gemma 4 가 종종 `"style": "anime style"` 같이 enum 위반. 시스템 프롬프트 명시 + 3회 재시도 + 끝까지 위반이면 `other` 강등 + `state='partial'`. 원문은 `description` 에 보존.
- **사운드 30s 클립 분할 정책** — `smart` 가 BGM 분류 정확도에 가장 안전한 선택. v1 기본은 smart. 너무 느리면 사용자가 `Config.audio_chunk_strategy="first"` 로 빠르게 전환 가능.
- **임베딩 차원 가정** — `nomic-embed-text` v1.5 는 768. 첫 호출 후 응답 길이로 확정해 `asset_embeddings.dim` 컬럼에 저장. 모델 변경 시 자동 적응(전체 재임베딩이 필요하지만 M2 범위는 아님).
- **GUI 스레드 안전성** — 워커 스레드의 store 쓰기는 GUI 가 메인 윈도우 refresh 와 충돌할 수 있다. SQLite WAL 모드 + 워커가 시그널만 emit 하고 refresh 는 메인 스레드에서 큐드 슬롯으로 실행되는 구조 유지. 여러 워커 동시 쓰기는 동시성 1 정책으로 회피.
- **분석 큐 폭주** — 큐 길이가 500 넘으면 GUI 트레이 알림(설계 §8.3). M2 plan 범위에서 알림 1줄만 띄우고 본격 큐 매트릭은 M7 마감.
- **torch CUDA / CPU 분기** — `OpenClipBackend` 가 `torch.cuda.is_available()` 자동 분기. CUDA 환경에선 ≈ 50ms/장, CPU 환경에선 ≈ 200ms/장. 분석 큐 동시성 1 이면 24h 1만장 처리 가능.
- **테스트 결정성** — Gemma 응답은 모킹이 필수. 실모델 의존 통합 테스트는 별도 마크. CI 기본 실행은 결정적 fake 만 사용.
- **라벨 추가/비활성화의 일관성** — 라벨이 늘면 새 분석은 자동으로 영향받지만, 이미 분석된 에셋의 `asset_labels` 행은 그대로 남는다. 즉 어휘 변경 후 라이브러리 전체에 일관 적용하려면 **재분석이 필요**. M2 범위 안에서 GUI 의 라벨 다이얼로그에 "이 변경은 이미 분석된 에셋에 적용되지 않습니다. 일괄 재분석은 M3 의 `request_rescan` 도구가 도입되면 가능해집니다." 한 줄 안내. 단일 에셋 재분석은 파일을 살짝 수정해 hash 만 바꿔도 트리거되지만, 사용자에게 권장하진 않는다.
- **사용자 토큰 오염** — `add_label` 의 정규식이 영문 lowercase + `_` 만 허용해 한글/공백/대문자는 거부. 그래도 의미적으로 중복되는 라벨(예: 사용자 `cellshaded` vs 시드 `low_poly`)이 생길 수 있다 — v1 은 정책으로 막지 않고 검색 UX(M4)에서 동의어 묶음을 제공할 여지를 둔다.
- **`labels` 테이블 마이그레이션** — M2 신규 테이블이라 M1 사용자 DB 에 자동 적용. 시드는 비어 있을 때만 INSERT 라 사용자가 이미 라벨을 추가한 환경에는 영향 없음.
- **ETA 부정확성 (첫 분석 / 종류 혼합)** — 분석 시간이 자산 종류(sprite ≈ 5~15s vs sound ≈ 10~40s)별로 분산이 크다. 표본 적을 때는 `eta_seconds=None` 표시("계산 중…"), 표본 누적 후엔 단일 평균. 종류 혼합 큐에선 ETA 가 ±50% 까지 흔들릴 수 있음. v1 은 이 정도 정확도로 시작하고, 종류별 분리 평균은 사용자 피드백 후 v2 검토.
- **CLIP 첫 다운로드 시간이 ETA 표본을 왜곡** — `OpenClipBackend` 가 모델 다운로드 시간을 별도 카운터로 빼고, 첫 inference 부터만 `_recent_durations` 에 push. 다운로드 진행률은 trace 로그(`open_clip` 표준 다운로더 출력)로만 노출 — GUI 표시는 M7 마감.
- **torch wheel 사이즈 + 첫 import 시간** — PyPI 기본 wheel 이 GPU/CPU 통합으로 ≈ 800 MB. 첫 import 시 cuDNN 로딩으로 3~8초 지연. 트레이 부팅 직후 5초 정도는 ETA 가 흔들릴 수 있어, 상태바는 `"분석 대기 중"` 으로 시작해 첫 enqueue 후에만 "분석 중" 으로 전환.
- **라벨 description 언어 통일** — 모든 시드 라벨 description 은 영어로 작성한다. 이유: (1) `nomic-embed-text` 의 영어 의미 공간이 가장 잘 학습됨, (2) FTS5 BM25 가 영어 토큰화에 안정, (3) M3 MCP 응답이 Claude Code 와 영어로 주고받는 게 정확. 사용자 자연어 쿼리(한국어 등)는 임베딩 단계에서 영어 라벨 description 과 동일 공간에서 코사인 비교 가능(nomic 은 다국어 학습). 사용자가 라벨 description 을 한국어로 입력하면 그대로 저장하되, 검색 정확도 저하 가능성을 GUI 에 안내.
- **임베딩 텍스트 길이 한계** — `nomic-embed-text` 가 8K 토큰까지 받지만, `for_embed` 는 의미 압축 위해 ≤ 256 토큰 가정. 라벨이 많이 붙은 에셋이라도 상위 5개 라벨 + 그 description 만 사용. 라벨 description 모두 박으면 평균 임베딩 벡터가 노이즈에 휘둘려 코사인 변별력이 떨어진다.
- **`for_fts` 토큰 prefix 충돌** — `category:character` 같은 prefix 토큰이 FTS5 의 콜론 토크나이저 처리에 어떤 영향을 줄지 사전 검증 필요. `tokenize='porter unicode61'` 이 콜론을 단어 구분자로 다루는지(분리되면 `category` 와 `character` 따로 색인 → 의도와 다름) M2 구현 단계에서 단위 테스트(`test_for_fts_includes_axis_prefixed_tokens`) 로 실측. 콜론이 분리되면 prefix 를 `_` 로 바꿔(`category_character`) 단일 토큰으로 색인하는 것으로 폴백.

## 7. M3 인계점

M2 가 끝나면 M3 가 검색·통일성·MCP 를 만들 때 다음을 그대로 받는다.

- **`assets_fts`** — 모든 `'ok'`/`'partial'` 행의 searchable_text 가 색인돼 있다. M3 `search.py` 가 `MATCH ?` 로 키워드 점수 산출.
- **`asset_embeddings`** — float32 BLOB. `EmbeddingEncoder.decode_vector` 로 numpy 변환. M3 가 쿼리도 같은 인코더로 인코딩해 코사인 유사도 산출.
- **`asset_labels`** — `(axis, label, score, source)` 다중. M3 가 `find_asset` 의 라벨 필터·소팅에 사용. `source='gemma'/'clip'/'user'` 별 가중치는 M4 풍부 UX 에서 슬라이더로 노출.
- **`labels` 테이블 + `LabelRegistry`** — 라벨 어휘의 단일 출처. M3 검색의 라벨 필터 칩 어휘, M4 의 라벨 다중 선택 UI 도 모두 이 테이블에서 라벨 목록을 읽는다. 사용자가 라벨을 추가/비활성화하면 그 변경이 검색 어휘에 즉시 반영. `request_rescan` MCP 도구가 도입되면(M3) "어휘 변경 → 라이브러리 일괄 재분석" 워크플로가 완성된다.
- **`AnalysisProgress` + `progressChanged` 시그널** — 분석 진행 상태와 ETA. M3 의 `request_rescan` 도구가 큰 일괄 재분석을 시작할 때 그대로 상태바에 표시됨. M4 풍부 UX 가 진행 상태를 사이드패널/그리드 오버레이로 풀어 표시할 수 있게 시그널은 그대로 노출 유지.

**M3 가 추가할 MCP 도구** (M2 의 데이터로 즉시 구현 가능):

- **메타 도구 (라벨 어휘 노출)** — Claude Code 가 사용자 자연어를 라벨로 풀어낼 수 있도록:
  - `list_label_axes() -> { axes: ["category", "style", ..., "sound_voice_type"] }`  // 24축
  - `list_labels(axis: str | None, enabled_only: bool = true, with_description: bool = true) -> { labels: [{ axis, label, description, source }], signature: "<sha256-16hex>" }`
  - `describe_label(axis: str, label: str) -> { axis, label, description, sample_assets: [...] }` — 해당 라벨이 붙은 상위 3개 에셋 샘플
  - 위 셋 모두 `LabelRegistry` 직접 호출. M2 에서 데이터는 이미 준비됨.
- **`find_asset` 입력 확장** (DESIGN §6.1 에 추가 명시):
  - `labels_any: list[{axis,label}]` — OR 매칭
  - `labels_all: list[{axis,label}]` — AND 매칭(모두 만족)
  - `labels_none: list[{axis,label}]` — NOT 매칭(제외)
  - 백엔드는 `assets_fts MATCH 'label:pixel_art AND label:heroic'` 같은 FTS 쿼리로 풀거나, `asset_labels` JOIN 으로 풀거나 — M3 plan 결정.
- **`find_asset` 응답 확장**:
  - `matched_labels: [{ axis, label, source, score }]` — 이 에셋이 왜 매칭됐는지 Claude Code 가 사용자에게 설명 가능
  - `score_breakdown.label_match: float` — 라벨 매칭 기여 점수 (DESIGN §4.6 의 가중치 공식에 한 항으로 추가)
- **MCP 서버 `instructions` 필드** — `mcp.server.FastMCP(...)` 에 표준 워크플로 안내:
  - 세션 시작 시 `list_packs` + `list_labels(with_description=true)` 로 카탈로그 한 번 캐싱
  - 자연어 요청 → `suggest_packs` → 사용자 선택 → `find_asset(force_pack_id=...)` → 채택 시 `record_asset_use`
  - 라벨 카탈로그는 `signature` 가 바뀌지 않으면 캐시 재사용

**M3 가 M2 데이터로 어떻게 정확한 검색을 만드는지 (예시)**:

사용자 요청: `"전투 시 깔릴 빠르고 어두운 오케스트라 BGM, 1분 이내, 루프"`

```
Claude Code → mcp.find_asset({
  query: "전투 시 깔릴 빠르고 어두운 오케스트라 BGM",
  kind: "sound",
  filters: { max_duration_ms: 60000, loopable: true },
  labels_all: [{axis:"sound_category", label:"bgm"}],
  labels_any: [
    {axis:"sound_mood",       label:"dark"},
    {axis:"sound_use",        label:"combat"},
    {axis:"sound_tempo",      label:"fast"},
    {axis:"sound_genre",      label:"orchestral"},
    {axis:"sound_instrument", label:"strings"}
  ],
  project_id: "D:/Unity/MyGame",
  count: 5
})

서버 내부:
1. assets_fts MATCH 'label:bgm AND (label:dark OR label:combat OR label:fast OR label:orchestral OR label:strings) AND loopable'
2. 후보들의 embedding 코사인 = sim(encode("전투 시 깔릴 빠르고 어두운 오케스트라 BGM"), asset.embedding)
3. 라벨 점수: asset_labels.score WHERE label IN ('dark','combat','fast','orchestral','strings','bgm')
4. consistency: §4.6 공식
5. final = w_sem*sem + w_kw*keyword + w_label*label_score + w_cons*consistency
6. matched_labels 에 (axis, label, source, score) 채워 반환
```

응답에 `why` + `matched_labels` 가 들어오므로 Claude Code 가 사용자에게:

> "1순위: `kenney_rpg_essentials/Sounds/battle_dark_01.ogg` (점수 0.91)
>  매칭된 라벨: sound_category=bgm (gemma, primary), sound_mood=dark (gemma, primary),
>  sound_tempo=fast (gemma, primary), sound_genre=orchestral (gemma, primary),
>  sound_instrument=strings (gemma, primary), sound_use=combat (gemma, secondary).
>  47초 루프 가능. 이 프로젝트가 Kenney 팩을 12번 채택해 통일성 가중치도 적용됨."

> *(사운드 라벨은 source 가 모두 'gemma' — CLIP 은 이미지 전용. 라벨이 풍부해서
>  매칭 라벨 6개로 추천 근거가 구체적.)*

이 추천 근거가 자동 생성되는 게 M2 가 만드는 데이터의 핵심 가치.
- **`packs.aggregate_meta`** — JSON. M3 `consistency.py` 의 통일성 가중치 계산 입력.
- **`Config.consistency_weight`** — 이미 존재(M0). M3 가중치 슬라이더의 백엔드 값.
- **분석 큐의 enqueue 인터페이스** — M3 의 `request_rescan` MCP 도구가 `queue.enqueue_pack/enqueue_asset` 을 그대로 호출.
- **i18n 준비된 GUI 문자열** — M3 가 추가하는 검색 박스/결과 그리드 위젯도 처음부터 `tr()` 로 감싼다.

또 M2 안에서 **의도적으로 남겨두는** 자리:

- `sprite_meta.frame_w/frame_h/frame_count/animation_tags` — M5 시트 자동 분할이 채운다. M2 는 항상 `None`.
- `clip_label_cache` 의 모델 식별자 — 사용자가 `Config.clip_model` 을 바꾸면 새 모델 키로 재계산. 기존 캐시는 보존(가비지 컬렉트 안 함).
- `asset_labels.weight` — Gemma 만 사용. CLIP 의 score 는 연속값이라 weight 컬럼이 NULL.
- 사운드용 `sound_category`/`mood` 외 라벨(`palette` 등) 은 M2 에서 채우지 않음. v2 에서 CLAP 도입 시 재검토.

---

## 자기 검토 메모

이 plan 을 작성한 후 다음을 점검했다.

- **메모리·DESIGN 결정 커버리지**: `project_m2_analysis_backend.md`(§3.3), `project_ollama_multimodal_api_shape.md`(§3.3), `project_output_language_strategy.md`(§3.6, §3.7, §3.13), `project_label_scoring_clip_inclusion.md`(§3.1, §3.2, §3.5, §3.7, §3.14, §6 라벨 가중치 + 사용자 라벨 추가 워크플로 결정), `feedback_milestone_manual_verification_format.md`(§5.5 및 verification 단계 안내) 모두 작업 단위에 매핑.
- **라벨 어휘 단일 출처**: §3.1 의 `labels` 테이블 + §3.2 의 `LabelRegistry` + §3.14 의 라벨 관리 다이얼로그가 같은 어휘를 일관되게 사용. 분석기/CLIP/검색 위젯 어디서도 코드 상수 `SEED_LABELS` 를 직접 읽지 않는다(시드 적재만이 예외).
- **타입 일관성**: `LabelScore.weight`, `AnalyzerResult.state`, `SoundMeta.audio_path_used`, `Config.description_language`, `LabelRegistry` 시그니처(`list_labels`/`add_label`/`set_enabled`/`bootstrap`) 모든 곳에서 동일 식별자 사용.
- **플레이스홀더 스캔**: "TBD"/"구현 예정"/"적절한 처리" 표현 없음. 각 작업 단위에 함수 시그니처·SQL·인터페이스가 구체 작성됨.
- **로드맵 정합**: 메모리 `project_search_ux_milestone.md` 의 M4 신설을 §7 M3 인계점에 반영. M2 가 만드는 산출물이 M3·M4 모두에 직접 입력됨을 명시. **M2 일정**: CLIP 편입으로 3주 + 라벨 DB 테이블화·GUI 다이얼로그·17개 신규 테스트로 +3~5일 + 분석 진행 ETA·상태바·트레이 툴팁 +1.5~2일 → **약 4주**. 메모리 `project_search_ux_milestone.md` 의 총 12주 일정은 약 13주로 소폭 확장.
- **시드 라벨 변경(84→316)**: 24축으로 확장(시각 14 + 사운드 10). CLIP 점수 대상은 사운드 10축 제외한 시각 14축. CLIP 라벨 임베딩은 lazy(분석 시점에 필요한 라벨만 계산) + 영구 캐시(`clip_label_cache`)라 시각 라벨이 181개여도 첫 분석 1회만 ≈ 5~10초 추가, 이후 0 비용. 사운드는 CLIP 없이 Gemma 단독으로 10축 분류 — Gemma E4B 의 토큰 예산(컨텍스트 128K)이 충분해 10축 enum 화이트리스트 모두 프롬프트에 박아도 여유.
- **CUDA 자동 감지 / 배포 호환**: `pyproject.toml` 의존성은 단일(`torch>=2.2`)이고 PyPI wheel 이 GPU+CPU 통합. `OpenClipBackend` 가 `torch.cuda.is_available()` 로 device 결정. 단일 PyInstaller 빌드로 다양한 사용자 환경 커버.
- **사용자 피드백 표시**: 분석 진행 ETA + 상태바 + 트레이 툴팁이 M2 안에서 동작. 메모리 `feedback_milestone_manual_verification_format.md` 의 수동 검증 체크리스트는 §5.5 에 11단계로 정리.
- **MCP 인계 준비 (§3.16, §7)**: 라벨이 자기 기술 가능(`labels.description`), FTS5 가 라벨/축 prefix 토큰을 색인, `for_embed` 가 의미 압축 짧은 텍스트라 임베딩 코사인 노이즈 적음, `asset_labels.source`/`weight` 분리로 추천 근거 설명 가능. M3 의 `find_asset`/`suggest_packs` 가 즉시 정확도 있는 결과를 낼 수 있게 데이터 준비 완료. `docs/MCP_USAGE_GUIDE.md` stub 으로 Claude Code 워크플로 안내.
