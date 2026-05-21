"""M11.3 Phase 1 — classify_image_assets: detection cache + sprite_meta 자동 save.

PR #19 (M11.2) 머지 후 detect_sheet 가 시트당 3중 호출되는 한계를 줄이기 위한
첫 단계.  classify_image_assets 에 다음 두 인자를 추가:

* ``cache: dict[int, SheetDetection | None] | None`` — sweep 메모리 캐시.  hit
  시 detect_sheet 우회.  miss 시 결과(양성 detection 또는 None)를 cache 에 기록.
* ``save_sprite_meta: bool = True`` — 시트 hit 시 ``compute_sprite_meta`` +
  ``enrich_sprite_meta_with_sheet`` + ``store.save_sprite_meta`` 까지 자동 수행
  (옵션 B = DB cross-sweep cache 활성화).

cache 키는 ``row.id``.  cache 값은:
* ``SheetDetection`` 인스턴스 — 시트로 검출됨.
* ``None`` — 시트 아님이 확인됨 (다음에도 detect_sheet 호출 안 함).

라이브러리 없는 환경 / library_dir=None / detect 예외 → 기존과 동일 graceful skip.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from assetcache.core.batch.sheet_classifier import classify_image_assets
from assetcache.core.sheet.detect import SheetDetection
from assetcache.core.sheet.types import AnimationSpec, FrameSpec


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


def _synth_detection() -> SheetDetection:
    """테스트용 합성 SheetDetection — detect_sheet 우회 검증에 사용."""
    return SheetDetection(
        frames=[FrameSpec(x=0, y=0, w=32, h=32, duration_ms=83, name="0")],
        tags=[
            AnimationSpec(
                name="walk", start_frame=0, end_frame=3,
                fps_hint=12, source="json_tag",
            ),
        ],
        source="json",
    )


def test_cache_hit_skips_detect_sheet(tmp_path, monkeypatch):
    """cache 에 row.id 가 있으면 detect_sheet 호출 안 함."""
    from assetcache.core.batch import sheet_classifier as mod

    cached_det = _synth_detection()
    rows = [_row(id=1, path="pack/anything.png")]

    calls: list[Path] = []

    def fake_detect_sheet(p):
        calls.append(p)
        raise AssertionError(
            f"detect_sheet should not be called on cache hit, got {p}",
        )

    monkeypatch.setattr(mod, "detect_sheet", fake_detect_sheet)
    store = MagicMock()
    cache = {1: cached_det}

    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store, cache=cache,
        save_sprite_meta=False,
    )

    assert calls == []
    assert len(sheet_results) == 1
    assert sheet_results[0][1] is cached_det
    assert sprite_rows == []
    store.update_asset_kind.assert_called_once_with(1, "spritesheet")


def test_cache_hit_none_short_circuits_to_sprite(tmp_path, monkeypatch):
    """cache[id] = None (이미 시트 아님 확인) → detect_sheet 우회 + sprite_rows."""
    from assetcache.core.batch import sheet_classifier as mod

    rows = [_row(id=2, path="pack/anything.png")]
    calls: list[Path] = []

    def fake_detect_sheet(p):
        calls.append(p)
        raise AssertionError("detect_sheet should not be called on cache hit")

    monkeypatch.setattr(mod, "detect_sheet", fake_detect_sheet)
    store = MagicMock()
    cache: dict[int, "SheetDetection | None"] = {2: None}

    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store, cache=cache,
        save_sprite_meta=False,
    )

    assert calls == []
    assert sheet_results == []
    assert len(sprite_rows) == 1 and sprite_rows[0].id == 2
    store.update_asset_kind.assert_not_called()


def test_cache_miss_populates_cache_with_detection(tmp_path):
    """cache 비어 있으면 detect_sheet 결과를 cache 에 저장 (양성)."""
    _png(tmp_path, "pack/hero.png", size=(128, 32))
    _aseprite_sidecar(
        tmp_path, "pack/hero.json",
        frame_w=32, frame_h=32, count=4, tags=[("idle", 0, 3)],
    )
    rows = [_row(id=5, path="pack/hero.png")]
    store = MagicMock()
    cache: dict[int, "SheetDetection | None"] = {}

    sheet_results, _ = classify_image_assets(
        rows, library_dir=tmp_path, store=store, cache=cache,
        save_sprite_meta=False,
    )

    assert 5 in cache
    assert cache[5] is not None
    assert isinstance(cache[5], SheetDetection)
    assert cache[5] is sheet_results[0][1]


def test_cache_miss_records_none_for_non_sheet(tmp_path):
    """단일 sprite (시트 아님) → cache[id] = None 음성 결과도 저장."""
    _png(tmp_path, "pack/single.png", size=(32, 32))
    rows = [_row(id=7, path="pack/single.png")]
    store = MagicMock()
    cache: dict[int, "SheetDetection | None"] = {}

    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store, cache=cache,
        save_sprite_meta=False,
    )

    assert sheet_results == []
    assert len(sprite_rows) == 1
    assert 7 in cache
    assert cache[7] is None


def test_save_sprite_meta_true_enriches_and_saves_on_sheet_hit(tmp_path):
    """save_sprite_meta=True (default) → 시트 hit 시 store.save_sprite_meta 호출.

    옵션 B 의 핵심 — sprite_meta.animations_json 에 frameTags 저장돼야
    Phase 3 의 BatchPoller cache hit 이 detect_sheet 우회 가능.
    """
    _png(tmp_path, "pack/hero.png", size=(128, 32))
    _aseprite_sidecar(
        tmp_path, "pack/hero.json",
        frame_w=32, frame_h=32, count=4, tags=[("idle", 0, 3)],
    )
    rows = [_row(id=9, path="pack/hero.png")]
    store = MagicMock()

    classify_image_assets(
        rows, library_dir=tmp_path, store=store,
    )

    store.save_sprite_meta.assert_called_once()
    args, _ = store.save_sprite_meta.call_args
    saved_asset_id, saved_meta = args
    assert saved_asset_id == 9
    assert saved_meta.frame_w == 32
    assert saved_meta.frame_h == 32
    assert saved_meta.frame_count == 4
    assert saved_meta.animations_json is not None
    assert "idle" in saved_meta.animations_json


def test_save_sprite_meta_false_skips_save_but_still_promotes(tmp_path):
    """save_sprite_meta=False → store.save_sprite_meta 호출 X, kind promote 는 O."""
    _png(tmp_path, "pack/hero.png", size=(128, 32))
    _aseprite_sidecar(
        tmp_path, "pack/hero.json",
        frame_w=32, frame_h=32, count=4, tags=[("idle", 0, 3)],
    )
    rows = [_row(id=11, path="pack/hero.png")]
    store = MagicMock()

    classify_image_assets(
        rows, library_dir=tmp_path, store=store,
        save_sprite_meta=False,
    )

    store.save_sprite_meta.assert_not_called()
    store.update_asset_kind.assert_called_once_with(11, "spritesheet")


def test_cache_none_default_preserves_existing_behavior(tmp_path):
    """cache=None (default) → 기존 동작 그대로, detect_sheet 매번 호출."""
    _png(tmp_path, "pack/hero.png", size=(128, 32))
    _aseprite_sidecar(
        tmp_path, "pack/hero.json",
        frame_w=32, frame_h=32, count=4, tags=[("idle", 0, 3)],
    )
    rows = [_row(id=13, path="pack/hero.png")]
    store = MagicMock()

    sheet_results, sprite_rows = classify_image_assets(
        rows, library_dir=tmp_path, store=store,
        # cache 인자 생략 — 기존 호출자 호환
    )

    assert len(sheet_results) == 1
    assert sprite_rows == []
    store.update_asset_kind.assert_called_once_with(13, "spritesheet")
