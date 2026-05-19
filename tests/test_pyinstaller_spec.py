"""M8 — assetcache.spec 정합성 smoke (실 빌드는 수동)."""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_gah_spec_exists():
    assert (REPO_ROOT / "assetcache.spec").exists()


def test_gah_spec_parses_as_python():
    spec = (REPO_ROOT / "assetcache.spec").read_text(encoding="utf-8")
    ast.parse(spec)  # SyntaxError 면 fail


def test_gah_spec_references_existing_data_paths():
    """spec 이 참조하는 핵심 경로가 실재해야 PyInstaller 가 빌드 시작 가능."""
    spec = (REPO_ROOT / "assetcache.spec").read_text(encoding="utf-8")
    # Analysis entrypoint 는 리터럴 문자열로 직접 명시
    assert "src/assetcache/__main__.py" in spec, "spec 에 entrypoint 참조 누락"
    # 아이콘은 리터럴 문자열로 직접 명시
    assert "assets/tray.ico" in spec, "spec 에 icon 참조 누락"
    # 실제 경로 존재 확인 (spec 이 Path 연산으로 구성하는 경로들)
    for p in (
        "src/assetcache/web/templates",
        "src/assetcache/web/static",
        "src/assetcache/web/locale",
        "src/assetcache/__main__.py",
        "assets/tray.ico",
    ):
        assert (REPO_ROOT / p).exists(), f"spec 이 참조하는 경로 부재: {p}"


def test_gah_spec_excludes_dev_deps():
    spec = (REPO_ROOT / "assetcache.spec").read_text(encoding="utf-8")
    for excluded in ("pytest", "playwright"):
        assert excluded in spec, f"excludes 에 {excluded} 누락"
