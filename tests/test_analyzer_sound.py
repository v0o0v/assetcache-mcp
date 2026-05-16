"""SoundAnalyzer tests — 3-tier fallback chain + 10-axis label persistence."""

from __future__ import annotations

import json

import httpx
import pytest

from gah.core.analyzer.sound import SoundAnalyzer
from gah.core.embedding import EmbeddingEncoder
from gah.core.labels import LabelRegistry
from gah.core.ollama_client import OllamaClient


class _FakeEmbedOllama:
    def embed(self, text, *, model=None):  # noqa: ANN001
        return [0.1] * 16


def _sound_ok_payload(**overrides) -> dict:
    base = {
        "category": "sfx",
        "mood": ["energetic"],
        "timbre": ["bright"],
        "environment": ["indoor"],
        "instruments": [],
        "tempo": "medium",
        "intensity": "moderate",
        "use": ["hit_impact"],
        "genre": None,
        "voice_type": None,
        "loopable": False,
        "transcript": "",
        "description": "짧고 밝은 효과음",
        "confidence": 0.7,
    }
    base.update(overrides)
    return base


def _ollama_response(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
    )


def _make_analyzer(store, tmp_path) -> SoundAnalyzer:
    registry = LabelRegistry(store)
    registry.bootstrap()
    client = OllamaClient(
        base_url="http://127.0.0.1:11434", model="gemma4:e4b",
        timeout_seconds=5, max_retries=2,
    )
    embedder = EmbeddingEncoder(_FakeEmbedOllama())  # type: ignore[arg-type]
    return SoundAnalyzer(
        ollama=client, embedder=embedder, registry=registry,
        spectrogram_cache_dir=tmp_path / "spectro",
    )


# ── 1·2·3차 폴백 체인 ───────────────────────────────────────────────


class TestFallbackChain:
    def test_analyze_short_sfx_uses_native_path(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_sound_ok_payload()))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        assert result.sound_meta.audio_path_used == "native"

    def test_analyze_long_bgm_with_smart_chunks_merges_results(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(
            _sound_ok_payload(category="bgm", mood=["heroic"])
        ))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("long_bgm_45s.wav"))
        assert result.sound_meta.category == "bgm"

    def test_analyze_falls_back_to_spectrogram_when_native_times_out(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        responses = [
            httpx.Response(408),
            _ollama_response(_sound_ok_payload()),
        ]
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=responses)
        mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(return_value=httpx.Response(500))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        assert result.sound_meta.audio_path_used == "spectrogram"

    def test_analyze_marks_audio_path_used_spectrogram_when_fallback_succeeds(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        responses = [
            httpx.Response(500),
            _ollama_response(_sound_ok_payload()),
        ]
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=responses)
        mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(return_value=httpx.Response(500))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        assert result.sound_meta.audio_path_used == "spectrogram"

    def test_analyze_falls_back_to_heuristic_when_both_paths_fail(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=httpx.Response(500))
        mock_ollama.post(
            "http://127.0.0.1:11434/api/chat"
        ).mock(return_value=httpx.Response(500))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs(
            "short_sfx_1s.wav",
            rel_path="kenney_bgm_pack/title_bgm_loop.wav",
        ))
        assert result.sound_meta.audio_path_used == "heuristic"
        assert result.state == "partial"


# ── 기술 특성 ───────────────────────────────────────────────────────


class TestTechnicalSpec:
    def test_analyze_extracts_loudness_db_from_librosa(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_sound_ok_payload()))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("medium_sfx_5s.wav"))
        assert result.sound_meta.loudness_db is not None
        assert result.sound_meta.loudness_db < 0  # dB scale

    def test_analyze_detects_loopable_from_gemma_response(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_sound_ok_payload(loopable=True)))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        assert result.sound_meta.loopable is True


# ── CLIP 격리 ───────────────────────────────────────────────────────


class TestClipIsolation:
    def test_analyze_does_not_call_clip_labeler(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(_sound_ok_payload()))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        # 사운드 분석은 CLIP 라벨을 안 만든다
        sources = {label.source for label in result.labels}
        assert "clip" not in sources


# ── 10축 라벨 ───────────────────────────────────────────────────────


class TestTenAxisLabels:
    def test_analyze_emits_labels_for_all_ten_sound_axes(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        payload = _sound_ok_payload(
            category="bgm",
            mood=["heroic"],
            timbre=["bright"],
            environment=["hall"],
            instruments=["piano"],
            tempo="fast",
            intensity="loud",
            use=["combat"],
            genre="orchestral",
        )
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(payload))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        axes = {label.axis for label in result.labels}
        for required in (
            "sound_category", "sound_mood", "sound_timbre",
            "sound_environment", "sound_instrument", "sound_tempo",
            "sound_intensity", "sound_use", "sound_genre",
        ):
            assert required in axes, f"missing axis {required}"

    def test_analyze_omits_voice_type_when_category_not_voice(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(
            _sound_ok_payload(category="sfx", voice_type=None)
        ))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        axes = {label.axis for label in result.labels}
        assert "sound_voice_type" not in axes

    def test_analyze_omits_genre_when_category_not_music(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(
            _sound_ok_payload(category="sfx", genre=None)
        ))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        axes = {label.axis for label in result.labels}
        assert "sound_genre" not in axes

    def test_analyze_rejects_genre_when_category_is_sfx_and_retries(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        bad = _sound_ok_payload(category="sfx", genre="orchestral")
        ok = _sound_ok_payload(category="sfx", genre=None)
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(side_effect=[_ollama_response(bad), _ollama_response(ok)])
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        assert result.state == "ok"

    def test_analyze_handles_list_typed_single_enum_fields(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        """Gemma 가 단일 enum(category/tempo/...)을 list 로 돌려주면 첫 요소로 squash 후 진행."""
        # 첫 응답: category 가 list — squash 후 validate 통과 (sfx 는 화이트리스트)
        bad_then_ok = _sound_ok_payload(category=["sfx", "bgm"])
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(bad_then_ok))
        analyzer = _make_analyzer(store, tmp_path)
        # squash 가 안 되면 TypeError 가 raise 되어 큐가 fail. 정상 동작이면 partial/ok.
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        assert result.state in ("ok", "partial")
        assert result.sound_meta.category == "sfx"  # 첫 요소 채택

    def test_analyze_persists_new_sound_meta_columns(
        self, store, analyzer_inputs, mock_ollama, tmp_path
    ) -> None:
        payload = _sound_ok_payload(
            category="bgm", tempo="fast", intensity="loud",
            genre="orchestral", voice_type=None,
        )
        mock_ollama.post(
            "http://127.0.0.1:11434/v1/chat/completions"
        ).mock(return_value=_ollama_response(payload))
        analyzer = _make_analyzer(store, tmp_path)
        result = analyzer.analyze(analyzer_inputs("short_sfx_1s.wav"))
        assert result.sound_meta.tempo == "fast"
        assert result.sound_meta.intensity == "loud"
        assert result.sound_meta.genre == "orchestral"
        assert result.sound_meta.voice_type is None
