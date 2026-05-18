"""M8 — `_t()` gettext 위임 + 폴백 체인 단위 테스트."""
from __future__ import annotations
import struct
from pathlib import Path

import pytest

from gah.web import i18n


def _write_mo(path: Path, entries: dict[str, str]) -> None:
    """msgid → msgstr dict 를 GNU .mo 바이너리로 저장 (gettext 표준 포맷)."""
    items = sorted(entries.items())
    keys = [k.encode("utf-8") for k, _ in items]
    vals = [v.encode("utf-8") for _, v in items]
    koffsets = []
    voffsets = []
    kstart = 7 * 4 + 16 * len(items)
    for k in keys:
        koffsets.append((len(k), kstart))
        kstart += len(k) + 1
    vstart = kstart
    for v in vals:
        voffsets.append((len(v), vstart))
        vstart += len(v) + 1
    out = struct.pack("Iiiiiii", 0x950412de, 0, len(items),
                      7 * 4, 7 * 4 + 8 * len(items), 0, 0)
    for L, O in koffsets:
        out += struct.pack("ii", L, O)
    for L, O in voffsets:
        out += struct.pack("ii", L, O)
    for k in keys:
        out += k + b"\x00"
    for v in vals:
        out += v + b"\x00"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)


_KO_METADATA = "Content-Type: text/plain; charset=UTF-8\n"
_EN_METADATA = "Content-Type: text/plain; charset=UTF-8\n"


@pytest.fixture
def tmp_locale_dir(tmp_path, monkeypatch):
    """ko/en .mo 두 개를 임시 디렉터리에 만들어 i18n 에 로드."""
    _write_mo(tmp_path / "ko" / "LC_MESSAGES" / "messages.mo",
              {"Library": "라이브러리", "": _KO_METADATA})
    _write_mo(tmp_path / "en" / "LC_MESSAGES" / "messages.mo",
              {"Library": "Library", "": _EN_METADATA})
    monkeypatch.setattr(i18n, "_translations", {})
    i18n._load_translations(tmp_path)
    return tmp_path


def test_t_translates_to_ko(tmp_locale_dir):
    assert i18n._t("Library", "ko") == "라이브러리"


def test_t_translates_to_en(tmp_locale_dir):
    assert i18n._t("Library", "en") == "Library"


def test_t_missing_msgid_returns_msgid(tmp_locale_dir):
    # 카탈로그에 없는 msgid → msgid 그대로 반환
    assert i18n._t("Untranslated", "ko") == "Untranslated"


def test_t_unknown_locale_falls_back_to_ko(tmp_locale_dir):
    # "auto" 등 비정상 locale → ko 카탈로그 재시도
    assert i18n._t("Library", "auto") == "라이브러리"


def test_t_no_catalogs_returns_msgid(monkeypatch):
    # 카탈로그 0개 → msgid 그대로
    monkeypatch.setattr(i18n, "_translations", {})
    assert i18n._t("Library", "ko") == "Library"


def test_load_translations_skips_missing_files(tmp_path, monkeypatch):
    # locale 디렉터리는 있지만 .mo 가 없는 케이스 — 예외 안 던짐
    (tmp_path / "ko" / "LC_MESSAGES").mkdir(parents=True)
    monkeypatch.setattr(i18n, "_translations", {})
    i18n._load_translations(tmp_path)  # 예외 없이 통과
    assert i18n._translations == {}
