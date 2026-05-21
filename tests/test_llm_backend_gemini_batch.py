"""Phase 2 — GeminiBackend.batch_chat mock tests."""

from unittest.mock import MagicMock

import pytest

from assetcache.core.batch.types import BatchChatRequest
from assetcache.core.llm.base import ChatMessage


@pytest.fixture
def gemini_backend(monkeypatch):
    fake_client = MagicMock()
    monkeypatch.setattr(
        "assetcache.core.llm.backends.gemini.genai.Client",
        lambda **kw: fake_client,
    )
    from assetcache.core.llm.backends.gemini import GeminiBackend
    backend = GeminiBackend(
        api_key="test",
        model_image="gemini-3.1-flash-lite",
        model_audio="gemini-3.1-flash-lite",
        model_embed="gemini-embedding-001",
        timeout=60.0,
    )
    return backend, fake_client


def test_batch_chat_image_returns_job_name(gemini_backend):
    backend, client = gemini_backend
    fake_job = MagicMock()
    fake_job.name = "batches/test-abc"
    client.batches.create.return_value = fake_job

    requests = [
        BatchChatRequest(
            asset_id=1,
            messages=[ChatMessage(role="user", content="describe")],
            force_json=True,
        ),
        BatchChatRequest(
            asset_id=2,
            messages=[ChatMessage(role="user", content="describe2")],
            force_json=True,
        ),
    ]
    job_name = backend.batch_chat(modality="chat_image", requests=requests)
    assert job_name == "batches/test-abc"
    client.batches.create.assert_called_once()
    kw = client.batches.create.call_args.kwargs
    assert kw["model"] == "gemini-3.1-flash-lite"
    assert "src" in kw
    assert len(kw["src"]) == 2
    assert "config" in kw and "display_name" in kw["config"]


def test_batch_chat_audio_uses_audio_model(gemini_backend, monkeypatch):
    backend, client = gemini_backend
    fake_job = MagicMock()
    fake_job.name = "batches/y"
    client.batches.create.return_value = fake_job
    monkeypatch.setattr(backend, "model_audio", "gemini-3.1-flash-lite-audio")
    backend.batch_chat(modality="chat_audio", requests=[
        BatchChatRequest(asset_id=1, messages=[ChatMessage(role="user", content="a")]),
    ])
    kw = client.batches.create.call_args.kwargs
    assert kw["model"] == "gemini-3.1-flash-lite-audio"


def test_batch_chat_invalid_modality_raises(gemini_backend):
    backend, _ = gemini_backend
    with pytest.raises(ValueError, match="modality"):
        backend.batch_chat(modality="text_embed", requests=[])


def test_batch_chat_spritesheet_uses_image_model(gemini_backend):
    """M11.2 — chat_spritesheet modality 는 model_image 사용 (chat_image 와 동일)."""
    backend, client = gemini_backend
    fake_job = MagicMock()
    fake_job.name = "batches/sheet-1"
    client.batches.create.return_value = fake_job
    backend.batch_chat(modality="chat_spritesheet", requests=[
        BatchChatRequest(
            asset_id=99,
            messages=[ChatMessage(role="user", content="x", images_b64=["aGk="])],
            force_json=True,
        ),
    ])
    kw = client.batches.create.call_args.kwargs
    assert kw["model"] == "gemini-3.1-flash-lite"
    assert "chat_spritesheet" in kw["config"]["display_name"]


def test_batch_chat_transient_error_raises_backend_error(gemini_backend):
    from assetcache.core.llm.base import BackendError
    backend, client = gemini_backend
    client.batches.create.side_effect = RuntimeError("connect timeout")
    with pytest.raises(BackendError) as exc_info:
        backend.batch_chat(modality="chat_image", requests=[
            BatchChatRequest(asset_id=1, messages=[ChatMessage(role="user", content="x")]),
        ])
    assert exc_info.value.transient is True


def test_batch_chat_hard_error_401(gemini_backend):
    from assetcache.core.llm.base import BackendError
    backend, client = gemini_backend
    client.batches.create.side_effect = Exception("401 unauthorized")
    with pytest.raises(BackendError) as exc_info:
        backend.batch_chat(modality="chat_image", requests=[
            BatchChatRequest(asset_id=1, messages=[ChatMessage(role="user", content="x")]),
        ])
    assert exc_info.value.transient is False


def test_batch_embed_returns_job_name(gemini_backend):
    backend, client = gemini_backend
    fake_job = MagicMock()
    fake_job.name = "batches/embed-1"
    client.batches.create_embeddings.return_value = fake_job
    name = backend.batch_embed(texts=["hello", "world"])
    assert name == "batches/embed-1"
    kw = client.batches.create_embeddings.call_args.kwargs
    assert kw["model"] == "gemini-embedding-001"
    assert "inlined_requests" in kw["src"]


def test_batch_embed_inlined_requests_uses_dict_with_contents_key(gemini_backend):
    """M11.3 patch C — SDK 가 `inlined_requests` 를 dict-with-contents 로 요구.

    `EmbeddingsBatchJobSource.inlined_requests` 는 단일 dict (옵션 config +
    contents: List[Content]) 형식 — list 로 보내면 pydantic ValidationError 로
    transient=True 처리되어 무한 retry.  실 SDK 호출 shape 을 단위 테스트가
    잡아둬야 회귀 방지.
    """
    backend, client = gemini_backend
    fake_job = MagicMock()
    fake_job.name = "batches/embed-2"
    client.batches.create_embeddings.return_value = fake_job
    backend.batch_embed(texts=["a", "b", "c"])
    kw = client.batches.create_embeddings.call_args.kwargs
    inlined = kw["src"]["inlined_requests"]
    assert isinstance(inlined, dict), f"inlined_requests must be dict, got {type(inlined).__name__}"
    assert "contents" in inlined
    assert len(inlined["contents"]) == 3
    assert inlined["contents"][0]["parts"][0]["text"] == "a"
    assert inlined["contents"][2]["parts"][0]["text"] == "c"


def test_batch_embed_empty_list_raises(gemini_backend):
    backend, _ = gemini_backend
    with pytest.raises(ValueError):
        backend.batch_embed(texts=[])


def test_batch_embed_transient_error(gemini_backend):
    from assetcache.core.llm.base import BackendError
    backend, client = gemini_backend
    client.batches.create_embeddings.side_effect = RuntimeError("503 unavailable")
    with pytest.raises(BackendError) as exc_info:
        backend.batch_embed(texts=["x"])
    assert exc_info.value.transient is True


def test_batch_get_succeeded_inline(gemini_backend):
    backend, client = gemini_backend
    fake_job = MagicMock()
    fake_job.state.name = "JOB_STATE_SUCCEEDED"
    fake_job.dest.inlined_responses = [MagicMock(), MagicMock()]
    fake_job.dest.file_name = None
    fake_job.error = None
    client.batches.get.return_value = fake_job
    status = backend.batch_get("batches/x")
    assert status.state == "JOB_STATE_SUCCEEDED"
    assert status.inlined_responses is not None
    assert len(status.inlined_responses) == 2
    assert status.file_name is None


def test_batch_get_running_dest_none(gemini_backend):
    backend, client = gemini_backend
    fake_job = MagicMock()
    fake_job.state.name = "JOB_STATE_RUNNING"
    fake_job.dest = None
    fake_job.error = None
    client.batches.get.return_value = fake_job
    status = backend.batch_get("batches/x")
    assert status.state == "JOB_STATE_RUNNING"
    assert status.inlined_responses is None
    assert status.file_name is None


def test_batch_cancel_calls_sdk(gemini_backend):
    backend, client = gemini_backend
    backend.batch_cancel("batches/x")
    client.batches.cancel.assert_called_once_with(name="batches/x")


def test_batch_cancel_swallows_error(gemini_backend):
    """Best-effort cancel — 예외 안 던짐."""
    backend, client = gemini_backend
    client.batches.cancel.side_effect = RuntimeError("network down")
    backend.batch_cancel("batches/x")  # 예외 없이 통과


def test_batch_download_file(gemini_backend):
    backend, client = gemini_backend
    client.files.download.return_value = b"binary data"
    data = backend.batch_download_file("files/abc")
    assert data == b"binary data"
    client.files.download.assert_called_once_with(file="files/abc")
