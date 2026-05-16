"""CLIP labeler tests.

The unit suite uses a deterministic :class:`FakeBackend` so no model
weights are downloaded.  Two opt-in cases marked ``clip_integration``
exercise the real :class:`OpenClipBackend` for developers who want
end-to-end coverage on their machines.
"""

from __future__ import annotations

import numpy as np
import pytest

from gah.core.clip_labeler import ClipLabeler, FakeBackend
from gah.core.labels import LabelRegistry
from gah.core.store import Store


def _seed_labels(store: Store) -> LabelRegistry:
    r = LabelRegistry(store)
    r.bootstrap()
    return r


def test_warmup_populates_cache_only_for_missing_labels(store: Store) -> None:
    backend = FakeBackend(dim=64)
    registry = _seed_labels(store)
    labeler = ClipLabeler(backend=backend, store=store, registry=registry)
    labeler.warmup(["pixel_art", "anime"])
    calls_before = backend.encode_text_call_count
    labeler.warmup(["pixel_art", "anime"])
    assert backend.encode_text_call_count == calls_before


def test_score_image_returns_scores_per_label_in_zero_one_range(
    store: Store, fake_clip_backend: FakeBackend, fixture_dir
) -> None:
    registry = _seed_labels(store)
    labeler = ClipLabeler(backend=fake_clip_backend, store=store,
                          registry=registry)
    scores = labeler.score_image(
        fixture_dir / "tiny_pixel_32.png",
        labels=["pixel_art", "anime", "vector_flat"],
    )
    assert set(scores.keys()) == {"pixel_art", "anime", "vector_flat"}
    for v in scores.values():
        assert 0.0 <= v <= 1.0


def test_score_image_clamps_negative_cosine_to_zero(
    store: Store, fixture_dir
) -> None:
    class _OppositeBackend(FakeBackend):
        def encode_image(self, path):  # noqa: ANN001
            return np.array([1.0] + [0.0] * (self.dim - 1), dtype=np.float32)

        def encode_text(self, texts):  # noqa: ANN001
            return np.array(
                [[-1.0] + [0.0] * (self.dim - 1)] * len(texts),
                dtype=np.float32,
            )

    registry = _seed_labels(store)
    labeler = ClipLabeler(backend=_OppositeBackend(dim=64), store=store,
                          registry=registry)
    scores = labeler.score_image(
        fixture_dir / "tiny_pixel_32.png", labels=["pixel_art"]
    )
    assert scores["pixel_art"] == 0.0


def test_score_image_uses_cached_label_vectors_after_warmup(
    store: Store, fake_clip_backend: FakeBackend, fixture_dir
) -> None:
    registry = _seed_labels(store)
    labeler = ClipLabeler(backend=fake_clip_backend, store=store,
                          registry=registry)
    labeler.warmup(["pixel_art"])
    before = fake_clip_backend.encode_text_call_count
    labeler.score_image(fixture_dir / "tiny_pixel_32.png",
                        labels=["pixel_art"])
    after = fake_clip_backend.encode_text_call_count
    assert before == after


def test_label_added_after_warmup_is_computed_lazily(
    store: Store, fake_clip_backend: FakeBackend, fixture_dir
) -> None:
    registry = _seed_labels(store)
    labeler = ClipLabeler(backend=fake_clip_backend, store=store,
                          registry=registry)
    labeler.warmup(["pixel_art"])
    before = fake_clip_backend.encode_text_call_count
    labeler.score_image(
        fixture_dir / "tiny_pixel_32.png",
        labels=["pixel_art", "new_unseen_label"],
    )
    after = fake_clip_backend.encode_text_call_count
    assert after > before  # 새 라벨 1개 추가 인코딩


def test_disabled_clip_returns_empty_dict(
    store: Store, fake_clip_backend: FakeBackend, fixture_dir
) -> None:
    registry = _seed_labels(store)
    labeler = ClipLabeler(backend=fake_clip_backend, store=store,
                          registry=registry, enabled=False)
    scores = labeler.score_image(
        fixture_dir / "tiny_pixel_32.png", labels=["pixel_art"]
    )
    assert scores == {}


@pytest.mark.clip_integration
def test_open_clip_backend_init_does_not_download_until_called() -> None:
    from gah.core.clip_labeler import OpenClipBackend

    backend = OpenClipBackend(model="ViT-B-32", pretrained="openai")
    # 생성만으로는 가중치 다운로드/로딩 X
    assert backend.is_loaded is False


@pytest.mark.clip_integration
def test_open_clip_backend_actual_inference(fixture_dir) -> None:
    from gah.core.clip_labeler import OpenClipBackend

    backend = OpenClipBackend(model="ViT-B-32", pretrained="openai")
    img_vec = backend.encode_image(fixture_dir / "tiny_pixel_32.png")
    assert img_vec.shape[-1] == backend.dim
