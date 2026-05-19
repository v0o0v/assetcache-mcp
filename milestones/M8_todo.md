# M8 — TODO 체크리스트

> 본 todo 는 [`docs/superpowers/plans/2026-05-19-m8-packaging-and-i18n.md`](../docs/superpowers/plans/2026-05-19-m8-packaging-and-i18n.md) 의 phase 진행 상황을 마일스톤 사이클 형식으로 추적.

## Phase 0 — 스캐폴딩

- [x] Task 1 — 의존성 + Config 신규 필드 (ui_language/ui_theme) + locale 디렉터리 + autostart 스켈레톤

## Phase 1 — i18n 인프라

- [x] Task 2 — `_t()` gettext 위임 + `_load_translations` (i18n.py 본격화)
- [x] Task 3 — LocaleMiddleware + ContextVar + Jinja2 `setup_jinja_i18n` 통합
- [x] Task 4 — app.py 통합 (startup 시 `_load_translations` 호출)

## Phase 2 — 문자열 추출 + 번역

- [x] Task 5 — babel.cfg + 첫 추출 + base.html lang 동적
- [x] Task 6 — 한글 msgid → 영어 msgid 일괄 변환 (159건 + fix 6건)
- [x] Task 7 — ko.po + en.po 작성 + .mo 컴파일

## Phase 3 — 설정 페이지 + 다크모드

- [x] Task 8 — /settings 페이지 + 라우터 (GET + POST /api/settings)
- [x] Task 9 — 다크모드 토글 (헤더 ☀️/🌙/🌗 + theme.js + CSS data-theme)

## Phase 4 — 자동 시작

- [x] Task 10 — autostart.py 본격 구현 (winreg HKCU\\...\\Run, is_enabled/enable/disable)
- [x] Task 11 — 트레이 메뉴 통합 + /api/autostart endpoint + 통합 테스트

## Phase 5 — 빌드

- [x] Task 12 — scripts/generate_tray_ico.py + assets/tray.ico (Pillow 4색 구체)
- [x] Task 13 — gah.spec (PyInstaller --onefile) + smoke 테스트 + .gitignore + README 빌드 안내

## Phase 6 — 검증

- [x] Task 14 — verification + HANDOFF/CLAUDE.md/DESIGN.md 갱신 + 메모리 갱신 + DRY 정리 (SUPPORTED 통합) + PR
