"""Embedding encoder backed by :class:`OllamaClient`.

The encoder is intentionally tiny — its main job is to lock in a
single dimension on first use so the BLOBs stored in
``asset_embeddings`` can be safely decoded later.
"""

from __future__ import annotations

import logging
from typing import Protocol

import numpy as np

log = logging.getLogger(__name__)


class _EmbedCapable(Protocol):
    def embed(self, text: str, *, model: str | None = None) -> list[float]: ...


class EmbeddingEncoder:
    def __init__(
        self,
        client: _EmbedCapable,
        *,
        model: str = "nomic-embed-text",
    ) -> None:
        self.client = client
        self.model = model
        self._dim: int | None = None

    def encode_text(self, text: str) -> tuple[bytes, int]:
        """Return ``(blob, dim)`` for ``text``.

        On the first successful response the dimension is captured and
        future responses are checked to match — if they don't we still
        accept the new vector but log a warning (M3 search needs
        uniform dims for cosine, so this is also a heads-up for a
        future migration).
        """
        vec = self.client.embed(text, model=self.model)
        arr = np.asarray(vec, dtype=np.float32)
        if self._dim is None:
            self._dim = int(arr.size)
        elif arr.size != self._dim:
            log.warning(
                "embedding dim changed: %d → %d (model %r)",
                self._dim, arr.size, self.model,
            )
        return arr.tobytes(), int(arr.size)


def decode_vector(blob: bytes, dim: int) -> np.ndarray:
    arr = np.frombuffer(blob, dtype=np.float32)
    if arr.size != dim:
        raise ValueError(
            f"blob size {arr.size} does not match expected dim {dim}"
        )
    return arr
