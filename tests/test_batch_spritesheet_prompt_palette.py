"""M11.6 A1 — BATCH_SPRITESHEET_PROMPT palette enum + tone group + hex 금지.

M11.5 LIVE 검증의 별도 발견 #1: 시트 자산 5/5 palette 라벨 부재.  원인은
`BATCH_SPRITESHEET_PROMPT` 가 palette 응답을 명시 안 하고 ``mood: []`` /
``palette: []`` 빈 배열로만 schema 를 제시하는 것.  BATCH_IMAGE_PROMPT 와
동일한 tone group enum (warm/cool/monochrome/high_contrast/pastel/neutral)
+ hex 금지 가이드를 추가해 spritesheet batch 응답도 palette 라벨을 채우게
한다.
"""
from __future__ import annotations

from assetcache.core.analyzer.messages import BATCH_SPRITESHEET_PROMPT


def test_spritesheet_prompt_lists_palette_tone_groups() -> None:
    """palette tone group 6 토큰 모두 prompt 에 노출."""
    for tone in (
        "warm", "cool", "monochrome", "high_contrast", "pastel", "neutral",
    ):
        assert tone in BATCH_SPRITESHEET_PROMPT, (
            f"missing tone group {tone!r} in BATCH_SPRITESHEET_PROMPT"
        )


def test_spritesheet_prompt_rejects_hex_palette() -> None:
    """hex 코드 (#FDD835) 사용 금지 가이드 명시."""
    lower = BATCH_SPRITESHEET_PROMPT.lower()
    assert "hex" in lower, "BATCH_SPRITESHEET_PROMPT must forbid hex codes"


def test_spritesheet_prompt_still_requests_json_only_response() -> None:
    """기존 'JSON only' 제약 + animation_hint placeholder 보존."""
    lower = BATCH_SPRITESHEET_PROMPT.lower()
    assert "json" in lower
    # animation_hint enum placeholder 는 builder 가 동적 치환
    assert "{anim_enum}" in BATCH_SPRITESHEET_PROMPT
    # 필수 필드 보존
    for field in ("animation_hint", "palette", "confidence"):
        assert field in lower
