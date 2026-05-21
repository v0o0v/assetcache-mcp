"""M11.6 A2-prompt — BATCH_IMAGE_PROMPT + BATCH_SPRITESHEET_PROMPT 에
'other' fallback 응답 금지 가이드.

M11.5 LIVE 검증의 별도 발견 #2: animation='other' 가 6 자산 중 4 자산에
합산됨.  prompt 가 enum 안에 'other' 를 valid 응답으로 노출해 모델이
미분류 케이스를 'other' 로 덤프하는 패턴.  enum 자체는 그대로 두되,
"do NOT use 'other'" 가이드를 추가해 모델이 가장 가까운 enum 값을 고르도록
유도한다.
"""
from __future__ import annotations

from assetcache.core.analyzer.messages import (
    BATCH_IMAGE_PROMPT,
    BATCH_SPRITESHEET_PROMPT,
)


def test_image_prompt_forbids_other_fallback() -> None:
    """BATCH_IMAGE_PROMPT 에 'do NOT use "other"' 또는 동등 표현."""
    lower = BATCH_IMAGE_PROMPT.lower()
    assert "other" in lower  # enum 안에 여전히 등장 가능
    # 금지 가이드 — "do not use 'other'" / "do not use \"other\""
    assert "do not use" in lower or "do not respond with" in lower, (
        "BATCH_IMAGE_PROMPT must include explicit 'do NOT use \"other\"' guidance"
    )
    # 'other' 와 do-not 가이드가 같은 문장에서 등장하는지 추가 검증
    assert "\"other\"" in BATCH_IMAGE_PROMPT or "'other'" in BATCH_IMAGE_PROMPT, (
        "BATCH_IMAGE_PROMPT must quote 'other' explicitly in the no-fallback guidance"
    )


def test_spritesheet_prompt_forbids_other_fallback() -> None:
    """BATCH_SPRITESHEET_PROMPT 에 'do NOT use "other"' 또는 동등 표현."""
    lower = BATCH_SPRITESHEET_PROMPT.lower()
    assert "do not use" in lower or "do not respond with" in lower, (
        "BATCH_SPRITESHEET_PROMPT must include explicit 'do NOT use \"other\"' guidance"
    )
    assert "\"other\"" in BATCH_SPRITESHEET_PROMPT or "'other'" in BATCH_SPRITESHEET_PROMPT, (
        "BATCH_SPRITESHEET_PROMPT must quote 'other' explicitly in the no-fallback guidance"
    )
