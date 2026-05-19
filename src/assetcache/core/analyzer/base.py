"""Shared types for sprite and sound analyzers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

# Re-export ``SearchableTexts`` so callers can grab everything they
# need from one module.  The analyzer's result wraps a searchable
# bundle, so keeping the type next to ``AnalyzerResult`` is the least
# surprising arrangement.
from ..searchable import SearchableTexts  # noqa: F401

if TYPE_CHECKING:
    from ..store import LabelScore, SoundMeta, SpriteMeta


@dataclass(frozen=True)
class AnalyzerInput:
    asset_id: int
    pack_id: int
    abs_path: Path
    rel_path: str
    language: str = "ko"


@dataclass(frozen=True)
class AnalyzerResult:
    kind: str                            # 'sprite' | 'sound'
    state: str                           # 'ok' | 'partial' | 'failed'
    error: str | None
    sprite_meta: "SpriteMeta | None"
    sound_meta: "SoundMeta | None"
    labels: list["LabelScore"]
    searchable: "SearchableTexts"
    embedding_vector: bytes
    embedding_dim: int
    embedding_model: str
    description: str


class AnalyzerError(RuntimeError):
    """Catch-all for analyzer-side failures (delegated to the queue)."""
