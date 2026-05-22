# CLIP torch 2.6 `weights_only=True` fix — Verification

- **Spec**: [`2026-05-22-clip-torch26-weights-only-fix.md`](./2026-05-22-clip-torch26-weights-only-fix.md)
- **Branch**: `fix/clip-torch26-weights-only`
- **Base**: main `1c85eaf` (M11.9 PR #31 squash 머지 후)
- **Verification 시각**: 2026-05-22

## 1. 자동 검증

### 1.1 회귀 (`pytest -q`)

| 시점 | Command | 결과 |
|---|---|---|
| Pre-fix baseline | `pytest -q` (브랜치 `fix/clip-torch26-weights-only`, edit 직후) | `1560 passed, 1 skipped, 57 deselected` (M11.9 baseline 정확 일치) |
| Post-fix 회귀 | 동일 — fix 가 FakeBackend 경로 영향 0 (unit suite default) | `1560 passed, 1 skipped, 57 deselected` |

**회귀 신규 0건** — `weights_only=False` 인자 추가가 unit suite 의 `FakeBackend` 경로에 영향 미치지 않음을 확인.

### 1.2 옵트인 CLIP integration (`pytest -m clip_integration -v`)

| 시점 | Command | 결과 |
|---|---|---|
| Pre-fix (reproduction) | `pytest -m clip_integration -v` (수정 전, spec §1 stack trace 참조) | `RuntimeError: Cannot use weights_only=True with TorchScript archives` (pre-existing) |
| Post-fix | `pytest -m clip_integration -v` (edit 후) | **2 passed, 1616 deselected in 31.23s** |

테스트 케이스 (둘 다 PASSED):
- `test_open_clip_backend_init_does_not_download_until_called` ✅ — lazy init 확인 (다운로드 X)
- `test_open_clip_backend_actual_inference` ✅ — 실제 ViT-B-32 다운로드 + `encode_image` 호출 → fix 검증의 핵심

**핵심 신호 — open_clip warning**:

```
UserWarning: 'torch.load' received a zip file that looks like a TorchScript
archive dispatching to 'torch.jit.load' (call 'torch.jit.load' directly to
silence this warning)
  checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=weights_only)
```

→ `weights_only=False` 가 인자로 전파된 후, torch 가 zip 형태(=TorchScript archive)임을 감지하고 `torch.jit.load` 로 자동 dispatch.  이전 `weights_only=True` 였을 때는 동일 위치에서 `RuntimeError` raise — fix 의 정상 동작 확인.

### 1.3 `weights_only` 전달 체인 (decision doc §4)

`clip_labeler.py:138` 의 `create_model_and_transforms(..., weights_only=False, ...)` 가 open_clip 3.3.0 factory 체인을 통해 `torch.load(..., weights_only=False)` 까지 전파됨을 코드 추적으로 확인:

```
create_model_and_transforms(weights_only=False)   # factory.py:984
  → create_model(weights_only=False)               # factory.py:949
    → load_checkpoint(weights_only=False)          # factory.py:514
      → load_state_dict(weights_only=False)        # factory.py:194
        → torch.load(..., weights_only=False)      # factory.py:164
```

→ TorchScript archive 도 `weights_only=False` 면 unpickle 정상 동작.

### 1.4 의존성 변화

- pyproject.toml 변경 **0건** (Option B/A 모두 불가 → Option C 변형 코드 1줄로 해소).
- `pip install` / reinstall 필요 **없음**.
- venv 기준: `torch 2.12.0` + `open_clip_torch 3.3.0` 유지.

## 2. 산출물

- `src/assetcache/core/clip_labeler.py:138-145` — `weights_only=False` 인자 + 6 라인 주석 (spec 참조 포함)
- `docs/superpowers/specs/2026-05-22-clip-torch26-weights-only-fix.md` — spec (M11.9 verification 세션에서 작성)
- `docs/superpowers/specs/2026-05-22-clip-torch26-weights-only-fix-verification.md` — 본 doc
- `.omc/research/clip-fix-decision.md` — Option B/A/C 가능성 조사 (document-specialist 산출물)
- HANDOFF.md — M11.9 PR #31 머지 후 wrap-up + CLIP fix 다음 작업 안내 갱신

## 3. 사용자 수동 검증 (LIVE)

수정 후 사용자가 트레이 부팅 + sprite 분석을 직접 확인해주세요.

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```
```powershell
cd D:\ClaudeCowork\game-asset-helper\game-asset-helper
```
```powershell
git checkout fix/clip-torch26-weights-only
```
```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m assetcache --tray --data-dir "$env:TEMP\clip-fix-data"
```

**기대 결과**:
- [ ] 트레이 부팅 stack trace 0건
- [ ] sprite asset 1개 이상 있는 라이브러리에서 분석 트리거 후 `RuntimeError: Cannot use weights_only=True` 메시지 발생 0건
- [ ] CLIP scoring 채널 정상 동작 (weight_semantic 0.35 + weight_label_match 0.20 = 55% 가중치) — `metadata.db` 의 `clip_label_cache` 테이블에 vector 행 누적 확인 (옵션)

## 4. 알려진 한계

- ViT-L/14 등 다른 backbone 으로 전환 시 동일 weights_only 인자 전달 형태가 유효한지 재검증 필요 (현재는 `ViT-B-32:openai` 단독 사용 — spec §7 Out of Scope).
- pickle 신뢰 — `weights_only=False` 가 임의 pickle 코드를 실행할 수 있음.  OpenAI 공식 checkpoint 라 실용적 안전, 그러나 사용자 환경에서 cache 경로를 가로채는 attacker 가 있다면 위험.  추가 보안 조치 (signature 검증) 는 별도 backlog.

## 5. 후속 작업 (별도 트리거)

- (선택) v0.2.8 publish — `pyproject.toml` + `src/assetcache/__init__.py` 0.2.7 → 0.2.8 bump + tag (M11.9 backend 정리 + 본 CLIP fix 동시 deliver, memory `feedback_commit_push_pr_auto_publish_manual` — 사용자 명시).
- (옵션) open_clip upstream 에 `except RuntimeError` fallback PR 제출 — 본 fix 가 호출 측 우회라 upstream 정식 fix 가 published 되면 인자 제거 가능.
