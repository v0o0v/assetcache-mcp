# M10 — PyPI 배포 + AssetCacheMCP rename (마일스톤 plan)

> 본 문서는 [`docs/superpowers/plans/2026-05-19-m10-pypi-and-rename.md`](../docs/superpowers/plans/2026-05-19-m10-pypi-and-rename.md) 의 마일스톤 사이클 표지다. 실제 구현 task 는 superpowers plan 참조.
>
> spec: [`docs/superpowers/specs/2026-05-19-m10-pypi-and-rename-design.md`](../docs/superpowers/specs/2026-05-19-m10-pypi-and-rename-design.md)

## 목표

- **PyPI 1순위 배포** — `pipx install assetcache-mcp` / `uv tool install assetcache-mcp` cross-platform 흐름
- **앱 rename** — `Game Asset Helper` / `gah` → `AssetCacheMCP` / `assetcache-mcp` (PyPI) / `assetcache` (CLI) / `src/assetcache/`
- **v0.0.1 데이터 마이그레이션 helper** — `%APPDATA%\GameAssetHelper\` → `%APPDATA%\AssetCacheMCP\` 첫 부팅 자동 detect + 웹 GUI 배너 + asyncio runner + path rewrite
- **M9 cherry-pick** — `version.py` + `checker.py` (PyPI JSON API 전환) + `pip_command.py` + 단순화 banner + tray notification (downloader/installer/swap drop)
- **GitHub Actions PyPI publish workflow** — tag v\* push 시 자동 build + twine upload

## 산출물

| Phase | Task | 산출물 | 신규 테스트 |
|---|---|---|---:|
| 0 | 0.1~0.4 | rename mechanical (git mv + import 일괄 + APP_NAME + .po + 회귀 검증) | 0 |
| 1 | 1.1~1.7 | `core/migration.py` + `web/routers/migration.py` + `_migration_banner.html` + CLI `--migrate` + i18n msgid 5건 | +15 |
| 2 | 2.1~2.7 | `core/updater/` cherry-pick + PyPI JSON API + `pip_command.py` + 단순화 banner + tray notification + i18n msgid 4건 | +15 |
| 3 | 3.1~3.3 | README/CLAUDE/HANDOFF/DESIGN 갱신 + i18n catalog 정합성 + M10_verification.md | +5 |
| 4 | 4.1~4.6 | pyproject.toml 확정 + main_mcp() + python -m build + GitHub Actions workflow + TestPyPI + PyPI 정식 + v0.1.0 release | 0 |
| 5 | 5.1~5.2 | PR + main 머지 | 0 |
| **합계** | | **MCP 20 도구 그대로, 신규 의존성 0 런타임 + 1 dev (`respx`, M9 에서 이미)** | **+35 (1047 → ~1082)** |

## 완료 조건

- [ ] `pytest -q` ~1082 passed + 1 skipped + 40 deselected, 회귀 0
- [ ] `Grep "from gah\|import gah" src/ tests/` = 0 hits
- [ ] `python -m build` 성공, `dist/assetcache_mcp-0.1.0-py3-none-any.whl` 생성
- [ ] 별도 venv 에 `pip install dist/*.whl` 후 `assetcache --version` 0.1.0 출력
- [ ] TestPyPI 에서 `pipx install --index-url ...` 정상 설치 + 부팅
- [ ] PyPI 정식 업로드 + `pipx install assetcache-mcp` 일반 사용자 흐름 검증
- [ ] GitHub repo `v0o0v/assetcache-mcp` 린네임 + redirect 동작
- [ ] v0.1.0 GitHub release publish + release notes 마이그레이션 안내
- [ ] M10_verification.md 시나리오 7건 모두 수동 검증 통과

## 일정 추정

- ~6일 (Phase 0~4 + PR/머지)
- Phase 4 의 PyPI 정식 업로드 + GitHub repo 린네임은 사용자 수동

## 의존성

런타임 신규 0건. dev 신규 0건 (`respx` 는 M9 에서 이미). 빌드 도구 `build` + `twine` 은 dev 의존으로 명시.

## 브랜치

`feat/m10-pypi-and-rename` (spec commit `b5dd17f` 기준).

---

**2026-05-20 후기**: M10 Phase 1 의 v0.0.1 (GameAssetHelper) 데이터 폴더 마이그레이션 helper 는 v0.1.1 (`chore/v011-yagni-clean`) 에서 yagni-clean 됐다. v0.0.1 외부 사용자·다운로드 0 확인 후, 관련 코드 + 테스트 21건 + i18n msgid 3건 + 문서 안내 일괄 제거. 본 문서의 Phase 1 본문은 historical record 로 보존.
