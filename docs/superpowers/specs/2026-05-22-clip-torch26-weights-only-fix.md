# CLIP torch 2.6 `weights_only=True` 호환 fix

- **Spec ID**: `clip-torch26-weights-only-fix-2026-05-22`
- **Trigger**: M11.9 (PR #31, main `1c85eaf`) 머지 후 `python -m assetcache --tray --data-dir "$env:TEMP\m11-9-verify-data"` 첫 부팅 시 CLIP 모델 lazy load 시점에서 `RuntimeError` — pre-existing torch 2.6 + open_clip 비호환 (M11.9 무관)
- **Severity**: medium — sprite analyzer fallback (Ollama-only mode) 으로 동작 자체는 계속되지만, CLIP scoring 채널 (weight_semantic 0.35 + weight_label_match 0.20 = 55% 가중) 손실로 검색 정확도 크게 저하.
- **Branch**: `fix/clip-torch26-weights-only` (mini chore PR, v0.2.8 candidate 와 합쳐도 됨)
- **추정 작업 시간**: 0.5~1.5h (option 선택에 따라)

## 1. 재현

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```
```powershell
cd D:\ClaudeCowork\game-asset-helper\game-asset-helper
```
```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m assetcache --tray --data-dir "$env:TEMP\clip-repro-data"
```

→ 라이브러리에 sprite asset 1개 이상 있으면 부팅 후 첫 분석 시도에서 stack trace 출력.

또는 단위:

```powershell
pytest -m clip_integration -v
```

→ `clip_labeler.encode_text` / `score_image` 호출 시 fail (pre-existing 옵트인 마커).

## 2. Stack Trace (M11.9 verification 세션 캡처, 2026-05-22 19:06:09)

```
File "D:\...\src\assetcache\core\clip_labeler.py", line 138, in _ensure_loaded
    model, _, preprocess = open_clip.create_model_and_transforms(
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "C:\...\.venvs\gah\Lib\site-packages\open_clip\factory.py", line 510, in create_model
    load_checkpoint(
File "C:\...\.venvs\gah\Lib\site-packages\open_clip\factory.py", line 194, in load_checkpoint
    state_dict = load_state_dict(checkpoint_path, device=device, weights_only=weights_only)
File "C:\...\.venvs\gah\Lib\site-packages\open_clip\factory.py", line 164, in load_state_dict
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=weights_only)
File "C:\...\.venvs\gah\Lib\site-packages\torch\serialization.py", line 1547, in load
    raise RuntimeError(
RuntimeError: Cannot use ``weights_only=True`` with TorchScript archives passed to
``torch.load``. In PyTorch 2.6, we changed the default value of the `weights_only`
argument in `torch.load` from `False` to `True`.
```

## 3. Root Cause

| Layer | 상태 |
|---|---|
| **PyTorch** | `torch.load` default `weights_only=False` → `True` (PyTorch 2.6 changelog).  TorchScript archive 는 unpickle 가 아닌 zip → `weights_only=True` 와 즉시 비호환 |
| **open_clip** | `open_clip/factory.py:164` 에서 `torch.load(..., weights_only=weights_only)` 호출.  `weights_only` 의 기본값을 명시 안 함 — torch 의 새 default 가 그대로 전파 |
| **ViT-B-32.pt** | OpenAI 가 배포하는 pretrained 가 **TorchScript archive** (`.pt` 가 zip + pickle 혼합).  open_clip 의 `factory.py:194` 가 `torch.jit.load` fallback 을 시도하긴 하지만 (`load_checkpoint:line 198+`), 그 fallback 진입 전에 `load_state_dict` 의 `torch.load` 가 먼저 raise |
| **AssetCacheMCP `clip_labeler.py:138`** | `open_clip.create_model_and_transforms(self._model_name, pretrained=self._pretrained, **cache_kw)` 호출만 함 — `weights_only` 인자 expose 안 함 (open_clip API 의존) |

pyproject 의존성:
- `torch>=2.2` (open lower bound, no upper) → torch 2.6+ 자동 설치됨
- `open_clip_torch>=2.24` (open lower bound) → 현재 venv 의 open_clip 버전 확인 필요

## 4. Fix Options (4 viable)

### Option A — pyproject 의 `torch` upper bound 추가 (band-aid, 빠름)

```diff
-  "torch>=2.2",
+  "torch>=2.2,<2.6",
```

- **Pros**: 1 라인 diff, 즉시 효과, 사용자 venv 에서 `pip install -e . --upgrade` 한 줄로 복구.
- **Cons**: torch 2.6+ 신기능 (e.g., `torch.compile` 개선) 차단.  **torch 2.6 출시 시점이 언제인지 확인 필수** — 이미 GA 면 ecosystem 따라가야 함.
- **추정**: 0.5h (test + push).

### Option B — `open_clip_torch` upper / lower 재bound (Option A 대안)

open_clip 의 새 버전이 `weights_only=False` 강제 지원하는지 확인:

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pip index versions open_clip_torch
```

새 버전 release note 에 fix 가 명시돼 있으면:

```diff
-  "open_clip_torch>=2.24",
+  "open_clip_torch>=X.Y.Z",  # torch 2.6+ weights_only=True 호환
```

- **Pros**: ecosystem 따라감 (torch 최신 유지).
- **Cons**: open_clip 측 fix 가 published 됐는지 확인 필요.  사용자 venv reinstall 필요.
- **추정**: 0.5~1h (버전 확인 + test + push).

### Option C — `clip_labeler.py` 에서 `torch.load` monkey-patch (즉시 in-tree fix)

```python
# clip_labeler.py _ensure_loaded 첫 줄
import torch
_orig_load = torch.load
torch.load = lambda *a, **kw: _orig_load(*a, **{**kw, "weights_only": False})
try:
    model, _, preprocess = open_clip.create_model_and_transforms(...)
finally:
    torch.load = _orig_load
```

- **Pros**: 의존성 변경 없음, 의도 명시적.
- **Cons**: ⚠️ **보안 위험** — `weights_only=False` 가 임의 pickle 코드 실행.  pretrained 모델이 신뢰된 source (`openai`) 라 실용적으로 안전하지만 — 일반 사용자 환경에서 monkey-patch 가 노출되면 다른 `torch.load` 호출까지 영향.  `try/finally` 로 좁히지만 thread-safety / re-entrance 한계.
- **추정**: 1h (test + 보안 주석 + push).

### Option D — `open_clip` 우회 + `torch.jit.load` 직접 (clean fix)

`clip_labeler.py` 가 open_clip API 우회하고 torch.jit.load 로 ViT-B-32 직접 로드.

- **Pros**: torch + open_clip 양쪽 의존성 모두 자유.
- **Cons**: open_clip 의 preprocess / tokenizer 도 따로 재구성 필요 — diff 큼.  ViT-B-32 외 다른 backbone (M11/M12 후속) 도 손봐야 함.
- **추정**: 1.5h+ (refactor + test).

### Recommended Path

**Option B first** — open_clip 의 새 버전이 fix 됐는지 확인.  됐으면 그게 가장 깨끗 (의존성 1줄 갱신).

안 됐으면 **Option A (torch<2.6 pin)** + 별 follow-up issue 로 open_clip upstream fix 트래킹.

Option C/D 는 위 두 옵션이 다 막혔을 때만 검토.

## 5. Acceptance Criteria

- [ ] `pytest -m clip_integration -v` PASSED (옵트인 CLIP 통합 테스트).  현재 fail.
- [ ] `python -m assetcache --tray --data-dir "$env:TEMP\clip-fix-data"` 부팅 후 sprite asset 1개 있는 라이브러리에서 첫 분석 시 CLIP scoring 정상 (stack trace 0).
- [ ] 회귀 `pytest -q` PASSED (M11.9 baseline `1560 passed + 1 skipped + 57 deselected` 유지).
- [ ] pyproject.toml 또는 clip_labeler.py 의 fix 1 줄~수 줄 — diff 최소화.
- [ ] 마일스톤 verification doc 1 파일 (mini chore — milestone 정식 plan/todo 생략 가능).

## 6. Test Plan

1. Reproduction case 캡처 (`.omc/logs/clip-repro-baseline.log`)
2. Option B 시도: `pip index versions open_clip_torch` + 최신 release note 읽기.  fix 있으면 → 의존성 bump → reinstall → repro 재실행 → PASSED 검증.
3. Option B 막히면 Option A: pyproject `torch<2.6` 추가 → `pip install -e . --force-reinstall --no-deps` + `pip install -e .` → repro PASSED.
4. 회귀 `pytest -q` → 1560 유지.
5. 옵트인 `pytest -m clip_integration -v` → PASSED.
6. 트레이 부팅 + sprite asset 분석 → CLIP scoring 동작 (Gemini 첫 호출 / Ollama embed 직후 CLIP 채널 점수가 음수 아닌 0+값).

## 7. Out of Scope

- M11/M12 후속 backbone (ViT-L/14 등) 지원 — 현재 ViT-B-32 단독.
- 모델 캐시 경로 변경 / cache 무효화.
- Gemini embedding fallback 조정 — M11.9 와 무관.

## 8. Open Questions

- torch 2.6 GA 시점 + open_clip upstream fix PR 존재 여부 — 다음 세션 Phase 0 에서 `pip index versions` + GitHub issue 검색.
- v0.2.8 publish 시점에 본 fix 를 묶을지 (M11.9 + CLIP fix 같이) 별도 v0.2.9 candidate 로 분리할지 — 사용자 결정.

## 9. References

- PyTorch 2.6 changelog (weights_only default switch): https://pytorch.org/blog/pytorch-2-6/
- open_clip factory.py (issue source): https://github.com/mlfoundations/open_clip/blob/main/src/open_clip/factory.py
- AssetCacheMCP `clip_labeler.py:138` (call site)
