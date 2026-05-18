# M8 — 패키징 + i18n 구현 plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PyInstaller 단일 `.exe` + 웹 UI i18n (ko/en) + 다크모드 수동 토글 + Windows 자동 시작 토글 — v1 최종 마일스톤.

**Architecture:** Babel `gettext` 백엔드 + `LocaleMiddleware` 5단계 결정 + `ContextVar` 로 request 별 locale 격리 + Alpine `localStorage.gah_theme` + winreg `HKCU\...\Run` + PyInstaller `--onefile`. M5 의 `_t()` passthrough 를 본격화하고 `/settings` 페이지에서 세 옵션 통합 관리. `tray.py` 의 런타임 QPixmap 을 빌드 사전 `scripts/generate_tray_ico.py` 가 ICO 로 export.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, Alpine.js, Babel ≥2.14, PyInstaller ≥6, `winreg` / `gettext` (stdlib), pytest-mock.

**Spec:** [`docs/superpowers/specs/2026-05-19-m8-packaging-and-i18n-design.md`](../specs/2026-05-19-m8-packaging-and-i18n-design.md)

**Baseline:** 1011 passed + 1 skipped + 40 deselected (M7 종료). 목표 ~1050 passed.

**Branch:** `feat/m8-packaging-and-i18n` (이미 생성됨, spec commit 1건 b5115f2 위에 누적).

---

## File Structure

신규 (16개):
```
gah.spec                                       (Task 13)
babel.cfg                                      (Task 5)
assets/tray.ico                                (Task 12)
scripts/generate_tray_ico.py                   (Task 12)
src/gah/platform/autostart.py                  (Task 1 스켈레톤 → Task 10 완성)
src/gah/web/locale_middleware.py               (Task 3)
src/gah/web/locale/ko/LC_MESSAGES/messages.po  (Task 7)
src/gah/web/locale/ko/LC_MESSAGES/messages.mo  (Task 7)
src/gah/web/locale/en/LC_MESSAGES/messages.po  (Task 7)
src/gah/web/locale/en/LC_MESSAGES/messages.mo  (Task 7)
src/gah/web/routers/settings.py                (Task 8)
src/gah/web/templates/settings.html            (Task 8)
src/gah/web/static/js/theme.js                 (Task 9)
tests/test_config_m8.py                        (Task 1)
tests/test_i18n.py                             (Task 2)
tests/test_locale_middleware.py                (Task 3)
tests/test_autostart.py                        (Task 10)
tests/test_settings_router.py                  (Task 8)
tests/test_dark_mode_markup.py                 (Task 9)
tests/test_pyinstaller_spec.py                 (Task 13)
tests/test_i18n_extraction.py                  (Task 5)
```

수정 (10개 카테고리):
```
pyproject.toml                                 (Task 1)
.gitignore                                     (Task 13)
README.md                                      (Task 13, 14)
src/gah/config.py                              (Task 1)
src/gah/tray.py                                (Task 11)
src/gah/web/i18n.py                            (Task 2, 3)
src/gah/web/app.py                             (Task 4)
src/gah/web/templates/base.html                (Task 5 — lang 동적)
src/gah/web/templates/_nav.html                (Task 9 — 토글/언어 셀렉터)
src/gah/web/templates/**/*.html                (Task 6 — 한글 msgid → 영어 msgid)
src/gah/web/static/css/main.css                (Task 9 — [data-theme])
src/gah/web/static/css/themes.css              (Task 9 — [data-theme])
milestones/M8_plan.md                          (Task 14 — todo + 상태 추적용 사본)
milestones/M8_verification.md                  (Task 14)
HANDOFF.md / CLAUDE.md / DESIGN.md             (Task 14)
```

---

## Task 1: Phase 0 — 스캐폴딩 (의존성 + Config + 디렉터리)

**목적**: 후속 task 가 의존하는 인프라 (Babel, locale 폴더, Config 필드, autostart 스켈레톤) 를 준비. 이 task 가 끝나면 `pytest -q` 가 1011 + ~5 passed.

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/gah/config.py`
- Create: `src/gah/platform/autostart.py`
- Create: `src/gah/web/locale/ko/LC_MESSAGES/` (빈 디렉터리, `.gitkeep`)
- Create: `src/gah/web/locale/en/LC_MESSAGES/` (빈 디렉터리, `.gitkeep`)
- Create: `tests/test_config_m8.py`

- [ ] **Step 1.1: `pyproject.toml` 에 의존성 추가**

`pyproject.toml` 의 `dependencies` 리스트 끝에 다음 줄 추가 (M5 의 sse-starlette 다음 줄):
```toml
  # M8: i18n 백엔드
  "Babel>=2.14",
```

`[project.optional-dependencies].dev` 리스트에 다음 줄 추가:
```toml
  # M8: PyInstaller 단일 exe 빌드 (사용자 dev only)
  "pyinstaller>=6",
```

- [ ] **Step 1.2: 의존성 설치 + 회귀 확인**

Run: `pip install -e .[dev]`
Run: `pytest -q`
Expected: `1011 passed, 1 skipped, 40 deselected` (회귀 0).

- [ ] **Step 1.3: locale 디렉터리 + `.gitkeep` 생성**

빈 파일 2개:
- `src/gah/web/locale/ko/LC_MESSAGES/.gitkeep`
- `src/gah/web/locale/en/LC_MESSAGES/.gitkeep`

(파일 내용 비어 있음)

- [ ] **Step 1.4: `Config` 신규 필드 — 실패 테스트 먼저**

`tests/test_config_m8.py` 신규 생성:

```python
"""M8 — Config 신규 필드 (ui_language, ui_theme) 회귀 테스트."""
from __future__ import annotations
from pathlib import Path

from gah.config import Config, load_config, save_config


def test_config_defaults_include_ui_language_and_theme():
    cfg = Config()
    assert cfg.ui_language == "auto"
    assert cfg.ui_theme == "auto"


def test_config_serialize_and_load_roundtrip(tmp_path: Path):
    cfg = Config(ui_language="en", ui_theme="dark")
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.ui_language == "en"
    assert loaded.ui_theme == "dark"


def test_config_invalid_ui_language_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text('ui_language = "klingon"\nui_theme = "dark"\n', encoding="utf-8")
    cfg = load_config(path)
    assert cfg.ui_language == "auto"  # 폴백
    assert cfg.ui_theme == "dark"  # 유효한 값은 유지


def test_config_invalid_ui_theme_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text('ui_theme = "neon"\n', encoding="utf-8")
    cfg = load_config(path)
    assert cfg.ui_theme == "auto"  # 폴백


def test_config_autostart_field_still_exists():
    # M0 부터 있는 필드 — M8 가 활용함을 회귀로 고정
    cfg = Config()
    assert cfg.autostart is False
```

Run: `pytest tests/test_config_m8.py -v`
Expected: 5 FAIL — `ui_language`, `ui_theme` 속성이 없다는 AttributeError.

- [ ] **Step 1.5: `Config` 에 신규 필드 + 유효성 검사 추가**

`src/gah/config.py` 의 `_VALID_DESCRIPTION_LANGUAGES` 줄 아래에 추가:

```python
_VALID_UI_LANGUAGES = ("ko", "en", "auto")
_VALID_UI_THEMES = ("auto", "light", "dark")
```

`Config` 데이터클래스의 `preference_usage_weight: float = 0.1` 줄 아래 (M7 신규 필드 마지막) 에 추가:

```python
    # M8 — 웹 UI 언어 / 테마 (description_language 와 별개)
    ui_language: str = "auto"  # "ko" | "en" | "auto"
    ui_theme: str = "auto"     # "auto" | "light" | "dark"
```

`from_mapping` 의 `strat = filtered.get("audio_chunk_strategy")` 블록 다음에 추가:

```python
        ui_lang = filtered.get("ui_language")
        if ui_lang is not None and ui_lang not in _VALID_UI_LANGUAGES:
            filtered.pop("ui_language")
        ui_theme = filtered.get("ui_theme")
        if ui_theme is not None and ui_theme not in _VALID_UI_THEMES:
            filtered.pop("ui_theme")
```

- [ ] **Step 1.6: Config 테스트 통과 확인**

Run: `pytest tests/test_config_m8.py -v`
Expected: 5 PASS.

- [ ] **Step 1.7: `platform/autostart.py` 스켈레톤 (Task 10 에서 본격 구현)**

`src/gah/platform/autostart.py` 신규 생성:

```python
"""M8 — Windows 자동 시작 토글 (HKCU\\...\\Run).

Task 10 에서 winreg 접근 본격 구현. 본 스켈레톤은 후속 task 가 import 만
하더라도 깨지지 않게 한다.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def is_autostart_enabled() -> bool:
    """현재 자동 시작 등록 여부. Task 10 에서 winreg 조회로 구현."""
    if sys.platform != "win32":
        return False
    return False  # Task 10 에서 본격 구현


def set_autostart(enabled: bool, exe_path: Path | None = None) -> None:
    """자동 시작 등록/해제. Task 10 에서 winreg.SetValueEx / DeleteValue 구현."""
    if sys.platform != "win32":
        log.info("autostart no-op on non-Windows")
        return
    # Task 10 에서 본격 구현
    return
```

- [ ] **Step 1.8: 전체 회귀 + 커밋**

Run: `pytest -q`
Expected: `1016 passed, 1 skipped, 40 deselected` (1011 + 5 신규).

Commit:
```bash
git add pyproject.toml src/gah/config.py src/gah/platform/autostart.py src/gah/web/locale/ tests/test_config_m8.py
git commit -m "feat(m8): Phase 0 — 의존성 (Babel, pyinstaller) + Config ui_language/ui_theme 신규 + autostart 스켈레톤"
```

---

## Task 2: i18n 인프라 — `_t()` gettext 위임 + `_load_translations`

**목적**: M5 passthrough 를 gettext 백엔드로 본격화. locale 카탈로그 로딩 + 폴백 체인 단위 테스트.

**Files:**
- Modify: `src/gah/web/i18n.py`
- Create: `tests/test_i18n.py`

- [ ] **Step 2.1: 실패 테스트 먼저**

`tests/test_i18n.py` 신규:

```python
"""M8 — `_t()` gettext 위임 + 폴백 체인 단위 테스트."""
from __future__ import annotations
import struct
from pathlib import Path

import pytest

from gah.web import i18n


def _write_mo(path: Path, entries: dict[str, str]) -> None:
    """msgid → msgstr dict 를 GNU .mo 바이너리로 저장 (gettext 표준 포맷)."""
    # msgid \x00 msgstr 쌍을 정렬해 인덱스 + 데이터 영역 작성
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


@pytest.fixture
def tmp_locale_dir(tmp_path, monkeypatch):
    """ko/en .mo 두 개를 임시 디렉터리에 만들어 i18n 에 로드."""
    _write_mo(tmp_path / "ko" / "LC_MESSAGES" / "messages.mo",
              {"Library": "라이브러리", "": ""})
    _write_mo(tmp_path / "en" / "LC_MESSAGES" / "messages.mo",
              {"Library": "Library", "": ""})
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
```

Run: `pytest tests/test_i18n.py -v`
Expected: 6 FAIL — `_load_translations` / `_t(msg, locale)` 시그니처 불일치.

- [ ] **Step 2.2: `_t()` + `_load_translations` 구현**

`src/gah/web/i18n.py` 를 다음 내용으로 **완전 교체**:

```python
"""M8 — i18n 백엔드 (Babel gettext 카탈로그 + ContextVar locale).

M5 의 passthrough 를 본격화. `_load_translations(locale_dir)` 가 boot 시
ko/en 의 `messages.mo` 를 메모리에 로드, `_t(msgid, locale)` 가 카탈로그
조회 + 폴백 체인 (locale → ko → msgid).

Jinja2 통합 (`setup_jinja_i18n`) 은 Task 3 에서 ContextVar 와 묶어
업데이트한다.
"""
from __future__ import annotations

import gettext
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# boot 시 1회 로드, request 시 read-only — 동시성 안전.
_translations: dict[str, gettext.GNUTranslations] = {}

SUPPORTED_LOCALES = ("ko", "en")


def _load_translations(locale_dir: Path) -> None:
    """`locale_dir/{ko,en}/LC_MESSAGES/messages.mo` 를 메모리에 로드."""
    for lang in SUPPORTED_LOCALES:
        mo = locale_dir / lang / "LC_MESSAGES" / "messages.mo"
        if not mo.exists():
            log.warning("i18n catalog missing: %s", mo)
            continue
        with mo.open("rb") as fh:
            _translations[lang] = gettext.GNUTranslations(fh)
        log.info("i18n catalog loaded: %s", lang)


def _t(text: str, locale: str = "ko") -> str:
    """msgid → translated. 폴백 체인: locale → ko → msgid.

    locale 카탈로그가 없거나 'auto' 등 비정상 값이면 ko 카탈로그로 폴백.
    """
    trans = _translations.get(locale) or _translations.get("ko")
    return trans.gettext(text) if trans else text


def setup_jinja_i18n(env: Any) -> None:
    """M5 호환 entry point — Task 3 에서 ContextVar 기반으로 재정의."""
    # 호환을 위한 임시 placeholder — Task 3 에서 install_gettext_callables 로 교체.
    env.globals["_"] = _t
```

- [ ] **Step 2.3: 테스트 통과 확인**

Run: `pytest tests/test_i18n.py -v`
Expected: 6 PASS.

- [ ] **Step 2.4: 회귀 확인**

Run: `pytest -q`
Expected: `1022 passed, 1 skipped, 40 deselected` (1016 + 6 신규).

이 시점에 `_t()` 가 본격화됐지만 카탈로그는 아직 로드되지 않으므로 (`_load_translations` 호출이 app.py 에 없음) 실제 페이지 렌더는 폴백 (msgid 그대로) 으로 동작. 회귀 없음.

- [ ] **Step 2.5: 커밋**

```bash
git add src/gah/web/i18n.py tests/test_i18n.py
git commit -m "feat(m8): _t() gettext 위임 + _load_translations + 폴백 체인 (locale → ko → msgid)"
```

---

## Task 3: LocaleMiddleware + ContextVar + Jinja2 통합

**목적**: request 별 locale 결정 (5단계) + `ContextVar` 격리 + Jinja2 의 `{{ _("...") }}` 가 현재 request locale 로 자동 동작.

**Files:**
- Create: `src/gah/web/locale_middleware.py`
- Modify: `src/gah/web/i18n.py`
- Create: `tests/test_locale_middleware.py`

- [ ] **Step 3.1: 실패 테스트 먼저**

`tests/test_locale_middleware.py` 신규:

```python
"""M8 — LocaleMiddleware 5단계 결정 + ContextVar 격리 테스트."""
from __future__ import annotations

from contextvars import copy_context

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from gah.config import Config
from gah.web.locale_middleware import LocaleMiddleware, current_locale


@pytest.fixture
def app_with_locale(tmp_path):
    app = FastAPI()
    cfg = Config()
    app.state.config = cfg
    app.add_middleware(LocaleMiddleware)

    @app.get("/probe")
    async def probe(request: Request):
        return JSONResponse({"locale": request.state.locale,
                             "ctx": current_locale.get()})
    return app, cfg


def test_locale_url_overrides_all(app_with_locale):
    app, cfg = app_with_locale
    cfg.ui_language = "ko"
    c = TestClient(app)
    r = c.get("/probe?lang=en", headers={"accept-language": "ko"},
              cookies={"gah_locale": "ko"})
    assert r.json() == {"locale": "en", "ctx": "en"}


def test_locale_cookie_overrides_config_and_header(app_with_locale):
    app, cfg = app_with_locale
    cfg.ui_language = "ko"
    c = TestClient(app)
    r = c.get("/probe", headers={"accept-language": "ko"},
              cookies={"gah_locale": "en"})
    assert r.json()["locale"] == "en"


def test_locale_config_overrides_header(app_with_locale):
    app, cfg = app_with_locale
    cfg.ui_language = "en"
    c = TestClient(app)
    r = c.get("/probe", headers={"accept-language": "ko"})
    assert r.json()["locale"] == "en"


def test_locale_accept_language_used_when_config_auto(app_with_locale):
    app, cfg = app_with_locale
    cfg.ui_language = "auto"
    c = TestClient(app)
    r1 = c.get("/probe", headers={"accept-language": "en-US,en;q=0.9,ko;q=0.5"})
    assert r1.json()["locale"] == "en"
    r2 = c.get("/probe", headers={"accept-language": "ko-KR,ko;q=0.9"})
    assert r2.json()["locale"] == "ko"


def test_locale_falls_back_to_ko(app_with_locale):
    app, cfg = app_with_locale
    cfg.ui_language = "auto"
    c = TestClient(app)
    r = c.get("/probe")  # 헤더/쿠키/Config 다 비어/auto
    assert r.json()["locale"] == "ko"


def test_locale_invalid_url_param_ignored(app_with_locale):
    app, cfg = app_with_locale
    cfg.ui_language = "ko"
    c = TestClient(app)
    r = c.get("/probe?lang=klingon")
    assert r.json()["locale"] == "ko"  # 잘못된 값 무시


def test_locale_contextvar_resets_between_requests(app_with_locale):
    app, cfg = app_with_locale
    cfg.ui_language = "ko"
    c = TestClient(app)
    c.get("/probe?lang=en")  # request 끝나면 ContextVar reset
    # 새 context 에서 default 값 확인
    ctx = copy_context()
    assert ctx.run(lambda: current_locale.get("ko")) == "ko"


def test_locale_invalid_cookie_value_ignored(app_with_locale):
    app, cfg = app_with_locale
    cfg.ui_language = "ko"
    c = TestClient(app)
    r = c.get("/probe", cookies={"gah_locale": "klingon"})
    assert r.json()["locale"] == "ko"
```

Run: `pytest tests/test_locale_middleware.py -v`
Expected: 8 FAIL — `LocaleMiddleware` / `current_locale` import 실패.

- [ ] **Step 3.2: LocaleMiddleware + ContextVar 구현**

`src/gah/web/locale_middleware.py` 신규:

```python
"""M8 — locale 결정 5단계 미들웨어 + ContextVar.

우선순위 (위가 우선):
  1. URL ?lang=ko|en
  2. 쿠키 gah_locale
  3. Config.ui_language (≠ "auto")
  4. Accept-Language 헤더 (Config.ui_language == "auto" 일 때)
  5. 폴백 "ko"

middleware 가 결정한 값을 `request.state.locale` + ContextVar `current_locale`
에 set. Jinja2 의 `_()` 가 ContextVar 를 읽어 현재 locale 로 번역.
"""
from __future__ import annotations

from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

current_locale: ContextVar[str] = ContextVar("gah_current_locale", default="ko")

SUPPORTED = ("ko", "en")


class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        locale = self._resolve(request)
        request.state.locale = locale
        token = current_locale.set(locale)
        try:
            response = await call_next(request)
        finally:
            current_locale.reset(token)
        return response

    def _resolve(self, request: Request) -> str:
        # 1. URL ?lang=
        q = request.query_params.get("lang")
        if q in SUPPORTED:
            return q
        # 2. 쿠키
        c = request.cookies.get("gah_locale")
        if c in SUPPORTED:
            return c
        # 3. Config.ui_language
        cfg = getattr(request.app.state, "config", None)
        cfg_lang = getattr(cfg, "ui_language", "auto") if cfg else "auto"
        if cfg_lang in SUPPORTED:
            return cfg_lang
        # 4. Accept-Language
        accept = request.headers.get("accept-language", "")
        for raw in accept.split(","):
            tag = raw.split(";")[0].strip().lower()
            if tag.startswith("en"):
                return "en"
            if tag.startswith("ko"):
                return "ko"
        # 5. 폴백
        return "ko"
```

- [ ] **Step 3.3: `setup_jinja_i18n` 을 ContextVar 기반으로 재정의**

`src/gah/web/i18n.py` 의 `setup_jinja_i18n` 함수를 다음으로 교체:

```python
def setup_jinja_i18n(env: Any) -> None:
    """Jinja2 환경에 i18n 확장 + `{{ _("...") }}` 가 현재 request locale 로 동작.

    M8: `jinja2.ext.i18n` 추가 + `install_gettext_callables` 로 gettext/ngettext
    바인딩. callable 은 ContextVar `current_locale` 을 읽어 매 호출마다 현재
    request 의 locale 을 적용.
    """
    from .locale_middleware import current_locale

    env.add_extension("jinja2.ext.i18n")

    def _gettext(msg: str) -> str:
        return _t(msg, current_locale.get())

    def _ngettext(singular: str, plural: str, n: int) -> str:
        return _t(singular if n == 1 else plural, current_locale.get())

    env.install_gettext_callables(  # type: ignore[attr-defined]
        gettext=_gettext, ngettext=_ngettext, newstyle=True,
    )
    # M5 호환 — `env.globals["_"]` 도 등록 (일부 템플릿이 직접 사용).
    env.globals["_"] = _gettext
```

- [ ] **Step 3.4: 테스트 통과 확인**

Run: `pytest tests/test_locale_middleware.py tests/test_i18n.py -v`
Expected: 14 PASS.

- [ ] **Step 3.5: 회귀 확인**

Run: `pytest -q`
Expected: `1030 passed, 1 skipped, 40 deselected` (1022 + 8 신규).

- [ ] **Step 3.6: 커밋**

```bash
git add src/gah/web/i18n.py src/gah/web/locale_middleware.py tests/test_locale_middleware.py
git commit -m "feat(m8): LocaleMiddleware 5단계 결정 + ContextVar + Jinja2 i18n 확장"
```

---

## Task 4: app.py 통합 — 미들웨어 등록 + 카탈로그 boot 로드

**목적**: `LocaleMiddleware` 를 FastAPI 앱에 등록하고 boot 시 `_load_translations` 호출. 이 시점에 카탈로그가 비어 있어도 폴백 (msgid 그대로) 으로 동작해 회귀 없음.

**Files:**
- Modify: `src/gah/web/app.py`

- [ ] **Step 4.1: app.py 의 import + build_app 수정**

`src/gah/web/app.py` 의 import 블록에 추가 (기존 `from .i18n import setup_jinja_i18n` 줄 다음):

```python
from .i18n import _load_translations, setup_jinja_i18n
from .locale_middleware import LocaleMiddleware
```

`_templates_dir()` 함수 다음, `build_app` 위에 신규 헬퍼 추가:

```python
def _locale_dir() -> Path:
    """패키지 내 locale 디렉터리 경로."""
    return Path(__file__).parent / "locale"
```

`build_app(deps)` 함수 본문에서 `templates = Jinja2Templates(...)` + `setup_jinja_i18n(templates.env)` 직전에 카탈로그 로드 + 미들웨어 등록:

```python
    # M8 — boot 시 i18n 카탈로그 1회 로드 + locale 미들웨어 등록
    _load_translations(_locale_dir())
    app.state.config = deps.config  # LocaleMiddleware 가 참조
    app.add_middleware(LocaleMiddleware)
```

위치: `app = FastAPI(...)` 로 인스턴스 만든 직후, 라우터 등록 전. (정확한 위치는 기존 코드 흐름 따라가며 결정 — 보통 `app = FastAPI(...)` 다음 줄.)

- [ ] **Step 4.2: 회귀 확인**

Run: `pytest -q`
Expected: `1030 passed, 1 skipped, 40 deselected` (회귀 0).

기존 페이지 렌더 테스트 (`test_pages_router.py` 등) 가 LocaleMiddleware 통과 후 정상 응답을 받는지 자동 확인됨.

- [ ] **Step 4.3: 커밋**

```bash
git add src/gah/web/app.py
git commit -m "feat(m8): app.py 에 LocaleMiddleware 등록 + boot 시 _load_translations 호출"
```

---

## Task 5: babel.cfg + 첫 추출 + base.html `lang` 동적

**목적**: `pybabel extract` 실행 환경을 만들고 첫 `messages.pot` 생성 + base.html 의 `<html lang="ko">` 를 동적 locale 로 교체.

**Files:**
- Create: `babel.cfg`
- Modify: `src/gah/web/templates/base.html`
- Create: `tests/test_i18n_extraction.py`

- [ ] **Step 5.1: `babel.cfg` 작성**

저장소 루트에 `babel.cfg` 신규:

```ini
[python: src/gah/**.py]
[jinja2: src/gah/web/templates/**.html]
extensions=jinja2.ext.i18n
```

- [ ] **Step 5.2: `pybabel extract` 실행 + `.pot` 산출 확인**

Run:
```powershell
pybabel extract -F babel.cfg -k _ -k _t -o src/gah/web/locale/messages.pot src/
```

Expected: `src/gah/web/locale/messages.pot` 파일 생성. 내부에 현재 `_("...")` 로 감싼 한국어 msgid 들이 (예: `msgid "라이브러리"`) 들어 있음.

이 .pot 은 Task 6 의 영어 msgid 변환 전 스냅샷. Task 6 이 끝나면 .pot 을 재추출한다.

- [ ] **Step 5.3: base.html `lang` 속성 동적화**

`src/gah/web/templates/base.html` line 2 수정:

기존:
```html
<html lang="ko">
```

신규:
```html
<html lang="{{ request.state.locale if request and request.state.locale is defined else 'ko' }}">
```

(`request` 가 모든 페이지 컨텍스트에 있다는 가정. FastAPI Jinja2Templates 가 자동 주입.)

- [ ] **Step 5.4: 추출 smoke 테스트**

`tests/test_i18n_extraction.py` 신규:

```python
"""M8 — pybabel extract 가 주요 키를 잡아내는지 smoke."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(
    subprocess.run(
        [sys.executable, "-c", "import babel"],
        capture_output=True,
    ).returncode != 0,
    reason="Babel 미설치 환경",
)
def test_babel_cfg_exists():
    assert (REPO_ROOT / "babel.cfg").exists()


def test_pot_has_known_msgids(tmp_path):
    """현재 hardcode 된 핵심 한국어가 .pot 에 들어가는지.

    Task 6 이 끝나면 영어 msgid 로 바뀌므로 이 테스트도 그때 갱신한다.
    """
    pot = REPO_ROOT / "src" / "gah" / "web" / "locale" / "messages.pot"
    if not pot.exists():
        pytest.skip(".pot 미생성 — pybabel extract 실행 필요")
    body = pot.read_text(encoding="utf-8")
    # Task 5 시점: 한국어 msgid 가 다수 — Task 6 후 'Library' 등 영어 msgid 로 교체됨.
    # 둘 중 하나가 있으면 통과.
    assert "라이브러리" in body or "Library" in body
```

Run: `pytest tests/test_i18n_extraction.py -v`
Expected: 2 PASS.

- [ ] **Step 5.5: 회귀 확인 + 커밋**

Run: `pytest -q`
Expected: `1032 passed, 1 skipped, 40 deselected` (1030 + 2 신규).

```bash
git add babel.cfg src/gah/web/templates/base.html src/gah/web/locale/messages.pot tests/test_i18n_extraction.py
git commit -m "feat(m8): babel.cfg + 첫 messages.pot 추출 + base.html lang 동적화"
```

---

## Task 6: 템플릿 한글 → 영어 msgid 일괄 변환

**목적**: spec D2 의 "msgid 영어 자연 문장" 정책을 모든 템플릿 + Python 코드에 적용. 이 task 가 plan 의 가장 큰 단일 작업.

**Files:**
- Modify: `src/gah/web/templates/**/*.html` (전체)
- Modify: `src/gah/web/**/*.py` (사용자 노출 문자열만)

**전략**: 한 번의 큰 sed 대신 카테고리별로 작은 commit. 각 commit 후 `pytest -q` 회귀 확인.

- [ ] **Step 6.1: msgid 매핑 작성 (가이드)**

작업 시작 전 매핑 표를 `docs/superpowers/notes/2026-05-19-m8-msgid-mapping.md` 에 임시 작성. 이 표는 plan 외부 노트 — 작업 끝나면 삭제 가능. 형식:

```markdown
# M8 msgid 매핑 (작업 임시 노트)

| 위치 | 기존 한국어 | 신규 영어 msgid |
|---|---|---|
| _nav.html | 라이브러리 | Library |
| _nav.html | 팩 | Packs |
| _nav.html | 라벨 관리 | Label management |
| _nav.html | 프로젝트 | Projects |
| _nav.html | Unity Asset Store | Unity Asset Store |
| _nav.html | Claude 요청 | Claude request |
| base.html | Game Asset Helper | Game Asset Helper |
| _header_project_dropdown.html | 프로젝트 선택 | Select project |
| ... (전체) | ... | ... |
```

전체 추출: `pybabel extract` 결과 .pot 의 msgid 들을 표로 옮겨 영어 매핑 적기.

- [ ] **Step 6.2: 네비게이션 (`_nav.html`, `_header_project_dropdown.html`, `_modal_new_project.html`)**

`_nav.html` 의 모든 `_("한국어")` 를 `_("English")` 로:

```html
<a href="/library"{% if page == "library" %} class="active"{% endif %}>{{ _("Library") }}</a>
<a href="/packs"{% if page == "packs" %} class="active"{% endif %}>{{ _("Packs") }}</a>
<a href="/labels/admin"{% if page == "labels" %} class="active"{% endif %}>{{ _("Label management") }}</a>
<a href="/projects"{% if page == "projects" %} class="active"{% endif %}>{{ _("Projects") }}</a>
<a href="/unity-asset-store"{% if page == "unity_asset_store" %} class="active"{% endif %}>{{ _("Unity Asset Store") }}</a>
...
🤖 {{ _("Claude request") }} (<span x-text="$store.notifications.pickCount"></span>)
```

`_header_project_dropdown.html`, `_modal_new_project.html` 도 동일한 패턴.

Run: `pytest -q`
Expected: 회귀 0 (현재 카탈로그 비어 있어 폴백으로 영어 msgid 가 그대로 화면에 — 의도된 중간 상태, Task 7 의 ko.po 가 한국어로 매핑).

Commit:
```bash
git add src/gah/web/templates/_nav.html src/gah/web/templates/_header_project_dropdown.html src/gah/web/templates/_modal_new_project.html
git commit -m "refactor(m8): 네비/헤더 msgid 영어 자연 문장으로 통일"
```

- [ ] **Step 6.3: 페이지 본문 템플릿들**

다음 파일들의 `_("한국어")` 를 영어 msgid 로 일괄 변환:

- `library.html`, `packs.html`, `labels_admin.html`, `search.html` (메인 페이지들)
- `projects_list.html`, `project_detail.html`, `unity_asset_store.html`

각 파일 변환 후 즉시 `pytest -q` 회귀 확인. 한 파일씩 또는 카테고리(2~3 파일) 묶어 commit.

각 commit 메시지:
```
refactor(m8): <파일> msgid 영어로 통일
```

- [ ] **Step 6.4: 부분 템플릿 (`_card_*`, `_modal_*`, `_preference_panel`, `_pick_card` 등)**

`src/gah/web/templates/_*.html` 의 나머지 부분 템플릿. Step 6.3 와 동일한 방식.

- [ ] **Step 6.5: Python 코드의 사용자 노출 문자열**

`src/gah/web/routers/**/*.py` 와 `src/gah/web/deps.py` 등에서 `_t("한국어")` 또는 raw string 으로 사용자에게 노출되는 메시지를 영어 msgid 로:

검색: `pytest -q --collect-only` 가 아니라, 다음 두 패턴을 grep:
- `_t\(["']([^"']*[가-힣][^"']*)["']\)`
- 에러 메시지 raw string 중 사용자에게 노출되는 것 (return JSONResponse, raise HTTPException(detail=...))

각 발견 위치를 영어 msgid 로 변환 후 `_t()` 로 래핑 (이미 래핑된 곳은 msgid 만 교체).

Commit:
```bash
git add src/gah/web/routers/ src/gah/web/deps.py
git commit -m "refactor(m8): 라우터/deps 의 사용자 노출 문자열 영어 msgid 로 통일"
```

- [ ] **Step 6.6: `.pot` 재추출 + 검증**

Run:
```powershell
pybabel extract -F babel.cfg -k _ -k _t -o src/gah/web/locale/messages.pot src/
```

`.pot` 내부 확인 — 한국어 msgid 가 더 이상 없고 영어 msgid 만 있어야 함. 누락된 항목 (`msgid ""` 빈 줄 옆에 한국어가 보이면 변환 누락) 발견 시 위 step 들로 돌아가 수정.

`tests/test_i18n_extraction.py` 의 `test_pot_has_known_msgids` 갱신:

```python
def test_pot_has_known_msgids(tmp_path):
    pot = REPO_ROOT / "src" / "gah" / "web" / "locale" / "messages.pot"
    if not pot.exists():
        pytest.skip(".pot 미생성")
    body = pot.read_text(encoding="utf-8")
    # Task 6 후: 영어 msgid 들이 들어 있어야 한다.
    for expected in ("Library", "Packs", "Projects", "Game Asset Helper"):
        assert expected in body, f"msgid 누락: {expected}"
    # 한국어 msgid 가 남아 있으면 Task 6 미완.
    assert "라이브러리" not in body, "한국어 msgid 가 남아 있음 — Task 6 미완"
```

Run: `pytest tests/test_i18n_extraction.py -v`
Expected: 2 PASS.

- [ ] **Step 6.7: 전체 회귀 + 임시 노트 삭제 + 커밋**

Run: `pytest -q`
Expected: `1032 passed` (회귀 0).

임시 노트 삭제: `git rm docs/superpowers/notes/2026-05-19-m8-msgid-mapping.md` (또는 디렉터리째).

Commit:
```bash
git add src/gah/web/locale/messages.pot tests/test_i18n_extraction.py
git rm docs/superpowers/notes/2026-05-19-m8-msgid-mapping.md
git commit -m "refactor(m8): .pot 재추출 + 임시 매핑 노트 삭제"
```

---

## Task 7: ko.po + en.po 작성 + .mo 컴파일

**목적**: 영어 msgid 들을 ko/en 으로 번역하고 `.mo` 바이너리를 빌드 + 커밋.

**Files:**
- Create: `src/gah/web/locale/ko/LC_MESSAGES/messages.po`
- Create: `src/gah/web/locale/ko/LC_MESSAGES/messages.mo`
- Create: `src/gah/web/locale/en/LC_MESSAGES/messages.po`
- Create: `src/gah/web/locale/en/LC_MESSAGES/messages.mo`
- Delete: `src/gah/web/locale/ko/LC_MESSAGES/.gitkeep`
- Delete: `src/gah/web/locale/en/LC_MESSAGES/.gitkeep`

- [ ] **Step 7.1: `pybabel init` 으로 빈 .po 두 개 생성**

Run:
```powershell
pybabel init -i src/gah/web/locale/messages.pot -d src/gah/web/locale -l ko
pybabel init -i src/gah/web/locale/messages.pot -d src/gah/web/locale -l en
```

산출: `src/gah/web/locale/{ko,en}/LC_MESSAGES/messages.po` 두 개.

`.gitkeep` 삭제:
```powershell
Remove-Item src/gah/web/locale/ko/LC_MESSAGES/.gitkeep
Remove-Item src/gah/web/locale/en/LC_MESSAGES/.gitkeep
```

- [ ] **Step 7.2: ko.po 작성 — msgstr 에 한국어 매핑**

`src/gah/web/locale/ko/LC_MESSAGES/messages.po` 의 각 항목을:

```po
msgid "Library"
msgstr "라이브러리"

msgid "Packs"
msgstr "팩"

msgid "Label management"
msgstr "라벨 관리"

msgid "Projects"
msgstr "프로젝트"

msgid "Unity Asset Store"
msgstr "Unity Asset Store"

msgid "Claude request"
msgstr "Claude 요청"

msgid "Game Asset Helper"
msgstr "Game Asset Helper"

msgid "Select project"
msgstr "프로젝트 선택"

...
```

(Task 6.1 의 매핑 표 참조하여 전체 항목 채움.)

- [ ] **Step 7.3: en.po 작성 — msgstr = msgid (영어 동일)**

`src/gah/web/locale/en/LC_MESSAGES/messages.po` 의 각 msgstr 에 msgid 그대로 복사:

```po
msgid "Library"
msgstr "Library"

msgid "Packs"
msgstr "Packs"

...
```

(빠른 변환: 텍스트 에디터 정규식 또는 Python 스크립트 — `pybabel update --previous` 옵션으로 msgid 를 msgstr 로 자동 복사 가능)

대안: `pybabel update -i ...pot -d ...en --previous` 후 사용자가 직접 채움 — 단 비효율적. 직접 정규식 치환 권장:
- Pattern: `^msgid "(.*?)"\s*\nmsgstr ""$`
- Replacement: `msgid "$1"\nmsgstr "$1"`

- [ ] **Step 7.4: `.mo` 컴파일**

Run:
```powershell
pybabel compile -d src/gah/web/locale
```

산출: `messages.mo` 두 개 (ko, en).

확인: 두 파일이 binary 로 존재하고 크기 > 0.

- [ ] **Step 7.5: 회귀 + 페이지 렌더 검증**

Run: `pytest -q`
Expected: `1032 passed` (회귀 0).

이 시점에 페이지 렌더 시 `_load_translations` 가 .mo 두 개를 로드 → `_t("Library", "ko")` → "라이브러리" 반환 → 페이지에 한국어로 보임 (M5 이전과 동일한 사용자 경험).

수동 검증: `python -m gah --tray` → 브라우저에서 한국어 표시 확인. `?lang=en` 으로 영어 확인. (이 수동 검증은 plan 외, M8_verification 의 일부.)

- [ ] **Step 7.6: 커밋**

```bash
git add src/gah/web/locale/
git commit -m "feat(m8): ko/en 번역 카탈로그 (messages.po + 컴파일된 .mo) 추가"
```

---

## Task 8: /settings 페이지 + 라우터

**목적**: 언어 / 테마 / 자동 시작 세 옵션을 한 페이지에서 관리. `POST /api/settings` 가 Config 저장 + 쿠키 + (Task 11 에서) 레지스트리 동기화.

**Files:**
- Create: `src/gah/web/routers/settings.py`
- Create: `src/gah/web/templates/settings.html`
- Modify: `src/gah/web/app.py` (라우터 등록)
- Modify: `src/gah/web/templates/_nav.html` (메뉴 링크)
- Create: `tests/test_settings_router.py`

- [ ] **Step 8.1: 실패 테스트 먼저**

`tests/test_settings_router.py` 신규:

```python
"""M8 — /settings 페이지 + POST /api/settings 통합 테스트."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(web_app):  # conftest.py 의 fixture 가정
    return TestClient(web_app)


def test_settings_page_renders_200(client):
    r = client.get("/settings")
    assert r.status_code == 200
    assert b"<form" in r.content


def test_settings_post_updates_ui_language(client, web_deps):
    r = client.post("/api/settings", json={"ui_language": "en"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert web_deps.config.ui_language == "en"
    # 쿠키 set 확인
    assert "gah_locale=en" in r.headers.get("set-cookie", "")


def test_settings_post_updates_ui_theme(client, web_deps):
    r = client.post("/api/settings", json={"ui_theme": "dark"})
    assert r.status_code == 200
    assert web_deps.config.ui_theme == "dark"


def test_settings_post_updates_autostart(client, web_deps, monkeypatch):
    """Task 11 에서 winreg 동기화 — 본 task 는 Config 만 검증."""
    # autostart 호출은 mock — Task 11 에서 실제 winreg 분기 테스트
    from gah.platform import autostart as autostart_mod
    monkeypatch.setattr(autostart_mod, "set_autostart", lambda enabled, exe_path=None: None)
    r = client.post("/api/settings", json={"autostart": True})
    assert r.status_code == 200
    assert web_deps.config.autostart is True


def test_settings_post_invalid_language_rejected(client):
    r = client.post("/api/settings", json={"ui_language": "klingon"})
    assert r.status_code == 422  # Pydantic Literal 거부


def test_settings_get_includes_current_locale(client, web_deps):
    web_deps.config.ui_language = "ko"
    r = client.get("/settings")
    body = r.text
    # 현재 선택된 라디오 확인
    assert 'value="ko" checked' in body or "ui_language" in body
```

Run: `pytest tests/test_settings_router.py -v`
Expected: 6 FAIL (라우터 미존재).

`conftest.py` 의 `web_app` / `web_deps` fixture 가 기존에 있는지 확인. 없으면 `tests/conftest.py` 에 신규 fixture 추가:

```python
# tests/conftest.py 에 추가 (이미 web_deps 가 있으면 skip)
import pytest
from gah.web.app import build_app
from gah.web.deps import WebDeps
from gah.config import Config, default_app_paths


@pytest.fixture
def web_deps(tmp_path):
    paths = default_app_paths(tmp_path)
    paths.ensure_dirs()
    cfg = Config()
    # ... 기존 WebDeps 생성 패턴 따름 (다른 M5/M7 fixture 참조)
    deps = WebDeps(config=cfg, paths=paths, ...)  # 실제 인자는 WebDeps 시그니처 따라
    return deps


@pytest.fixture
def web_app(web_deps):
    return build_app(web_deps)
```

(기존 fixture 가 다른 이름으로 있으면 그것 재사용.)

- [ ] **Step 8.2: `settings.py` 라우터 구현**

`src/gah/web/routers/settings.py` 신규:

```python
"""M8 — /settings 페이지 + POST /api/settings (언어/테마/자동 시작)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from gah.config import save_config
from gah.platform.autostart import is_autostart_enabled, set_autostart
from gah.web.deps import WebDeps, get_web_deps

router = APIRouter()


class SettingsUpdate(BaseModel):
    ui_language: Literal["ko", "en", "auto"] | None = None
    ui_theme: Literal["auto", "light", "dark"] | None = None
    autostart: bool | None = None


def _templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    deps: WebDeps = Depends(get_web_deps),
):
    return _templates(request).TemplateResponse(
        "settings.html",
        {
            "request": request,
            "page": "settings",
            "config": deps.config,
            "autostart_actual": is_autostart_enabled(),
        },
    )


@router.post("/api/settings")
async def update_settings(
    payload: SettingsUpdate,
    deps: WebDeps = Depends(get_web_deps),
):
    cfg = deps.config
    if payload.ui_language is not None:
        cfg.ui_language = payload.ui_language
    if payload.ui_theme is not None:
        cfg.ui_theme = payload.ui_theme
    if payload.autostart is not None:
        try:
            set_autostart(payload.autostart)
            cfg.autostart = payload.autostart
        except OSError as e:
            return JSONResponse(
                {"ok": False, "error": str(e)},
                status_code=500,
            )
    save_config(cfg, deps.paths.config_path)
    response = JSONResponse({"ok": True})
    if payload.ui_language is not None and payload.ui_language != "auto":
        response.set_cookie(
            "gah_locale",
            payload.ui_language,
            max_age=31_536_000,
            samesite="lax",
        )
    return response
```

- [ ] **Step 8.3: `app.py` 의 라우터 등록 + templates 노출**

`src/gah/web/app.py` 의 import 에 추가:
```python
from .routers import settings as settings_router
```

`build_app` 내 라우터 등록 블록에 추가:
```python
app.include_router(settings_router.router)
```

`templates` 인스턴스를 `app.state.templates` 로 노출 (settings.py 에서 `request.app.state.templates` 접근하기 위함):
```python
# 기존: templates = Jinja2Templates(...) 직후
app.state.templates = templates
```

- [ ] **Step 8.4: `settings.html` 템플릿**

`src/gah/web/templates/settings.html` 신규:

```html
{% extends "base.html" %}
{% block title %}{{ _("Settings") }} · {{ _("Game Asset Helper") }}{% endblock %}
{% block content %}
<section class="settings-page" x-data="settingsForm()">
  <h1>{{ _("Settings") }}</h1>

  <form @submit.prevent="save">
    <fieldset>
      <legend>{{ _("Language") }}</legend>
      <label><input type="radio" name="ui_language" value="ko"
                    x-model="form.ui_language"> {{ _("Korean") }} (한국어)</label>
      <label><input type="radio" name="ui_language" value="en"
                    x-model="form.ui_language"> {{ _("English") }} (English)</label>
      <label><input type="radio" name="ui_language" value="auto"
                    x-model="form.ui_language"> {{ _("Auto-detect") }}</label>
    </fieldset>

    <fieldset>
      <legend>{{ _("Theme") }}</legend>
      <label><input type="radio" name="ui_theme" value="auto"
                    x-model="form.ui_theme"> {{ _("Auto (system)") }}</label>
      <label><input type="radio" name="ui_theme" value="light"
                    x-model="form.ui_theme"> {{ _("Light") }}</label>
      <label><input type="radio" name="ui_theme" value="dark"
                    x-model="form.ui_theme"> {{ _("Dark") }}</label>
    </fieldset>

    <fieldset>
      <legend>{{ _("Startup") }}</legend>
      <label><input type="checkbox" x-model="form.autostart">
             {{ _("Start with Windows") }}</label>
      <small x-show="!autostartSupported">{{ _("Only available on Windows") }}</small>
    </fieldset>

    <button type="submit" :disabled="saving">
      <span x-show="!saving">{{ _("Save") }}</span>
      <span x-show="saving">{{ _("Saving...") }}</span>
    </button>
    <span x-show="error" class="error" x-text="error"></span>
  </form>
</section>

<script>
function settingsForm() {
    return {
        form: {
            ui_language: "{{ config.ui_language }}",
            ui_theme: "{{ config.ui_theme }}",
            autostart: {{ "true" if autostart_actual else "false" }},
        },
        saving: false,
        error: "",
        autostartSupported: navigator.userAgent.includes("Windows"),
        async save() {
            this.saving = true;
            this.error = "";
            try {
                const r = await fetch("/api/settings", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(this.form),
                });
                if (!r.ok) {
                    const data = await r.json().catch(() => ({}));
                    this.error = data.error || `HTTP ${r.status}`;
                    return;
                }
                window.location.reload();
            } catch (e) {
                this.error = String(e);
            } finally {
                this.saving = false;
            }
        },
    };
}
</script>
{% endblock %}
```

- [ ] **Step 8.5: `_nav.html` 에 "Settings" 메뉴 항목 추가**

`_nav.html` 의 `<a href="/unity-asset-store"...>` 다음에 추가:

```html
    <span class="nav-divider">|</span>
    <a href="/settings"{% if page == "settings" %} class="active"{% endif %}>{{ _("Settings") }}</a>
```

- [ ] **Step 8.6: en.po / ko.po 에 신규 msgid 추가 + 재컴파일**

Task 7 의 .po 파일들에 `Settings`, `Language`, `Theme`, `Startup`, `Korean`, `English`, `Auto-detect`, `Auto (system)`, `Light`, `Dark`, `Start with Windows`, `Only available on Windows`, `Save`, `Saving...` msgid 추가:

`ko.po`:
```po
msgid "Settings"
msgstr "설정"
msgid "Language"
msgstr "언어"
... (전부)
```

`en.po`: msgstr = msgid.

Run:
```powershell
pybabel compile -d src/gah/web/locale
```

- [ ] **Step 8.7: 회귀 + 통합 테스트 통과 확인**

Run: `pytest tests/test_settings_router.py -v`
Expected: 6 PASS.

Run: `pytest -q`
Expected: `1038 passed, 1 skipped, 40 deselected` (1032 + 6 신규).

- [ ] **Step 8.8: 커밋**

```bash
git add src/gah/web/routers/settings.py src/gah/web/templates/settings.html src/gah/web/templates/_nav.html src/gah/web/app.py src/gah/web/locale/ tests/test_settings_router.py
git commit -m "feat(m8): /settings 페이지 + POST /api/settings (언어/테마/자동시작)"
```

---

## Task 9: 다크모드 수동 토글 (헤더 + theme.js + CSS data-theme)

**목적**: 헤더에 ☀️/🌙/🌗 토글 + Alpine `localStorage.gah_theme` 영속화 + CSS `[data-theme]` 강제 셀렉터.

**Files:**
- Create: `src/gah/web/static/js/theme.js`
- Modify: `src/gah/web/templates/_nav.html`
- Modify: `src/gah/web/templates/base.html` (인라인 anti-flash 스크립트)
- Modify: `src/gah/web/static/css/themes.css` 또는 `main.css`
- Create: `tests/test_dark_mode_markup.py`

- [ ] **Step 9.1: 기존 CSS 점검**

`src/gah/web/static/css/themes.css` 와 `main.css` 를 빠르게 살펴 현재 `prefers-color-scheme: dark` 가 어떻게 정의되어 있는지 확인. CSS 변수 사용 여부 + 다크 셀렉터 위치 파악.

(Plan 작성 시점에 정확한 CSS 셀렉터를 모르므로, 구현 시점에 grep 으로 위치 찾고 그 다음 패턴에 맞춰 작업.)

- [ ] **Step 9.2: 실패 테스트 먼저**

`tests/test_dark_mode_markup.py` 신규:

```python
"""M8 — 다크모드 토글 헤더 마크업 + theme.js 로드 확인."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_nav_has_theme_toggle_button(client):
    r = client.get("/library")
    assert r.status_code == 200
    body = r.text
    assert 'x-data="themeToggle()"' in body or "themeToggle()" in body
    assert "theme-toggle-btn" in body


def test_theme_js_loaded_in_base(client):
    r = client.get("/library")
    assert "/static/js/theme.js" in r.text


def test_anti_flash_inline_script_present(client):
    r = client.get("/library")
    # localStorage 즉시 적용 인라인 스크립트
    assert "gah_theme" in r.text
    # <head> 내부에서 data-theme 적용
    assert "documentElement.setAttribute" in r.text or "data-theme" in r.text
```

Run: `pytest tests/test_dark_mode_markup.py -v`
Expected: 3 FAIL.

- [ ] **Step 9.3: `theme.js` 작성**

`src/gah/web/static/js/theme.js` 신규:

```javascript
// M8 — 다크/라이트 모드 수동 토글 (Alpine 컴포넌트 + localStorage 영속화).
//
// 토글 사이클: auto → light → dark → auto ...
//
// auto = prefers-color-scheme (CSS 미디어쿼리) 따라감
// light = <html data-theme="light"> 강제
// dark  = <html data-theme="dark">  강제
//
// 초기 깜빡임 방지: base.html 의 <head> 인라인 스크립트가 페이지 파싱 직후
// localStorage 값 즉시 적용. 본 Alpine 컴포넌트는 토글 UI + apply() 만.

function themeToggle() {
    return {
        mode: 'auto',
        init() {
            this.mode = localStorage.getItem('gah_theme') || 'auto';
            this.apply();
        },
        cycle() {
            this.mode = this.mode === 'auto' ? 'light'
                      : this.mode === 'light' ? 'dark'
                      : 'auto';
            localStorage.setItem('gah_theme', this.mode);
            this.apply();
        },
        apply() {
            if (this.mode === 'auto') {
                document.documentElement.removeAttribute('data-theme');
            } else {
                document.documentElement.setAttribute('data-theme', this.mode);
            }
        },
        get icon() {
            return this.mode === 'dark' ? '🌙'
                 : this.mode === 'light' ? '☀️'
                 : '🌗';
        },
        get label() {
            return this.mode === 'dark' ? '다크'
                 : this.mode === 'light' ? '라이트'
                 : '자동';
        },
    };
}
```

- [ ] **Step 9.4: `base.html` 인라인 anti-flash 스크립트 + theme.js 로드**

`base.html` 의 `<head>` 안, 마지막 `<script>` 들 직후에 추가:

```html
  <script>
    // M8 anti-flash — localStorage 값이 있으면 페이지 파싱 직후 즉시 적용.
    (function () {
        var t = localStorage.getItem('gah_theme');
        if (t === 'light' || t === 'dark') {
            document.documentElement.setAttribute('data-theme', t);
        }
    })();
  </script>
  <script src="/static/js/theme.js" defer></script>
```

- [ ] **Step 9.5: `_nav.html` 헤더에 토글 버튼 추가**

`_nav.html` 의 `<div class="nav-notifications">` 안 `_header_project_dropdown` include 직후에 추가:

```html
    <button type="button"
            x-data="themeToggle()"
            x-init="init()"
            @click="cycle()"
            x-text="icon"
            :title="`${$el.dataset.tooltipPrefix || 'Theme'}: ${label}`"
            class="theme-toggle-btn"
            data-tooltip-prefix="{{ _('Theme') }}"
            aria-label="{{ _('Toggle theme') }}">
    </button>
```

(`data-tooltip-prefix` 는 i18n 라벨을 JS 에 전달하는 우회 — Jinja `_()` 는 서버사이드, Alpine 은 클라이언트사이드라 직접 호출 불가.)

- [ ] **Step 9.6: CSS `[data-theme]` 셀렉터 추가**

`src/gah/web/static/css/themes.css` (또는 main.css) 의 기존 `@media (prefers-color-scheme: dark) { ... }` 블록을 다음 패턴으로 조정:

```css
/* 라이트 변수 (default) */
:root {
    --bg: #fff;
    --fg: #111;
    /* ... 기존 라이트 변수들 */
}

/* M8 — data-theme="light" 강제 모드 (auto 가 아닐 때 미디어쿼리 무시) */
html[data-theme="light"] {
    --bg: #fff;
    --fg: #111;
    /* 라이트 변수 강제 — :root 와 동일 */
}

/* M8 — data-theme="dark" 강제 모드 */
html[data-theme="dark"] {
    --bg: #1a1a1a;
    --fg: #e0e0e0;
    /* 다크 변수 — 기존 @media 블록의 변수들을 여기로 복제 */
}

/* 기존 자동 모드 — data-theme 미설정 + 시스템 다크일 때만 */
@media (prefers-color-scheme: dark) {
    html:not([data-theme]) {
        --bg: #1a1a1a;
        --fg: #e0e0e0;
        /* 기존 변수들 그대로 — :not([data-theme]) 셀렉터만 추가 */
    }
}

/* 토글 버튼 스타일 */
.theme-toggle-btn {
    background: transparent;
    border: 1px solid var(--fg);
    color: var(--fg);
    border-radius: 4px;
    padding: 4px 8px;
    cursor: pointer;
    font-size: 1.1em;
}
.theme-toggle-btn:hover {
    background: var(--fg);
    color: var(--bg);
}
```

(정확한 변수명/값은 기존 CSS 따라 사용 — 구현 시 grep 으로 기존 다크 변수 추출 후 복제.)

- [ ] **Step 9.7: 회귀 + 마크업 테스트 통과**

Run: `pytest tests/test_dark_mode_markup.py -v`
Expected: 3 PASS.

Run: `pytest -q`
Expected: `1041 passed` (1038 + 3 신규).

- [ ] **Step 9.8: 수동 검증 (선택)**

`python -m gah --tray` → 브라우저 → 헤더 토글 클릭 사이클 → 페이지 새로고침 후 유지 확인. (자동 테스트가 충분히 커버 — 이 step 은 optional.)

- [ ] **Step 9.9: 커밋**

```bash
git add src/gah/web/static/js/theme.js src/gah/web/static/css/themes.css src/gah/web/static/css/main.css src/gah/web/templates/_nav.html src/gah/web/templates/base.html tests/test_dark_mode_markup.py
git commit -m "feat(m8): 다크모드 수동 토글 (헤더 ☀️/🌙/🌗 + localStorage + data-theme)"
```

---

## Task 10: autostart.py 본격 구현 (winreg get/set)

**목적**: Task 1 의 스켈레톤을 실제 winreg 호출로 채움. mock 기반 단위 테스트.

**Files:**
- Modify: `src/gah/platform/autostart.py`
- Create: `tests/test_autostart.py`

- [ ] **Step 10.1: 실패 테스트 먼저**

`tests/test_autostart.py` 신규:

```python
"""M8 — autostart.py winreg get/set 단위 테스트 (mock)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gah.platform import autostart


@pytest.fixture
def mock_winreg(monkeypatch):
    """winreg 모듈 자체를 MagicMock 으로 대체 (Windows 외 환경에서도 import 가능)."""
    mock = MagicMock()
    mock.HKEY_CURRENT_USER = "HKCU"
    mock.KEY_SET_VALUE = 2
    mock.REG_SZ = 1
    monkeypatch.setitem(sys.modules, "winreg", mock)
    monkeypatch.setattr(autostart.sys, "platform", "win32")
    return mock


def test_is_enabled_returns_true_when_key_exists(mock_winreg):
    mock_winreg.OpenKey.return_value.__enter__.return_value = MagicMock()
    mock_winreg.QueryValueEx.return_value = ("C:/path/exe --tray", 1)
    assert autostart.is_autostart_enabled() is True


def test_is_enabled_returns_false_when_key_missing(mock_winreg):
    mock_winreg.OpenKey.return_value.__enter__.return_value = MagicMock()
    mock_winreg.QueryValueEx.side_effect = FileNotFoundError()
    assert autostart.is_autostart_enabled() is False


def test_is_enabled_returns_false_on_non_windows(monkeypatch):
    monkeypatch.setattr(autostart.sys, "platform", "linux")
    assert autostart.is_autostart_enabled() is False


def test_set_enabled_writes_value(mock_winreg, tmp_path):
    key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = key
    exe = tmp_path / "GAH.exe"
    exe.write_bytes(b"\x00")  # exists
    autostart.set_autostart(True, exe_path=exe)
    mock_winreg.SetValueEx.assert_called_once()
    args = mock_winreg.SetValueEx.call_args[0]
    assert args[1] == "GameAssetHelper"  # value name
    assert str(exe) in args[4]  # 명령에 exe 경로 포함


def test_set_enabled_deletes_value_when_disabled(mock_winreg):
    key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = key
    autostart.set_autostart(False)
    mock_winreg.DeleteValue.assert_called_once_with(key, "GameAssetHelper")


def test_set_handles_missing_value_on_disable(mock_winreg):
    key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = key
    mock_winreg.DeleteValue.side_effect = FileNotFoundError()
    # 이미 없는 키 삭제 시도는 무시 (예외 안 던짐)
    autostart.set_autostart(False)


def test_set_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(autostart.sys, "platform", "darwin")
    autostart.set_autostart(True)  # 예외 없이 통과


def test_resolve_exe_command_uses_frozen_path(monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
    monkeypatch.setattr(autostart.sys, "executable", "C:/dist/GAH.exe")
    cmd = autostart._resolve_exe_command(None)
    assert "C:/dist/GAH.exe" in cmd
    assert "--tray" in cmd


def test_resolve_exe_command_uses_dev_pythonw(monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
    monkeypatch.setattr(autostart.sys, "executable", "C:/Python/python.exe")
    cmd = autostart._resolve_exe_command(None)
    assert "python" in cmd.lower()
    assert "-m gah" in cmd
    assert "--tray" in cmd
```

Run: `pytest tests/test_autostart.py -v`
Expected: 9 FAIL — `is_autostart_enabled` / `set_autostart` 스켈레톤만 있어 mock 호출 안 됨.

- [ ] **Step 10.2: `autostart.py` 본격 구현**

`src/gah/platform/autostart.py` 를 다음 내용으로 **완전 교체**:

```python
"""M8 — Windows 자동 시작 토글 (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run).

표준 사용자 권한으로 HKCU 에 쓰기 가능. GPO 차단 시 OSError 가 발생,
호출처 (settings router) 가 캐치해 사용자에게 표시.

비-Windows 에서는 모든 함수가 no-op / False 반환.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "GameAssetHelper"


def is_autostart_enabled() -> bool:
    """현재 HKCU\\...\\Run 에 GAH 키가 있는지."""
    if sys.platform != "win32":
        return False
    try:
        import winreg  # type: ignore[import-not-found]
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            try:
                value, _ = winreg.QueryValueEx(key, _VALUE_NAME)
                return bool(value)
            except FileNotFoundError:
                return False
    except OSError as e:
        log.warning("autostart 조회 실패: %s", e)
        return False


def set_autostart(enabled: bool, exe_path: Path | None = None) -> None:
    """`enabled=True` 면 키 등록, `False` 면 삭제. 비-Windows 는 no-op."""
    if sys.platform != "win32":
        log.info("autostart no-op on non-Windows (%s)", sys.platform)
        return
    import winreg  # type: ignore[import-not-found]
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE,
    ) as key:
        if enabled:
            target = _resolve_exe_command(exe_path)
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, target)
            log.info("autostart enabled: %s", target)
        else:
            try:
                winreg.DeleteValue(key, _VALUE_NAME)
                log.info("autostart disabled")
            except FileNotFoundError:
                log.debug("autostart 키 이미 없음 — no-op")


def _resolve_exe_command(exe_path: Path | None) -> str:
    """레지스트리에 넣을 실행 명령 문자열.

    우선순위:
      1. 인자 `exe_path` 가 명시되면 그 경로 + ' --tray'
      2. `sys.frozen` (PyInstaller 빌드) 이면 `sys.executable + " --tray"`
      3. dev 환경이면 `sys.executable + " -m gah --tray"` (pythonw 권장)
    """
    if exe_path is not None:
        return f'"{exe_path}" --tray'
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    return f'"{sys.executable}" -m gah --tray'
```

- [ ] **Step 10.3: 테스트 통과 확인**

Run: `pytest tests/test_autostart.py -v`
Expected: 9 PASS.

- [ ] **Step 10.4: 회귀 확인 + 커밋**

Run: `pytest -q`
Expected: `1050 passed, 1 skipped, 40 deselected` (1041 + 9 신규).

```bash
git add src/gah/platform/autostart.py tests/test_autostart.py
git commit -m "feat(m8): autostart.py 본격 구현 (winreg HKCU\\...\\Run get/set + mock 테스트 9건)"
```

---

## Task 11: 트레이 메뉴 통합 + /api/settings autostart 분기 검증

**목적**: 트레이 메뉴 우클릭에 "Start with Windows" 체크박스. `/api/settings` 의 autostart 분기가 실제로 set_autostart 를 호출하는지 통합 테스트로 고정.

**Files:**
- Modify: `src/gah/tray.py`

- [ ] **Step 11.1: tray.py 메뉴 항목 추가**

`src/gah/tray.py` 의 `make_tray_icon` 함수에서 QMenu 항목 추가하는 블록을 찾아, "메인 창 열기" 다음 + "종료" 전에 "자동 시작" 체크박스 추가:

```python
    from gah.platform.autostart import is_autostart_enabled, set_autostart

    autostart_action = menu.addAction("자동 시작 (Windows)")
    autostart_action.setCheckable(True)
    autostart_action.setChecked(is_autostart_enabled())

    def _toggle_autostart(checked: bool):
        try:
            set_autostart(checked)
        except OSError as e:
            log.warning("자동 시작 토글 실패: %s", e)
            autostart_action.setChecked(is_autostart_enabled())  # 롤백

    autostart_action.toggled.connect(_toggle_autostart)
```

(트레이 텍스트는 i18n 외 — 트레이는 Config.ui_language 부팅 시 한 번 결정. 단순화: 한국어 고정 또는 `_t("Start with Windows", cfg.ui_language)` 호출. 본 plan 은 단순 한국어 — Qt i18n 은 v2.)

- [ ] **Step 11.2: Task 8 의 `test_settings_post_updates_autostart` 가 이미 검증**

(Task 8 의 테스트가 `set_autostart` 호출을 monkeypatch 로 mock 해 검증 완료.)

추가 통합 테스트가 필요한 경우 `tests/test_settings_router.py` 에 1건 추가:

```python
def test_settings_post_autostart_failure_returns_500(client, web_deps, monkeypatch):
    from gah.platform import autostart as autostart_mod
    def _boom(enabled, exe_path=None):
        raise OSError("Permission denied")
    monkeypatch.setattr(autostart_mod, "set_autostart", _boom)
    r = client.post("/api/settings", json={"autostart": True})
    assert r.status_code == 500
    assert r.json()["ok"] is False
    assert "Permission denied" in r.json()["error"]
```

- [ ] **Step 11.3: 회귀 + 커밋**

Run: `pytest -q`
Expected: `1051 passed` (또는 1050 + 추가 통합 1건 = 1051).

```bash
git add src/gah/tray.py tests/test_settings_router.py
git commit -m "feat(m8): 트레이 메뉴에 자동 시작 체크박스 + 권한 거부 500 회귀 테스트"
```

---

## Task 12: scripts/generate_tray_ico.py + assets/tray.ico

**목적**: `tray.py` 의 `_build_app_icon()` 런타임 QPixmap 결과를 ICO 파일로 export 해 PyInstaller 빌드의 `--icon=` 에 사용.

**Files:**
- Create: `scripts/generate_tray_ico.py`
- Create: `assets/tray.ico`

- [ ] **Step 12.1: 헬퍼 스크립트 작성**

`scripts/generate_tray_ico.py` 신규:

```python
"""M8 — tray._build_app_icon() 결과 QPixmap 을 ICO 로 export.

PyInstaller 빌드 사전 1회 실행:
    python scripts/generate_tray_ico.py

산출: assets/tray.ico (멀티 사이즈 16/32/48/64/256).
이 ICO 는 gah.spec 의 EXE(icon=...) 에 참조된다.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

# PySide6 가 import 필요 — 빌드 환경에서만 실행 (런타임 빌드 절차).
from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gah.tray import _build_app_icon  # noqa: E402

SIZES = (16, 32, 48, 64, 256)


def main() -> None:
    app = QApplication.instance() or QApplication([])
    _ = app  # keep ref
    icon = _build_app_icon()

    out_dir = REPO_ROOT / "assets"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "tray.ico"

    # PySide6 의 QIcon.pixmap(size) 으로 각 크기 추출 후 ICO 로 저장.
    # Qt 가 .ico 멀티 사이즈 직접 저장 지원 — QImage 의 첫 sub-image 만 저장하는
    # 경우 PIL 폴백.
    try:
        from PIL import Image  # type: ignore[import-not-found]

        pil_images = []
        for s in SIZES:
            pm = icon.pixmap(QSize(s, s))
            img = pm.toImage().convertToFormat(QImage.Format_RGBA8888)
            buf = img.bits().tobytes()
            pil = Image.frombuffer("RGBA", (img.width(), img.height()),
                                   buf, "raw", "RGBA", 0, 1)
            pil_images.append(pil)
        pil_images[0].save(
            out_path,
            format="ICO",
            sizes=[(s, s) for s in SIZES],
            append_images=pil_images[1:],
        )
    except ImportError:
        # Pillow 없을 때 폴백 — 단일 256 사이즈만
        pm = icon.pixmap(QSize(256, 256))
        pm.save(str(out_path), "ICO")

    print(f"ICO written: {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 12.2: 스크립트 실행 + ICO 산출**

Run:
```powershell
python scripts/generate_tray_ico.py
```

Expected: `assets/tray.ico` 파일 생성 (수 KB).

- [ ] **Step 12.3: ICO 시각 확인 (수동)**

Windows 탐색기에서 `assets/tray.ico` 우클릭 → "속성" → 미리보기 확인. 또는 그냥 더블클릭으로 viewer 에서 확인.

- [ ] **Step 12.4: 커밋**

```bash
git add scripts/generate_tray_ico.py assets/tray.ico
git commit -m "feat(m8): generate_tray_ico.py 헬퍼 + assets/tray.ico (PyInstaller --icon 용)"
```

---

## Task 13: gah.spec + smoke 테스트 + .gitignore + README

**목적**: PyInstaller spec 파일 + smoke 테스트 + 빌드 절차 README.

**Files:**
- Create: `gah.spec`
- Modify: `.gitignore`
- Modify: `README.md`
- Create: `tests/test_pyinstaller_spec.py`

- [ ] **Step 13.1: `gah.spec` 작성**

저장소 루트에 `gah.spec` 신규:

```python
# -*- mode: python ; coding: utf-8 -*-
# M8 — PyInstaller 단일 exe spec.
#
# 빌드:
#   pybabel compile -d src/gah/web/locale
#   python scripts/generate_tray_ico.py
#   pyinstaller gah.spec
#
# 산출: dist/GameAssetHelper.exe (~1.5~2 GB, --onefile)
#
# 첫 실행 시:
#   - CLIP 모델 가중치 자동 다운로드 (%APPDATA%/GameAssetHelper/cache/clip/, ~600 MB)
#   - SingleInstance lock 후 트레이 + 브라우저 자동 열림

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

REPO = Path(SPECPATH)
SRC = REPO / "src" / "gah"

datas = [
    (str(SRC / "web" / "templates"), "gah/web/templates"),
    (str(SRC / "web" / "static"), "gah/web/static"),
    (str(SRC / "web" / "locale"), "gah/web/locale"),
]

# open_clip 의 모델 메타 (가중치는 첫 실행 시 다운로드)
datas += collect_data_files("open_clip", excludes=["*.pt"])

a = Analysis(
    ["src/gah/__main__.py"],
    pathex=[str(REPO / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "gah",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest", "pytest_asyncio", "playwright",
        "respx", "pytest_playwright", "pytest_mock",
        "matplotlib.tests", "numpy.tests", "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="GameAssetHelper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 압축은 venv 환경에서 false positive 안티바이러스 빈번
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # --noconsole
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/tray.ico",
)
```

- [ ] **Step 13.2: smoke 테스트 작성**

`tests/test_pyinstaller_spec.py` 신규:

```python
"""M8 — gah.spec 정합성 smoke (실 빌드는 수동)."""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_gah_spec_exists():
    assert (REPO_ROOT / "gah.spec").exists()


def test_gah_spec_parses_as_python():
    spec = (REPO_ROOT / "gah.spec").read_text(encoding="utf-8")
    ast.parse(spec)  # SyntaxError 면 fail


def test_gah_spec_references_existing_data_paths():
    """datas= 의 각 경로가 실재해야 PyInstaller 가 빌드 시작 가능."""
    spec = (REPO_ROOT / "gah.spec").read_text(encoding="utf-8")
    for p in (
        "src/gah/web/templates",
        "src/gah/web/static",
        "src/gah/web/locale",
        "src/gah/__main__.py",
        "assets/tray.ico",
    ):
        assert p in spec, f"spec 에 {p} 참조 누락"
        assert (REPO_ROOT / p).exists(), f"spec 이 참조하는 경로 부재: {p}"


def test_gah_spec_excludes_dev_deps():
    spec = (REPO_ROOT / "gah.spec").read_text(encoding="utf-8")
    for excluded in ("pytest", "playwright"):
        assert excluded in spec, f"excludes 에 {excluded} 누락"
```

Run: `pytest tests/test_pyinstaller_spec.py -v`
Expected: 4 PASS.

- [ ] **Step 13.3: `.gitignore` 업데이트**

`.gitignore` 끝에 추가 (이미 있으면 skip):

```
# M8 — PyInstaller 빌드 산출물
/build/
/dist/
*.spec.bak
```

(`*.mo` 는 의도적으로 커밋하므로 ignore 안 함.)

- [ ] **Step 13.4: README 빌드 가이드 섹션**

`README.md` 의 적절한 위치 (개발자 섹션 또는 별도 "배포" 섹션) 에 추가:

```markdown
## 배포 — 단일 exe 빌드 (M8)

일반 사용자에게 배포할 단일 `.exe` 를 만든다.

```powershell
# 1. dev 의존성 설치 (Babel, pyinstaller 포함)
pip install -e .[dev]

# 2. 번역 카탈로그 컴파일 (.po → .mo)
pybabel compile -d src/gah/web/locale

# 3. 트레이 아이콘 ICO 생성 (런타임 QPixmap → assets/tray.ico)
python scripts/generate_tray_ico.py

# 4. exe 빌드 (10분 내외, dist/GameAssetHelper.exe ≈ 1.5~2 GB)
pyinstaller gah.spec
```

빌드된 exe 는 단일 파일로 배포 가능. 첫 실행 시 CLIP 모델 가중치 (~600 MB) 가
`%APPDATA%\GameAssetHelper\cache\clip\` 로 자동 다운로드된다.

## 번역 추가 (M8)

신규 언어 추가 시:

```powershell
# 1. 소스에서 msgid 추출 (한 번)
pybabel extract -F babel.cfg -k _ -k _t -o src/gah/web/locale/messages.pot src/

# 2. 새 언어 카탈로그 생성 (예: 일본어)
pybabel init -i src/gah/web/locale/messages.pot -d src/gah/web/locale -l ja

# 3. messages.po 의 msgstr 채우기

# 4. 컴파일
pybabel compile -d src/gah/web/locale
```

추가로 `src/gah/web/locale_middleware.py` 의 `SUPPORTED` 튜플과
`src/gah/web/i18n.py` 의 `SUPPORTED_LOCALES` 에 새 언어 코드를 추가하고,
`Config` 의 `_VALID_UI_LANGUAGES` 도 확장.
```

- [ ] **Step 13.5: 회귀 + 커밋 (빌드는 수동 검증으로)**

Run: `pytest -q`
Expected: `1055 passed, 1 skipped, 40 deselected` (1051 + 4 신규).

```bash
git add gah.spec .gitignore README.md tests/test_pyinstaller_spec.py
git commit -m "feat(m8): gah.spec + smoke 4건 + .gitignore + README 빌드/번역 가이드"
```

- [ ] **Step 13.6: 수동 빌드 1회 (사용자 검증으로 옮길지 결정)**

PyInstaller 빌드는 10분 + ~2 GB 산출물이라 자동 테스트에 부적합. 수동 검증으로 옮긴다 — `milestones/M8_verification.md` 의 시나리오 1~3 에서 사용자가 직접 실행.

만약 본 plan 실행 중 빌드 검증을 원하면 별도 step:

```powershell
pybabel compile -d src/gah/web/locale
python scripts/generate_tray_ico.py
pyinstaller gah.spec
dist/GameAssetHelper.exe --version
```

→ "0.0.1" 출력 확인.

---

## Task 14: verification + 문서 마감

**목적**: M8_verification.md 작성, HANDOFF/CLAUDE.md/DESIGN.md 업데이트, 메모리 갱신, PR 본문 작성.

**Files:**
- Create: `milestones/M8_plan.md` (본 plan 의 todo 형식 사본)
- Create: `milestones/M8_todo.md`
- Create: `milestones/M8_verification.md`
- Modify: `HANDOFF.md`
- Modify: `CLAUDE.md`
- Modify: `DESIGN.md` (§11 Milestone 8 → 완료 표시)
- Modify: `C:\Users\v0o0v\.claude\projects\D--ClaudeCowork-game-asset-helper-game-asset-helper\memory\MEMORY.md` (M9 또는 v1-complete 메모리 추가)

- [ ] **Step 14.1: `milestones/M8_plan.md` 본 plan 의 todo 사본 작성**

CLAUDE.md §4.2 의 마일스톤 사이클은 `M{N}_plan.md` + `M{N}_todo.md` + `M{N}_verification.md` 3 세트를 요구. 본 plan (`docs/superpowers/plans/...`) 는 superpowers 형식이고, milestones/ 디렉터리의 plan/todo 는 CLAUDE.md 의 마일스톤 사이클 형식.

`milestones/M8_plan.md` 신규 — 본 plan 의 헤더 + Task 목록 요약 + spec 링크:

```markdown
# M8 — 패키징 + i18n (마일스톤 plan)

> 본 문서는 [`docs/superpowers/plans/2026-05-19-m8-packaging-and-i18n.md`](../docs/superpowers/plans/2026-05-19-m8-packaging-and-i18n.md) 의 마일스톤 사이클 표지다. 실제 구현 task 는 superpowers plan 참조.
>
> spec: [`docs/superpowers/specs/2026-05-19-m8-packaging-and-i18n-design.md`](../docs/superpowers/specs/2026-05-19-m8-packaging-and-i18n-design.md)

## 목표
- PyInstaller `--onefile` 빌드로 일반 사용자 배포 가능한 단일 `.exe`
- 웹 UI i18n (ko/en) — Babel gettext + LocaleMiddleware 5단계
- 다크/라이트 모드 수동 토글 (Alpine + localStorage + data-theme)
- Windows 자동 시작 토글 (winreg HKCU\\...\\Run)

## 산출물

| Phase | Task | 산출물 | 신규 테스트 |
|---|---|---|---:|
| 0 | 1 | Babel/pyinstaller 의존성, Config 신규 필드, autostart 스켈레톤 | +5 |
| 1 | 2~4 | `_t()` gettext + LocaleMiddleware + app.py 통합 | +14 |
| 2 | 5~7 | babel.cfg + 추출 + 한글→영어 msgid + ko/en .po/.mo | +2 |
| 3 | 8~9 | /settings 페이지 + 다크모드 토글 | +9 |
| 4 | 10~11 | autostart 본격 구현 + 트레이 메뉴 | +9~10 |
| 5 | 12~13 | tray.ico 헬퍼 + gah.spec + smoke + README | +4 |
| 6 | 14 | verification + 문서 | 0 |
| **합계** | | | **~44** |

## 완료 조건

- [ ] `pytest -q` ~1055 passed, 회귀 0
- [ ] `pyinstaller gah.spec` 빌드 성공 + `dist/GameAssetHelper.exe --version` 동작
- [ ] M8_verification.md 시나리오 1~10 통과
- [ ] PR 본문 작성 (한국어)
```

- [ ] **Step 14.2: `milestones/M8_todo.md` 작성**

본 plan 의 Task 1~14 를 체크박스 todo 로 정리:

```markdown
# M8 — TODO 체크리스트

> 본 todo 는 [`docs/superpowers/plans/2026-05-19-m8-packaging-and-i18n.md`](../docs/superpowers/plans/2026-05-19-m8-packaging-and-i18n.md) 의 phase 진행 상황을 마일스톤 사이클 형식으로 추적한다.

## Phase 0 — 스캐폴딩
- [ ] Task 1 — 의존성 + Config + locale 디렉터리 + autostart 스켈레톤

## Phase 1 — i18n 인프라
- [ ] Task 2 — `_t()` gettext 위임 + `_load_translations`
- [ ] Task 3 — LocaleMiddleware + ContextVar + Jinja2 통합
- [ ] Task 4 — app.py 통합

## Phase 2 — 문자열 추출 + 번역
- [ ] Task 5 — babel.cfg + 첫 추출 + base.html lang 동적
- [ ] Task 6 — 한글 msgid → 영어 msgid 일괄 변환
- [ ] Task 7 — ko.po + en.po 작성 + .mo 컴파일

## Phase 3 — 설정 페이지 + 다크모드
- [ ] Task 8 — /settings 페이지 + 라우터
- [ ] Task 9 — 다크모드 토글 (헤더 + theme.js + CSS data-theme)

## Phase 4 — 자동 시작
- [ ] Task 10 — autostart.py 본격 구현 (winreg)
- [ ] Task 11 — 트레이 메뉴 통합 + 통합 테스트

## Phase 5 — 빌드
- [ ] Task 12 — generate_tray_ico.py + assets/tray.ico
- [ ] Task 13 — gah.spec + smoke + .gitignore + README

## Phase 6 — 검증
- [ ] Task 14 — verification + HANDOFF/CLAUDE.md/DESIGN.md + 메모리 + PR
```

- [ ] **Step 14.3: `milestones/M8_verification.md` 작성**

수동 검증 시나리오 (spec §10 의 시나리오 1~10) 를 체크박스로:

```markdown
# M8 — 검증 결과

## 자동 검증

| 항목 | 결과 |
|---|---|
| `pytest -q` | ~1055 passed + 1 skipped + 40 deselected |
| `pytest -m mcp_integration -v` | 2/2 (MCP 20 도구 그대로) |
| `pytest -m e2e -v` | (M8 범위 외 — skip) |

## 수동 검증 시나리오

각 단계를 사용자가 실제 실행하며 결과를 ✅ / ❌ 로 표기.

### 1. PyInstaller 빌드 + 단일 exe 동작
- [ ] `pyinstaller gah.spec` 빌드 성공 (10분 내, 메모리 4GB+ 권장)
- [ ] `dist/GameAssetHelper.exe` 가 ~1.5~2 GB 크기로 산출
- [ ] `dist/GameAssetHelper.exe --version` → "0.0.1" 출력
- [ ] `dist/GameAssetHelper.exe --tray` → 트레이 등장 + 브라우저 자동 열림
- [ ] 첫 검색 시 CLIP 가중치 자동 다운로드 (~5분)

### 2. i18n 동작
- [ ] 브라우저 기본 (ko) → UI 한국어 표시
- [ ] `?lang=en` → UI 영어 전환
- [ ] `/settings` → 언어 라디오 "English" 선택 → 저장 → reload 후 영어 유지
- [ ] 쿠키 `gah_locale` 가 set 되어 있음 (브라우저 dev tools 로 확인)

### 3. 다크 모드 토글
- [ ] 헤더 ☀️/🌙/🌗 버튼 보임
- [ ] 클릭 사이클: auto → light → dark → auto
- [ ] 페이지 reload 후 토글 상태 유지 (localStorage)
- [ ] 시스템 다크 모드일 때 auto 모드가 시스템 따라감

### 4. 자동 시작
- [ ] `/settings` 토글 on → `regedit` `HKCU\\...\\Run\\GameAssetHelper` 값 존재 확인
- [ ] 토글 off → 값 삭제 확인
- [ ] 트레이 우클릭 → "자동 시작 (Windows)" 체크박스 동기 동작
- [ ] PC 재부팅 → 자동 시작 켠 상태라면 GAH 자동 실행

### 5. 기존 기능 회귀
- [ ] M5 — 라이브러리 / 검색 / 채택 정상 동작
- [ ] M6 — 시트 분석 / `suggest_animation_frames` 정상
- [ ] M7 — Unity Asset Store 스캔 / 임포트 / 프로젝트 페이지 정상

## 알려진 한계

- SmartScreen 경고: 서명 없는 빌드라 사용자가 "추가 정보 → 실행" 클릭 필요.
- exe 크기 ~1.5~2 GB: GitHub release 단일 파일 제한 (2 GB) 에 근접.
- WAL 잔존: SQLite WAL 파일이 `.exe` 종료 후 잔존 가능 — 다음 부팅 시 자동 정리.
- Qt 트레이 메뉴 i18n 은 한국어 고정 — Qt i18n (`.ts/.qm`) 은 v2.
```

- [ ] **Step 14.4: `HANDOFF.md` 갱신**

`HANDOFF.md` 의 핵심 헤더를 M8 완료로:

```markdown
**마지막 인계 시각**: 2026-05-XX (M8 완료)
**마지막 완료 마일스톤**: **M8 — 패키징 + i18n** — ✅ 완료
**현재 브랜치**: `feat/m8-packaging-and-i18n` (PR 대기)
**다음 작업**: M8 PR 머지 후 v1 release (v9 = v1 release 마일스톤 또는 그대로 v1 완료)
```

§2 의 테스트 표에 M8 phase 행 추가, §5 의 다음 세션 절차 갱신.

- [ ] **Step 14.5: `CLAUDE.md` 갱신**

§2 의 진행 현황 표에 M8 행 ✅ 완료로:

```markdown
| **M8 — 패키징 + i18n (1주)** | ✅ 완료 | PyInstaller --onefile + Babel gettext (ko/en) + 다크모드 토글 + autostart. 신규 의존성 2. ~44 신규 테스트 (총 ~1055). spec: ... plan: ... |
```

§8 의 "다음 작업" 섹션을 "v1 완료 — release" 로:

```markdown
## 8. 다음 작업 (v1 release 또는 v2 계획)

M8 가 ✅ 완료됐다 — v1 모든 마일스톤 종료. 다음 작업은 사용자 결정:

1. v1 release — GitHub release 페이지에 `GameAssetHelper.exe` 업로드
2. v2 계획 — `project_distribution_torch_strategy.md` + 미룸 항목 목록으로 brainstorming
```

- [ ] **Step 14.6: `DESIGN.md` §11 Milestone 8 → 완료 표시**

§11 의 "Milestone 8 — 패키징 + i18n + 풍부 UX 마감" 헤더에 "✅ 완료" 추가, 미룸 항목 (Pack/프로젝트 풍부 UX 등) 은 v2 로 명시 이동.

- [ ] **Step 14.7: 메모리 갱신**

`MEMORY.md` 에 신규 entry:

```markdown
- [M8 완료 — v1 모든 마일스톤 종료 (2026-05-XX)](project_m8_complete.md) — feat/m8 브랜치, ~1055 passed, PyInstaller exe + ko/en i18n + 다크모드 + autostart. v1 release 또는 v2 brainstorming
```

`project_m8_complete.md` 신규:

```markdown
---
name: M8 완료 — v1 모든 마일스톤 종료 (2026-05-XX)
description: feat/m8 브랜치, ~1055 passed, PyInstaller exe + ko/en i18n + 다크모드 + autostart. v1 release 다음 또는 v2 brainstorming
type: project
---
2026-05-XX M8 완료 시점.

## 직전 상태
- 브랜치: feat/m8-packaging-and-i18n (PR 대기)
- pytest: ~1055 passed + 1 skipped + 40 deselected
- MCP 도구: 20 (M7 그대로)
- 신규 의존성: Babel>=2.14 (런타임), pyinstaller>=6 (dev)
- 신규 테스트: ~44

## v2 또는 release 결정
사용자가 다음 결정:
1. v1 release (GitHub release + exe 업로드)
2. v2 brainstorming (Pack/프로젝트 풍부 UX, E2E, 추가 언어, 자동 동기화, 인스톨러, 코드 서명 등)

## stale 처리
- project_m8_starting_state.md → stale (M8 완료)
- project_m7_starting_state.md → 이미 stale
```

`project_m8_starting_state.md` 의 description 끝에 " — STALE (M8 완료, M8_complete 참조)" 추가.

- [ ] **Step 14.8: PR 본문 작성**

PR 본문 (`gh pr create --body` 입력용) 을 임시 파일로 작성:

```markdown
# M8 — 패키징 + i18n + 다크모드 토글 + Windows 자동 시작

## Summary
v1 의 최종 마일스톤. 일반 사용자 배포 가능한 단일 `.exe` 빌드 + 웹 UI 다국어 (ko/en) + 다크/라이트 모드 수동 토글 + Windows 자동 시작 토글.

## 핵심 결정 (8개)
- D1 — PyInstaller `--onefile` + `scripts/generate_tray_ico.py` (런타임 QPixmap → ICO)
- D2 — Babel `gettext` (`.po/.mo`, msgid 영어 자연 문장, `.mo` 커밋)
- D3 — `_t()` 본격화 (locale → ko → msgid 폴백 체인)
- D4 — `LocaleMiddleware` 5단계 결정 (URL > 쿠키 > Config > Accept-Language > ko)
- D5 — `Config.ui_language` / `ui_theme` 신규 (`autostart` 는 기존 활용)
- D6 — 다크모드 Alpine + `localStorage` + `data-theme` + anti-flash 인라인 스크립트
- D7 — winreg `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run` 자동 시작
- D8 — `/settings` 페이지 + `POST /api/settings`

## 산출물
- 신규 모듈: `platform/autostart.py`, `web/locale_middleware.py`, `web/routers/settings.py`
- 신규 자원: `gah.spec`, `babel.cfg`, `assets/tray.ico`, `scripts/generate_tray_ico.py`, `locale/{ko,en}/...`, `web/static/js/theme.js`
- 수정: `config.py`, `web/i18n.py`, `web/app.py`, `tray.py`, 모든 템플릿의 한글 msgid → 영어 msgid 변환
- 신규 의존성: `Babel>=2.14`, `pyinstaller>=6` (dev)

## 테스트
- `pytest -q` — ~1055 passed + 1 skipped + 40 deselected (회귀 0)
- `pytest -m mcp_integration -v` — 20 도구 그대로
- 수동 검증 시나리오 1~5 (`milestones/M8_verification.md`)

## 비목표 (v2)
- Pack/프로젝트 풍부 UX, Playwright E2E, 모바일 최적화, 추가 언어 (ja/zh), 인스톨러 (MSI/NSIS), 코드 서명, 자동 업데이트, 자동 동기화 스케줄러.

## Test plan
- [ ] `pyinstaller gah.spec` 빌드 → `dist/GameAssetHelper.exe` 생성
- [ ] `dist/GameAssetHelper.exe --version` → "0.0.1"
- [ ] `dist/GameAssetHelper.exe --tray` → 트레이 + 브라우저 자동 열림
- [ ] `?lang=en` → 영어 UI
- [ ] `/settings` 언어/테마/자동시작 모두 동작 + reload 후 유지
- [ ] 트레이 우클릭 "자동 시작" 체크박스 동기
- [ ] PC 재부팅 시 자동 실행 확인
- [ ] M5/M6/M7 기존 시나리오 회귀 없음

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 14.9: 회귀 + 최종 커밋 + PR (사용자 명시 시)**

Run: `pytest -q`
Expected: ~1055 passed.

Commit:
```bash
git add milestones/M8_plan.md milestones/M8_todo.md milestones/M8_verification.md HANDOFF.md CLAUDE.md DESIGN.md
git commit -m "docs(m8): verification + HANDOFF + CLAUDE.md + DESIGN.md §11 → ✅ 완료"
```

메모리 갱신은 별도 (Memory 도구 사용 — Write 로 파일 직접 작성).

PR 생성은 **사용자 명시 요청 시에만**:
```powershell
git push -u origin feat/m8-packaging-and-i18n
gh pr create --title "M8 — 패키징 + i18n" --body "$(cat <<'EOF'
... (위 본문)
EOF
)"
```

---

## 마무리

본 plan 의 모든 Task 가 끝나면:

- ✅ M8 완료
- ✅ v1 모든 마일스톤 종료
- ✅ `pytest -q` ~1055 passed
- ✅ 단일 `.exe` 배포 가능
- ✅ ko/en 양방향 i18n
- ✅ 다크/라이트 토글
- ✅ Windows 자동 시작 토글

다음은 사용자 결정 — GitHub release (v1.0.0) 또는 v2 계획.
