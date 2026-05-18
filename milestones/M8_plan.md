# M8 — 패키징 + i18n (마일스톤 plan)

> 본 문서는 [`docs/superpowers/plans/2026-05-19-m8-packaging-and-i18n.md`](../docs/superpowers/plans/2026-05-19-m8-packaging-and-i18n.md) 의 마일스톤 사이클 표지다. 실제 구현 task 는 superpowers plan 참조.
>
> spec: [`docs/superpowers/specs/2026-05-19-m8-packaging-and-i18n-design.md`](../docs/superpowers/specs/2026-05-19-m8-packaging-and-i18n-design.md)

## 목표

- PyInstaller `--onefile` 빌드로 일반 사용자 배포 가능한 단일 `.exe`
- 웹 UI i18n (ko/en) — Babel gettext + LocaleMiddleware 5단계
- 다크/라이트 모드 수동 토글 (Alpine + localStorage + data-theme)
- Windows 자동 시작 토글 (winreg HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)

## 산출물

| Phase | Task | 산출물 | 신규 테스트 |
|---|---|---|---:|
| 0 | 1 | Babel/pyinstaller 의존성, Config 신규 필드, autostart 스켈레톤 | +5 |
| 1 | 2~4 | `_t()` gettext + LocaleMiddleware + app.py 통합 | +14 |
| 2 | 5~7 | babel.cfg + 추출 + 한글→영어 msgid + ko/en .po/.mo | +2 |
| 3 | 8~9 | /settings 페이지 + 다크모드 토글 | +9 |
| 4 | 10~11 | autostart 본격 구현 + 트레이 메뉴 | +9~10 |
| 5 | 12~13 | tray.ico 헬퍼 + gah.spec + smoke + README | +4 |
| 6 | 14 | verification + 문서 마감 + DRY 정리 | 0 |
| **합계** | | | **~44** |

## 완료 조건

- [x] `pytest -q` 1046 passed, 회귀 0
- [ ] `pyinstaller gah.spec` 빌드 성공 + `dist/GameAssetHelper.exe --version` 동작 (수동 검증)
- [ ] M8_verification.md 시나리오 1~10 통과 (수동 검증)
- [ ] PR 본문 작성 (한국어)

## 비목표 (v2)

- Pack/프로젝트 풍부 UX (메타 수정, manual_override, 프로젝트 pin/block, 사용 분포 차트)
- Playwright E2E 테스트
- 모바일/태블릿 최적화
- 추가 언어 (ja/zh)
- 인스톨러 (MSI/NSIS)
- 코드 서명
- 자동 업데이트
- 자동 동기화 스케줄러
- 트레이 알림
