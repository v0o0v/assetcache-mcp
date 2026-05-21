# M11.2 — Batch Spritesheet Modality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Spritesheet 자산도 batch 50% 비용 절감을 받도록 `chat_spritesheet` modality 신설 + 8칸 합성 strip + 시트 전용 prompt 로 sync `SpritesheetAnalyzer` 와 동등한 라벨/메타 생성.

**Architecture:** `chat_image` modality 의 kind 필터를 `("sprite",)` 로 좁히고 신규 `chat_spritesheet` modality 가 `("spritesheet",)` 를 담당한다. `BatchManager.try_submit("chat_image")` 가 fetch 단계에서 `classify_image_assets` 로 시트를 식별 → DB 의 `kind` 를 `spritesheet` 로 promote (다음 sweep 에서 `chat_spritesheet` 가 픽업). `try_submit("chat_spritesheet")` 는 시트 전용 builder (composite strip + `BATCH_SPRITESHEET_PROMPT`) 로 batch 제출. BatchPoller 의 신규 `_persist_spritesheet_payload` 가 sync `_call_gemma` 의 `animation_hint` 경로와 동등한 결과 (frame 박스 + frameTags + Gemma 추측 라벨) 를 DB 에 저장.

**Tech Stack:** Python 3.12 / FastAPI / SQLite / Pillow / google-genai SDK (Gemini Batch API) / Babel gettext.

**Pre-flight:** main `12ebc42` 기준 baseline `pytest -q` = **1490 passed + 3 skipped + 56 deselected**. 신규 의존성 0. 예상 신규 테스트 ~40.

---

## 0. 시작 절차

- [ ] **Step 0.1: 환경 활성화**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\Activate.ps1"
```

- [ ] **Step 0.2: main 동기화 + baseline 확인**

```powershell
git checkout main
```

```powershell
git pull
```

```powershell
pytest -q
```

Expected: `1490 passed, 3 skipped, 56 deselected`.

- [ ] **Step 0.3: feature branch**

```powershell
git checkout -b feat/m11-2-batch-spritesheet-modality
```

---

## Phase 1 — Modality 분리 (store / config / chain / registry)

`chat_image` 의 kind 필터를 `("sprite",)` 로 좁히고 `chat_spritesheet` modality 를 자료 구조에 추가. Chain 은 `chat_spritesheet` 를 chat_image 와 동일 capability 로 취급, 사용자 config 에 누락 시 chat_image 로 자동 fallback.

### Task 1.1: Store `_MODALITY_KIND_FILTER` 분리

**Files:**
- Modify: `src/assetcache/core/store.py:448-452`
- Test: `tests/test_store_modality_kind_filter.py` (신규)

- [ ] **Step 1.1.1: 실패 테스트 작성**

신규 파일 `tests/test_store_modality_kind_filter.py`:

```python
"""M11.2 — chat_image 가 sprite 만, chat_spritesheet 가 spritesheet 만 잡는지 확인."""

import pytest

from assetcache.core.store import Store


def _seed(store, *, sprites: int, sheets: int, sounds: int):
    """packs/assets 시드 — pending 상태."""
    pack_id = store.add_pack(
        name="t", display_name="t", vendor=None, source_url=None,
        license=None, description=None,
    )
    now = 0
    aid = 0
    for kind, count in (("sprite", sprites), ("spritesheet", sheets), ("sound", sounds)):
        for i in range(count):
            store.add_asset(
                pack_id=pack_id,
                path=f"{kind}/{i}.png",
                kind=kind,
                file_hash=f"h{aid}",
                file_size=10,
                added_at=now,
            )
            aid += 1


def test_count_pending_chat_image_only_includes_sprite(tmp_path):
    """chat_image 카운트가 spritesheet 를 포함하면 안 됨."""
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    assert store.count_pending_by_modality("chat_image") == 3


def test_count_pending_chat_spritesheet_only_includes_spritesheet(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    assert store.count_pending_by_modality("chat_spritesheet") == 4


def test_count_pending_chat_audio_unchanged(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    assert store.count_pending_by_modality("chat_audio") == 2


def test_count_pending_text_embed_unchanged(tmp_path):
    """text_embed 는 dict 에 없으므로 모든 kind 카운트."""
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    assert store.count_pending_by_modality("text_embed") == 9


def test_fetch_pending_chat_spritesheet_returns_only_spritesheet_rows(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.initialize()
    _seed(store, sprites=3, sheets=4, sounds=2)
    rows = store.fetch_pending_by_modality("chat_spritesheet", limit=100)
    assert len(rows) == 4
    assert {r.kind for r in rows} == {"spritesheet"}
```

- [ ] **Step 1.1.2: 실패 확인**

Run: `pytest tests/test_store_modality_kind_filter.py -v`
Expected: 5 FAIL — `chat_image` 카운트가 7 (= 3 sprite + 4 spritesheet) 로 나옴, `chat_spritesheet` 키 없어서 default 동작 (모든 kind 카운트 → 9).

- [ ] **Step 1.1.3: 구현 — `_MODALITY_KIND_FILTER` 분리**

`src/assetcache/core/store.py:448-452`:

```python
_MODALITY_KIND_FILTER: dict[str, tuple[str, ...]] = {
    "chat_image": ("sprite",),
    "chat_spritesheet": ("spritesheet",),
    "chat_audio": ("sound",),
    # text_embed → 모든 kind (dict 에 없으면 kind 필터 미적용)
}
```

- [ ] **Step 1.1.4: 테스트 통과 확인**

Run: `pytest tests/test_store_modality_kind_filter.py -v`
Expected: 5 PASS.

- [ ] **Step 1.1.5: 회귀 영향 확인**

Run: `pytest tests/test_store.py tests/test_batch_*.py -q`
Expected: 회귀 0. 만약 `chat_image` 가 spritesheet 를 포함한다고 가정한 기존 테스트가 깨지면 해당 테스트를 새 의미에 맞게 갱신 (이전: 시트도 chat_image 로 처리 → 이제: 시트는 chat_spritesheet 로 분리). 새 의미가 옳음.

### Task 1.2: Config `_VALID_CHAIN_MODALITIES` + `_default_chains` 확장

**Files:**
- Modify: `src/assetcache/config.py:89` (`_VALID_CHAIN_MODALITIES`)
- Modify: `src/assetcache/config.py:144-149` (`_default_chains`)
- Test: `tests/test_config.py` (기존 파일 — 신규 케이스 append)

- [ ] **Step 1.2.1: 실패 테스트 추가**

`tests/test_config.py` 끝에 append:

```python
def test_default_chains_includes_chat_spritesheet():
    """기본 chains 에 chat_spritesheet 가 등록되어 있어야 — chat_image 와 동일 순서."""
    from assetcache.config import Config

    cfg = Config()
    assert "chat_spritesheet" in cfg.chains
    assert cfg.chains["chat_spritesheet"] == cfg.chains["chat_image"]


def test_from_mapping_accepts_chat_spritesheet_chain():
    """사용자가 chat_spritesheet 를 명시하면 그대로 저장."""
    from assetcache.config import Config

    cfg = Config.from_mapping({
        "chains": {"chat_spritesheet": ["gemini", "ollama"]},
    })
    assert cfg.chains["chat_spritesheet"] == ["gemini", "ollama"]


def test_from_mapping_chat_spritesheet_defaults_to_chat_image_when_absent():
    """사용자 config 에 chat_spritesheet 가 없으면 chat_image 와 동일 chain 으로 fallback."""
    from assetcache.config import Config

    cfg = Config.from_mapping({
        "chains": {"chat_image": ["gemini", "ollama"]},
    })
    assert cfg.chains["chat_spritesheet"] == ["gemini", "ollama"]
```

- [ ] **Step 1.2.2: 실패 확인**

Run: `pytest tests/test_config.py -k chat_spritesheet -v`
Expected: 3 FAIL — `chat_spritesheet` 키가 chains 에 없음.

- [ ] **Step 1.2.3: 구현 — `_VALID_CHAIN_MODALITIES` 확장**

`src/assetcache/config.py:89`:

```python
_VALID_CHAIN_MODALITIES = ("chat_image", "chat_spritesheet", "chat_audio", "text_embed")
```

- [ ] **Step 1.2.4: 구현 — `_default_chains` 갱신**

`src/assetcache/config.py:144-149`:

```python
def _default_chains() -> dict[str, list[str]]:
    return {
        "chat_image": ["ollama"],
        "chat_spritesheet": ["ollama"],
        "chat_audio": ["ollama"],
        "text_embed": ["ollama"],
    }
```

- [ ] **Step 1.2.5: 구현 — `from_mapping` 에 chat_spritesheet fallback 추가**

`src/assetcache/config.py:312-318` 의 `chains` 처리 블록을 다음으로 교체:

```python
        chains = _default_chains()
        data_chains = data.get("chains") or {}
        if isinstance(data_chains, dict):
            for modality, order in data_chains.items():
                if modality in _VALID_CHAIN_MODALITIES and isinstance(order, list):
                    chains[modality] = [str(x) for x in order]
        # chat_spritesheet 미지정 시 chat_image 와 동일 chain 으로 fallback
        if "chat_spritesheet" not in (data_chains if isinstance(data_chains, dict) else {}):
            chains["chat_spritesheet"] = list(chains["chat_image"])
        filtered["chains"] = chains
```

- [ ] **Step 1.2.6: 테스트 통과 확인**

Run: `pytest tests/test_config.py -k chat_spritesheet -v`
Expected: 3 PASS.

Run: `pytest tests/test_config.py -q`
Expected: 전체 PASS (기존 회귀 0).

### Task 1.3: Chain `_eligible` 에 chat_spritesheet 추가

**Files:**
- Modify: `src/assetcache/core/llm/chain.py:21,29-40`
- Modify: `src/assetcache/core/llm/registry.py:20`
- Test: `tests/test_llm_chain.py` (기존 파일 — append) 또는 새 `tests/test_llm_chain_spritesheet.py`

- [ ] **Step 1.3.1: 실패 테스트 작성**

신규 파일 `tests/test_llm_chain_spritesheet.py`:

```python
"""M11.2 — chat_spritesheet modality 가 chat_image 와 동일 capability 로 처리되는지."""

from unittest.mock import MagicMock

import pytest

from assetcache.core.llm.base import BackendError, ChatMessage
from assetcache.core.llm.chain import BackendChain


def _fake_backend(*, name: str, supports_image: bool, supports_audio: bool = False):
    b = MagicMock()
    b.info.name = name
    b.info.capabilities.supports_chat_image = supports_image
    b.info.capabilities.supports_chat_audio = supports_audio
    b.info.capabilities.supports_text_embed = False
    return b


def test_eligible_chat_spritesheet_uses_image_capability():
    """chat_spritesheet chain 에서 supports_chat_image=True backend 만 eligible."""
    img_backend = _fake_backend(name="gemini", supports_image=True)
    audio_only = _fake_backend(name="claude_audio", supports_image=False, supports_audio=True)
    chain = BackendChain([img_backend, audio_only], modality="chat_spritesheet")
    eligible = chain._eligible()
    assert eligible == [img_backend]


def test_chat_spritesheet_chain_calls_chat():
    """chat_spritesheet chain.chat() 가 첫 image-capable backend 호출."""
    img_backend = _fake_backend(name="gemini", supports_image=True)
    img_backend.chat.return_value = {"animation_hint": ["run"], "description": "d"}
    chain = BackendChain([img_backend], modality="chat_spritesheet")
    payload, name = chain.chat([ChatMessage(role="user", content="x")], force_json=True)
    assert payload == {"animation_hint": ["run"], "description": "d"}
    assert name == "gemini"
```

- [ ] **Step 1.3.2: 실패 확인**

Run: `pytest tests/test_llm_chain_spritesheet.py -v`
Expected: 2 FAIL — `_eligible()` 가 빈 list 반환 (chat_spritesheet 모달리티 분기 없음).

- [ ] **Step 1.3.3: 구현 — Modality Literal 확장 + `_eligible` 분기**

`src/assetcache/core/llm/chain.py:21`:

```python
Modality = Literal["chat_image", "chat_spritesheet", "chat_audio", "text_embed"]
```

`src/assetcache/core/llm/chain.py:29-40` 의 `_eligible` 메서드를 다음으로 교체:

```python
    def _eligible(self) -> list[LLMBackend]:
        """capabilities 가 modality 를 지원하는 backend 만."""
        result: list[LLMBackend] = []
        for b in self.backends:
            cap = b.info.capabilities
            if self.modality in ("chat_image", "chat_spritesheet") and cap.supports_chat_image:
                result.append(b)
            elif self.modality == "chat_audio" and cap.supports_chat_audio:
                result.append(b)
            elif self.modality == "text_embed" and cap.supports_text_embed:
                result.append(b)
        return result
```

- [ ] **Step 1.3.4: 구현 — Registry `Modality` 동기화**

`src/assetcache/core/llm/registry.py:20`:

```python
Modality = Literal["chat_image", "chat_spritesheet", "chat_audio", "text_embed"]
```

- [ ] **Step 1.3.5: 테스트 통과 확인**

Run: `pytest tests/test_llm_chain_spritesheet.py -v`
Expected: 2 PASS.

Run: `pytest tests/test_llm_chain.py tests/test_llm_registry.py -q`
Expected: 회귀 0.

### Task 1.4: 커밋

- [ ] **Step 1.4.1: 커밋**

```powershell
git add src/assetcache/core/store.py src/assetcache/config.py src/assetcache/core/llm/chain.py src/assetcache/core/llm/registry.py tests/test_store_modality_kind_filter.py tests/test_config.py tests/test_llm_chain_spritesheet.py
```

```powershell
git commit -m "M11.2 phase 1 — modality split: chat_image=sprite only, chat_spritesheet=spritesheet"
```

---

## Phase 2 — 시트 분류 helper (`sheet_classifier.py`)

`BatchManager._do_submit("chat_image")` 가 fetch 후 `detect_sheet` 로 시트를 식별 → kind 를 `spritesheet` 로 promote 하고 (sheet_results, sprite_rows) 로 분리하는 helper. 시트 결과는 `(AssetRow, SheetDetection)` 튜플 — 다음 phase 의 builder 가 detection 을 재사용해 더블 detect 비용 회피.

### Task 2.1: `sheet_classifier.py` 신설

**Files:**
- Create: `src/assetcache/core/batch/sheet_classifier.py`
- Test: `tests/test_batch_sheet_classifier.py` (신규)

- [ ] **Step 2.1.1: 실패 테스트 작성**

신규 파일 `tests/test_batch_sheet_classifier.py`:

```python
"""M11.2 — classify_image_assets: detect_sheet → sheet/sprite 분리 + kind promote."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from assetcache.core.batch.sheet_classifier import classify_image_assets
from assetcache.core.sheet.detect import SheetDetection


def _png(library: Path, rel: str, *, size=(64, 32)) -> Path:
    p = library / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (0, 0, 0, 0)).save(p)
    return p


def _aseprite_sidecar(library: Path, rel: str, *, frame_w, frame_h, count, tags):
    frames = {
        f"f_{i}": {
            "frame": {"x": i * frame_w, "y": 0, "w": frame_w, "h": frame_h},
            "duration": 83,
        }
        for i in range(count)
    }
    frame_tags = [
        {"name": n, "from": s, "to": e, "direction": "forward"}
        for n, s, e in tags
    ]
    (library / rel).write_text(
        json.dumps({"frames": frames, "meta": {"frameTags": frame_tags}}),
        encoding="utf-8",
    )


def _row(*, id: int, path: str, kind: str = "sprite"):
    r = MagicMock()
    r.id = id
    r.path = path
    r.kind = kind
    return r


def test_classify_aseprite_sheet_returns_sheet_result_and_promotes(tmp_path):
    _png(tmp_path, "pack/hero.png", size=(128, 32))
    _aseprite_sidecar(
        tmp_path, "pack/hero.json",
        frame_w=32, frame_h=32, count=4, tags=[("idle", 0, 3)],
    )
    rows = [_row(id=1, path="pack/hero.png")]
    store = MagicMock()
    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store,
    )
    assert len(sheet_results) == 1
    assert len(sprite_rows) == 0
    row, det = sheet_results[0]
    assert row.id == 1
    assert isinstance(det, SheetDetection)
    assert det.source == "json"
    store.update_asset_kind.assert_called_once_with(1, "spritesheet")


def test_classify_grid_only_sheet_promotes_without_frame_tags(tmp_path):
    """JSON 사이드카 없는 격자 시트 — grid_detect hit → promote, tags 비어 있음."""
    # 4x1 grid PNG — 균일 격자
    fw, fh = 32, 32
    img = Image.new("RGBA", (fw * 4, fh), (0, 0, 0, 0))
    # 각 셀에 컬러 사각형 — grid_detect 가 알파 경계로 식별
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    for i in range(4):
        draw.rectangle(
            [i * fw + 4, 4, i * fw + fw - 4, fh - 4],
            fill=(255, 0, 0, 255),
        )
    p = tmp_path / "pack/grid.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)

    rows = [_row(id=10, path="pack/grid.png")]
    store = MagicMock()
    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store,
    )
    # grid_detect 가 hit 했다면 sheet, 아니면 sprite — 양쪽 모두 valid 케이스라
    # 분기 검증: hit 면 promote, miss 면 promote 호출 안 함
    if sheet_results:
        assert sprite_rows == []
        store.update_asset_kind.assert_called_once_with(10, "spritesheet")
        _, det = sheet_results[0]
        assert det.source == "grid"
        assert det.tags == []
    else:
        assert len(sprite_rows) == 1
        store.update_asset_kind.assert_not_called()


def test_classify_non_sheet_returns_sprite_only(tmp_path):
    """단일 sprite (시트 아님) → sprite_rows 만, promote 호출 안 함."""
    _png(tmp_path, "pack/single.png", size=(32, 32))
    rows = [_row(id=20, path="pack/single.png")]
    store = MagicMock()
    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store,
    )
    assert sheet_results == []
    assert len(sprite_rows) == 1
    assert sprite_rows[0].id == 20
    store.update_asset_kind.assert_not_called()


def test_classify_io_error_falls_through_as_sprite(tmp_path):
    """파일이 없는 row → 예외 삼키고 sprite 로 분류."""
    rows = [_row(id=30, path="pack/missing.png")]
    store = MagicMock()
    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store,
    )
    assert sheet_results == []
    assert len(sprite_rows) == 1
    store.update_asset_kind.assert_not_called()


def test_classify_mixed_batch_separates_correctly(tmp_path):
    """시트 + sprite 혼합 입력 → 각각 올바르게 분리."""
    _png(tmp_path, "pack/sheet.png", size=(128, 32))
    _aseprite_sidecar(
        tmp_path, "pack/sheet.json",
        frame_w=32, frame_h=32, count=4, tags=[("walk", 0, 3)],
    )
    _png(tmp_path, "pack/single.png", size=(32, 32))
    rows = [
        _row(id=1, path="pack/sheet.png"),
        _row(id=2, path="pack/single.png"),
    ]
    store = MagicMock()
    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store,
    )
    assert len(sheet_results) == 1 and sheet_results[0][0].id == 1
    assert len(sprite_rows) == 1 and sprite_rows[0].id == 2
    store.update_asset_kind.assert_called_once_with(1, "spritesheet")


def test_classify_preserves_input_order_per_bucket(tmp_path):
    """입력 순서가 각 버킷 내에서 보존돼야."""
    for i in range(3):
        _png(tmp_path, f"pack/s{i}.png", size=(32, 32))
    rows = [_row(id=i, path=f"pack/s{i}.png") for i in range(3)]
    store = MagicMock()
    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store,
    )
    assert [r.id for r in sprite_rows] == [0, 1, 2]
```

- [ ] **Step 2.1.2: 실패 확인**

Run: `pytest tests/test_batch_sheet_classifier.py -v`
Expected: 6 FAIL — `ImportError: cannot import name 'classify_image_assets'`.

- [ ] **Step 2.1.3: 구현 — `sheet_classifier.py`**

신규 파일 `src/assetcache/core/batch/sheet_classifier.py`:

```python
"""M11.2 — BatchManager fetch 단계용 시트 분류 helper.

`classify_image_assets(rows, library_dir, store)` 는 각 row 에 대해
``detect_sheet`` 를 호출해 시트면 ``(AssetRow, SheetDetection)`` 튜플로,
일반 sprite 면 그대로 두 버킷으로 분리한다.  시트로 식별된 row 는 즉시
``store.update_asset_kind(id, 'spritesheet')`` 로 promote — 다음 sweep 의
``chat_spritesheet`` 카운트에 즉시 반영된다.

파일 I/O / detect_sheet 예외는 silent skip + sprite 로 분류 (graceful
fallback).  library_dir 이 ``None`` 이면 분류 자체를 skip 하고 모든 row 를
sprite_rows 로 반환한다 (테스트 / library 없는 환경 호환).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ..sheet.detect import detect_sheet

if TYPE_CHECKING:
    from ..sheet.detect import SheetDetection
    from ..store import AssetRow, Store

log = logging.getLogger(__name__)


def classify_image_assets(
    rows: "list[AssetRow]",
    *,
    library_dir: Path | None,
    store: "Store",
) -> "tuple[list[tuple[AssetRow, SheetDetection]], list[AssetRow]]":
    """detect_sheet 결과로 (sheet_results, sprite_rows) 로 분리 + kind promote.

    sheet_results: ``[(row, detection), ...]`` — kind 가 spritesheet 로 promote 됨.
    sprite_rows: detect_sheet miss / 예외 / library_dir=None — 일반 sprite.
    """
    if library_dir is None:
        return [], list(rows)

    sheet_results: list[tuple["AssetRow", "SheetDetection"]] = []
    sprite_rows: list["AssetRow"] = []

    for row in rows:
        try:
            abs_path = (library_dir / row.path).resolve()
            detection = detect_sheet(abs_path)
        except Exception as e:  # noqa: BLE001 — file I/O 또는 detect 오류 graceful skip
            log.warning(
                "classify_image_assets: detect_sheet failed asset_id=%d path=%s: %s",
                row.id, row.path, e,
            )
            sprite_rows.append(row)
            continue
        if detection is None:
            sprite_rows.append(row)
        else:
            sheet_results.append((row, detection))
            try:
                store.update_asset_kind(row.id, "spritesheet")
            except Exception as e:  # noqa: BLE001 — DB 오류여도 batch 진행
                log.warning(
                    "classify_image_assets: update_asset_kind failed asset_id=%d: %s",
                    row.id, e,
                )
    return sheet_results, sprite_rows
```

- [ ] **Step 2.1.4: 테스트 통과 확인**

Run: `pytest tests/test_batch_sheet_classifier.py -v`
Expected: 6 PASS.

### Task 2.2: 커밋

- [ ] **Step 2.2.1: 커밋**

```powershell
git add src/assetcache/core/batch/sheet_classifier.py tests/test_batch_sheet_classifier.py
```

```powershell
git commit -m "M11.2 phase 2 — sheet_classifier: detect_sheet split + kind promote"
```

---

## Phase 3 — 시트 전용 prompt + composite builder

`BATCH_SPRITESHEET_PROMPT` 상수 + `build_spritesheet_chat_messages(abs_path, detection, prompt, anim_enum, *, max_long_edge)` — sync `SpritesheetAnalyzer._call_gemma` 의 system prompt 와 동일한 schema 로 batch 메시지 1개 생성. composite strip 은 `make_preview_composite` 재사용.

### Task 3.1: `BATCH_SPRITESHEET_PROMPT` + builder

**Files:**
- Modify: `src/assetcache/core/analyzer/messages.py:30-46` (상수 추가) + 끝에 builder 함수 추가
- Test: `tests/test_analyzer_messages_spritesheet.py` (신규)

- [ ] **Step 3.1.1: 실패 테스트 작성**

신규 파일 `tests/test_analyzer_messages_spritesheet.py`:

```python
"""M11.2 — BATCH_SPRITESHEET_PROMPT + build_spritesheet_chat_messages."""

import base64
from pathlib import Path

import pytest
from PIL import Image

from assetcache.core.analyzer.messages import (
    BATCH_SPRITESHEET_PROMPT,
    build_spritesheet_chat_messages,
)
from assetcache.core.sheet.detect import SheetDetection
from assetcache.core.sheet.types import AnimationSpec, FrameSpec


def _sheet_png(library: Path, rel: str, *, frame_w, frame_h, count) -> Path:
    """가로 stripe 시트 PNG — count 개 frame."""
    p = library / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (frame_w * count, frame_h), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    for i in range(count):
        draw.rectangle(
            [i * frame_w + 2, 2, i * frame_w + frame_w - 2, frame_h - 2],
            fill=(50 * i, 100, 200, 255),
        )
    img.save(p)
    return p


def _detection(*, frame_w, frame_h, count, source="grid", tag_names=()):
    frames = [
        FrameSpec(x=i * frame_w, y=0, w=frame_w, h=frame_h, duration_ms=0, name=str(i))
        for i in range(count)
    ]
    tags = [
        AnimationSpec(
            name=n, start_frame=0, end_frame=count - 1, fps_hint=12, source="json_tag",
        )
        for n in tag_names
    ]
    return SheetDetection(frames=frames, tags=tags, source=source)


def test_batch_spritesheet_prompt_is_nonempty_string():
    assert isinstance(BATCH_SPRITESHEET_PROMPT, str) and BATCH_SPRITESHEET_PROMPT
    # animation_hint 와 description 키워드는 포함돼야
    assert "animation_hint" in BATCH_SPRITESHEET_PROMPT
    assert "description" in BATCH_SPRITESHEET_PROMPT


def test_build_spritesheet_chat_messages_includes_composite_b64(tmp_path):
    """composite strip 이 base64 인코딩되어 메시지에 포함."""
    _sheet_png(tmp_path, "sheet.png", frame_w=32, frame_h=32, count=4)
    det = _detection(frame_w=32, frame_h=32, count=4)
    messages = build_spritesheet_chat_messages(
        abs_path=tmp_path / "sheet.png",
        detection=det,
        prompt=BATCH_SPRITESHEET_PROMPT,
        anim_enum="idle, walk, run",
    )
    # system + user 두 메시지
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert "animation_hint" in messages[0].content
    assert "idle, walk, run" in messages[0].content
    assert messages[1].role == "user"
    assert len(messages[1].images_b64) == 1
    # composite 가 빈 문자열이 아닌 base64 PNG
    b64 = messages[1].images_b64[0]
    raw = base64.b64decode(b64)
    assert raw.startswith(b"\x89PNG")


def test_build_spritesheet_chat_messages_resizes_to_max_long_edge(tmp_path):
    """긴 변이 max_long_edge 이하로 다운스케일."""
    _sheet_png(tmp_path, "big.png", frame_w=200, frame_h=200, count=8)
    det = _detection(frame_w=200, frame_h=200, count=8)
    messages = build_spritesheet_chat_messages(
        abs_path=tmp_path / "big.png",
        detection=det,
        prompt=BATCH_SPRITESHEET_PROMPT,
        anim_enum="idle",
        max_long_edge=400,
    )
    import io
    from PIL import Image as _PIL
    raw = base64.b64decode(messages[1].images_b64[0])
    img = _PIL.open(io.BytesIO(raw))
    assert max(img.size) <= 400


def test_build_spritesheet_chat_messages_force_json_friendly(tmp_path):
    """system prompt 가 JSON-only 응답을 명시."""
    _sheet_png(tmp_path, "x.png", frame_w=32, frame_h=32, count=4)
    det = _detection(frame_w=32, frame_h=32, count=4)
    messages = build_spritesheet_chat_messages(
        abs_path=tmp_path / "x.png",
        detection=det,
        prompt=BATCH_SPRITESHEET_PROMPT,
        anim_enum="idle",
    )
    assert "JSON" in messages[0].content


def test_build_spritesheet_chat_messages_empty_anim_enum_still_valid(tmp_path):
    """registry 에 animation 라벨이 없어도 builder 가 graceful 하게 동작."""
    _sheet_png(tmp_path, "y.png", frame_w=32, frame_h=32, count=2)
    det = _detection(frame_w=32, frame_h=32, count=2)
    messages = build_spritesheet_chat_messages(
        abs_path=tmp_path / "y.png",
        detection=det,
        prompt=BATCH_SPRITESHEET_PROMPT,
        anim_enum="",
    )
    # system 메시지 정상 + 빈 enum 으로 인한 crash 없음
    assert len(messages) == 2
```

- [ ] **Step 3.1.2: 실패 확인**

Run: `pytest tests/test_analyzer_messages_spritesheet.py -v`
Expected: 5 FAIL — import 실패.

- [ ] **Step 3.1.3: 구현 — `BATCH_SPRITESHEET_PROMPT` 상수 추가**

`src/assetcache/core/analyzer/messages.py` 의 `BATCH_AUDIO_PROMPT` 정의 직후 (line 47 부근) 에 추가:

```python
# M11.2 — Spritesheet batch 전용 prompt.  sync SpritesheetAnalyzer._call_gemma 의
# system prompt 와 동일한 schema — animation_hint enum 은 호출 시점에 builder
# 가 동적 주입한다.  ``{anim_enum}`` placeholder 는 build_spritesheet_chat_messages
# 가 ``.format(anim_enum=...)`` 로 치환.
BATCH_SPRITESHEET_PROMPT = (
    "You are a game animation labeler. Respond ONLY with valid JSON.\n\n"
    "Input is a horizontal strip of sprite frames.\n"
    "Schema:\n"
    "- animation_hint: array (1..4) from [{anim_enum}]\n"
    "- description: one sentence\n"
    "- subject: short noun phrase\n"
    "- category: 'character'\n"
    "- style: 'pixel_art'\n"
    "- mood: []\n"
    "- palette: []\n"
    "- confidence: float 0..1\n"
)
```

- [ ] **Step 3.1.4: 구현 — `build_spritesheet_chat_messages` 함수 추가**

`src/assetcache/core/analyzer/messages.py` 끝에 추가:

```python
def build_spritesheet_chat_messages(
    *,
    abs_path: Path,
    detection,
    prompt: str,
    anim_enum: str,
    max_long_edge: int = 768,
) -> list[ChatMessage]:
    """시트 자산을 batch 전송하기 위한 composite strip + 시트 전용 prompt.

    detect_sheet 결과의 frames 를 ``make_preview_composite`` 로 8칸 가로 strip
    으로 합성한 뒤 PNG base64 로 인코딩.  system 메시지에 schema (enum 동적
    주입) + user 메시지에 합성 이미지 1장.  sync SpritesheetAnalyzer 의
    ``_call_gemma`` 와 동일 schema.
    """
    import io

    from PIL import Image as _PILImage

    from ..sheet.preview import make_preview_composite

    with _PILImage.open(abs_path) as src:
        src.load()
        composite = make_preview_composite(
            src, list(detection.frames), max_size=max_long_edge,
        )
    buf = io.BytesIO()
    composite.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    system_content = prompt.format(anim_enum=anim_enum)
    return [
        ChatMessage(role="system", content=system_content),
        ChatMessage(
            role="user",
            content="Identify the animation in this strip.",
            images_b64=[img_b64],
        ),
    ]
```

- [ ] **Step 3.1.5: 테스트 통과 확인**

Run: `pytest tests/test_analyzer_messages_spritesheet.py -v`
Expected: 5 PASS.

Run: `pytest tests/test_analyzer_messages.py -q`
Expected: 회귀 0.

### Task 3.2: 커밋

- [ ] **Step 3.2.1: 커밋**

```powershell
git add src/assetcache/core/analyzer/messages.py tests/test_analyzer_messages_spritesheet.py
```

```powershell
git commit -m "M11.2 phase 3 — BATCH_SPRITESHEET_PROMPT + composite builder"
```

---

## Phase 4 — BatchManager 분기

`_MODALITIES` 확장 + `_do_submit("chat_image")` 가 fetch 후 classify → sprite_rows 만 chat_image batch + sheet rows 는 promote-only (다음 sweep 의 chat_spritesheet 가 픽업). `_do_submit("chat_spritesheet")` 신규 — chat_spritesheet kind 로 fetch + composite builder + batch_chat submit. `AnalysisQueue._try_batch_submit` 가 chat_spritesheet 도 시도.

### Task 4.1: `_MODALITIES` 확장 + `try_submit` 4-modality 지원

**Files:**
- Modify: `src/assetcache/core/batch/manager.py:26` (`_MODALITIES`)
- Modify: `src/assetcache/core/batch/manager.py:84-136` (`_do_submit`)
- Test: `tests/test_batch_manager_spritesheet.py` (신규)

- [ ] **Step 4.1.1: 실패 테스트 작성 (manager 분기 검증)**

신규 파일 `tests/test_batch_manager_spritesheet.py`:

```python
"""M11.2 — BatchManager 의 chat_spritesheet modality 분기."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from assetcache.core.batch.manager import BatchManager


def _make_manager(*, library_dir: Path, threshold: int = 1):
    store = MagicMock()
    chain = MagicMock()
    aq = MagicMock()
    cfg = MagicMock()
    cfg.batch.toggle = "auto"
    cfg.batch.threshold = threshold
    cfg.batch.expiry_grace_seconds = 86400
    return BatchManager(
        store=store, chain_registry=chain, analysis_queue=aq,
        cfg=cfg, library_dir=library_dir,
    ), store, chain, aq


def _gemini_backend():
    b = MagicMock()
    b.info.name = "gemini"
    b.supports_batch.return_value = True
    b.batch_chat.return_value = "batches/fake-job-id"
    return b


def _sheet_png(library: Path, rel: str, *, frame_w=32, frame_h=32, count=4):
    p = library / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (frame_w * count, frame_h), (0, 0, 0, 0)).save(p)
    return p


def _aseprite(library: Path, rel: str, *, frame_w, frame_h, count, tags):
    frames = {
        f"f_{i}": {
            "frame": {"x": i * frame_w, "y": 0, "w": frame_w, "h": frame_h},
            "duration": 83,
        }
        for i in range(count)
    }
    frame_tags = [
        {"name": n, "from": s, "to": e, "direction": "forward"}
        for n, s, e in tags
    ]
    (library / rel).write_text(
        json.dumps({"frames": frames, "meta": {"frameTags": frame_tags}}),
        encoding="utf-8",
    )


def _row(*, id: int, path: str, kind: str = "sprite"):
    r = MagicMock()
    r.id = id
    r.path = path
    r.kind = kind
    return r


def test_modalities_includes_chat_spritesheet():
    """_MODALITIES 가 chat_spritesheet 를 포함해야."""
    from assetcache.core.batch.manager import _MODALITIES
    assert "chat_spritesheet" in _MODALITIES


def test_try_submit_chat_spritesheet_invalid_check_passes():
    """try_submit 가 'chat_spritesheet' 를 valid modality 로 인식."""
    mgr, store, chain, aq = _make_manager(library_dir=Path("/tmp"))
    chain.first_backend.return_value = None  # backend 없음 → None 반환이지만 invalid 경고는 안 나야
    out = mgr.try_submit("chat_spritesheet")
    assert out is None
    # _MODALITIES 에 있으므로 first_backend 까지 진행


def test_try_submit_chat_image_classifies_and_promotes_sheets(tmp_path):
    """chat_image fetch 시 sheet 식별 → kind promote + sprite_rows 만 batch submit."""
    # 1 sheet + 1 sprite 시드
    _sheet_png(tmp_path, "pack/sheet.png", count=4)
    _aseprite(tmp_path, "pack/sheet.json", frame_w=32, frame_h=32, count=4,
              tags=[("walk", 0, 3)])
    _sheet_png(tmp_path, "pack/single.png", count=1)

    mgr, store, chain, aq = _make_manager(library_dir=tmp_path, threshold=1)
    store.count_pending_by_modality.return_value = 2
    store.fetch_pending_by_modality.return_value = [
        _row(id=1, path="pack/sheet.png"),
        _row(id=2, path="pack/single.png"),
    ]
    backend = _gemini_backend()
    chain.first_backend.return_value = backend
    store.save_batch_job.return_value = 99

    job_id = mgr.try_submit("chat_image")

    # sheet 는 promote, sprite 1개만 batch submit
    store.update_asset_kind.assert_called_once_with(1, "spritesheet")
    backend.batch_chat.assert_called_once()
    call = backend.batch_chat.call_args
    assert call.kwargs["modality"] == "chat_image"
    sent_ids = [req.asset_id for req in call.kwargs["requests"]]
    assert sent_ids == [2]
    assert job_id == 99


def test_try_submit_chat_image_all_sheets_returns_none(tmp_path):
    """chat_image fetch 결과 전부 시트면 promote 만 하고 batch submit 0."""
    _sheet_png(tmp_path, "pack/a.png", count=4)
    _aseprite(tmp_path, "pack/a.json", frame_w=32, frame_h=32, count=4,
              tags=[("idle", 0, 3)])

    mgr, store, chain, aq = _make_manager(library_dir=tmp_path, threshold=1)
    store.count_pending_by_modality.return_value = 1
    store.fetch_pending_by_modality.return_value = [_row(id=10, path="pack/a.png")]
    backend = _gemini_backend()
    chain.first_backend.return_value = backend

    out = mgr.try_submit("chat_image")
    assert out is None
    store.update_asset_kind.assert_called_once_with(10, "spritesheet")
    backend.batch_chat.assert_not_called()


def test_try_submit_chat_spritesheet_uses_composite_builder(tmp_path):
    """chat_spritesheet fetch → detect_sheet hit 한 row 만 composite builder 로 batch."""
    _sheet_png(tmp_path, "pack/hero.png", count=4)
    _aseprite(tmp_path, "pack/hero.json", frame_w=32, frame_h=32, count=4,
              tags=[("walk", 0, 3)])

    mgr, store, chain, aq = _make_manager(library_dir=tmp_path, threshold=1)
    store.count_pending_by_modality.return_value = 1
    store.fetch_pending_by_modality.return_value = [
        _row(id=100, path="pack/hero.png", kind="spritesheet"),
    ]
    backend = _gemini_backend()
    chain.first_backend.return_value = backend
    store.save_batch_job.return_value = 500
    # registry mock — list_labels('animation') 의 enum
    from unittest.mock import patch

    job_id = mgr.try_submit("chat_spritesheet")

    backend.batch_chat.assert_called_once()
    call = backend.batch_chat.call_args
    assert call.kwargs["modality"] == "chat_spritesheet"
    sent_ids = [req.asset_id for req in call.kwargs["requests"]]
    assert sent_ids == [100]
    assert job_id == 500


def test_try_submit_chat_image_no_library_dir_skips_classification(tmp_path):
    """library_dir=None 이면 classification skip → legacy 동작 (전체 sprite)."""
    mgr, store, chain, aq = _make_manager(library_dir=None, threshold=1)
    store.count_pending_by_modality.return_value = 1
    store.fetch_pending_by_modality.return_value = [_row(id=1, path="x.png")]
    backend = _gemini_backend()
    chain.first_backend.return_value = backend
    store.save_batch_job.return_value = 1

    mgr.try_submit("chat_image")
    backend.batch_chat.assert_called_once()
    store.update_asset_kind.assert_not_called()
```

- [ ] **Step 4.1.2: 실패 확인**

Run: `pytest tests/test_batch_manager_spritesheet.py -v`
Expected: 6 FAIL — `_MODALITIES` 에 chat_spritesheet 없음 (`try_submit invalid modality` 경고).

- [ ] **Step 4.1.3: 구현 — `_MODALITIES` 확장**

`src/assetcache/core/batch/manager.py:26`:

```python
_MODALITIES = ("chat_image", "chat_spritesheet", "chat_audio", "text_embed")
```

(`self._locks = {m: threading.Lock() for m in _MODALITIES}` 는 자동으로 4개 lock 으로 확장됨.)

- [ ] **Step 4.1.4: 구현 — `_do_submit` chat_image classification 분기**

`src/assetcache/core/batch/manager.py:84-136` 의 `_do_submit` 메서드 전체를 다음으로 교체:

```python
    def _do_submit(self, modality: str, backend) -> int | None:
        threshold = self._cfg.batch.threshold
        rows = self._store.fetch_pending_by_modality(modality, limit=threshold)
        if not rows:
            return None

        sheet_results: list = []  # [(AssetRow, SheetDetection), ...]
        if modality == "chat_image":
            # M11.2 — 시트 식별 + kind promote.  sheet rows 는 다음 sweep 의
            # chat_spritesheet 가 픽업.  sprite rows 만 chat_image batch 로 진행.
            from .sheet_classifier import classify_image_assets
            sheet_results, rows = classify_image_assets(
                rows, library_dir=self._library_dir, store=self._store,
            )
            if not rows:
                # 전부 시트 — promote 만 수행, batch submit 0.
                return None
        elif modality == "chat_spritesheet":
            # spritesheet kind 는 이미 promoted 상태.  builder 에 detection 을
            # 다시 전달하기 위해 여기서 detect_sheet 한 번 호출.
            from .sheet_classifier import classify_image_assets
            sheet_results, leftover = classify_image_assets(
                rows, library_dir=self._library_dir, store=self._store,
            )
            if not sheet_results:
                # spritesheet kind 인데 detect 실패 — sprite 로 강등하지 말고 skip.
                log.warning(
                    "chat_spritesheet submit: 0 detect_sheet hits in %d rows",
                    len(rows),
                )
                return None
            rows = [row for row, _ in sheet_results]

        asset_ids = [r.id for r in rows]
        self._store.mark_assets_batch_queued(asset_ids)
        try:
            if modality in ("chat_image", "chat_audio"):
                requests = self._build_chat_requests(modality, rows)
            elif modality == "chat_spritesheet":
                requests = self._build_spritesheet_requests(sheet_results)
            else:  # text_embed
                texts = self._build_embed_texts(rows)

            if modality in ("chat_image", "chat_audio", "chat_spritesheet"):
                asset_ids_built = [req.asset_id for req in requests]
                skipped = set(asset_ids) - set(asset_ids_built)
                for aid in skipped:
                    self._store.mark_asset_batch_state(aid, "none")
                if not requests:
                    log.warning(
                        "batch submit modality=%s: all assets failed to build, abort",
                        modality,
                    )
                    return None
                backend_job_id = backend.batch_chat(
                    modality=modality, requests=requests,
                )
                asset_ids = asset_ids_built
            else:  # text_embed
                backend_job_id = backend.batch_embed(texts=texts)
        except Exception as e:
            log.warning(
                "batch submit failed modality=%s — rollback: %s", modality, e,
            )
            for aid in asset_ids:
                self._store.mark_asset_batch_state(aid, "none")
            return None
        now = int(time.time())
        job_id = self._store.save_batch_job(
            backend="gemini",
            modality=modality,
            backend_job_id=backend_job_id,
            asset_count=len(asset_ids),
            submitted_at=now,
            expires_at=now + self._cfg.batch.expiry_grace_seconds,
            display_name=f"assetcache-{modality}-{now}",
        )
        self._store.mark_assets_batch_submitted(asset_ids, job_id)
        self._aq.dequeue_assets(asset_ids)
        log.info(
            "batch submitted modality=%s job_id=%d backend_job_id=%s count=%d",
            modality, job_id, backend_job_id, len(asset_ids),
        )
        return job_id
```

- [ ] **Step 4.1.5: 구현 — `_build_spritesheet_requests` 신규 메서드**

`src/assetcache/core/batch/manager.py:138-173` 의 `_build_chat_requests` 메서드 직후에 추가:

```python
    def _build_spritesheet_requests(self, sheet_results):
        """시트 + detection 튜플 list 를 composite strip + 시트 전용 prompt 로 변환.

        sheet_results: ``[(AssetRow, SheetDetection), ...]`` from classify_image_assets.
        registry 가 있으면 ``list_labels('animation')`` 으로 enum 동적 주입.
        없으면 빈 enum 으로 fallback (sync SpritesheetAnalyzer 와 동일 동작).
        """
        from ..analyzer.messages import (
            BATCH_SPRITESHEET_PROMPT,
            build_spritesheet_chat_messages,
        )

        anim_enum = ""
        registry = getattr(self, "_registry", None)
        if registry is not None:
            try:
                anim_enum = ", ".join(registry.list_labels("animation"))
            except Exception:  # noqa: BLE001 — registry 오류 silent fallback
                anim_enum = ""

        out: list[BatchChatRequest] = []
        for row, detection in sheet_results:
            if self._library_dir is not None:
                abs_path = (self._library_dir / row.path).resolve()
            else:
                abs_path = Path(row.path)
            try:
                messages = build_spritesheet_chat_messages(
                    abs_path=abs_path,
                    detection=detection,
                    prompt=BATCH_SPRITESHEET_PROMPT,
                    anim_enum=anim_enum,
                )
            except (OSError, ValueError) as e:
                log.warning(
                    "batch spritesheet: cannot build composite asset_id=%d (%s): %s",
                    row.id, abs_path, e,
                )
                continue
            out.append(BatchChatRequest(
                asset_id=row.id,
                messages=messages,
                force_json=True,
            ))
        return out
```

- [ ] **Step 4.1.6: 구현 — `BatchManager.__init__` 에 registry 인자 추가**

`src/assetcache/core/batch/manager.py:36-50`:

```python
    def __init__(
        self,
        *,
        store: "Store",
        chain_registry: "BackendRegistry",
        analysis_queue: "AnalysisQueue",
        cfg: "Config",
        library_dir: Path | None = None,
        registry: "LabelRegistry | None" = None,
    ) -> None:
        self._store = store
        self._chain = chain_registry
        self._aq = analysis_queue
        self._cfg = cfg
        self._library_dir = library_dir
        self._registry = registry
        self._locks = {m: threading.Lock() for m in _MODALITIES}
```

그리고 상단 TYPE_CHECKING 블록에 `from ..labels import LabelRegistry` 추가:

```python
if TYPE_CHECKING:
    from ..analysis_queue import AnalysisQueue
    from ..labels import LabelRegistry
    from ..llm.registry import BackendRegistry
    from ..store import Store
    from ...config import Config
```

- [ ] **Step 4.1.7: 테스트 통과 확인**

Run: `pytest tests/test_batch_manager_spritesheet.py -v`
Expected: 6 PASS.

Run: `pytest tests/test_batch_manager*.py -q`
Expected: 회귀 0. 기존 chat_image only 테스트가 library_dir 없는 manager 시드를 사용한다면 그대로 통과해야 함 (classify_image_assets 가 library_dir=None 일 때 모두 sprite 로 반환).

### Task 4.2: AnalysisQueue 가 chat_spritesheet 도 try_submit

**Files:**
- Modify: `src/assetcache/core/analysis_queue.py:117-128`
- Test: `tests/test_analysis_queue.py` (기존 — append 또는 새 테스트 파일)

- [ ] **Step 4.2.1: 실패 테스트 추가**

`tests/test_analysis_queue.py` 끝에 append (없으면 새로 만들기):

```python
def test_try_batch_submit_calls_all_4_modalities():
    """M11.2 — chat_spritesheet 까지 4 modality 모두 시도."""
    from unittest.mock import MagicMock

    from assetcache.core.analysis_queue import AnalysisQueue

    aq = AnalysisQueue.__new__(AnalysisQueue)
    aq._batch_manager = MagicMock()
    aq._try_batch_submit()
    called = [c.args[0] for c in aq._batch_manager.try_submit.call_args_list]
    assert called == ["chat_image", "chat_spritesheet", "chat_audio", "text_embed"]
```

- [ ] **Step 4.2.2: 실패 확인**

Run: `pytest tests/test_analysis_queue.py::test_try_batch_submit_calls_all_4_modalities -v`
Expected: FAIL — 현재는 3개만 호출.

- [ ] **Step 4.2.3: 구현 — modality 루프에 chat_spritesheet 추가**

`src/assetcache/core/analysis_queue.py:124`:

```python
        for modality in ("chat_image", "chat_spritesheet", "chat_audio", "text_embed"):
```

- [ ] **Step 4.2.4: 테스트 통과 확인**

Run: `pytest tests/test_analysis_queue.py -q`
Expected: 회귀 0.

### Task 4.3: GeminiBackend.batch_chat 가 chat_spritesheet 지원

**Files:**
- Modify: `src/assetcache/core/llm/backends/gemini.py:189-194`
- Test: `tests/test_llm_backend_gemini.py` (기존 — append)

- [ ] **Step 4.3.1: 실패 테스트 추가**

`tests/test_llm_backend_gemini.py` 적당한 위치 (또는 신규 파일 `tests/test_llm_backend_gemini_spritesheet.py`):

```python
def test_batch_chat_chat_spritesheet_uses_model_image():
    """chat_spritesheet modality 는 chat_image 와 동일하게 model_image 사용."""
    from unittest.mock import MagicMock, patch

    from assetcache.core.batch.types import BatchChatRequest
    from assetcache.core.llm.backends.gemini import GeminiBackend
    from assetcache.core.llm.base import ChatMessage

    backend = GeminiBackend.__new__(GeminiBackend)
    backend._client = MagicMock()
    backend.model_image = "gemini-3.1-flash-lite"
    backend.model_audio = "gemini-3.1-flash-lite"
    backend.model_embed = "gemini-embedding-001"
    backend._client.batches.create.return_value = MagicMock(name="batches/x")
    # MagicMock.name 은 특별 — explicit attr 로 강제
    fake_job = MagicMock()
    fake_job.name = "batches/x"
    backend._client.batches.create.return_value = fake_job

    out = backend.batch_chat(
        modality="chat_spritesheet",
        requests=[BatchChatRequest(
            asset_id=1,
            messages=[ChatMessage(role="user", content="x", images_b64=["aGk="])],
            force_json=True,
        )],
    )
    assert out == "batches/x"
    args = backend._client.batches.create.call_args
    assert args.kwargs["model"] == "gemini-3.1-flash-lite"
```

- [ ] **Step 4.3.2: 실패 확인**

Run: `pytest tests/test_llm_backend_gemini.py::test_batch_chat_chat_spritesheet_uses_model_image -v`
Expected: FAIL — `ValueError: batch_chat invalid modality: 'chat_spritesheet'`.

- [ ] **Step 4.3.3: 구현 — modality 분기 확장**

`src/assetcache/core/llm/backends/gemini.py:189-194`:

```python
        if modality in ("chat_image", "chat_spritesheet"):
            model = self.model_image
        elif modality == "chat_audio":
            model = self.model_audio
        else:
            raise ValueError(f"batch_chat invalid modality: {modality!r}")
```

- [ ] **Step 4.3.4: 테스트 통과 확인**

Run: `pytest tests/test_llm_backend_gemini.py -q`
Expected: 회귀 0 + 새 테스트 PASS.

### Task 4.4: 커밋

- [ ] **Step 4.4.1: 커밋**

```powershell
git add src/assetcache/core/batch/manager.py src/assetcache/core/analysis_queue.py src/assetcache/core/llm/backends/gemini.py tests/test_batch_manager_spritesheet.py tests/test_analysis_queue.py tests/test_llm_backend_gemini.py
```

```powershell
git commit -m "M11.2 phase 4 — BatchManager classify-on-fetch + chat_spritesheet submit"
```

---

## Phase 5 — BatchPoller spritesheet handler

`_handle_succeeded` modality switch 에 `chat_spritesheet` 분기 추가 → 신규 `_persist_spritesheet_payload(asset, payload)` 가 sync `SpritesheetAnalyzer` 와 동등한 결과 (validated labels + animation_hint 라벨 + sprite_meta enrich + kind 유지) 생성.

### Task 5.1: `_persist_spritesheet_payload` 신설

**Files:**
- Modify: `src/assetcache/core/batch/poller.py:156-227` (`_handle_succeeded`)
- Modify: `src/assetcache/core/batch/poller.py:234-293` (`_persist_image_payload` 이후 신규 메서드 추가)
- Test: `tests/test_batch_poller_spritesheet_modality.py` (신규)

- [ ] **Step 5.1.1: 실패 테스트 작성**

신규 파일 `tests/test_batch_poller_spritesheet_modality.py`:

```python
"""M11.2 — BatchPoller 의 chat_spritesheet handler.

_persist_spritesheet_payload 가 sync SpritesheetAnalyzer 와 동등한 결과
(category/style/mood/palette + animation_hint 라벨 + sprite_meta enrich +
kind='spritesheet' 보존) 를 DB 에 저장하는지.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from assetcache.core.batch.poller import BatchPoller


@dataclass(frozen=True)
class _LabelRow:
    label: str
    description: str | None = None


class _StubRegistry:
    def __init__(self, axis_labels):
        self._axis_labels = axis_labels

    def list_labels(self, axis=None, *, enabled_only=True, with_description=False):
        labels = self._axis_labels.get(axis, []) if axis else []
        if with_description:
            return [_LabelRow(label=l) for l in labels]
        return labels


def _registry():
    return _StubRegistry({
        "category": ["character", "other"],
        "style": ["pixel_art", "other"],
        "mood": ["calm"],
        "palette": ["vibrant"],
        "animation": ["idle", "walk", "run", "attack"],
    })


def _make_poller(library_dir: Path):
    store = MagicMock()
    store.list_active_batch_jobs.return_value = []
    cfg = MagicMock()
    cfg.batch.poll_interval_seconds = 0.05
    return BatchPoller(
        store=store, chain_registry=MagicMock(), analysis_queue=MagicMock(),
        cfg=cfg, registry=_registry(), library_dir=library_dir,
    ), store


def _aseprite_sheet(library: Path, base: str, *, count, tags):
    fw, fh = 32, 32
    img = Image.new("RGBA", (fw * count, fh), (200, 50, 50, 255))
    p = library / f"{base}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)
    frames = {
        f"f_{i}": {
            "frame": {"x": i * fw, "y": 0, "w": fw, "h": fh},
            "duration": 83,
        }
        for i in range(count)
    }
    frame_tags = [
        {"name": n, "from": s, "to": e, "direction": "forward"}
        for n, s, e in tags
    ]
    (library / f"{base}.json").write_text(
        json.dumps({"frames": frames, "meta": {"frameTags": frame_tags}}),
        encoding="utf-8",
    )


def test_persist_spritesheet_payload_validates_and_emits_animation_labels(tmp_path):
    """payload 의 animation_hint + frameTags 모두 라벨로 등록."""
    _aseprite_sheet(tmp_path, "pack/hero", count=4, tags=[("idle", 0, 3)])
    p, store = _make_poller(tmp_path)
    asset = MagicMock(id=1, path="pack/hero.png")
    payload = {
        "category": "character",
        "style": "pixel_art",
        "mood": [],
        "palette": [],
        "animation_hint": ["walk", "run"],
        "description": "Hero animation",
        "confidence": 0.85,
    }
    p._persist_spritesheet_payload(asset, payload)

    saved_labels = store.save_asset_labels.call_args.args[1]
    anim = {l.label for l in saved_labels if l.axis == "animation"}
    # Gemma 추측 (walk/run) + frameTags (idle)
    assert anim == {"walk", "run", "idle"}
    # category/style 도 등록
    cat = [l for l in saved_labels if l.axis == "category"]
    assert cat and cat[0].label == "character"


def test_persist_spritesheet_payload_enriches_sprite_meta(tmp_path):
    """sprite_meta 에 frame_w/h/count + animations_json 채워야."""
    _aseprite_sheet(tmp_path, "pack/x", count=4, tags=[("walk", 0, 3)])
    p, store = _make_poller(tmp_path)
    asset = MagicMock(id=2, path="pack/x.png")
    payload = {
        "category": "character", "style": "pixel_art",
        "animation_hint": ["walk"], "description": "x", "confidence": 0.9,
    }
    p._persist_spritesheet_payload(asset, payload)

    store.save_sprite_meta.assert_called_once()
    _, meta = store.save_sprite_meta.call_args.args
    assert meta.frame_w == 32 and meta.frame_h == 32
    assert meta.frame_count == 4
    assert meta.animations_json == {
        "walk": {"start_frame": 0, "end_frame": 3, "fps_hint": 12, "source": "json_tag"},
    }


def test_persist_spritesheet_payload_keeps_kind_spritesheet(tmp_path):
    """이미 promoted 된 kind 는 그대로 유지 (재호출 noop)."""
    _aseprite_sheet(tmp_path, "pack/k", count=2, tags=[("idle", 0, 1)])
    p, store = _make_poller(tmp_path)
    asset = MagicMock(id=3, path="pack/k.png")
    p._persist_spritesheet_payload(asset, {
        "category": "character", "style": "pixel_art",
        "animation_hint": ["idle"], "description": "k", "confidence": 1.0,
    })
    # update_asset_kind 는 호출돼도 'spritesheet' 로 — idempotent
    if store.update_asset_kind.called:
        for c in store.update_asset_kind.call_args_list:
            assert c.args[1] == "spritesheet"


def test_persist_spritesheet_payload_fts_includes_animation_tokens(tmp_path):
    """FTS 에 animation:idle 등 토큰 포함."""
    _aseprite_sheet(tmp_path, "pack/a", count=4, tags=[("idle", 0, 3)])
    p, store = _make_poller(tmp_path)
    asset = MagicMock(id=4, path="pack/a.png")
    p._persist_spritesheet_payload(asset, {
        "category": "character", "style": "pixel_art",
        "animation_hint": ["idle"], "description": "a", "confidence": 0.5,
    })
    _, fts_text = store.update_fts.call_args.args
    assert "animation:idle" in fts_text


def test_persist_spritesheet_payload_handles_invalid_animation_hint_gracefully(tmp_path):
    """animation_hint 가 enum 밖이면 demote, frameTags 만 남음."""
    _aseprite_sheet(tmp_path, "pack/b", count=2, tags=[("walk", 0, 1)])
    p, store = _make_poller(tmp_path)
    asset = MagicMock(id=5, path="pack/b.png")
    p._persist_spritesheet_payload(asset, {
        "category": "character", "style": "pixel_art",
        "animation_hint": ["bogus_label", "walk"], "description": "b", "confidence": 0.5,
    })
    saved_labels = store.save_asset_labels.call_args.args[1]
    anim = {l.label for l in saved_labels if l.axis == "animation"}
    assert "walk" in anim  # frameTags + validated payload
    assert "bogus_label" not in anim


def test_persist_spritesheet_payload_grid_only_sheet_still_gets_gemma_anim_labels(tmp_path):
    """JSON 사이드카 없는 grid-only 시트도 Gemma 의 animation_hint 추측을 라벨로 보존.

    M11.2 의 핵심 가치 — PR #18 한계 해소.
    """
    # 4 cell PNG only (no JSON sidecar)
    fw, fh = 32, 32
    img = Image.new("RGBA", (fw * 4, fh), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    for i in range(4):
        draw.rectangle(
            [i * fw + 4, 4, i * fw + fw - 4, fh - 4],
            fill=(255 - 50 * i, 50, 50, 255),
        )
    p_path = tmp_path / "pack/grid.png"
    p_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(p_path)

    p, store = _make_poller(tmp_path)
    asset = MagicMock(id=6, path="pack/grid.png")
    p._persist_spritesheet_payload(asset, {
        "category": "character", "style": "pixel_art",
        "animation_hint": ["run"], "description": "grid", "confidence": 0.7,
    })
    saved_labels = store.save_asset_labels.call_args.args[1]
    anim = {l.label for l in saved_labels if l.axis == "animation"}
    # grid-only 라 frameTags 는 비어 있지만 Gemma 의 'run' 은 살아남아야
    assert "run" in anim


def test_handle_succeeded_dispatches_chat_spritesheet_to_persist(tmp_path):
    """_handle_succeeded 의 modality switch 에 chat_spritesheet 분기 존재."""
    _aseprite_sheet(tmp_path, "pack/h", count=2, tags=[("idle", 0, 1)])
    p, store = _make_poller(tmp_path)

    asset = MagicMock(id=10, path="pack/h.png")
    store.list_assets_in_batch.return_value = [asset]
    job = MagicMock()
    job.id = 999
    job.modality = "chat_spritesheet"

    resp = MagicMock()
    resp.error = None
    resp.response.text = json.dumps({
        "category": "character", "style": "pixel_art",
        "animation_hint": ["idle"], "description": "h", "confidence": 0.5,
    })

    status = MagicMock()
    status.inlined_responses = [resp]
    status.file_name = None

    p._handle_succeeded(job, status, MagicMock())

    # backend_used 에 image 로 마킹
    store.mark_asset_backends.assert_called_with(10, image="gemini")
    # sprite_meta 저장됨 → spritesheet handler 분기 작동 확인
    store.save_sprite_meta.assert_called_once()
```

- [ ] **Step 5.1.2: 실패 확인**

Run: `pytest tests/test_batch_poller_spritesheet_modality.py -v`
Expected: 7 FAIL — `_persist_spritesheet_payload` 메서드 없음 + modality switch 미지원.

- [ ] **Step 5.1.3: 구현 — `_handle_succeeded` 에 chat_spritesheet 분기 추가**

`src/assetcache/core/batch/poller.py:194-209` 의 modality switch 블록을 다음으로 교체:

```python
            try:
                if job.modality == "chat_image":
                    payload = json.loads(resp.response.text)
                    self._persist_image_payload(asset, payload)
                    self._store.mark_asset_backends(asset.id, image="gemini")
                elif job.modality == "chat_spritesheet":
                    payload = json.loads(resp.response.text)
                    self._persist_spritesheet_payload(asset, payload)
                    self._store.mark_asset_backends(asset.id, image="gemini")
                elif job.modality == "chat_audio":
                    payload = json.loads(resp.response.text)
                    self._persist_audio_payload(asset, payload)
                    self._store.mark_asset_backends(asset.id, audio="gemini")
                elif job.modality == "text_embed":
                    vec = list(resp.embedding.values)
                    blob = _serialize_vec(vec)
                    model = self._get_gemini_embed_model()
                    self._store.save_embedding(asset.id, model, blob, len(vec))
                    self._store.mark_asset_backends(asset.id, embed="gemini")
                else:
                    raise ValueError(f"unknown modality {job.modality!r}")
```

- [ ] **Step 5.1.4: 구현 — `_persist_spritesheet_payload` 메서드 추가**

`src/assetcache/core/batch/poller.py:294` 의 `_persist_image_payload` 직후 (그리고 `_try_compute_sprite_meta` 직전) 에 추가:

```python
    def _persist_spritesheet_payload(self, asset, payload: dict) -> None:
        """시트 batch 결과를 sync SpritesheetAnalyzer 와 동등하게 persist.

        sync 와 차이:
        * sync 는 ``_call_gemma`` 가 동기로 호출 — 여기는 batch 응답을 받았을 뿐
          schema 동일.
        * 동일 ``validate_image_payload`` + ``image_payload_to_labels`` 사용 →
          animation_hint 가 enum 안에 있으면 그대로 라벨화.
        * ``_try_enrich_with_sheet`` 로 frame 박스 + frameTags 추가 라벨 (중복
          제거됨).  grid-only 시트도 Gemma animation_hint 가 살아남아 PR #18
          한계 해소.

        kind 는 이미 ``classify_image_assets`` 단계에서 ``spritesheet`` 로
        promote 된 상태.  ``_try_enrich_with_sheet`` 가 다시 호출돼도 idempotent.
        """
        analyzed_at = int(time.time())
        if self._registry is None:
            self._store.save_asset_labels(asset.id, [])
            self._store.mark_asset_state(
                asset.id, "ok", error=None, analyzed_at=analyzed_at,
            )
            return

        ok, err, fixed = validate_image_payload(payload, self._registry)
        if not ok:
            log.info(
                "batch spritesheet payload validation: asset_id=%d %s",
                asset.id, err,
            )
        labels = image_payload_to_labels(fixed)

        sprite_meta = self._try_compute_sprite_meta(asset)
        if sprite_meta is not None:
            sheet_result = self._try_enrich_with_sheet(asset, sprite_meta)
            if sheet_result is not None:
                sprite_meta, anim_labels = sheet_result
                # frameTags 추가 — 중복 (animation_hint 의 walk + frameTag 의 walk) 은
                # label key 기반으로 dedupe
                seen = {(l.axis, l.label) for l in labels}
                for new in anim_labels:
                    if (new.axis, new.label) not in seen:
                        labels.append(new)
                        seen.add((new.axis, new.label))
                # kind promote — chat_spritesheet 경로에서는 이미 promoted 지만
                # 누락된 케이스 (BatchManager 가 라이브러리 변경된 후 poll) 안전망
                self._store.update_asset_kind(asset.id, "spritesheet")
            self._store.save_sprite_meta(asset.id, sprite_meta)

        descs = collect_label_descriptions(labels, self._registry)
        searchable = build_searchable(
            meta=sprite_meta,
            labels=labels,
            label_descriptions=descs,
            description=fixed.get("description") or "",
            rel_path=asset.path,
        )
        self._store.save_asset_labels(asset.id, labels)
        self._store.update_fts(asset.id, searchable.for_fts)
        self._store.mark_asset_state(
            asset.id, "ok", error=None, analyzed_at=analyzed_at,
        )
```

- [ ] **Step 5.1.5: 테스트 통과 확인**

Run: `pytest tests/test_batch_poller_spritesheet_modality.py -v`
Expected: 7 PASS.

Run: `pytest tests/test_batch_poller*.py -q`
Expected: 회귀 0 (PR #18 의 `test_batch_poller_spritesheet.py` 가 chat_image 경로의 시트 검출 fallback 을 검증 — 그대로 통과해야).

### Task 5.2: 커밋

- [ ] **Step 5.2.1: 커밋**

```powershell
git add src/assetcache/core/batch/poller.py tests/test_batch_poller_spritesheet_modality.py
```

```powershell
git commit -m "M11.2 phase 5 — BatchPoller _persist_spritesheet_payload + modality switch"
```

---

## Phase 6 — UI / i18n / settings router

`/settings` 의 modality 표에 4번째 행 (`chat_spritesheet`) 추가, `/analyzing` dashboard 의 summary 에 `batch_spritesheet` 카운트 추가, settings router 의 `_VALID_MODALITIES` 갱신, ko/en `.po` 에 신규 msgid (`Batch spritesheet`, `spritesheet` 등) 추가.

### Task 6.1: Settings router `_VALID_MODALITIES` 갱신

**Files:**
- Modify: `src/assetcache/web/routers/settings.py:33`
- Test: `tests/test_settings_router.py` (기존 — append)

- [ ] **Step 6.1.1: 실패 테스트 추가**

`tests/test_settings_router.py` 적당한 위치 (chains 검증 영역 근처):

```python
def test_post_chains_accepts_chat_spritesheet():
    """settings router 가 chat_spritesheet 를 valid modality 로 인정."""
    from fastapi.testclient import TestClient
    from assetcache.web.app import create_app
    # ... 기존 픽스처 활용 (test_settings_router.py 의 helper 와 동일 패턴) ...
    # 핵심: POST /settings/chains with {"chat_spritesheet": ["ollama"]} → 200
```

(실제 fixture 는 `tests/test_settings_router.py` 기존 코드의 `_client` 헬퍼 참고.)

- [ ] **Step 6.1.2: 실패 확인**

Run: `pytest tests/test_settings_router.py::test_post_chains_accepts_chat_spritesheet -v`
Expected: FAIL — 400 `unknown modality: chat_spritesheet`.

- [ ] **Step 6.1.3: 구현 — `_VALID_MODALITIES` 확장**

`src/assetcache/web/routers/settings.py:33`:

```python
_VALID_MODALITIES = ("chat_image", "chat_spritesheet", "chat_audio", "text_embed")
```

- [ ] **Step 6.1.4: 테스트 통과 확인**

Run: `pytest tests/test_settings_router.py -q`
Expected: 회귀 0.

### Task 6.2: /analyzing dashboard 4행 modality

**Files:**
- Modify: `src/assetcache/web/routers/analyzing.py:31-54`
- Modify: `src/assetcache/web/templates/analyzing/_partial.html:11-22`
- Test: `tests/test_web_routers_analyzing.py` (기존 — append)

- [ ] **Step 6.2.1: 실패 테스트 추가**

`tests/test_web_routers_analyzing.py` 적당한 위치:

```python
def test_analyzing_partial_renders_batch_spritesheet_count(tmp_path):
    """summary 에 batch_spritesheet 카운트가 노출돼야."""
    from fastapi.testclient import TestClient
    # ... 기존 _make_client helper 활용 ...
    # 핵심: GET /analyzing/partial → HTML 에 'Batch spritesheet' 라벨 + 정수 카운트
```

(실제 fixture 는 기존 `_make_client` 패턴 참고.)

- [ ] **Step 6.2.2: 실패 확인**

Run: `pytest tests/test_web_routers_analyzing.py::test_analyzing_partial_renders_batch_spritesheet_count -v`
Expected: FAIL — 템플릿에 `batch_spritesheet` 변수 없음.

- [ ] **Step 6.2.3: 구현 — view_model 에 `batch_spritesheet` 추가**

`src/assetcache/web/routers/analyzing.py:28-58` 의 view_model 구성을 다음과 같이 갱신:

```python
    if aq is None:
        summary = {
            "interactive_count": 0,
            "batch_image": 0,
            "batch_spritesheet": 0,
            "batch_audio": 0,
            "batch_embed": 0,
            "eta_seconds": None,
        }
        interactive = {
            "in_flight_path": None,
            "queue": [],
        }
    else:
        progress = aq.progress()
        batch_image = aq.pending_by_modality("chat_image")
        batch_spritesheet = aq.pending_by_modality("chat_spritesheet")
        batch_audio = aq.pending_by_modality("chat_audio")
        batch_embed = aq.pending_by_modality("text_embed")
        interactive_assets = aq.snapshot_queue(limit=50)

        summary = {
            "interactive_count": progress.pending,
            "batch_image": batch_image,
            "batch_spritesheet": batch_spritesheet,
            "batch_audio": batch_audio,
            "batch_embed": batch_embed,
            "eta_seconds": progress.eta_seconds,
        }
        interactive = {
            "in_flight_path": progress.in_flight_path,
            "queue": interactive_assets,
        }
```

- [ ] **Step 6.2.4: 구현 — partial template Section A 4행 갱신**

`src/assetcache/web/templates/analyzing/_partial.html:11-22`:

```html
  {# ── Section A — 요약 ──────────────────────────────────────────── #}
  <section class="analyzing-summary">
    <h2>{{ _("Summary") }}</h2>
    <p>
      {{ _("Interactive queue") }}: <strong>{{ summary.interactive_count }}</strong>
      · {{ _("Batch image") }}: <strong>{{ summary.batch_image }}</strong>
      · {{ _("Batch spritesheet") }}: <strong>{{ summary.batch_spritesheet }}</strong>
      · {{ _("Batch audio") }}: <strong>{{ summary.batch_audio }}</strong>
      · {{ _("Batch embed") }}: <strong>{{ summary.batch_embed }}</strong>
      {% if summary.eta_seconds is not none and summary.eta_seconds > 0 %}
      · ETA: ~{{ (summary.eta_seconds / 60) | round(0) | int }} {{ _("minutes") }}
      {% endif %}
    </p>
  </section>
```

- [ ] **Step 6.2.5: 테스트 통과 확인**

Run: `pytest tests/test_web_routers_analyzing.py -q`
Expected: 회귀 0 + 새 테스트 PASS.

### Task 6.3: i18n msgid 추가

**Files:**
- Modify: `src/assetcache/locale/ko/LC_MESSAGES/assetcache.po`
- Modify: `src/assetcache/locale/en/LC_MESSAGES/assetcache.po`
- Test: `tests/test_i18n.py` (기존 — append)

- [ ] **Step 6.3.1: msgid 등록 — ko**

`src/assetcache/locale/ko/LC_MESSAGES/assetcache.po` 끝에 append:

```po
msgid "Batch spritesheet"
msgstr "배치 시트"

msgid "spritesheet"
msgstr "스프라이트시트"
```

- [ ] **Step 6.3.2: msgid 등록 — en**

`src/assetcache/locale/en/LC_MESSAGES/assetcache.po` 끝에 append:

```po
msgid "Batch spritesheet"
msgstr "Batch spritesheet"

msgid "spritesheet"
msgstr "spritesheet"
```

- [ ] **Step 6.3.3: .mo 컴파일**

```powershell
python -m babel compile -d src/assetcache/locale
```

Expected: ko + en `.mo` 갱신 (오류 없이).

- [ ] **Step 6.3.4: i18n 테스트 추가**

`tests/test_i18n.py` 끝에 append:

```python
def test_msgid_batch_spritesheet_registered_ko():
    from assetcache.web.i18n import get_translator
    t = get_translator("ko")
    assert t.gettext("Batch spritesheet") == "배치 시트"


def test_msgid_batch_spritesheet_registered_en():
    from assetcache.web.i18n import get_translator
    t = get_translator("en")
    assert t.gettext("Batch spritesheet") == "Batch spritesheet"
```

- [ ] **Step 6.3.5: 테스트 통과 확인**

Run: `pytest tests/test_i18n.py -q`
Expected: 회귀 0 + 새 테스트 PASS.

### Task 6.4: 커밋

- [ ] **Step 6.4.1: 커밋**

```powershell
git add src/assetcache/web/routers/settings.py src/assetcache/web/routers/analyzing.py src/assetcache/web/templates/analyzing/_partial.html src/assetcache/locale/ko/LC_MESSAGES/assetcache.po src/assetcache/locale/en/LC_MESSAGES/assetcache.po src/assetcache/locale/ko/LC_MESSAGES/assetcache.mo src/assetcache/locale/en/LC_MESSAGES/assetcache.mo tests/test_settings_router.py tests/test_web_routers_analyzing.py tests/test_i18n.py
```

```powershell
git commit -m "M11.2 phase 6 — UI/i18n: chat_spritesheet modality row + msgid"
```

---

## Phase 7 — 통합 / 회귀 / 옵트인 / docs / PR

전체 회귀 검증 + 옵트인 Gemini batch 실 호출 1건 추가 + verification 문서 + CLAUDE.md / HANDOFF.md 갱신.

### Task 7.1: 전체 회귀

- [ ] **Step 7.1.1: 전체 회귀 실행**

```powershell
pytest -q
```

Expected: 1490 baseline + ~40 신규 → 약 **1530 passed, 3 skipped, 56 deselected** (회귀 0). 만약 다른 테스트가 깨지면 root cause 먼저 — 새 동작이 옳고 기존 가정이 부정확했다면 기존 테스트 갱신, 그 외엔 구현 수정.

- [ ] **Step 7.1.2: 회귀 결과 메모**

깨진 테스트가 있으면 fix 후 재실행. 깨끗하면 다음 단계.

### Task 7.2: 옵트인 Gemini batch 실 호출 (선택)

**Files:**
- Modify: `tests/test_llm_backend_gemini_batch_integration.py` (기존 — `llm_integration` marker 케이스 append)

- [ ] **Step 7.2.1: 옵트인 케이스 추가**

`tests/test_llm_backend_gemini_batch_integration.py` 끝에 append:

```python
@pytest.mark.llm_integration
def test_batch_chat_spritesheet_submit_and_cancel():
    """실 Gemini API 로 chat_spritesheet batch 작업 제출 후 취소.

    GEMINI_API_KEY 가 설정돼 있어야 실행됨 (pytest -m llm_integration).
    Gemini 가 inlined composite PNG 를 받아 batch job 을 생성하는지 확인.
    """
    import base64
    import io
    import os
    from PIL import Image
    from assetcache.core.batch.types import BatchChatRequest
    from assetcache.core.llm.backends.gemini import GeminiBackend
    from assetcache.core.llm.base import ChatMessage

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set")

    # 8 frame composite strip
    img = Image.new("RGBA", (256, 32), (50, 50, 200, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    backend = GeminiBackend(
        api_key=api_key,
        model_image="gemini-3.1-flash-lite",
        model_audio="gemini-3.1-flash-lite",
        model_embed="gemini-embedding-001",
        timeout=60,
    )
    job_id = backend.batch_chat(
        modality="chat_spritesheet",
        requests=[BatchChatRequest(
            asset_id=1,
            messages=[
                ChatMessage(role="system", content="JSON only. animation_hint array."),
                ChatMessage(role="user", content="Identify.", images_b64=[b64]),
            ],
            force_json=True,
        )],
    )
    assert job_id.startswith("batches/")
    # 즉시 취소 — 실제 분석 비용 0
    backend.batch_cancel(job_id)
```

- [ ] **Step 7.2.2: 옵트인 케이스 실행 (선택, API key 보유 시)**

```powershell
pytest -m llm_integration tests/test_llm_backend_gemini_batch_integration.py::test_batch_chat_spritesheet_submit_and_cancel -v
```

Expected: PASS (또는 GEMINI_API_KEY 없으면 skip).

### Task 7.3: M11_2_todo.md + M11_2_verification.md 작성

- [ ] **Step 7.3.1: `milestones/M11_2_todo.md` 작성**

신규 파일. 본 plan 의 Phase 진행 체크리스트를 짧게 미러:

```markdown
# M11.2 TDD 체크리스트

자세한 step 은 [`docs/superpowers/plans/2026-05-21-m11-2-batch-spritesheet-modality.md`](../docs/superpowers/plans/2026-05-21-m11-2-batch-spritesheet-modality.md) 참고.

- [ ] Phase 1 — modality 분리 (store / config / chain / registry)
- [ ] Phase 2 — sheet_classifier
- [ ] Phase 3 — BATCH_SPRITESHEET_PROMPT + composite builder
- [ ] Phase 4 — BatchManager chat_spritesheet 분기 + AnalysisQueue + Gemini backend
- [ ] Phase 5 — BatchPoller _persist_spritesheet_payload
- [ ] Phase 6 — UI / i18n / settings router
- [ ] Phase 7 — 통합 / 옵트인 / verification / PR
```

- [ ] **Step 7.3.2: `milestones/M11_2_verification.md` 작성**

신규 파일:

```markdown
# M11.2 검증 — Batch Spritesheet Modality

## 1. 자동 검증

```powershell
pytest -q
```

Expected: ~1530 passed, 3 skipped, 56 deselected.  baseline 1490 + 신규 ~40.

옵트인 (GEMINI_API_KEY 필요):

```powershell
pytest -m llm_integration -q
```

Expected: 17 case (M11.1 16 + M11.2 1).

## 2. 수동 검증 시나리오

### 2.1 grid-only 시트 — Gemma animation_hint 보존
1. library 에 JSON 사이드카 없는 격자 PNG 1개 (e.g. 4 cell horizontal strip) 드롭.
2. `/settings` 에서 Gemini chain enabled + `chat_spritesheet` chain 도 [gemini, ollama] 인지 확인.
3. `cfg.batch.toggle="forced_on"` 으로 즉시 batch 진입.
4. `python -m assetcache --tray` 실행 후 `/analyzing` dashboard 에서 chat_image batch job 이 promote 만 하고 사라지는지, 곧 chat_spritesheet job 이 생성되는지 관찰.
5. job 완료 후 `sqlite3 %APPDATA%\AssetCacheMCP\library.db "SELECT axis, label FROM asset_labels WHERE asset_id=?"` — animation 라벨 1개 이상 있어야 (PR #18 까지는 0).

### 2.2 Aseprite 시트 — frameTags + Gemma 동시 라벨
1. Aseprite JSON 사이드카 있는 PNG 드롭.
2. 위와 동일 흐름으로 chat_spritesheet 진입.
3. DB 확인 — animation 라벨에 frameTags (예: idle/walk) + Gemma animation_hint (예: run) 모두 등록.

### 2.3 sprite 만 있는 라이브러리 — 회귀
1. 시트 0개, 단일 sprite 만 있는 라이브러리.
2. chat_image batch 정상 동작 (분류 후 sprite_rows = 전체) — `_partial.html` summary 의 batch_spritesheet=0 유지.

### 2.4 chains 누락 호환성
1. 기존 사용자 `config.toml` (chat_spritesheet 키 없음) 로 부팅.
2. `cfg.chains["chat_spritesheet"]` 가 chat_image 와 동일 chain 으로 자동 채워졌는지 `/settings` 에서 확인.

### 2.5 /analyzing 4행 modality
1. /analyzing 페이지 진입 — summary 가 4 modality (image/spritesheet/audio/embed) 표시.
2. ko/en 언어 토글 — "Batch spritesheet" → "배치 시트" 정상 번역.

## 3. 알려진 한계

- BatchManager 가 chat_image fetch 시 sheet 를 promote 만 하고 batch 0건 (전부 시트) 인 케이스 — 다음 sweep 의 chat_spritesheet 가 threshold 미달이면 대기.  M11.1 의 `forced_on` toggle 이 immediate submit 보장.
- `make_preview_composite` 가 detect_sheet 결과를 재사용하지 못해 BatchManager submit 시 + BatchPoller persist 시 두 번 detect 호출.  성능 문제는 크지 않음 (~ms 단위).  향후 batch_jobs row 에 detection JSON 캐시 가능.
- grid-only 시트의 frameTag 는 여전히 비어 있음 (sync 도 동일).  Gemma 의 animation_hint 추측만 의존.
```

### Task 7.4: CLAUDE.md + HANDOFF.md 갱신

**Files:**
- Modify: `CLAUDE.md` (M11.2 마일스톤 행 + §8 다음 작업 섹션)
- Modify: `HANDOFF.md`

- [ ] **Step 7.4.1: CLAUDE.md M11.2 행 status 갱신**

`CLAUDE.md` §2 의 M11.2 행을 다음 형식으로 갱신 (PR/v0.2.2 publish 는 머지 후 결정):

```markdown
| **M11.2 — Batch Spritesheet Modality** | ✅ 완료 (feat 브랜치 `feat/m11-2-batch-spritesheet-modality`, PR 대기) | `chat_spritesheet` modality + composite strip + 시트 전용 prompt → grid-only 시트의 animation 라벨 비어 있던 PR #18 한계 해소.  신규 모듈 3 (`core/batch/sheet_classifier.py` + `BATCH_SPRITESHEET_PROMPT` + `build_spritesheet_chat_messages`).  **+40 신규 테스트** (1490 → **1530**).  spec: [link], plan: [link], verification: [link] |
```

- [ ] **Step 7.4.2: CLAUDE.md §8 다음 작업 갱신**

M11.2 implement 완료 → 다음 세션 작업을 "v0.2.2 publish 결정" 또는 "M12 implement" 로 갱신.  구체 표현은 PR 머지 후.

- [ ] **Step 7.4.3: HANDOFF.md 갱신**

현재 상태 (브랜치 / 회귀 카운트 / 다음 작업) 한 줄 인계.

### Task 7.5: 커밋 + PR

- [ ] **Step 7.5.1: 최종 커밋**

```powershell
git add milestones/M11_2_todo.md milestones/M11_2_verification.md CLAUDE.md HANDOFF.md tests/test_llm_backend_gemini_batch_integration.py
```

```powershell
git commit -m "M11.2 phase 7 — verification + docs + opt-in integration case"
```

- [ ] **Step 7.5.2: push + PR 생성**

```powershell
git push -u origin feat/m11-2-batch-spritesheet-modality
```

PR 본문은 한글 (CLAUDE.md §4.1 + feedback `korean_for_pr_and_commits`).  AskUserQuestion popup 으로 PR 본문 초안 사용자 확인 → `gh pr create` 로 생성.

- [ ] **Step 7.5.3: 머지 후 (사용자 결정)**

- v0.2.2 publish — PR 머지 후 main 에서 `git tag v0.2.2 && git push origin v0.2.2` → Trusted Publishing 자동.
- 또는 다음 마일스톤 (M12 측정/벤치마크) 와 묶을지 사용자 결정.

---

## Self-Review (작성자 점검)

### 1. Spec coverage
- spec §3 의 결정 매트릭스 옵션 ④ → Phase 1~5 가 직접 구현 ✅
- spec §4 architecture → Phase 1 (modality 분리) + Phase 4 (BatchManager 분기) + Phase 5 (BatchPoller handler) ✅
- spec §5 module breakdown — 모든 신규/변경 파일 Task 에 매핑 ✅
- spec §6 test strategy — Phase 1~5 의 신규 테스트 파일 4종 + 옵트인 1건 (Phase 7) ✅
- spec §7 data shape — DB 마이그레이션 0 (변경 없음, batch_jobs.modality 자유 문자열) ✅
- spec §8 UI — Phase 6 의 settings + analyzing 4행 modality ✅
- spec §9 알려진 한계 — Phase 7 의 verification.md 에 mirror ✅

### 2. Placeholder scan
- Phase 6 의 router 테스트는 fixture 패턴이 기존 `test_settings_router.py` / `test_web_routers_analyzing.py` 의 `_make_client` 헬퍼를 그대로 사용한다 — 실 코드는 engineer 가 그 헬퍼 시그니처 보고 채워 넣음 (placeholder 아님 — 의도적 ref).
- 그 외 step 모두 실 코드 / 실 명령어로 채워져 있음 ✅

### 3. Type consistency
- `classify_image_assets` 반환 타입 `(list[tuple[AssetRow, SheetDetection]], list[AssetRow])` — Phase 2 정의 → Phase 4 `_do_submit` + `_build_spritesheet_requests` 가 동일 사용 ✅
- `build_spritesheet_chat_messages` 시그니처 keyword-only `abs_path, detection, prompt, anim_enum, max_long_edge` — Phase 3 정의 → Phase 4 `_build_spritesheet_requests` 가 동일 호출 ✅
- `_persist_spritesheet_payload` — Phase 5 정의 → Phase 5 `_handle_succeeded` modality switch 가 동일 호출 ✅

OK.
