"""M11.2 — BatchManager 의 chat_spritesheet modality 분기."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from assetcache.core.batch.manager import BatchManager


def _make_manager(*, library_dir: Path | None, threshold: int = 1):
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
    """try_submit 가 'chat_spritesheet' 를 valid modality 로 인식 — 'invalid modality' 경고 안 남."""
    mgr, store, chain, aq = _make_manager(library_dir=None)
    # backend 없음 — 진행은 first_backend 까지 가야 하므로 None 반환 가능
    chain.first_backend.return_value = None
    out = mgr.try_submit("chat_spritesheet")
    # invalid 가 아니라면 first_backend 호출됨
    chain.first_backend.assert_called_with("chat_spritesheet")
    assert out is None


def test_try_submit_chat_image_classifies_and_promotes_sheets(tmp_path):
    """chat_image fetch 시 sheet 식별 → kind promote + sprite_rows 만 batch submit."""
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

    job_id = mgr.try_submit("chat_spritesheet")

    backend.batch_chat.assert_called_once()
    call = backend.batch_chat.call_args
    assert call.kwargs["modality"] == "chat_spritesheet"
    sent_ids = [req.asset_id for req in call.kwargs["requests"]]
    assert sent_ids == [100]
    assert job_id == 500


def test_try_submit_chat_image_no_library_dir_skips_classification(tmp_path):
    """library_dir=None 이면 classification skip → legacy 동작 (전체 sprite)."""
    # library_dir=None 경로에서는 row.path 가 절대 경로로 해석됨 — 실 파일 필요.
    img = tmp_path / "x.png"
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(img)
    mgr, store, chain, aq = _make_manager(library_dir=None, threshold=1)
    store.count_pending_by_modality.return_value = 1
    store.fetch_pending_by_modality.return_value = [_row(id=1, path=str(img))]
    backend = _gemini_backend()
    chain.first_backend.return_value = backend
    store.save_batch_job.return_value = 1

    mgr.try_submit("chat_image")
    backend.batch_chat.assert_called_once()
    store.update_asset_kind.assert_not_called()


def test_try_submit_chat_spritesheet_with_no_detect_hits_returns_none(tmp_path):
    """chat_spritesheet 큐에 들어왔지만 detect_sheet 모두 miss → submit 0."""
    # 단일 sprite — detect_sheet miss 예상
    p = tmp_path / "pack/not_a_sheet.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(p)

    mgr, store, chain, aq = _make_manager(library_dir=tmp_path, threshold=1)
    store.count_pending_by_modality.return_value = 1
    store.fetch_pending_by_modality.return_value = [
        _row(id=200, path="pack/not_a_sheet.png", kind="spritesheet"),
    ]
    backend = _gemini_backend()
    chain.first_backend.return_value = backend

    out = mgr.try_submit("chat_spritesheet")
    assert out is None
    backend.batch_chat.assert_not_called()
