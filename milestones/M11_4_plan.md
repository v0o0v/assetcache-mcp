# M11.4 Plan — grid_detect 강화 + LLM 분류 정확도 (v0.2.3 candidate)

## 0. 본 plan 의 위치

- 상위 spec: [`docs/superpowers/specs/2026-05-21-m11-4-grid-detect-strengthen-llm-accuracy.md`](../docs/superpowers/specs/2026-05-21-m11-4-grid-detect-strengthen-llm-accuracy.md)
- 전제: [PR #20](https://github.com/v0o0v/assetcache-mcp/pull/20) M11.3 main 머지 + v0.2.2 publish 완료
- 본 plan 은 **starter** — 다음 세션에서 `superpowers:writing-plans` 로 확장 또는 직접 TDD.

## 1. 목표

M11.3 LIVE 검증 v2 에서 발견된 두 한계 해소:

* **D-1**: `elemental_cyan` 처럼 alpha 균일 + color-cycling 시트가 sprite 로 오분류되는 grid_detect 한계
* **LLM #3**: `crown_icon` 류 inventory item 이 character 로 잘못 분류 + UI element / neutral palette 같은 반복적 whitelist 위반

## 2. 산출물

| # | 산출물 | 비고 |
|---:|---|---|
| 1 | `core/sheet/grid_detect.py` — alpha + color edge 합성 시그널 | color-cycling 시트 검출 |
| 2 | `core/config.py` — `grid_detect_alpha_color_weight: float = 0.5` 신설 | toggle 가능 |
| 3 | LabelRegistry seed 확장 — `inventory_item`, `ui_icon` category + `neutral`/`minimalist` mood | M2 시드 |
| 4 | `core/analyzer/messages.py` — BATCH_IMAGE_PROMPT / BATCH_SPRITESHEET_PROMPT 의 enum 명시 강화 + palette tone group 지시 | LLM 응답 정확도 |
| 5 | `core/analyzer/payload_parser.py` — palette tone group whitelist (hex 거부 + 정규화) | 누락된 hex 거부 |
| 6 | `tests/test_sheet_grid_detect_color_edge.py` (신규, ~5) | D-1 단위 |
| 7 | `tests/test_label_registry_seed.py` (확장, ~3) | seed 확장 |
| 8 | `tests/test_analyzer_payload_parser.py` (확장, ~5) | tone group whitelist |
| 9 | `tests/test_batch_image_prompt_inventory_item.py` (신규, ~4) | prompt enum 명시 |
| 10 | `tests/test_analyzer_sprite_inventory_classification.py` (신규, ~3) | sync 분류 회귀 |
| 11 | `milestones/M11_4_verification.md` — elemental_cyan + crown_icon 재검증 | LIVE |

## 3. Phase 분할 (얇은 starter)

### Phase 1 — D-1 grid_detect color-edge

* `grid_detect.py` 의 `_compute_col_signal` 분리
* color edge (인접 column RGB 차이의 합) 시그널 추가
* `Config.grid_detect_alpha_color_weight` 신설 + 합성
* 신규 5 테스트 (alpha 균일 + color-cycling 검출)

### Phase 2 — LabelRegistry seed 확장

* M2 시드 JSON / 코드의 category / mood 확장
* 기존 데이터 마이그 영향 평가 (사용자가 'other' 라벨 가진 경우 자동 재분류 X)
* 신규 3 테스트

### Phase 3 — prompt + payload_parser tone group

* `BATCH_*_PROMPT` 에 enum + tone group 명시
* `validate_image_payload` 의 palette whitelist 를 tone group set 으로 변경
* hex 응답은 'neutral' 또는 None 으로 fallback
* 신규 5 + 4 = 9 테스트

### Phase 4 — sync 분류 회귀 + 옵트인

* `SpriteAnalyzer` 의 enum 명시 강화도 동일 적용 (sync/batch parity)
* 신규 3 테스트 (sync inventory_item 분류)
* `pytest -m llm_integration` 에 2 케이스 추가 (실 Gemini 호출)

### Phase 5 — 회귀 + verification + PR

* 전체 회귀 `pytest -q` 통과 (1559 + ~20)
* `M11_4_verification.md` — make_complex_sheets.py 의 elemental_cyan + crown_icon 재검증 LIVE
* PR → main 머지 → tag v0.2.3 → Trusted Publishing 자동 publish (6회째)

## 4. 작업 시간 추정

- Phase 1: 0.5일
- Phase 2: 0.3일
- Phase 3: 0.7일
- Phase 4: 0.5일
- Phase 5: 0.5일
- **합계 ~2.5일**

## 5. 시작 명령

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```

```powershell
cd D:\ClaudeCowork\game-asset-helper\game-asset-helper
```

```powershell
git checkout main
```

```powershell
git pull
```

```powershell
git checkout -b feat/m11-4-grid-detect-strengthen
```

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

→ 베이스라인 1559+ 확인 후 Phase 1 부터.

## 6. 검증 시나리오 (M11_4_verification.md 후보)

| # | 자산 | 기대 결과 | M11.3 결과 |
|---:|---|---|---|
| 1 | elemental_cyan (1×6 64×64) | kind=spritesheet (D-1 효과) | kind=sprite ⚠ |
| 2 | crown_icon (32×32) | category=inventory_item (LLM #3 효과) | category=character ⚠ |
| 3 | UI 버튼 시트 (신규 자산) | category=ui_icon | n/a |
| 4 | knight_gold (32×32, 1×8) | frame_w=32 (M11.3 D-2 그대로) | frame_w=32 ✓ |
| 5 | mage_purple (Aseprite) | animations_json 유지 | ✓ |

검증 자산은 `make_complex_sheets.py` + 신규 UI 버튼 자산 1~2 추가.
