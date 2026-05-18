"""M4/M6 — `core/thumbnails.py` lazy 256×256 PNG 캐시.

sprite + spritesheet 자산 처리 (M6 부터), sound → None.
캐시 hit 시 즉시 반환 (재생성 없음).
첫 호출 시 캐시 디렉터리 자동 생성.
잘못된 path → None + log.exception (silent fail 없음).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _make_sprite_png(target: Path, *, size: int = 512) -> Path:
    """테스트용 sprite PNG — 512×512 (썸네일이 작아져야 효과 보임)."""
    from PIL import Image

    target.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (size, size), color=(120, 200, 60))
    img.save(target, "PNG")
    return target


def test_first_call_generates_256_png(tmp_path: Path) -> None:
    from gah.core.thumbnails import ensure_thumbnail
    from PIL import Image

    asset_path = _make_sprite_png(tmp_path / "src" / "hero.png", size=512)
    cache_dir = tmp_path / "cache" / "thumbnails"

    out = ensure_thumbnail(asset_path, kind="sprite", cache_dir=cache_dir,
                           asset_id=42, max_size=256)
    assert out is not None
    assert out.exists()
    with Image.open(out) as img:
        # `Image.thumbnail` 은 max_size 안에 들어가도록 비례 축소 — 512 → 256.
        assert max(img.size) <= 256


def test_second_call_returns_cached_file_without_regeneration(tmp_path: Path) -> None:
    from gah.core.thumbnails import ensure_thumbnail

    asset_path = _make_sprite_png(tmp_path / "src" / "hero.png", size=512)
    cache_dir = tmp_path / "cache" / "thumbnails"

    first = ensure_thumbnail(asset_path, kind="sprite", cache_dir=cache_dir,
                             asset_id=42, max_size=256)
    assert first is not None
    mtime_before = first.stat().st_mtime_ns

    # 같은 asset_id 로 다시 호출 — 캐시 hit 이라 mtime 변경 없음.
    second = ensure_thumbnail(asset_path, kind="sprite", cache_dir=cache_dir,
                              asset_id=42, max_size=256)
    assert second == first
    assert second.stat().st_mtime_ns == mtime_before


def test_sound_kind_returns_none(tmp_path: Path) -> None:
    from gah.core.thumbnails import ensure_thumbnail

    # 사운드 자산: 썸네일 생성 안 함 → None
    out = ensure_thumbnail(
        tmp_path / "fake.wav", kind="sound",
        cache_dir=tmp_path / "cache", asset_id=99,
    )
    assert out is None


def test_spritesheet_kind_generates_thumbnail(tmp_path: Path) -> None:
    """M6 — spritesheet 자산도 sprite 와 동일하게 256×256 썸네일 생성."""
    from gah.core.thumbnails import ensure_thumbnail
    from PIL import Image

    # 가로로 긴 시트 (8 프레임 × 32px = 256×32) 모사
    asset_path = tmp_path / "src" / "sheet.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 32), color=(150, 100, 200, 255)).save(asset_path, "PNG")

    out = ensure_thumbnail(asset_path, kind="spritesheet",
                           cache_dir=tmp_path / "cache",
                           asset_id=7, max_size=256)
    assert out is not None
    assert out.exists()
    with Image.open(out) as img:
        assert max(img.size) <= 256


def test_cache_directory_auto_created(tmp_path: Path) -> None:
    from gah.core.thumbnails import ensure_thumbnail

    asset_path = _make_sprite_png(tmp_path / "src" / "x.png", size=64)
    deep_cache = tmp_path / "deeply" / "nested" / "cache"
    assert not deep_cache.exists()

    out = ensure_thumbnail(asset_path, kind="sprite", cache_dir=deep_cache,
                           asset_id=1)
    assert out is not None
    assert deep_cache.is_dir()


def test_invalid_path_returns_none_and_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from gah.core.thumbnails import ensure_thumbnail

    # 존재하지 않는 경로 → Pillow 가 FileNotFoundError, 헬퍼는 swallow + 로그.
    bogus = tmp_path / "does_not_exist.png"
    cache_dir = tmp_path / "cache"

    with caplog.at_level("ERROR"):
        out = ensure_thumbnail(bogus, kind="sprite", cache_dir=cache_dir,
                               asset_id=7)
    assert out is None
    # silent fail 방지 — log.exception 이 traceback 박는다.
    assert any("thumbnail" in r.message.lower() for r in caplog.records)
