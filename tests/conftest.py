"""Shared pytest fixtures for GAH tests.

Heavy third-party imports (numpy, Pillow, soundfile, respx, torch) are
deliberately inside fixture bodies / helper functions rather than at
module top level — that way pytest can still collect M0/M1 tests in an
environment where the M2 dev-extras have not been installed yet, which
matters during the bootstrap of milestone M2 itself.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Iterator

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def qt_offscreen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force Qt to use the offscreen platform plugin so PySide6 can import
    without a display server in CI/sandbox environments."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def qapp():
    """Provide a singleton :class:`QApplication` for widget tests.

    PySide6 forbids more than one QApplication per process and several
    widget constructors (notably :class:`QMainWindow` + ``QShortcut``)
    deadlock when none exists.  This fixture creates one on demand and
    reuses it across tests, mirroring what ``gah.ui.test_ui_smoke``
    already does manually.
    """
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def tmp_appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Override GAH's data root to a fresh temp directory for the test."""
    monkeypatch.setenv("GAH_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def library_root(tmp_appdata: Path) -> Path:
    """A fresh, empty library directory inside the temporary AppData root."""
    root = tmp_appdata / "library"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def make_pack(library_root: Path) -> Callable[..., Path]:
    """Factory for building a pack directory under ``library_root``.

    Usage::

        pack_dir = make_pack(
            "kenney_demo",
            files={"PNG/hero.png": b"\\x89PNG...", "Sounds/jump.wav": b"RIFF..."},
            manifest={"name": "Kenney Demo", "vendor": "kenney"},
        )
    """

    def _make_pack(
        name: str,
        *,
        files: dict[str, bytes] | None = None,
        manifest: dict | None = None,
        manifest_format: str = "json",
    ) -> Path:
        pack_dir = library_root / name
        pack_dir.mkdir(parents=True, exist_ok=True)
        for rel, payload in (files or {}).items():
            file_path = pack_dir / rel
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(payload)
        if manifest is not None:
            if manifest_format == "json":
                (pack_dir / "pack.json").write_text(
                    json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
                )
            elif manifest_format == "toml":
                import tomli_w

                (pack_dir / "pack.toml").write_bytes(tomli_w.dumps(manifest).encode("utf-8"))
            else:  # pragma: no cover - defensive
                raise ValueError(f"unknown manifest_format: {manifest_format!r}")
        return pack_dir

    return _make_pack


@pytest.fixture
def store(tmp_appdata: Path) -> Iterator["object"]:
    """Initialised on-disk Store at ``tmp_appdata/test.db``.

    Returns the live Store object; callers can use ``store.conn`` if they
    need raw SQL access for assertions.
    """
    from gah.core.store import Store

    s = Store(tmp_appdata / "test.db")
    s.initialize()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def clean_root_logger():
    """Snapshot and restore the root logger so logging tests don't bleed."""
    import logging

    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    for h in list(root.handlers):
        root.removeHandler(h)
    try:
        yield root
    finally:
        for h in list(root.handlers):
            try:
                h.close()
            except Exception:
                pass
            root.removeHandler(h)
        for h in saved_handlers:
            root.addHandler(h)
        root.setLevel(saved_level)


# ─────────────────────────────────────────────────────────────────────
# M2 fixtures — deterministic test assets + HTTP/CLIP mocks
#
# Why deterministic generators instead of binary blobs in git?
#   * keeps the repo small and reviewable
#   * regenerates byte-identical files every time, so test results stay
#     reproducible across machines
#   * fixtures live under tests/fixtures/ but are .gitignored (see
#     .gitignore — only .gitkeep is tracked)
# ─────────────────────────────────────────────────────────────────────


def _build_tiny_pixel_32(path: Path) -> None:
    """32x32 pixel-art image with only 4 colors → triggers the pixel-art heuristic."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed=1234)
    palette = np.array(
        [[255, 80, 80], [80, 200, 80], [80, 80, 255], [240, 220, 60]],
        dtype=np.uint8,
    )
    indices = rng.integers(0, len(palette), size=(32, 32))
    img = palette[indices]
    Image.fromarray(img, mode="RGB").save(path)


def _build_tiny_vector_256(path: Path) -> None:
    """256x256 smooth gradient → should NOT be classified as pixel art."""
    import numpy as np
    from PIL import Image

    xs = np.linspace(0, 1, 256, dtype=np.float32)
    ys = np.linspace(0, 1, 256, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    r = (xx * 255).astype(np.uint8)
    g = (yy * 255).astype(np.uint8)
    b = ((1 - xx) * 200 + (1 - yy) * 50).astype(np.uint8)
    img = np.stack([r, g, b], axis=-1)
    Image.fromarray(img, mode="RGB").save(path)


def _build_transparent_alpha(path: Path) -> None:
    """64x64 RGBA image with a real alpha channel."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed=42)
    rgba = rng.integers(0, 255, size=(64, 64, 4), dtype=np.uint8)
    Image.fromarray(rgba, mode="RGBA").save(path)


def _write_wav(path: Path, samples, sample_rate: int = 16000) -> None:
    import numpy as np
    import soundfile as sf

    arr = np.clip(samples, -1.0, 1.0).astype(np.float32)
    sf.write(str(path), arr, sample_rate, subtype="PCM_16")


def _build_short_sfx_1s(path: Path) -> None:
    """1 second 440Hz sine — exercises the 'short SFX → native path' branch."""
    import numpy as np

    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
    _write_wav(path, 0.5 * np.sin(2 * np.pi * 440 * t), sr)


def _build_medium_sfx_5s(path: Path) -> None:
    """5 second white-noise SFX."""
    import numpy as np

    sr = 16000
    rng = np.random.default_rng(seed=7)
    _write_wav(path, 0.3 * rng.standard_normal(sr * 5).astype(np.float32), sr)


def _build_long_bgm_45s(path: Path) -> None:
    """45 second multi-tone tonal loop — exercises the smart 3-chunk path."""
    import numpy as np

    sr = 16000
    duration = 45
    t = np.linspace(0, duration, sr * duration, endpoint=False, dtype=np.float32)
    tone = (
        0.3 * np.sin(2 * np.pi * 220 * t)
        + 0.2 * np.sin(2 * np.pi * 330 * t)
        + 0.1 * np.sin(2 * np.pi * 440 * t)
    )
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * t)
    _write_wav(path, tone * env, sr)


def _build_mel_sample(path: Path) -> None:
    """A stand-in for the mel-spectrogram PNG used by the 2nd-tier sound fallback."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed=99)
    img = rng.integers(0, 255, size=(128, 256, 3), dtype=np.uint8)
    Image.fromarray(img, mode="RGB").save(path)


_FIXTURE_BUILDERS: dict[str, Callable[[Path], None]] = {
    "tiny_pixel_32.png": _build_tiny_pixel_32,
    "tiny_vector_256.png": _build_tiny_vector_256,
    "transparent_alpha.png": _build_transparent_alpha,
    "short_sfx_1s.wav": _build_short_sfx_1s,
    "medium_sfx_5s.wav": _build_medium_sfx_5s,
    "long_bgm_45s.wav": _build_long_bgm_45s,
    "mel_sample.png": _build_mel_sample,
}


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    """Absolute path to ``tests/fixtures``; lazily materializes any missing files.

    Session-scoped so the deterministic generators only fire once per
    test run — subsequent fixtures just observe the existing files.
    """
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for name, builder in _FIXTURE_BUILDERS.items():
        target = FIXTURES_DIR / name
        if not target.exists():
            builder(target)
    return FIXTURES_DIR


@pytest.fixture
def mock_ollama():
    """``respx`` router configured for both Ollama transports.

    Tests get a ready-made ``router`` object and can attach routes for
    ``POST /v1/chat/completions`` (OpenAI-compatible) and
    ``POST /api/chat`` (Ollama native).  ``assert_all_mocked=True`` means
    any unstubbed HTTP call is a test bug rather than a silent network
    hit.
    """
    import respx

    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


@pytest.fixture
def fake_clip_backend():
    """Deterministic CLIP stand-in.

    Imported lazily because ``gah.core.clip_labeler`` only exists once the
    C.3 step of M2 is implemented; until then this fixture will simply
    fail to collect — that is intentional and matches the RED phase.
    """
    from gah.core.clip_labeler import FakeBackend  # type: ignore[import-not-found]

    return FakeBackend(dim=128)


@pytest.fixture
def analyzer_inputs(fixture_dir: Path):
    """Factory that builds ``AnalyzerInput`` objects pointing at fixture files.

    Same lazy-import note as ``fake_clip_backend`` — only resolvable once
    ``gah.core.analyzer.base`` lands in C.4.
    """
    from gah.core.analyzer.base import AnalyzerInput  # type: ignore[import-not-found]

    def _build(
        name: str,
        *,
        asset_id: int = 1,
        pack_id: int = 1,
        rel_path: str | None = None,
        language: str = "ko",
    ) -> "AnalyzerInput":
        return AnalyzerInput(
            asset_id=asset_id,
            pack_id=pack_id,
            abs_path=fixture_dir / name,
            rel_path=rel_path or f"test_pack/{name}",
            language=language,
        )

    return _build
