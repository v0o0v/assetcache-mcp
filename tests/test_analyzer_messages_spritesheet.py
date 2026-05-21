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
