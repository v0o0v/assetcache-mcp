"""M6 — sheet detection 오케스트레이션 (JSON 사이드카 → grid → None)."""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from assetcache.core.sheet.detect import SheetDetection, detect_sheet

FIXTURES = Path(__file__).parent / "fixtures" / "sheets"


def _save_sheet_png(path: Path, frame_count: int, fw: int = 32, fh: int = 32,
                    gap: int = 2) -> None:
    total_w = frame_count * fw + (frame_count - 1) * gap
    img = Image.new("RGBA", (total_w, fh), (0, 0, 0, 0))
    for i in range(frame_count):
        tile = Image.new("RGBA", (fw, fh), (200, 100, 50, 255))
        img.paste(tile, (i * (fw + gap), 0))
    img.save(path)


def test_json_sidecar_preferred(tmp_path):
    # PNG + JSON 모두 있으면 JSON 사용 (frames 가 JSON 기준)
    png = tmp_path / "hero_walk_aseprite_array.png"
    json_src = FIXTURES / "hero_walk_aseprite_array.json"
    _save_sheet_png(png, frame_count=8)
    shutil.copy(json_src, tmp_path / "hero_walk_aseprite_array.json")

    detection = detect_sheet(png)
    assert detection is not None
    assert detection.source == "json"
    assert len(detection.frames) == 8
    assert len(detection.tags) == 1


def test_grid_fallback_when_no_json(tmp_path):
    png = tmp_path / "slime.png"
    _save_sheet_png(png, frame_count=4)
    detection = detect_sheet(png)
    assert detection is not None
    assert detection.source == "grid"
    assert len(detection.frames) == 4
    assert detection.tags == []


def test_returns_none_when_no_json_and_no_grid(tmp_path):
    # 단일 프레임 — JSON 없음, grid 검출 불가
    png = tmp_path / "sword.png"
    Image.new("RGBA", (32, 32), (200, 100, 50, 255)).save(png)
    assert detect_sheet(png) is None


def test_sidecar_path_naming(tmp_path):
    # png 와 같은 이름의 .json
    png = tmp_path / "abc.png"
    json_path = tmp_path / "abc.json"
    _save_sheet_png(png, frame_count=8)
    shutil.copy(FIXTURES / "hero_walk_aseprite_array.json", json_path)
    detection = detect_sheet(png)
    assert detection is not None
    assert detection.source == "json"


def test_invalid_image_returns_none(tmp_path):
    # PNG 아닌 파일 — Pillow open 실패
    p = tmp_path / "junk.bin"
    p.write_bytes(b"not a real image")
    assert detect_sheet(p) is None


def test_sheet_detection_dataclass_fields():
    sd = SheetDetection(frames=[], tags=[], source="grid")
    assert sd.frames == []
    assert sd.tags == []
    assert sd.source == "grid"


# === M11.3 patch D-2 — FrameSpec.w/h 는 slot size (stride) =================


def test_grid_detect_frame_size_uses_slot_not_content_bounds(tmp_path):
    """gap 없는 시트 + 프레임당 padded content → FrameSpec.w/h 가 slot 크기.

    M11.3 patch D-2 — 사용자 검증 v2 에서 발견한 한계: grid_detect 의
    `frame_w` 는 alpha-tight 경계만 보고 좁게 계산해 (32 슬롯에 17 padding
    bound 같은 결과) sprite_meta.frame_w 가 실제 frame 크기 (애니메이션 재생
    슬롯 크기) 와 어긋남.  detect_sheet 가 FrameSpec 의 w/h 에 ``stride_x``
    (``total_w // cols``) 와 ``stride_y`` 를 사용해야 slot 크기가 정확함.
    """
    fw_slot, fh_slot = 32, 32
    cols = 4
    total_w = fw_slot * cols
    img = Image.new("RGBA", (total_w, fh_slot), (0, 0, 0, 0))
    # 각 frame 안에 16×16 content 만 (8px padding 사방) — grid_detect 가 tight
    # bound 만 보면 frame_w 를 16~17 으로 잘못 계산하는 케이스를 reproduces.
    content_pad = 8
    content_w = fw_slot - 2 * content_pad
    content_h = fh_slot - 2 * content_pad
    for i in range(cols):
        tile = Image.new("RGBA", (content_w, content_h), (200, 100, 50, 255))
        img.paste(tile, (i * fw_slot + content_pad, content_pad))
    png = tmp_path / "padded.png"
    img.save(png)

    detection = detect_sheet(png)
    assert detection is not None
    assert detection.source == "grid"
    assert len(detection.frames) == cols
    # slot 크기 (stride) — 사용자가 sprite_meta.frame_w 로 보는 값.
    for i, frame in enumerate(detection.frames):
        assert frame.w == fw_slot, (
            f"frame[{i}].w = {frame.w}, expected slot size {fw_slot}"
        )
        assert frame.h == fh_slot, (
            f"frame[{i}].h = {frame.h}, expected slot size {fh_slot}"
        )
    # 좌표는 slot 시작점 (0, 32, 64, …) 이어야
    assert [f.x for f in detection.frames] == [i * fw_slot for i in range(cols)]


def test_grid_detect_existing_gap_sheet_frame_size_matches_stride(tmp_path):
    """기존 _save_sheet_png 가 만드는 gap 시트 (gap=2) 의 frame.w 가 stride 와 일치.

    M11.3 patch D-2 — total_w = cols*fw + (cols-1)*gap.  stride = total_w//cols.
    검증: 기존 회귀 호환 유지 — 4×32 + 3×2 = 134, stride = 33.  alpha-tight
    경계는 32 였으나 패치 후 stride 33 사용 (slot 크기 더 정확).
    """
    fw_content, fh, count, gap = 32, 32, 4, 2
    total_w = count * fw_content + (count - 1) * gap
    img = Image.new("RGBA", (total_w, fh), (0, 0, 0, 0))
    for i in range(count):
        tile = Image.new("RGBA", (fw_content, fh), (200, 100, 50, 255))
        img.paste(tile, (i * (fw_content + gap), 0))
    png = tmp_path / "with_gap.png"
    img.save(png)

    detection = detect_sheet(png)
    assert detection is not None
    expected_stride = total_w // count
    # 모든 frame 이 동일 stride 크기.
    for frame in detection.frames:
        assert frame.w == expected_stride, f"frame.w={frame.w}, expected stride={expected_stride}"
