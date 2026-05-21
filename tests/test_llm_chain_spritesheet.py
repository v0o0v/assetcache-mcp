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
