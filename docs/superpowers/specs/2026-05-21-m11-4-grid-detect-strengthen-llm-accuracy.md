# 2026-05-21 — M11.4 Design Spec: grid_detect 강화 + LLM 분류 정확도 (v0.2.3 candidate)

## 0. 본 spec 의 위치

- 상위 roadmap: [`2026-05-20-roadmap-design.md`](./2026-05-20-roadmap-design.md) — M11.3 의 후속 patch 묶음
- 전제: [`2026-05-21-m11-3-detection-cache.md`](./2026-05-21-m11-3-detection-cache.md) (M11.3) + v0.2.2 publish 완료
- 본 spec 다음: `milestones/M11_4_plan.md` (starter) → TDD red→green
- Version 후보: **v0.2.3 patch** (M11.3 와 별도 publish)

## 1. 한 줄 요약

M11.3 LIVE 검증 v2 (`milestones/M11_3_verification.md` §4b) 에서 발견된 두 한계 해소:

* (D-1) **grid_detect 의 alpha-edge 의존성** — color-cycling effect 시트 (예: `elemental_cyan` 1×6 64×64) 가 alpha 가 균일해 격자 인식 실패 → sprite 오분류
* (LLM #3) **Gemma 분류 정확도** — `crown_icon` 같은 inventory item 이 character 로 잘못 분류, whitelist 위반 (`category='UI element'`) → 'other' demote

## 2. 결정 매트릭스

| 항목 | 작업량 | 효과 범위 | 마이그 | 채택 |
|---|---:|---|---|---|
| D-1: grid_detect 에 color-edge 분석 추가 | ~1.5일 | alpha 균일 시트 (effect 류, color-cycling) | 0 | ✅ |
| LLM #3: prompt 튜닝 + whitelist 확장 (UI/item 카테고리 추가) | ~1일 | inventory/UI 자산 분류 정확도 | seed 라벨 추가 | ✅ |
| Gemini 모델 업그레이드 (3.1-flash-lite → 3.1-flash) | ~0.2일 | 전반적 정확도 + 비용 ↑ | config 변경 | 보류 (M12 후보) |
| LabelRegistry seed 라벨 확장 (`crown` 같은 specific noun) | ~0.5일 | 사용자 라벨 관리 UI 로 충분 | 0 | 보류 |

**채택: D-1 + LLM #3 결합** (~2.5일).

## 3. Architecture — D-1 (grid_detect color-edge)

### 3.1 현재 알고리즘 한계

```python
# grid_detect.py 현재
arr = np.asarray(img.convert("RGBA"))
alpha = arr[..., 3]
col_sums = alpha.sum(axis=0)   # 알파 합으로 column 활동 측정
row_sums = alpha.sum(axis=1)
# 활동 valley → 격자 경계
```

`elemental_cyan` 처럼 alpha 채널이 모든 frame 에서 동일 (orb 형태 + 같은 위치) 한 경우 alpha 합이 평평한 모양 → valley 검출 실패.

### 3.2 강화안

color-edge (인접 frame 사이 색상 변화) 도 시그널로 합산:

```python
# 후보 알고리즘
rgb = arr[..., :3].astype(np.int16)
horizontal_diff = np.abs(rgb[:, 1:] - rgb[:, :-1]).sum(axis=-1)  # H,W-1
col_color_activity = horizontal_diff.sum(axis=0)  # W-1

# alpha + color 합성 시그널
col_signal = alpha_norm + alpha_color_weight * color_norm
```

`alpha_color_weight` cfg toggle (default 0.5).  alpha 강한 (캐릭터) 시트에선 alpha 우세, color-uniform 시트에선 color edge 가 시그널 제공.

### 3.3 frame_w 정확도 (D-2 와 별도)

D-2 (이미 적용됨, M11.3 PR) — `detect_sheet` 가 `stride_x` 사용해 sprite_meta.frame_w 의 slot 크기 정확도 확보.  M11.4 는 D-1 만 추가.

## 4. Architecture — LLM #3 (Gemma 분류 정확도)

### 4.1 현재 한계

* `validate_image_payload` 의 enum whitelist 가 좁아 `category=UI element`, `mood=neutral`, `palette=#FDD835` 같은 합리적 응답이 모두 'other' / [] 로 demote.
* `crown_icon` → category=character (Gemma 오분류 + whitelist 통과)

### 4.2 해소안

#### 4.2.1 카테고리 확장
LabelRegistry 시드에 `inventory_item`, `ui_icon`, `effect` 등 자주 보이는 카테고리 추가:

```python
LabelRegistry seed 'category' axis 확장:
  ['character', 'tile', 'effect', 'background',
   'inventory_item',  # 신규 — crown, sword, potion 등
   'ui_icon',         # 신규 — button, hud
   'other']
```

#### 4.2.2 mood 확장
`['heroic', 'dark', 'playful', 'minimalist', 'neutral']` — `neutral`/`minimalist` 추가.

#### 4.2.3 palette 토큰화
현재 hex string (`#FDD835`) 그대로 — 색상 hash 가 whitelist 등록 불가.  대안:

* 사전 분류된 톤 그룹 (`warm`/`cool`/`monochrome`/`high_contrast`/`pastel`) 으로 정규화
* prompt 에서 Gemma 가 hex 대신 톤 그룹 출력하도록 강제 (JSON schema 강화)

### 4.3 prompt 강화

`BATCH_IMAGE_PROMPT` + `BATCH_SPRITESHEET_PROMPT` 에 다음 가이드 추가:

```
- category: choose ONLY from: character, tile, effect, background, inventory_item, ui_icon, other
- palette: choose ONLY tone group names: warm, cool, monochrome, high_contrast, pastel, neutral
- mood: choose ONLY from the provided list
- For inventory items (crown, sword, potion, gem), use 'inventory_item' NOT 'character'
```

## 5. Module breakdown

### 5.1 신규 / 변경 파일

| 파일 | 변경 |
|---|---|
| `src/assetcache/core/sheet/grid_detect.py` | `_compute_col_signal` 분리 + `_uniform_frame_size` 가 color 시그널 합성 시 더 견고 |
| `src/assetcache/config.py` | `Config.grid_detect_alpha_color_weight: float = 0.5` 신설 |
| `src/assetcache/core/labels.py` 또는 seed JSON | category 시드 라벨 확장 (`inventory_item`, `ui_icon`), mood 시드 확장 |
| `src/assetcache/core/analyzer/messages.py` | `BATCH_IMAGE_PROMPT` + `BATCH_SPRITESHEET_PROMPT` 의 enum 명시 강화 + tone group 지시 |
| `src/assetcache/core/analyzer/payload_parser.py` | palette tone group whitelist (hex 거부) |
| `tests/test_sheet_grid_detect_color_edge.py` (신규) | color-edge 시트 검출 정확도 5~7 케이스 |
| `tests/test_label_registry_seed.py` (확장) | inventory_item / ui_icon 시드 확인 |
| `tests/test_analyzer_payload_parser.py` (확장) | tone group whitelist 통과/실패 |
| `tests/test_batch_image_prompt_inventory_item.py` (신규) | prompt 가 enum 명시하는지 |

## 6. Test strategy

### 6.1 신규 단위 테스트 (~20건)

| 파일 | 범위 | 케이스 |
|---|---|---:|
| `test_sheet_grid_detect_color_edge.py` | alpha 균일 + color-edge 만 있는 시트 검출 | 5 |
| `test_label_registry_seed.py` | inventory_item / ui_icon 시드 등록 | 3 |
| `test_analyzer_payload_parser.py` 확장 | tone group whitelist | 5 |
| `test_batch_image_prompt_inventory_item.py` | prompt enum 명시 + tone group 지시 | 4 |
| `test_analyzer_sprite_inventory_classification.py` | crown_icon 류 분류 | 3 |

### 6.2 회귀

* 기존 ~1559 + ~20 신규 → ~1579
* M11.3 회귀 0 유지

### 6.3 옵트인 (`pytest -m llm_integration`)

* `crown_icon`, `potion_icon` 류 inventory item 의 실 Gemini 분류 결과 검증 (+2 케이스)

## 7. Data shape

### 7.1 DB 변경 — 없음

* LabelRegistry seed 는 데이터 일뿐 schema 변경 0.

### 7.2 Config 변경

* `Config.grid_detect_alpha_color_weight: float = 0.5` (신규, 기본값 안전 fallback)

## 8. UI 변경

* `/labels` 페이지에 inventory_item / ui_icon 신규 라벨 자동 표시 (LabelRegistry 가 채움)
* 그 외 UI 변경 0

## 9. 알려진 한계 / 향후

| 항목 | 우선순위 | 후속 |
|---|---|---|
| Gemma 자체 분류 정확도 | 중 | M12 (모델 업그레이드 또는 prompt engineering) |
| hex palette 정확도 | 낮 | tone group 으로 우회 — hex 자체는 미사용 |
| 비균일 시트 (variable frame size) | 낮 | M16 (이미지 유사 검색) 와 함께 |

## 10. 다음 단계

1. 이 spec 사용자 검토
2. `milestones/M11_4_plan.md` 작성 (Phase 분할, TDD step)
3. `M11_4_todo.md` 체크리스트
4. Phase 별 TDD cycle
5. `M11_4_verification.md` — 복잡 시트 v2 의 elemental_cyan + crown_icon 재검증
6. PR → main → tag v0.2.3 → Trusted Publishing 자동 publish (6회째)

작업 단위 추정: **~2.5일** (D-1 1.5일 + LLM #3 1일, 신규 의존성 0, ~20 신규 테스트).
