# M11.2 검증 — Batch Spritesheet Modality

## 1. 자동 검증

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 약 **1528 passed, 3 skipped, 56 deselected**. baseline 1490 + 신규 38.

옵트인 (GEMINI_API_KEY 필요):

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -m llm_integration -q
```

Expected: 17 case (M11.1 16 + M11.2 1).

## 2. 수동 검증 시나리오

### 2.1 grid-only 시트 — Gemma animation_hint 보존 (M11.2 의 핵심 가치)
1. library 에 JSON 사이드카 없는 격자 PNG 1개 (예: 4 cell horizontal strip) 드롭.
2. `/settings` 에서 Gemini chain enabled + `chat_spritesheet` chain 도 [gemini, ollama] 인지 확인.
3. `cfg.batch.toggle="forced_on"` 으로 즉시 batch 진입 또는 30+ 시트 드롭 후 자동 trigger.
4. `python -m assetcache --tray` 실행 후 `/analyzing` dashboard 에서:
   - chat_image batch job 이 promote 만 하고 sprite 가 부족하면 사라짐.
   - 곧 chat_spritesheet job 이 생성됨.
5. job 완료 후:
   ```powershell
   sqlite3 $env:APPDATA\AssetCacheMCP\library.db "SELECT axis, label FROM asset_labels WHERE asset_id=<id>"
   ```
   → animation 라벨 1개 이상 있어야 (PR #18 까지는 0건이던 케이스).

### 2.2 Aseprite 시트 — frameTags + Gemma 동시 라벨
1. Aseprite JSON 사이드카 있는 PNG 드롭.
2. 위와 동일 흐름으로 chat_spritesheet 진입.
3. DB 확인 — animation 라벨에 frameTags (예: idle/walk) + Gemma animation_hint (예: run) 모두 등록.

### 2.3 sprite 만 있는 라이브러리 — 회귀
1. 시트 0개, 단일 sprite 만 있는 라이브러리.
2. chat_image batch 정상 동작 (분류 후 sprite_rows = 전체) — `/analyzing` summary 의 batch_spritesheet=0 유지.

### 2.4 chains 누락 호환성
1. 기존 사용자 `config.toml` (chat_spritesheet 키 없음) 로 부팅.
2. `cfg.chains["chat_spritesheet"]` 가 chat_image 와 동일 chain 으로 자동 채워졌는지 `/settings` 에서 확인.

### 2.5 /analyzing 4행 modality
1. /analyzing 페이지 진입 — summary 가 4 modality (image/spritesheet/audio/embed) 표시.
2. ko/en 언어 토글 — "Batch spritesheet" → "배치 시트" 정상 번역.

## 3. 알려진 한계

- BatchManager 가 chat_image fetch 시 sheet 를 promote 만 하고 batch 0건 (전부 시트) 인 케이스 — 다음 sweep 의 chat_spritesheet 가 threshold 미달이면 대기. M11.1 의 `forced_on` toggle 이 immediate submit 보장.
- `make_preview_composite` 가 detect_sheet 결과를 재사용하지 못해 BatchManager submit 시 + BatchPoller persist 시 두 번 detect 호출. 성능 문제는 크지 않음 (~ms 단위). 향후 batch_jobs row 에 detection JSON 캐시 가능.
- grid-only 시트의 frameTag 는 여전히 비어 있음 (sync 도 동일). Gemma 의 animation_hint 추측만 의존.
- chat_image batch 가 첫 sweep 에서 자동으로 시트 classify + promote → 사용자 첫 batch 도입 직후 일시적으로 chat_image 가 sub-threshold 로 떨어질 수 있음. v0.2.x 의 forced_on 으로 우회.
