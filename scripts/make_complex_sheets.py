"""M11.3 ~ M11.5 LIVE 검증용 합성 자산 6종 생성.

사용:

    python scripts/make_complex_sheets.py <out_dir>

`<out_dir>` 가 비어 있는 디렉토리여야 한다.  6개 파일을 만든다:

| 자산 | 종류 | 파일 |
|---|---|---|
| hero_warrior   | Aseprite 4×4 (64px, 16f, 4 anim)  | hero_warrior.png + .json |
| mage_purple    | Aseprite 3×4 (48px, 12f, 3 anim)  | mage_purple.png + .json |
| knight_gold    | grid 1×8 (32px slot, content 17px) | knight_gold.png |
| monster_red    | grid 2×2 (48px slot, content 41px) | monster_red.png |
| elemental_cyan | alpha-uniform color cycle 1×6 64px | elemental_cyan.png |
| crown_icon     | single 32px inventory icon          | crown_icon.png |

M11.3 v2 / M11.4 / M11.5 의 fresh `--data-dir` LIVE 검증에서 사용하는 자산을
재현 가능하게 한다.  Aseprite/TexturePacker 라이선스 자산을 외부에서 받지
않고도 PR 검증 환경을 만들 수 있게 하는 게 목적.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def _aseprite_sheet(
    out_path: Path,
    *,
    cols: int,
    rows: int,
    frame_size: int,
    body_color: tuple[int, int, int],
    accent_color: tuple[int, int, int],
    tags: list[tuple[str, int, int]],
    duration_ms: int = 100,
) -> None:
    """Aseprite atlas (frames=dict + meta.frameTags) + PNG 시트 생성."""
    sheet_w = cols * frame_size
    sheet_h = rows * frame_size
    img = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    n = cols * rows
    for idx in range(n):
        c = idx % cols
        r = idx // cols
        x0 = c * frame_size + 8
        y0 = r * frame_size + 8
        x1 = (c + 1) * frame_size - 8
        y1 = (r + 1) * frame_size - 8
        # body
        draw.rectangle((x0, y0, x1, y1), fill=body_color + (255,))
        # accent (frame index visual cue)
        ax = x0 + 4 + (idx % 4) * 4
        draw.rectangle((ax, y0 + 4, ax + 4, y0 + 12),
                       fill=accent_color + (255,))
    img.save(out_path)

    # JSON sidecar
    frames: dict = {}
    for idx in range(n):
        c = idx % cols
        r = idx // cols
        name = f"{out_path.stem} {idx}.png"
        frames[name] = {
            "frame": {"x": c * frame_size, "y": r * frame_size,
                      "w": frame_size, "h": frame_size},
            "duration": duration_ms,
        }
    frame_tags = [
        {"name": name, "from": start, "to": end, "direction": "forward"}
        for name, start, end in tags
    ]
    meta = {
        "app": "https://www.aseprite.org/",
        "version": "1.3.0",
        "image": out_path.name,
        "format": "RGBA8888",
        "size": {"w": sheet_w, "h": sheet_h},
        "scale": "1",
        "frameTags": frame_tags,
    }
    sidecar = out_path.with_suffix(".json")
    sidecar.write_text(
        json.dumps({"frames": frames, "meta": meta}, indent=2),
        encoding="utf-8",
    )


def _grid_sheet_content_smaller_than_slot(
    out_path: Path,
    *,
    cols: int,
    rows: int,
    slot_size: int,
    content_size: int,
    body_color: tuple[int, int, int],
) -> None:
    """sidecar 없는 grid 시트 — alpha 빈 padding 포함.

    grid_detect 가 alpha-tight 로 ``frame_w=content_size`` 를 보고하지만 D-2
    patch (detect.py) 가 ``stride = total_w / cols`` 로 보정 → ``sprite_meta``
    의 frame_w 는 slot_size 가 된다.  본 검증의 핵심은 stride 보정과 검출이
    성공하는지 여부.
    """
    sheet_w = cols * slot_size
    sheet_h = rows * slot_size
    img = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = (slot_size - content_size) // 2
    for r in range(rows):
        for c in range(cols):
            x0 = c * slot_size + pad
            y0 = r * slot_size + pad
            x1 = x0 + content_size
            y1 = y0 + content_size
            draw.ellipse((x0, y0, x1, y1), fill=body_color + (255,))
    img.save(out_path)


def _elemental_cyan_color_cycle(out_path: Path) -> None:
    """alpha-uniform 6 frame 색상 cycle — M11.4 D-1 핵심 케이스.

    모든 픽셀 alpha=255, 배경색만 frame 마다 다름 + 중앙 검은 orb.  M11.3 의
    alpha-valley 알고리즘이 sprite 로 오분류한 자산.  M11.4 color-edge fallback
    이 spritesheet 로 promote 해야 한다.
    """
    colors = [
        (0, 200, 200), (200, 0, 200), (200, 200, 0),
        (200, 0, 0), (0, 0, 200), (0, 200, 0),
    ]
    frame = 64
    img = Image.new("RGBA", (6 * frame, frame), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    for i, color in enumerate(colors):
        x0 = i * frame
        draw.rectangle((x0, 0, x0 + frame, frame), fill=color + (255,))
        # 중앙 검은 orb (frame 마다 위치 동일 → "centered_orb" 시나리오)
        cx = x0 + frame // 2
        cy = frame // 2
        draw.ellipse((cx - 16, cy - 16, cx + 16, cy + 16),
                     fill=(20, 20, 20, 255))
    img.save(out_path)


def _crown_icon(out_path: Path) -> None:
    """단순 32px 노란 왕관 아이콘 — inventory_item 후보.

    M11.3 v2 에서 Gemini 가 character 로 잘못 분류 → M11.4 prompt 강화 →
    M11.5 LIVE 검증으로 효과 측정.
    """
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    gold = (255, 200, 40, 255)
    # 사다리꼴 본체
    draw.polygon([(6, 24), (26, 24), (24, 16), (8, 16)], fill=gold)
    # 봉우리 3개
    draw.polygon([(6, 16), (10, 16), (8, 8)], fill=gold)
    draw.polygon([(14, 16), (18, 16), (16, 6)], fill=gold)
    draw.polygon([(22, 16), (26, 16), (24, 8)], fill=gold)
    # 빨간 보석 1개
    draw.ellipse((14, 18, 18, 22), fill=(220, 30, 30, 255))
    img.save(out_path)


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # hero_warrior — Aseprite 4×4, 64px, 16f, 4 anims
    _aseprite_sheet(
        out_dir / "hero_warrior.png",
        cols=4, rows=4, frame_size=64,
        body_color=(60, 110, 200),
        accent_color=(240, 230, 200),
        tags=[
            ("idle", 0, 3),
            ("walk", 4, 7),
            ("attack", 8, 11),
            ("hurt", 12, 15),
        ],
    )

    # mage_purple — Aseprite 3×4, 48px, 12f, 3 anims
    _aseprite_sheet(
        out_dir / "mage_purple.png",
        cols=3, rows=4, frame_size=48,
        body_color=(140, 70, 200),
        accent_color=(240, 200, 240),
        tags=[
            ("cast", 0, 3),
            ("idle", 4, 7),
            ("walk", 8, 11),
        ],
    )

    # knight_gold — grid 1×8, slot 32, content 17×28 (anisotropic)
    # 17×28 content 를 만들기 위해 ellipse 가 아닌 직접 rect 로 그린다
    _knight = out_dir / "knight_gold.png"
    img = Image.new("RGBA", (8 * 32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for c in range(8):
        # 17×28 직사각형, slot 안에서 가운데 정렬
        x0 = c * 32 + (32 - 17) // 2
        y0 = (32 - 28) // 2
        draw.rectangle((x0, y0, x0 + 17, y0 + 28),
                       fill=(220, 180, 60, 255))
    img.save(_knight)

    # monster_red — grid 2×2, slot 48, content 41×41
    _grid_sheet_content_smaller_than_slot(
        out_dir / "monster_red.png",
        cols=2, rows=2, slot_size=48, content_size=41,
        body_color=(200, 50, 50),
    )

    # elemental_cyan — alpha-uniform color cycle 1×6 64px (D-1 target)
    _elemental_cyan_color_cycle(out_dir / "elemental_cyan.png")

    # crown_icon — single 32px inventory icon (LLM #3 target)
    _crown_icon(out_dir / "crown_icon.png")

    print(f"Generated 6 assets in {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/make_complex_sheets.py <out_dir>")
        sys.exit(1)
    main(Path(sys.argv[1]))
