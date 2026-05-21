# M11.5 검증 — LIVE validation + tuning patches (v0.2.4 candidate)

## 0. 본 문서의 위치

- 상위 spec: [`docs/superpowers/specs/2026-05-21-m11-5-live-validation-and-tuning.md`](../docs/superpowers/specs/2026-05-21-m11-5-live-validation-and-tuning.md)
- 상위 plan: [`M11_5_plan.md`](./M11_5_plan.md)
- 전제: [PR #21](https://github.com/v0o0v/assetcache-mcp/pull/21) M11.4 main 머지 (`7794d48`) + (선택) v0.2.3 PyPI publish
- 본 문서는 **Phase 1 LIVE 검증 (gate) → Phase 2/4 분기 → 조건부 Phase 3/5/6 → Phase 7 wrap-up** 흐름의 결과를 누적한다.

## 1. 자동 baseline

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected (Phase 1 진입 시점): **1592 passed + 1 skipped + 59 deselected** (M11.4 main `7794d48` baseline 그대로).

상태: ✅ 2026-05-22 재현 — `1592 passed, 1 skipped, 59 deselected in 81.94s`.  Phase 진행에 따라 신규 테스트 합산.

## 2. LIVE 검증 셋업 (Phase 1 gate)

### 2.1 합성 자산 생성

`scripts/make_complex_sheets.py` 가 M11.3 LIVE v2 의 6 자산을 재현한다 (Aseprite/TexturePacker 외부 라이선스 자산 없이도 검증 가능).

```powershell
$libDir = "$env:TEMP\m11_5_verify_data\library\m113_complex"
```

```powershell
Remove-Item -Recurse -Force "$env:TEMP\m11_5_verify_data" -ErrorAction SilentlyContinue
```

```powershell
New-Item -ItemType Directory -Path $libDir -Force | Out-Null
```

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" scripts/make_complex_sheets.py $libDir
```

→ 8 파일 생성 (6 PNG + 2 Aseprite JSON sidecar).

### 2.2 detect_sheet smoke 결과 (LLM 호출 전)

`scripts/make_complex_sheets.py` 검증 시 detect_sheet 결과:

| 자산 | source | frames | frame_w/h | tags |
|---|---|---:|---|---|
| hero_warrior | json | 16 | 64/64 | idle/walk/attack/hurt |
| mage_purple | json | 12 | 48/48 | cast/idle/walk |
| knight_gold | grid | 8 | 32/32 (stride) | — |
| monster_red | grid | 4 | 48/48 (stride) | — |
| **elemental_cyan** | **grid** | **6** | **64/64** | — ← **M11.4 D-1 color-edge fallback 작동 확인** |
| crown_icon | None | — | — | (single sprite) |

→ M11.3 LIVE v2 에서 sprite 로 떨어졌던 elemental_cyan 이 detect 단계에서 spritesheet 로 promote 됨. Phase 2 (#2 AXIS_SPAN_RATIO 튜닝) 의 트리거 여부는 batch chat_image 분류 단계까지 가야 최종 확정.

### 2.3 tray 부팅 + LIVE Gemini 배치

사용자가 직접 실행 (GEMINI_API_KEY 보유):

```powershell
$env:GEMINI_API_KEY = "AIza..."
```

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m assetcache --tray --data-dir "$env:TEMP\m11_5_verify_data"
```

`/settings` 에서:
- `chains.chat_image = ["gemini"]`, `chains.chat_spritesheet = ["gemini"]`
- `batch.toggle = "forced_on"`

자동 sweep 종료 후 SQL 측정:

```powershell
sqlite3 "$env:TEMP\m11_5_verify_data\metadata.db" "SELECT a.name, a.kind, m.frame_w, m.frame_h, m.frame_count FROM assets a LEFT JOIN sprite_meta m ON m.asset_id=a.id WHERE a.kind IN ('sprite','spritesheet') ORDER BY a.id"
```

```powershell
sqlite3 "$env:TEMP\m11_5_verify_data\metadata.db" "SELECT a.name, l.axis, l.label FROM asset_labels l JOIN assets a ON a.id=l.asset_id WHERE l.axis IN ('category','palette','mood','animation') ORDER BY a.name, l.axis"
```

## 3. LIVE 결과 표 (Phase 1 gate)

| # | 자산 | M11.4 기대 | LIVE 결과 | 분기 |
|---:|---|---|---|---|
| 1 | elemental_cyan | kind=spritesheet, 6 frame | TBD | sprite 면 → Phase 3 (#2 AXIS_SPAN_RATIO 튜닝) |
| 2 | crown_icon | category ∈ {inventory_item, item, icon} | TBD | character 면 → M12 (모델 업그레이드) trigger |
| 3 | hero_warrior | category=character, 4 anim 라벨 | TBD | regression 0 여부 |
| 4 | mage_purple | category=character, 3 anim 라벨 | TBD | regression 0 |
| 5 | knight_gold | kind=spritesheet, frame_w=32 (D-2 stride) | TBD | M11_3_verification 의 "17/28" 은 D-2 적용 전 결과 — D-2 적용 후 32 가 정상 |
| 6 | monster_red | kind=spritesheet, 4 frame | TBD | regression 0 |
| 7 | palette 응답 분포 | hex 0건 + tone group 안 | TBD | hex 가 있으면 prompt 추가 강화 (Phase 6 trigger) |

## 4. Phase 2 / 4 분기 결정 매트릭스

`§3` 의 LIVE 결과를 보고 채우는 표.

| trigger | 조건 | 진입 Phase | 산출물 |
|---|---|---|---|
| #1 elemental_cyan sprite 유지 | LIVE 결과 #1 = sprite | Phase 3 (AXIS_SPAN_RATIO 튜닝) | `core/sheet/grid_detect.py` ratio 조정 또는 std-검증 |
| #1 elemental_cyan spritesheet 통과 | LIVE 결과 #1 = spritesheet | Phase 3 skip | — |
| #2 crown_icon character 유지 | LIVE 결과 #2 = character | M12 spec trigger (별 마일스톤) | M11.5 범위 밖 |
| #2 crown_icon inventory_item 통과 | LIVE 결과 #2 ∈ acceptable | Phase 5 (acceptable set strict) 진입 가능 | `tests/.../inventory_item_integration.py` strict |
| #7 palette hex 검출 | LIVE 응답에 `#XXXXXX` 라벨 | Phase 6 (palette narrow + prompt 강화) | `core/labels.py` 시드 narrow + `messages.py` hex 강조 |
| #7 palette tone group 응답 | `vibrant`/`saturated`/`muted` 빈도 高 | Phase 6 strict | 동일 |
| #3~#6 regression 발견 | 변경 0 가정 깨짐 | Phase 7 별 patch | 회귀별 trace |

## 5. Phase 3 — AXIS_SPAN_RATIO 튜닝 (조건부, TBD)

LIVE 결과 #1 = sprite 일 때만 진입.  현재 가설:

* `_AXIS_SPAN_RATIO=0.8` ratio 조정 (0.7 / 0.75 / 0.85 sweep)
* 또는 boundary 후보 row 별 diff 의 표준편차 임계 도입 (object 만 변화 → std 高, 균일 색 경계 → std 低)

신규 테스트 ~3 (sweep 케이스 + std 검증).

## 6. Phase 5 — llm_integration acceptable set strict (조건부, TBD)

LIVE 결과 #2 통과 후 1회 strict 화:

* crown: `{inventory_item, item}` (icon/ui_icon/other 제거)
* ui_button: `{ui_icon, ui}` (inventory_item/icon/other 제거)

옵트인 `pytest -m llm_integration` 가 strict set 으로 통과해야 PR 머지.

## 7. Phase 6 — palette tone-group narrow (조건부, TBD)

LIVE 응답 분포 본 후 결정:

* **strict 채택 조건**: `vibrant`/`saturated`/`muted`/`desaturated`/`dark`/`light`/`earthy` 중 prompt 외 토큰 빈도 < 5% (Gemini 가 prompt enum 만 사용)
* **strict 채택 시 작업**: 시드 7 토큰 `is_enabled=0` 마이그 (delete 안 함, 기존 라벨 보호), `label_catalog_signature` 변경 확인
* **prompt 강화** (별도): `BATCH_IMAGE_PROMPT` 에 hex 예시 늘리기 + tone group 가이드 강화

신규 테스트 ~3.

## 8. 알려진 한계 (M11.5 범위 밖)

| 항목 | 상태 | 후속 |
|---|---|---|
| Gemini 모델 업그레이드 (3.1-flash-lite → 3.1-flash) | M12 별 spec | LIVE 결과 #2 = character 일 때 trigger |
| BATCH_SPRITESHEET_PROMPT category 강제 완화 (multi-frame inventory) | M12+ 별 마일스톤 | 회전 coin 등 요구 시점 |
| `make_complex_sheets.py` 자산이 합성 픽셀 아트 → 실 게임 자산 분포와 차이 가능 | M11.5 범위 밖 | 사용자 라이브러리로 별도 검증 권장 |

## 9. Phase 7 — 회귀 + verification + PR (검증 완료 후)

1. 전체 회귀 통과:
   ```powershell
   & "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
   ```
   → `1592 + (Phase 별 신규)` passed 확인.
2. PR → main 머지.
3. `pyproject.toml` + `src/assetcache/__init__.py` 0.2.2 → 0.2.4 bump 커밋.
   (v0.2.3 publish 보류했으므로 0.2.3 결번 — v0.2.1 와 같은 패턴, [HISTORY](./HISTORY.md) 의 "Trusted Publishing 패턴" 참조.)
4. tag + push:
   ```powershell
   git tag v0.2.4
   ```
   ```powershell
   git push origin v0.2.4
   ```
5. Trusted Publishing OIDC workflow 자동 트리거 — 7회째 자동 publish (평균 30초).
6. [PyPI v0.2.4 publish 확인](https://pypi.org/project/assetcache-mcp/) + GitHub release 자동 생성 확인.

## 10. 현재 진행 상태 (2026-05-22)

| Phase | 상태 |
|---|---|
| 1 — LIVE 검증 (gate) | 🟡 자산 생성 + detect_sheet smoke 완료, **사용자 GEMINI_API_KEY + tray 실행 단계 대기** |
| 2 — 분기 결정 | ⏸ Phase 1 결과 대기 |
| 3 — AXIS_SPAN_RATIO 튜닝 | ⏸ 조건부 |
| 5 — llm_integration strict | ⏸ 조건부 |
| 6 — palette narrow | ⏸ 조건부 |
| 7 — PR + tag | ⏸ Phase 3/5/6 종료 후 |
