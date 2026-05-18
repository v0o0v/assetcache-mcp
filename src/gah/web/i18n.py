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
