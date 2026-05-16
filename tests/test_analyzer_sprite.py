"""SpriteAnalyzer integration tests with mocked Ollama and Fake CLIP."""

from __future__ import annotations

import base64
import io
import json

import httpx
import pytest

from gah.core.analyzer.sprite import SpriteAnalyzer
from gah.core.clip_labeler import ClipLabeler, FakeBackend
from gah.core.embedding import EmbeddingEncoder
from gah.core.labels import LabelRegistry
from gah.core.ollama_client import OllamaClient


class _FakeEmbedOllama:
    def embed(self, text, *, model=None):  # noqa: ANN001
        return [0.1] * 16


def _gemma_ok_payload() -> dict:
    return {
        "category": "character",
        "style": "pixel_art",
        "mood": ["heroic", "serious"],
        "palette": ["warm"],
        "animation_hint": ["idle"],
        "subject": "기사",
        "description": "검을 든 기사",
        "confidence": 0.85,
    }


def _ollama_response(content: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(content)}}]},
    )


def _make_analyzer(store, *, clip_enabled: bool = True) -> SpriteAnalyzer:
    registry = LabelRegistry(store)
    registry.bootstrap()
    client = OllamaClient(
        base_url="http://127.0.0.1:11434", model="gemma4:e4b",
        timeout_seconds=5, max_retries=3,
    )
    embedder = EmbeddingEncoder(_FakeEmbedOllama())  # type: ignore[arg-type]
    clip = ClipLabeler(
        backend=FakeBackend(dim=64), store=store,
        registry=registry, enabled=clip_enabled,
    )
    return SpriteAnalyzer(
        ollama=client, clip=clip, embedder=embedder, registry=registry
    )


# ── 기술 특성 추출 ──────────────────────────────────────────────────


class TestTechnicalSpec:
    def test_analyze_pixel_art_classifies_as_pixel_art_via_heuristic(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_gemma_ok_payload()))
        analyzer = _make_analyzer(store)
        result = analyzer.analyze(analyzer_inputs("tiny_pixel_32.png"))
        assert result.sprite_meta.is_pixel_art is True

    def test_analyze_vector_classifies_as_not_pixel_art(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_gemma_ok_payload()))
        analyzer = _make_analyzer(store)
        result = analyzer.analyze(analyzer_inputs("tiny_vector_256.png"))
        assert result.sprite_meta.is_pixel_art is False

    def test_analyze_extracts_alpha_correctly(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_gemma_ok_payload()))
        analyzer = _make_analyzer(store)
        result = analyzer.analyze(analyzer_inputs("transparent_alpha.png"))
        assert result.sprite_meta.has_alpha is True

    def test_analyze_extracts_5_dominant_colors(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_gemma_ok_payload()))
        analyzer = _make_analyzer(store)
        result = analyzer.analyze(analyzer_inputs("tiny_pixel_32.png"))
        assert len(result.sprite_meta.dominant_colors) == 5


# ── Ollama 호출 모양 ────────────────────────────────────────────────


class TestOllamaCall:
    def test_analyze_calls_ollama_with_resampled_image(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        captured: dict = {}

        def handler(request):  # noqa: ANN001
            captured["body"] = json.loads(request.content)
            return _ollama_response(_gemma_ok_payload())

        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=handler)

        analyzer = _make_analyzer(store)
        analyzer.analyze(analyzer_inputs("tiny_vector_256.png"))
        # 시스템 메시지는 텍스트 only — 이미지가 첨부된 user 메시지를 찾는다.
        user_msg = next(
            m for m in captured["body"]["messages"] if m.get("role") == "user"
        )
        parts = user_msg["content"]
        img_part = next(p for p in parts if p.get("type") == "image_url")
        data_uri = img_part["image_url"]["url"]
        _, b64 = data_uri.split(",", 1)
        img_bytes = base64.b64decode(b64)
        from PIL import Image

        img = Image.open(io.BytesIO(img_bytes))
        assert max(img.size) <= 768

    def test_analyze_validates_response_against_whitelist(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        bad_then_good = [
            _ollama_response(
                {**_gemma_ok_payload(), "style": "anime style XYZ"}
            ),
            _ollama_response(_gemma_ok_payload()),
        ]
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=bad_then_good)
        analyzer = _make_analyzer(store)
        result = analyzer.analyze(analyzer_inputs("tiny_pixel_32.png"))
        assert result.state == "ok"

    def test_analyze_falls_back_to_other_after_max_retries(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        bad = _ollama_response(
            {**_gemma_ok_payload(), "category": "totally_invented"}
        )
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=bad)
        mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(return_value=httpx.Response(500))
        analyzer = _make_analyzer(store)
        result = analyzer.analyze(analyzer_inputs("tiny_pixel_32.png"))
        assert result.state == "partial"


# ── CLIP 통합 ───────────────────────────────────────────────────────


class TestClipIntegration:
    def test_analyze_integrates_clip_scores_as_separate_source_labels(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_gemma_ok_payload()))
        analyzer = _make_analyzer(store, clip_enabled=True)
        result = analyzer.analyze(analyzer_inputs("tiny_pixel_32.png"))
        sources = {label.source for label in result.labels}
        assert "gemma" in sources
        assert "clip" in sources


# ── searchable 텍스트 ───────────────────────────────────────────────


class TestSearchableText:
    def test_analyze_searchable_for_embed_includes_korean_description(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_gemma_ok_payload()))
        analyzer = _make_analyzer(store)
        result = analyzer.analyze(
            analyzer_inputs("tiny_pixel_32.png", language="ko")
        )
        assert "기사" in result.searchable.for_embed

    def test_analyze_searchable_for_fts_uses_english_enum_regardless_of_language(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_gemma_ok_payload()))
        analyzer = _make_analyzer(store)
        result = analyzer.analyze(
            analyzer_inputs("tiny_pixel_32.png", language="ko")
        )
        assert "category:character" in result.searchable.for_fts
        assert "style:pixel_art" in result.searchable.for_fts

    def test_analyze_searchable_for_fts_includes_label_descriptions_from_registry(
        self, store, analyzer_inputs, mock_ollama
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_gemma_ok_payload()))
        analyzer = _make_analyzer(store)
        result = analyzer.analyze(analyzer_inputs("tiny_pixel_32.png"))
        assert (
            "Animate" in result.searchable.for_fts
            or "Low-resolution sprite art" in result.searchable.for_fts
        )
