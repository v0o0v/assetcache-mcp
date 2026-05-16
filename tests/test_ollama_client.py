"""OllamaClient HTTP tests using ``respx`` for both OpenAI-compatible
and Ollama-native paths.
"""

from __future__ import annotations

import json

import httpx
import pytest

from gah.core.ollama_client import (
    ChatMessage,
    OllamaClient,
    OllamaError,
    encode_audio_clip,
    encode_image,
)


def _make_client(
    base_url: str = "http://127.0.0.1:11434",
    model: str = "gemma4:e4b",
    timeout: float = 5.0,
    max_retries: int = 3,
) -> OllamaClient:
    return OllamaClient(
        base_url=base_url, model=model,
        timeout_seconds=timeout, max_retries=max_retries,
    )


def _openai_response(content_obj: dict) -> dict:
    return {
        "choices": [
            {"message": {"role": "assistant",
                         "content": json.dumps(content_obj)}}
        ]
    }


def _native_response(content_obj: dict) -> dict:
    return {"message": {"role": "assistant",
                        "content": json.dumps(content_obj)}}


# ── 라우팅: OpenAI 1차 + 네이티브 폴백 ──────────────────────────────


class TestChatRouting:
    def test_chat_uses_openai_endpoint_first(self, mock_ollama) -> None:
        route = mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=httpx.Response(200, json=_openai_response({"ok": True})))
        client = _make_client()
        result = client.chat([ChatMessage(role="user", content="hi")])
        assert result == {"ok": True}
        assert route.called

    def test_chat_falls_back_to_native_on_openai_4xx(self, mock_ollama) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=httpx.Response(404, text="not found"))
        native = mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(return_value=httpx.Response(200, json=_native_response({"ok": True})))
        client = _make_client()
        result = client.chat([ChatMessage(role="user", content="hi")])
        assert result == {"ok": True}
        assert native.called

    def test_chat_falls_back_to_native_on_connect_error(self, mock_ollama) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=httpx.ConnectError("no route"))
        native = mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(return_value=httpx.Response(200, json=_native_response({"ok": True})))
        client = _make_client()
        result = client.chat([ChatMessage(role="user", content="hi")])
        assert result == {"ok": True}
        assert native.called


# ── 페이로드 모양 — 메모리 결정 검증 ────────────────────────────────


class TestPayloadShape:
    def test_native_payload_packs_image_and_audio_into_single_images_field(
        self, mock_ollama
    ) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_native_response({"ok": True}))

        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=httpx.Response(500))
        mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(side_effect=handler)

        client = _make_client()
        msg = ChatMessage(
            role="user", content="please",
            images_b64=["AAA"],
            audio_b64=[("BBB", "audio/wav")],
        )
        client.chat([msg])
        body = captured["body"]
        # 메모리 project_ollama_multimodal_api_shape: 이미지·오디오 모두 같은 images 배열
        assert body["messages"][0]["images"] == ["AAA", "BBB"]

    def test_openai_payload_uses_image_url_data_uri(self, mock_ollama) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_openai_response({"ok": True}))

        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=handler)
        client = _make_client()
        msg = ChatMessage(role="user", content="see", images_b64=["AAA"])
        client.chat([msg])
        content_items = captured["body"]["messages"][0]["content"]
        url_parts = [c for c in content_items if c.get("type") == "image_url"]
        assert url_parts
        assert url_parts[0]["image_url"]["url"].startswith("data:image/")

    def test_openai_payload_uses_input_audio_dict(self, mock_ollama) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_openai_response({"ok": True}))

        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=handler)
        client = _make_client()
        msg = ChatMessage(
            role="user", content="listen",
            audio_b64=[("BBB", "audio/wav")],
        )
        client.chat([msg])
        content_items = captured["body"]["messages"][0]["content"]
        audio_parts = [c for c in content_items if c.get("type") == "input_audio"]
        assert audio_parts
        assert audio_parts[0]["input_audio"]["data"] == "BBB"
        assert audio_parts[0]["input_audio"]["format"] == "wav"


# ── force_json + 재시도 ─────────────────────────────────────────────


class TestRetry:
    def test_chat_force_json_retries_on_invalid_json(self, mock_ollama) -> None:
        responses = [
            httpx.Response(200, json={"choices": [{"message":
                                                   {"content": "not json"}}]}),
            httpx.Response(200, json=_openai_response({"ok": True})),
        ]
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=responses)
        client = _make_client(max_retries=3)
        result = client.chat(
            [ChatMessage(role="user", content="hi")], force_json=True
        )
        assert result == {"ok": True}

    def test_chat_gives_up_after_max_retries(self, mock_ollama) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "junk"}}]}
        ))
        mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(return_value=httpx.Response(
            200, json={"message": {"content": "junk"}}
        ))
        client = _make_client(max_retries=2)
        with pytest.raises(OllamaError):
            client.chat([ChatMessage(role="user", content="hi")],
                        force_json=True)

    def test_chat_raises_typed_error_on_total_failure(self, mock_ollama) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=httpx.ConnectError("boom"))
        mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(side_effect=httpx.ConnectError("boom"))
        client = _make_client(max_retries=1)
        with pytest.raises(OllamaError) as exc:
            client.chat([ChatMessage(role="user", content="hi")])
        assert exc.value.stage == "chat"


# ── embed ───────────────────────────────────────────────────────────


class TestEmbed:
    def test_embed_uses_openai_first_then_native(self, mock_ollama) -> None:
        oai = mock_ollama.post(
            "http://127.0.0.1:11434/v1/embeddings"
        ).mock(return_value=httpx.Response(404))
        nat = mock_ollama.post(
            "http://127.0.0.1:11434/api/embeddings"
        ).mock(return_value=httpx.Response(
            200, json={"embedding": [0.1, 0.2]}
        ))
        client = _make_client()
        result = client.embed("hello")
        assert result == [0.1, 0.2]
        assert oai.called and nat.called

    def test_embed_returns_floats_unchanged(self, mock_ollama) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/embeddings"
        ).mock(return_value=httpx.Response(
            200, json={"data": [{"embedding": [0.5, -0.5, 1.0]}]}
        ))
        client = _make_client()
        result = client.embed("hello")
        assert result == [0.5, -0.5, 1.0]


# ── 옵션 전달 ───────────────────────────────────────────────────────


class TestOptions:
    def test_chat_passes_num_ctx_to_native(self, mock_ollama) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_native_response({"ok": True}))

        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=httpx.Response(500))
        mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(side_effect=handler)
        client = _make_client()
        client.chat([ChatMessage(role="user", content="hi")], num_ctx=4096)
        assert captured["body"]["options"]["num_ctx"] == 4096

    def test_chat_passes_format_json_to_native(self, mock_ollama) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_native_response({"ok": True}))

        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=httpx.Response(500))
        mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(side_effect=handler)
        client = _make_client()
        client.chat([ChatMessage(role="user", content="hi")], force_json=True)
        assert captured["body"].get("format") == "json"

    def test_chat_uses_timeout_from_config(self) -> None:
        client = _make_client(timeout=2.5)
        assert client.timeout_seconds == 2.5


# ── base64 헬퍼 ─────────────────────────────────────────────────────


class TestHelpers:
    def test_encode_image_helper_base64(self, fixture_dir) -> None:
        path = fixture_dir / "tiny_pixel_32.png"
        b64 = encode_image(path)
        assert all(c.isalnum() or c in "+/=" for c in b64)
        assert len(b64) > 0

    def test_encode_audio_clip_helper_outputs_wav_base64(self) -> None:
        import numpy as np

        samples = np.zeros(16000, dtype=np.float32)
        b64 = encode_audio_clip(samples, sample_rate=16000)
        assert all(c.isalnum() or c in "+/=" for c in b64)
        assert len(b64) > 0
