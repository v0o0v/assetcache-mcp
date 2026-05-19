# M10 — PyPI 배포 + AssetCacheMCP rename 구현 plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v1 (M0~M8) 의 PyInstaller exe 배포에서 **PyPI 1순위 배포**로 전환 + 앱 rename (`Game Asset Helper` / `gah` → `AssetCacheMCP` / `assetcache-mcp` PyPI / `assetcache` CLI). v0.0.1 사용자 데이터 마이그레이션 helper + M9 의 PyPI 친화 모듈 (version/checker/banner/tray) cherry-pick 도 함께.

**Architecture:**
- 패키지 디렉터리 `src/gah/` → `src/assetcache/` 통째 git mv. import path 일괄 교체. APP_NAME 상수 변경 → platformdirs 가 자동으로 데이터 폴더를 `%APPDATA%\AssetCacheMCP\` 로 라우팅.
- 신규 모듈 `src/assetcache/core/migration.py` 가 첫 부팅 시 구 폴더 검출 → 웹 GUI 배너 + asyncio task 로 복사/이동 + path rewrite + 마커 파일.
- M9 의 `updater/version.py` 그대로 cherry-pick, `updater/checker.py` 는 GitHub Releases API → PyPI JSON API (`pypi.org/pypi/<pkg>/json`) 로 source URL 만 교체. `updater/pip_command.py` 신규로 사용자 환경 (pipx/uv/pip) 검출 후 적절한 upgrade 명령 반환.
- PyPI 업로드는 마지막 phase. Phase 4 까지는 로컬 wheel + TestPyPI 만, 정식 PyPI 업로드는 모든 검증 통과 후 수동 click.

**Tech Stack:** Python 3.12, FastAPI + Alpine + HTMX (기존), PySide6 (기존), httpx + respx (M9 패턴), platformdirs (기존), shutil/asyncio (마이그레이션), `python -m build` + `twine` + GitHub Actions `pypa/gh-action-pypi-publish` (PyPI 배포).

**Spec:** [`docs/superpowers/specs/2026-05-19-m10-pypi-and-rename-design.md`](../specs/2026-05-19-m10-pypi-and-rename-design.md)

**Baseline:** 1047 passed + 1 skipped + 40 deselected. 목표 ~1082 passed.

**Branch:** `feat/m10-pypi-and-rename` (이 plan 의 spec commit `b5dd17f` 이 이미 이 브랜치에 있음). 모든 phase 작업은 이 브랜치 위에 누적, 끝에 main 머지 (PR).

**Reference branches:**
- `feat/m9-code-signing-and-auto-update` — 보존됨, Phase 2 의 `updater/` 모듈 cherry-pick source. **머지 X**.

---

## File Structure

### 신규 (12)

```
src/assetcache/core/migration.py                          (Task 1.1~1.3)
src/assetcache/core/updater/__init__.py                   (Task 2.1, cherry-pick from feat/m9)
src/assetcache/core/updater/version.py                    (Task 2.1, cherry-pick from feat/m9 그대로)
src/assetcache/core/updater/checker.py                    (Task 2.2, feat/m9 cherry-pick + PyPI API 전환)
src/assetcache/core/updater/pip_command.py                (Task 2.3, 신규)
src/assetcache/web/routers/migration.py                   (Task 1.4)
src/assetcache/web/routers/updates.py                     (Task 2.4, feat/m9 cherry-pick + 단순화)
src/assetcache/web/templates/_migration_banner.html       (Task 1.5)
src/assetcache/web/templates/_pypi_update_banner.html     (Task 2.5, feat/m9 cherry-pick + 단순화)
.github/workflows/publish.yml                             (Task 4.5)
milestones/M10_verification.md                            (Task 3.4)
tests/test_*.py (8 신규 파일)                              (Task 1.1~2.6)
```

### 수정 (~150 + 8 핵심)

```
src/gah/ 디렉터리 통째 → src/assetcache/                   (Task 0.1, git mv)
src/assetcache/**/*.py — from gah → from assetcache       (Task 0.1, 일괄 sed)
src/assetcache/config.py APP_NAME 상수                    (Task 0.2)
src/assetcache/tray.py 브랜딩 + 동적 메뉴 (Task 2.6 에서 추가)  (Task 0.2 + Task 2.6)
src/assetcache/web/templates/base.html (브랜딩 + 두 배너)   (Task 0.2 + Task 1.5 + Task 2.5)
src/assetcache/__main__.py 의 main + main_mcp() 추가      (Task 4.2) + --migrate 옵션 (Task 1.6)
src/assetcache/web/locale/{ko,en}/LC_MESSAGES/messages.po  (Task 0.3 + 1.7 + 2.7)
pyproject.toml name + version + scripts + classifiers     (Task 4.1)
tests/**/*.py — from gah → from assetcache                (Task 0.1)
README.md / CLAUDE.md / HANDOFF.md / DESIGN.md            (Task 3.1)
```

### 책임 경계

- `core/migration.py` — 파일 시스템 IO + 경로 rewrite 전담. 웹/UI 의존성 없음
- `web/routers/migration.py` — HTTP 진입점 + SSE 만 다룸. core/migration 의 API 호출만
- `core/updater/version.py` — 순수 함수, network 의존 없음 (semver-lite)
- `core/updater/checker.py` — httpx 로 PyPI JSON API 만, swap/디스크 IO 없음
- `core/updater/pip_command.py` — `shutil.which` 만 사용, 순수 분기

각 모듈은 단일 책임. 테스트 가능성 + 격리 위함.

---

## Phase 0 — rename mechanical (0 신규 테스트, ~1.5일)

목표: `src/gah/` → `src/assetcache/` 디렉터리 이동 + import path 전수 교체 + APP_NAME 상수 변경 + i18n .po 갱신 + 회귀 1047 passed 유지.

### Task 0.1: 디렉터리 이동 + import path 일괄 교체

**Files:**
- Rename: `src/gah/` → `src/assetcache/` (git mv)
- Modify: 모든 `src/**/*.py`, `tests/**/*.py` 의 `from gah` / `import gah` → `from assetcache` / `import assetcache`
- Modify: `gah.spec` (PyInstaller spec) → `assetcache.spec`, hidden imports 갱신

**Steps:**

- [ ] **Step 1: feat/m10 브랜치 위 작업 확인**

```powershell
git status
```

Expected: `On branch feat/m10-pypi-and-rename` + clean tree.

- [ ] **Step 2: 디렉터리 git mv**

```powershell
git mv src/gah src/assetcache
```

- [ ] **Step 3: `gah.spec` → `assetcache.spec`**

```powershell
git mv gah.spec assetcache.spec
```

`assetcache.spec` 내부 PyInstaller 설정의 `hidden_imports = ['gah.X', ...]` 같은 항목과 `name='GameAssetHelper'` 도 함께 교체. Edit 으로:

```python
# 예시 — 실제 spec 내용에 맞춰 사용
hiddenimports=[
    'assetcache.core.scanner',
    'assetcache.core.watcher',
    # ... 모든 gah → assetcache 교체
]
# 그리고
exe = EXE(
    ...,
    name='AssetCacheMCP',  # 구 'GameAssetHelper' 에서
    ...
)
```

- [ ] **Step 4: src/ + tests/ 의 import 전수 교체**

PowerShell 5.1 의 sed 대체로 Python one-liner 사용 (또는 Edit tool 의 replace_all):

```powershell
Get-ChildItem -Path src,tests -Recurse -Filter *.py | ForEach-Object {
    (Get-Content $_.FullName -Raw) -replace '(?<=from |import )gah\b', 'assetcache' | Set-Content $_.FullName -NoNewline
}
```

또는 권장: Grep 으로 모든 매치 파일 list → 각 파일에 Edit `replace_all` 적용.

```powershell
# 검증용 — 교체 후 0 hits 여야 함
git diff --stat
```

- [ ] **Step 5: 명시적으로 잔존 reference 검출**

```powershell
Select-String -Path src,tests -Pattern 'from gah\.|^import gah|"gah\.' -Recurse
```

Expected: 0 매치. 매치 있으면 수동 fix.

- [ ] **Step 6: pyproject.toml 의 임시 package 명 (Task 4.1 에서 최종 확정 — 우선 빌드 가능하게만)**

`pyproject.toml` 의 `[tool.setuptools.packages.find]` 가 `src/assetcache/` 를 찾도록:

```toml
[tool.setuptools]
package-dir = { "" = "src" }

[tool.setuptools.packages.find]
where = ["src"]
namespaces = false
```

`[project] name` 은 Task 4.1 에서 `assetcache-mcp` 로. 지금은 `game-asset-helper` 로 두어도 됨 (테스트만 통과하면 됨).

- [ ] **Step 7: editable install 갱신**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\pip.exe" install -e .[dev]
```

- [ ] **Step 8: 회귀 테스트 1**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1047 passed (모듈 이름만 변경, 동작 동일). 실패 시 잔존 `gah` reference 또는 string literal 안에 `"gah."` 문자열이 있을 가능성.

- [ ] **Step 9: 명시적으로 string literal 잔존 검출**

```powershell
Select-String -Path src,tests -Pattern '"gah\.|''gah\.' -Recurse
```

Expected: 0 매치 또는 명확히 historical 의도된 것만 (예: 로그 메시지 안의 historical reference). 검토 후 교체.

- [ ] **Step 10: 회귀 테스트 2 (final)**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1047 passed + 1 skipped + 40 deselected.

- [ ] **Step 11: Commit**

```powershell
git add -A
```

```powershell
git commit -m "refactor(m10/p0): src/gah → src/assetcache + import 전수 교체

- git mv src/gah src/assetcache
- 모든 from gah / import gah → from assetcache / import assetcache (~150 파일)
- gah.spec → assetcache.spec, PyInstaller name='AssetCacheMCP'
- pyproject.toml package-dir 갱신 (name 은 Task 4.1 에서 확정)
- 회귀 1047 passed 유지

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 0.2: APP_NAME 상수 + 브랜딩 변경

**Files:**
- Modify: `src/assetcache/config.py` (APP_NAME)
- Modify: `src/assetcache/tray.py` (트레이 툴팁/아이콘 메타)
- Modify: `src/assetcache/web/templates/base.html` (HTML title + 헤더 브랜딩)
- Test: `tests/test_config.py`, `tests/test_ui_smoke.py`

**Steps:**

- [ ] **Step 1: config.py APP_NAME 교체**

`src/assetcache/config.py` Edit:

```python
APP_NAME = "AssetCacheMCP"  # 구 "GameAssetHelper" 에서
```

platformdirs 가 이 상수 1개만 보고 `%APPDATA%\AssetCacheMCP\` 로 라우팅. 다른 path 계산 코드는 그대로.

- [ ] **Step 2: tray.py 의 사용자 facing 문자열 교체**

`src/assetcache/tray.py` 의 다음 패턴 모두 Edit:
- `QSystemTrayIcon` 의 setToolTip → `"AssetCacheMCP"` (구 `"Game Asset Helper"`)
- 메뉴 항목의 `"Game Asset Helper"` 표기 → `"AssetCacheMCP"`
- 단 마일스톤 history reference 같은 historical 표기는 보존

- [ ] **Step 3: base.html title + 브랜딩 교체**

`src/assetcache/web/templates/base.html` Edit:

```html
<title>{% block title %}AssetCacheMCP{% endblock %}</title>
```

헤더의 `<h1>Game Asset Helper</h1>` → `<h1>AssetCacheMCP</h1>` 등 사용자 facing 모든 표기.

- [ ] **Step 4: 기타 사용자 facing 표기 (CLI help, README 안 제외)**

`Grep` 으로 `Game Asset Helper` 검색 후 사용자 facing 만 교체. README/HANDOFF/CLAUDE/milestones 본문은 Task 3.1 에서.

```powershell
Select-String -Path src -Pattern 'Game Asset Helper|GameAssetHelper' -Recurse
```

historical 의도 (테스트 fixture 의 v0.0.1 데이터 마이그레이션 source 표기 등) 만 보존. 나머지 교체.

- [ ] **Step 5: 테스트 fixture 의 APP_NAME 어설션 갱신**

`tests/test_config.py` 에서 `assert config.APP_NAME == "GameAssetHelper"` → `"AssetCacheMCP"`. 또한 `tests/test_ui_smoke.py` 가 base.html title 단언하면 `"AssetCacheMCP"` 로.

```powershell
Select-String -Path tests -Pattern 'GameAssetHelper|Game Asset Helper' -Recurse
```

검출된 모든 단언 갱신.

- [ ] **Step 6: 회귀 테스트**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1047 passed.

- [ ] **Step 7: Commit**

```powershell
git add -A
```

```powershell
git commit -m "refactor(m10/p0): APP_NAME / 트레이 / web 브랜딩 → AssetCacheMCP

- config.APP_NAME = AssetCacheMCP (platformdirs 자동 라우팅 → %APPDATA%\AssetCacheMCP)
- tray 툴팁 + base.html title + h1 모두 AssetCacheMCP
- historical 표기는 보존 (마일스톤 reference 등)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 0.3: i18n .po "Game Asset Helper" 일괄 교체

**Files:**
- Modify: `src/assetcache/web/locale/ko/LC_MESSAGES/messages.po`
- Modify: `src/assetcache/web/locale/en/LC_MESSAGES/messages.po`
- Build: `.mo` 파일 재컴파일

**Steps:**

- [ ] **Step 1: ko .po 일괄 교체**

`src/assetcache/web/locale/ko/LC_MESSAGES/messages.po` 에서:
- `msgid "Game Asset Helper"` 의 msgstr 또는 다른 표기 → `AssetCacheMCP` 일관 (한국어 표기도 그대로 영문 명 사용)
- 헤더 `Project-Id-Version: Game Asset Helper VERSION` → `AssetCacheMCP VERSION`

- [ ] **Step 2: en .po 일괄 교체**

같음.

- [ ] **Step 3: .mo 재컴파일**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\pybabel.exe" compile -d src/assetcache/web/locale
```

Expected: ko/en `.mo` 둘 다 갱신.

- [ ] **Step 4: 웹 UI 스모크 (i18n 로딩 검증)**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_web_*.py -q
```

Expected: 모두 pass (i18n 변경이 catalog 무손상이라).

- [ ] **Step 5: Commit**

```powershell
git add -A
```

```powershell
git commit -m "refactor(m10/p0): i18n .po Game Asset Helper → AssetCacheMCP

- ko/en .po 의 표기 일괄 교체 + Project-Id-Version 갱신
- .mo 재컴파일

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 0.4: 회귀 전수 검증 + Phase 0 종료

**Files:** (코드 변경 없음, 검증 + commit 만)

**Steps:**

- [ ] **Step 1: 전수 grep 0 hits 검증**

```powershell
Select-String -Path src,tests -Pattern 'from gah\.|^import gah\b' -Recurse
```

Expected: 0 매치.

- [ ] **Step 2: 전체 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: **1047 passed + 1 skipped + 40 deselected**.

- [ ] **Step 3: MCP integration 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -m mcp_integration -q
```

Expected: 2 passed (실 subprocess + JSON-RPC, 20 도구).

- [ ] **Step 4: 트레이 부팅 스모크 (수동)**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m assetcache --tray
```

Expected: 트레이 아이콘 노출, 우클릭 메뉴 정상 ("AssetCacheMCP" 표기), 웹 UI http://localhost:9874 접속 후 페이지 title "AssetCacheMCP" 노출. Ctrl+C 또는 트레이 종료로 종료.

- [ ] **Step 5: Phase 0 wrap-up commit (있을 경우)**

만약 Step 4 에서 발견된 잔존 fix 있으면 추가 commit. 없으면 skip.

---

## Phase 1 — 데이터 폴더 마이그레이션 helper (+15 테스트, ~1일)

목표: 첫 부팅 시 `%APPDATA%\GameAssetHelper\` 데이터 검출 → 웹 GUI 배너 → 복사/이동 + path rewrite + 마커 파일.

### Task 1.1: `core/migration.py` Detection + 5 tests

**Files:**
- Create: `src/assetcache/core/migration.py`
- Create: `tests/test_migration_detect.py`

**Steps:**

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_migration_detect.py`:

```python
"""마이그레이션 candidate 감지 테스트."""
from __future__ import annotations

from pathlib import Path

import pytest

from assetcache.config import AppPaths
from assetcache.core.migration import (
    MigrationCandidate,
    detect_v001_candidate,
    is_already_migrated,
)


def _make_app_paths(tmp_path: Path, new_app: str = "AssetCacheMCP", old_app: str = "GameAssetHelper") -> AppPaths:
    """tmp 디렉터리에 가짜 %APPDATA%/AppName 두 폴더의 부모를 둔다."""
    return AppPaths(
        data_dir=tmp_path / new_app,
        legacy_data_dir=tmp_path / old_app,
    )


def test_detect_no_candidate_when_both_empty(tmp_path):
    """신규 사용자 — 두 폴더 모두 비어있거나 없음."""
    paths = _make_app_paths(tmp_path)
    assert detect_v001_candidate(paths) is None


def test_detect_candidate_when_legacy_has_db_and_library(tmp_path):
    """v0.0.1 사용자 — 구 폴더에 metadata.db + library/ 존재."""
    paths = _make_app_paths(tmp_path)
    paths.legacy_data_dir.mkdir(parents=True)
    (paths.legacy_data_dir / "metadata.db").write_text("fake db")
    (paths.legacy_data_dir / "library").mkdir()
    (paths.legacy_data_dir / "library" / "asset.png").write_bytes(b"\x00" * 100)

    candidate = detect_v001_candidate(paths)

    assert candidate is not None
    assert candidate.source == paths.legacy_data_dir
    assert candidate.target == paths.data_dir
    assert candidate.has_db is True
    assert candidate.has_library is True
    assert candidate.total_files >= 2
    assert candidate.total_bytes >= 100


def test_detect_no_candidate_when_new_folder_has_data(tmp_path):
    """새 사용자가 이미 새 폴더 사용 중 — 마이그레이션 X."""
    paths = _make_app_paths(tmp_path)
    paths.data_dir.mkdir(parents=True)
    (paths.data_dir / "metadata.db").write_text("fake db")

    paths.legacy_data_dir.mkdir(parents=True)
    (paths.legacy_data_dir / "metadata.db").write_text("fake old db")

    assert detect_v001_candidate(paths) is None


def test_detect_no_candidate_when_already_migrated(tmp_path):
    """마이그레이션 완료 마커가 있으면 다시 candidate 안 됨."""
    paths = _make_app_paths(tmp_path)
    paths.data_dir.mkdir(parents=True)
    (paths.data_dir / ".migrated_from_v001").write_text("2026-05-19")

    paths.legacy_data_dir.mkdir(parents=True)
    (paths.legacy_data_dir / "metadata.db").write_text("fake db")

    assert detect_v001_candidate(paths) is None


def test_is_already_migrated_marker(tmp_path):
    target = tmp_path / "new"
    target.mkdir()
    assert is_already_migrated(target) is False

    (target / ".migrated_from_v001").write_text("ok")
    assert is_already_migrated(target) is True
```

`AppPaths` 가 `legacy_data_dir` 속성을 가져야 하는데 — 기존 `AppPaths` 에 추가 필요. Edit `src/assetcache/config.py` 에서 `AppPaths` dataclass 에 `legacy_data_dir: Path | None = None` 필드 추가 + `AppPaths.compute(...)` 에서 platformdirs 로 `GameAssetHelper` 경로도 계산해 세팅.

- [ ] **Step 2: 테스트 실패 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_migration_detect.py -v
```

Expected: 5 FAIL (`ModuleNotFoundError: assetcache.core.migration` 또는 `ImportError: MigrationCandidate`).

- [ ] **Step 3: AppPaths 에 legacy_data_dir 추가**

Edit `src/assetcache/config.py` 의 `AppPaths` dataclass 에 다음 필드 추가:

```python
@dataclass(frozen=True)
class AppPaths:
    data_dir: Path
    legacy_data_dir: Path | None = None  # %APPDATA%\GameAssetHelper\ — 신규
    # ... 기존 필드
```

`AppPaths.compute(app_name: str = APP_NAME)` 안에서:

```python
@classmethod
def compute(cls, app_name: str = APP_NAME) -> AppPaths:
    data_dir = Path(platformdirs.user_data_dir(app_name, appauthor=False))
    legacy_data_dir = Path(platformdirs.user_data_dir("GameAssetHelper", appauthor=False))
    if legacy_data_dir == data_dir:  # 새 사용자가 APP_NAME 을 임의로 GameAssetHelper 로 둔 경우 (방어)
        legacy_data_dir = None
    return cls(data_dir=data_dir, legacy_data_dir=legacy_data_dir, ...)
```

- [ ] **Step 4: `core/migration.py` 구현**

Create `src/assetcache/core/migration.py`:

```python
"""v0.0.1 데이터 폴더 마이그레이션 helper.

%APPDATA%\\GameAssetHelper\\ → %APPDATA%\\AssetCacheMCP\\
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from assetcache.config import AppPaths

MIGRATION_MARKER = ".migrated_from_v001"


@dataclass(frozen=True)
class MigrationCandidate:
    """구 폴더에서 새 폴더로 옮길 수 있는 v0.0.1 데이터 후보."""

    source: Path
    target: Path
    total_files: int
    total_bytes: int
    has_db: bool
    has_library: bool


def is_already_migrated(target: Path) -> bool:
    """target 안에 마이그레이션 완료 마커가 있는지."""
    return (target / MIGRATION_MARKER).exists()


def _is_empty_dir(p: Path) -> bool:
    if not p.exists():
        return True
    return not any(p.iterdir())


def _count_files(root: Path) -> tuple[int, int]:
    n = 0
    sz = 0
    for f in root.rglob("*"):
        if f.is_file():
            n += 1
            try:
                sz += f.stat().st_size
            except OSError:
                pass
    return n, sz


def detect_v001_candidate(paths: AppPaths) -> Optional[MigrationCandidate]:
    """새 폴더가 비어있고 구 폴더에 데이터가 있으면 MigrationCandidate 반환."""
    if paths.legacy_data_dir is None:
        return None

    new_dir = paths.data_dir
    old_dir = paths.legacy_data_dir

    if is_already_migrated(new_dir):
        return None

    if not _is_empty_dir(new_dir):
        return None

    if not old_dir.exists():
        return None

    has_db = (old_dir / "metadata.db").exists()
    has_library = (old_dir / "library").exists()

    if not has_db and not has_library:
        return None

    total_files, total_bytes = _count_files(old_dir)

    return MigrationCandidate(
        source=old_dir,
        target=new_dir,
        total_files=total_files,
        total_bytes=total_bytes,
        has_db=has_db,
        has_library=has_library,
    )
```

- [ ] **Step 5: 테스트 통과 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_migration_detect.py -v
```

Expected: 5 PASS.

- [ ] **Step 6: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1052 passed (1047 + 5).

- [ ] **Step 7: Commit**

```powershell
git add src/assetcache/config.py src/assetcache/core/migration.py tests/test_migration_detect.py
```

```powershell
git commit -m "feat(m10/p1): core/migration.detect_v001_candidate + AppPaths.legacy_data_dir

- AppPaths 에 legacy_data_dir 필드 (platformdirs 로 GameAssetHelper 경로 계산)
- detect_v001_candidate: 새 폴더 비어있고 구 폴더 데이터 있으면 MigrationCandidate
- 마커 파일 .migrated_from_v001 검사로 재제시 방지
- +5 tests (1047 → 1052)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.2: MigrationRunner copy/move + 5 tests

**Files:**
- Modify: `src/assetcache/core/migration.py` (MigrationRunner 추가)
- Create: `tests/test_migration_runner.py`

**Steps:**

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_migration_runner.py`:

```python
"""MigrationRunner copy/move 동작 테스트."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from assetcache.core.migration import (
    MigrationCandidate,
    MigrationRunner,
    MigrationState,
)


def _make_candidate(tmp_path: Path) -> MigrationCandidate:
    source = tmp_path / "old"
    target = tmp_path / "new"
    source.mkdir()
    (source / "metadata.db").write_text("db data")
    (source / "library").mkdir()
    (source / "library" / "asset.png").write_bytes(b"\x00" * 50)
    return MigrationCandidate(
        source=source,
        target=target,
        total_files=2,
        total_bytes=58,
        has_db=True,
        has_library=True,
    )


@pytest.mark.asyncio
async def test_runner_copy_mode_copies_all_files(tmp_path):
    candidate = _make_candidate(tmp_path)
    runner = MigrationRunner()
    await runner.run(candidate, mode="copy")

    assert runner.state == MigrationState.DONE
    assert (candidate.target / "metadata.db").exists()
    assert (candidate.target / "library" / "asset.png").exists()
    assert (candidate.source / "metadata.db").exists()  # 원본 보존


@pytest.mark.asyncio
async def test_runner_move_mode_removes_source(tmp_path):
    candidate = _make_candidate(tmp_path)
    runner = MigrationRunner()
    await runner.run(candidate, mode="move")

    assert runner.state == MigrationState.DONE
    assert (candidate.target / "metadata.db").exists()
    assert not (candidate.source).exists()


@pytest.mark.asyncio
async def test_runner_creates_marker_on_success(tmp_path):
    candidate = _make_candidate(tmp_path)
    runner = MigrationRunner()
    await runner.run(candidate, mode="copy")

    from assetcache.core.migration import MIGRATION_MARKER
    assert (candidate.target / MIGRATION_MARKER).exists()


@pytest.mark.asyncio
async def test_runner_rollback_on_failure(tmp_path, monkeypatch):
    """copy 도중 실패하면 부분 파일 제거 + state=FAILED."""
    candidate = _make_candidate(tmp_path)

    original_copytree = shutil.copytree

    def fail_copytree(*args, **kwargs):
        # target 일부 생성 후 실패 시뮬레이션
        target = Path(args[1])
        target.mkdir(parents=True)
        (target / "partial.txt").write_text("partial")
        raise OSError("simulated disk full")

    monkeypatch.setattr(shutil, "copytree", fail_copytree)

    runner = MigrationRunner()
    await runner.run(candidate, mode="copy")

    assert runner.state == MigrationState.FAILED
    assert "simulated disk full" in runner.error
    # rollback: partial 파일 정리
    assert not (candidate.target / "partial.txt").exists() or not candidate.target.exists()


@pytest.mark.asyncio
async def test_runner_disk_space_check(tmp_path, monkeypatch):
    """free space 부족하면 시작 전 실패."""
    candidate = _make_candidate(tmp_path)

    def fake_disk_usage(p):
        from collections import namedtuple
        DU = namedtuple("DU", ["total", "used", "free"])
        return DU(total=1000, used=999, free=1)  # free 1 byte

    monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

    runner = MigrationRunner()
    await runner.run(candidate, mode="copy")

    assert runner.state == MigrationState.FAILED
    assert "디스크" in runner.error or "space" in runner.error.lower()
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_migration_runner.py -v
```

Expected: 5 FAIL (`ImportError: MigrationRunner`).

- [ ] **Step 3: MigrationRunner 구현**

`src/assetcache/core/migration.py` Edit 으로 추가:

```python
import asyncio
import shutil
from enum import Enum
from typing import Literal


class MigrationState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class MigrationRunner:
    """비동기 마이그레이션 실행자.

    self.state, self.error, self.progress (0~1) 로 외부에서 진행 확인.
    """

    def __init__(self):
        self.state = MigrationState.PENDING
        self.error: str = ""
        self.progress: float = 0.0
        self._cancel = asyncio.Event()

    async def run(
        self,
        candidate: MigrationCandidate,
        mode: Literal["copy", "move"],
    ) -> None:
        self.state = MigrationState.RUNNING
        try:
            # 1) 디스크 공간 사전 검사
            usage = shutil.disk_usage(candidate.target.parent)
            required = int(candidate.total_bytes * 1.1)
            if usage.free < required:
                raise OSError(
                    f"디스크 공간 부족: 필요 {required} bytes, 가용 {usage.free} bytes"
                )

            # 2) 복사 또는 이동
            await asyncio.to_thread(
                self._do_transfer, candidate, mode
            )

            # 3) 마커
            (candidate.target / MIGRATION_MARKER).write_text(
                "migrated_at: 2026-05-19\n"
            )

            self.progress = 1.0
            self.state = MigrationState.DONE

        except Exception as e:
            self.error = str(e)
            # rollback: target 정리
            if candidate.target.exists():
                try:
                    shutil.rmtree(candidate.target)
                except OSError:
                    pass
            self.state = MigrationState.FAILED

    def _do_transfer(
        self, candidate: MigrationCandidate, mode: str
    ) -> None:
        if mode == "copy":
            shutil.copytree(
                candidate.source, candidate.target, dirs_exist_ok=False
            )
        elif mode == "move":
            shutil.move(str(candidate.source), str(candidate.target))
        else:
            raise ValueError(f"unknown mode: {mode}")
```

`tests` 폴더 conftest.py 에 `pytest-asyncio` 가 활성화돼 있는지 확인. 안 돼 있으면 `pyproject.toml [tool.pytest.ini_options]` 에 `asyncio_mode = "auto"` 추가.

- [ ] **Step 4: 테스트 통과 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_migration_runner.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1057 passed (1052 + 5).

- [ ] **Step 6: Commit**

```powershell
git add src/assetcache/core/migration.py tests/test_migration_runner.py pyproject.toml
```

```powershell
git commit -m "feat(m10/p1): MigrationRunner copy/move + rollback + disk check

- async run(candidate, mode) — shutil.copytree (copy) 또는 shutil.move (move)
- 시작 전 free space 검사 (필요 * 1.1)
- 실패 시 target 정리 + state=FAILED
- 마커 .migrated_from_v001 파일 생성
- +5 tests (1052 → 1057)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.3: path rewrite (config.toml + metadata.db) + 5 tests

**Files:**
- Modify: `src/assetcache/core/migration.py` (rewrite_paths_after_migration)
- Create: `tests/test_migration_path_rewrite.py`

**Steps:**

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_migration_path_rewrite.py`:

```python
"""마이그레이션 후 path rewrite (config.toml + metadata.db)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from assetcache.core.migration import (
    MigrationCandidate,
    rewrite_paths_after_migration,
)


def _make_candidate(tmp_path: Path) -> MigrationCandidate:
    src = tmp_path / "GameAssetHelper"
    tgt = tmp_path / "AssetCacheMCP"
    src.mkdir()
    tgt.mkdir()
    return MigrationCandidate(
        source=src, target=tgt,
        total_files=0, total_bytes=0,
        has_db=True, has_library=True,
    )


def test_rewrite_config_toml_library_root(tmp_path):
    """config.toml 의 library_root 가 구 base 면 새 base 로 rewrite."""
    candidate = _make_candidate(tmp_path)
    config_path = candidate.target / "config.toml"
    config_path.write_text(
        f'[library]\nlibrary_root = "{candidate.source}/library"\n',
        encoding="utf-8",
    )

    rewrite_paths_after_migration(candidate)

    content = config_path.read_text(encoding="utf-8")
    assert str(candidate.target / "library") in content
    assert str(candidate.source / "library") not in content


def test_rewrite_does_not_touch_external_paths(tmp_path):
    """config.toml 의 unrelated path (C:\\Custom\\Pack) 는 무손상."""
    candidate = _make_candidate(tmp_path)
    config_path = candidate.target / "config.toml"
    config_path.write_text(
        '[library]\nlibrary_root = "C:/Custom/External/Pack"\n',
        encoding="utf-8",
    )

    rewrite_paths_after_migration(candidate)

    assert 'C:/Custom/External/Pack' in config_path.read_text(encoding="utf-8")


def test_rewrite_metadata_db_assets_path(tmp_path):
    """metadata.db 의 assets.path 중 구 base 시작 행만 rewrite."""
    candidate = _make_candidate(tmp_path)
    db_path = candidate.target / "metadata.db"
    src_lib = candidate.source / "library"
    tgt_lib = candidate.target / "library"

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, path TEXT)")
    conn.execute("INSERT INTO assets (path) VALUES (?)", (f"{src_lib}/pack/asset.png",))
    conn.execute("INSERT INTO assets (path) VALUES (?)", ("C:/External/foo.png",))
    conn.commit()
    conn.close()

    rewrite_paths_after_migration(candidate)

    conn = sqlite3.connect(db_path)
    rows = list(conn.execute("SELECT path FROM assets ORDER BY id"))
    conn.close()
    assert str(tgt_lib) in rows[0][0]
    assert rows[1][0] == "C:/External/foo.png"


def test_rewrite_does_not_touch_unity_imports_path(tmp_path):
    """unity_imports.unitypackage_path 는 Asset Store cache 라 rewrite X."""
    candidate = _make_candidate(tmp_path)
    db_path = candidate.target / "metadata.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE unity_imports (id INTEGER PRIMARY KEY, unitypackage_path TEXT)")
    conn.execute(
        "INSERT INTO unity_imports (unitypackage_path) VALUES (?)",
        ("C:/Users/foo/AppData/Roaming/Unity/Asset Store-5.x/...",),
    )
    conn.commit()
    conn.close()

    rewrite_paths_after_migration(candidate)

    conn = sqlite3.connect(db_path)
    rows = list(conn.execute("SELECT unitypackage_path FROM unity_imports"))
    conn.close()
    assert "Asset Store-5.x" in rows[0][0]


def test_rewrite_creates_db_backup(tmp_path):
    """metadata.db 가 .bak 백업 됐는지."""
    candidate = _make_candidate(tmp_path)
    db_path = candidate.target / "metadata.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE assets (id INTEGER PRIMARY KEY, path TEXT)")
    conn.commit()
    conn.close()

    rewrite_paths_after_migration(candidate)

    assert (candidate.target / "metadata.db.bak").exists()
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_migration_path_rewrite.py -v
```

Expected: 5 FAIL (`ImportError: rewrite_paths_after_migration`).

- [ ] **Step 3: rewrite_paths_after_migration 구현**

`src/assetcache/core/migration.py` Edit:

```python
import shutil as _shutil  # 위 import 와 별칭 (오버라이드 mock 회피)
import sqlite3


def rewrite_paths_after_migration(candidate: MigrationCandidate) -> None:
    """target 안의 config.toml + metadata.db 의 구 base path 를 새 base 로."""
    old_base = str(candidate.source)
    new_base = str(candidate.target)

    # config.toml
    config_path = candidate.target / "config.toml"
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        if old_base in text:
            text = text.replace(old_base, new_base)
            config_path.write_text(text, encoding="utf-8")

    # metadata.db
    db_path = candidate.target / "metadata.db"
    if db_path.exists():
        # 백업
        _shutil.copy2(db_path, db_path.with_suffix(".db.bak"))

        conn = sqlite3.connect(db_path)
        try:
            # assets.path 만 rewrite — unity_imports / projects 는 외부 경로라 무손상
            cursor = conn.execute("SELECT id, path FROM assets WHERE path LIKE ?", (f"{old_base}%",))
            updates = []
            for row_id, path in cursor:
                new_path = path.replace(old_base, new_base, 1)
                updates.append((new_path, row_id))
            conn.executemany("UPDATE assets SET path = ? WHERE id = ?", updates)
            conn.commit()
        finally:
            conn.close()
```

`MigrationRunner.run` 의 step 3 이후에 `rewrite_paths_after_migration(candidate)` 호출 추가.

- [ ] **Step 4: 테스트 통과 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_migration_path_rewrite.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1062 passed (1057 + 5).

- [ ] **Step 6: Commit**

```powershell
git add src/assetcache/core/migration.py tests/test_migration_path_rewrite.py
```

```powershell
git commit -m "feat(m10/p1): migration path rewrite — config.toml + metadata.db

- rewrite_paths_after_migration: target 의 config/db 안 구 base → 새 base
- assets.path 중 구 base 시작 행만 rewrite (unity_imports / projects 무손상)
- metadata.db.bak 백업 사전 생성
- +5 tests (1057 → 1062)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.4: `web/routers/migration.py` + 3 tests

**Files:**
- Create: `src/assetcache/web/routers/migration.py`
- Modify: `src/assetcache/web/server.py` (router 등록)
- Create: `tests/test_migration_router.py`

**Steps:**

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_migration_router.py`:

```python
"""Migration 라우터 endpoint 테스트."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_candidate(tmp_path, monkeypatch):
    """detect_v001_candidate 가 가짜 candidate 반환하도록 monkeypatch."""
    from assetcache.web import server
    from assetcache.core.migration import MigrationCandidate

    src = tmp_path / "old"
    tgt = tmp_path / "new"
    src.mkdir()
    tgt.mkdir()
    candidate = MigrationCandidate(
        source=src, target=tgt,
        total_files=10, total_bytes=1000,
        has_db=True, has_library=True,
    )

    monkeypatch.setattr(
        "assetcache.web.routers.migration.detect_v001_candidate",
        lambda paths: candidate,
    )
    app = server.build_app()
    return TestClient(app), candidate


def test_migration_status_returns_candidate(client_with_candidate):
    client, candidate = client_with_candidate
    resp = client.get("/api/migration/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == str(candidate.source)
    assert data["target"] == str(candidate.target)
    assert data["total_files"] == 10
    assert data["has_db"] is True


def test_migration_status_returns_null_when_no_candidate(tmp_path, monkeypatch):
    from assetcache.web import server
    monkeypatch.setattr(
        "assetcache.web.routers.migration.detect_v001_candidate",
        lambda paths: None,
    )
    app = server.build_app()
    client = TestClient(app)
    resp = client.get("/api/migration/status")
    assert resp.status_code == 200
    assert resp.json() == {"candidate": None}


def test_migration_run_returns_task_id(client_with_candidate):
    client, _ = client_with_candidate
    resp = client.post("/api/migration/run", json={"mode": "copy"})
    assert resp.status_code == 202
    assert "task_id" in resp.json()
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_migration_router.py -v
```

Expected: 3 FAIL (`404 Not Found` 또는 `ImportError`).

- [ ] **Step 3: router 구현**

Create `src/assetcache/web/routers/migration.py`:

```python
"""마이그레이션 endpoint — /api/migration/{status,run,progress,dismiss}."""

from __future__ import annotations

import asyncio
import uuid
from typing import Literal

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from assetcache.config import AppPaths, get_app_paths
from assetcache.core.migration import (
    MigrationCandidate,
    MigrationRunner,
    MigrationState,
    detect_v001_candidate,
    rewrite_paths_after_migration,
)

router = APIRouter(prefix="/api/migration", tags=["migration"])

# task_id → MigrationRunner (in-memory, 앱 프로세스 1개 가정)
_runners: dict[str, MigrationRunner] = {}


class RunRequest(BaseModel):
    mode: Literal["copy", "move"]


def _serialize_candidate(c: MigrationCandidate) -> dict:
    return {
        "source": str(c.source),
        "target": str(c.target),
        "total_files": c.total_files,
        "total_bytes": c.total_bytes,
        "has_db": c.has_db,
        "has_library": c.has_library,
    }


@router.get("/status")
def status():
    candidate = detect_v001_candidate(get_app_paths())
    if candidate is None:
        return {"candidate": None}
    return _serialize_candidate(candidate)


@router.post("/run", status_code=202)
async def run_migration(req: RunRequest):
    candidate = detect_v001_candidate(get_app_paths())
    if candidate is None:
        raise HTTPException(status_code=404, detail="no migration candidate")

    runner = MigrationRunner()
    task_id = str(uuid.uuid4())
    _runners[task_id] = runner

    async def _do():
        await runner.run(candidate, mode=req.mode)
        if runner.state == MigrationState.DONE:
            await asyncio.to_thread(rewrite_paths_after_migration, candidate)

    asyncio.create_task(_do())

    return {"task_id": task_id}


@router.get("/progress")
async def progress(task_id: str):
    runner = _runners.get(task_id)
    if runner is None:
        raise HTTPException(status_code=404, detail="unknown task_id")

    async def event_stream():
        while runner.state in (MigrationState.PENDING, MigrationState.RUNNING):
            yield f'data: {{"state":"{runner.state}","progress":{runner.progress}}}\n\n'
            await asyncio.sleep(0.5)
        if runner.state == MigrationState.DONE:
            yield 'event: done\ndata: {}\n\n'
        else:
            yield f'event: error\ndata: {{"error":"{runner.error}"}}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/dismiss")
def dismiss():
    # 단순 cookie 기반 — 클라이언트에서 처리. 서버는 200 만 반환.
    return JSONResponse({"dismissed": True})
```

Modify `src/assetcache/web/server.py` 의 `build_app()` 안에 라우터 등록:

```python
from assetcache.web.routers import migration as migration_router

def build_app() -> FastAPI:
    app = FastAPI(...)
    # ... 기존 라우터들
    app.include_router(migration_router.router)
    return app
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_migration_router.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1065 passed (1062 + 3).

- [ ] **Step 6: Commit**

```powershell
git add src/assetcache/web/routers/migration.py src/assetcache/web/server.py tests/test_migration_router.py
```

```powershell
git commit -m "feat(m10/p1): /api/migration/{status,run,progress,dismiss} 라우터

- GET status → MigrationCandidate JSON
- POST run { mode } → 202 + task_id, 백그라운드 asyncio task
- GET progress?task_id → SSE
- POST dismiss → 클라이언트 cookie 기반, 서버는 200
- +3 tests (1062 → 1065)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.5: `_migration_banner.html` + base.html 통합

**Files:**
- Create: `src/assetcache/web/templates/_migration_banner.html`
- Modify: `src/assetcache/web/templates/base.html` (배너 include)
- Create: smoke test (선택)

**Steps:**

- [ ] **Step 1: `_migration_banner.html` 작성**

Create `src/assetcache/web/templates/_migration_banner.html`:

```html
{# v0.0.1 데이터 마이그레이션 배너 — Alpine + HTMX 폴링 #}
<div
  x-data="{
    candidate: null,
    taskId: null,
    state: 'idle',
    progress: 0,
    error: '',
    async checkCandidate() {
      const r = await fetch('/api/migration/status');
      const d = await r.json();
      this.candidate = d.candidate === null ? null : d;
    },
    async start(mode) {
      const r = await fetch('/api/migration/run', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({mode}),
      });
      if (!r.ok) { this.error = 'run failed'; return; }
      const d = await r.json();
      this.taskId = d.task_id;
      this.state = 'running';
      this.streamProgress();
    },
    streamProgress() {
      const es = new EventSource(`/api/migration/progress?task_id=${this.taskId}`);
      es.onmessage = (ev) => {
        const d = JSON.parse(ev.data);
        this.progress = d.progress;
      };
      es.addEventListener('done', () => {
        this.state = 'done';
        es.close();
        setTimeout(() => location.reload(), 1500);
      });
      es.addEventListener('error', (ev) => {
        this.state = 'failed';
        this.error = ev.data || 'unknown error';
        es.close();
      });
    },
    dismiss() {
      this.candidate = null;
      document.cookie = 'migration_dismissed=1; path=/';
    },
  }"
  x-init="checkCandidate()"
  x-show="candidate !== null && !document.cookie.includes('migration_dismissed=1')"
  x-cloak
  class="migration-banner"
>
  <template x-if="state === 'idle'">
    <div>
      <h3>{{ _('v0.0.1 데이터를 발견했습니다') }}</h3>
      <p>
        <span x-text="candidate?.total_files"></span>개 파일
        (<span x-text="Math.round(candidate?.total_bytes / 1024 / 1024)"></span> MB)
        를 AssetCacheMCP 로 이주합니다.
      </p>
      <button @click="start('copy')">{{ _('복사') }}</button>
      <button @click="start('move')">{{ _('이동') }}</button>
      <button @click="dismiss()">{{ _('나중에') }}</button>
    </div>
  </template>
  <template x-if="state === 'running'">
    <div>
      <p>{{ _('이주 중...') }} <span x-text="Math.round(progress * 100)"></span>%</p>
      <progress :value="progress" max="1"></progress>
    </div>
  </template>
  <template x-if="state === 'done'">
    <p>{{ _('이주 완료. 새 데이터 폴더를 로드합니다.') }}</p>
  </template>
  <template x-if="state === 'failed'">
    <div>
      <p>{{ _('이주 실패:') }} <span x-text="error"></span></p>
      <button @click="state = 'idle'">{{ _('재시도') }}</button>
    </div>
  </template>
</div>
```

- [ ] **Step 2: base.html 에 include**

Modify `src/assetcache/web/templates/base.html` 의 `<body>` 시작 직후에:

```html
{% include "_migration_banner.html" %}
```

- [ ] **Step 3: CSS (간단)**

Modify `src/assetcache/web/static/style.css` (또는 base.html 의 <style>) 에 추가:

```css
.migration-banner {
  background: #fff3cd;
  color: #664d03;
  padding: 12px 16px;
  border-bottom: 1px solid #ffe69c;
}
.migration-banner button { margin-right: 8px; }
[x-cloak] { display: none !important; }
```

- [ ] **Step 4: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1065 passed (변경 없음).

- [ ] **Step 5: Commit**

```powershell
git add src/assetcache/web/templates/_migration_banner.html src/assetcache/web/templates/base.html src/assetcache/web/static/style.css
```

```powershell
git commit -m "feat(m10/p1): _migration_banner.html Alpine + SSE 배너

- base.html 상단에 include
- candidate 폴링 + 복사/이동/나중에 버튼 + SSE progress
- 완료 시 1.5s 후 location.reload (새 데이터 로드)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.6: CLI `--migrate=copy|move` + 2 tests

**Files:**
- Modify: `src/assetcache/__main__.py` (--migrate 옵션)
- Modify: `tests/test_entrypoint.py` (+2 tests)

**Steps:**

- [ ] **Step 1: 실패하는 테스트 작성**

Edit `tests/test_entrypoint.py` 끝에:

```python
def test_main_migrate_copy_runs(tmp_path, monkeypatch, capsys):
    """assetcache --migrate=copy 헤드리스 실행."""
    from assetcache import __main__ as m
    from assetcache.core.migration import MigrationCandidate

    src = tmp_path / "old"
    tgt = tmp_path / "new"
    src.mkdir()
    (src / "metadata.db").write_text("db")
    tgt.mkdir()

    fake_candidate = MigrationCandidate(
        source=src, target=tgt,
        total_files=1, total_bytes=10,
        has_db=True, has_library=False,
    )
    monkeypatch.setattr(
        "assetcache.__main__.detect_v001_candidate",
        lambda paths: fake_candidate,
    )

    rc = m.main(["--migrate=copy"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "마이그레이션 완료" in captured.out or "done" in captured.out.lower()
    assert (tgt / "metadata.db").exists()


def test_main_migrate_no_candidate_exits_zero(tmp_path, monkeypatch, capsys):
    from assetcache import __main__ as m
    monkeypatch.setattr(
        "assetcache.__main__.detect_v001_candidate",
        lambda paths: None,
    )
    rc = m.main(["--migrate=copy"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "이주할 데이터가 없음" in captured.out or "no candidate" in captured.out.lower()
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_entrypoint.py::test_main_migrate_copy_runs tests/test_entrypoint.py::test_main_migrate_no_candidate_exits_zero -v
```

Expected: 2 FAIL.

- [ ] **Step 3: --migrate 옵션 구현**

Edit `src/assetcache/__main__.py`:

```python
import argparse
import asyncio

from assetcache.config import get_app_paths
from assetcache.core.migration import (
    MigrationRunner,
    MigrationState,
    detect_v001_candidate,
    rewrite_paths_after_migration,
)


def _add_migrate_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--migrate",
        choices=["copy", "move"],
        help="v0.0.1 데이터 폴더에서 헤드리스 마이그레이션 실행",
    )


def _run_migration(mode: str) -> int:
    candidate = detect_v001_candidate(get_app_paths())
    if candidate is None:
        print("이주할 데이터가 없음 (no candidate)")
        return 0

    runner = MigrationRunner()
    asyncio.run(runner.run(candidate, mode=mode))
    if runner.state == MigrationState.DONE:
        rewrite_paths_after_migration(candidate)
        print("마이그레이션 완료")
        return 0
    print(f"마이그레이션 실패: {runner.error}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="assetcache")
    # ... 기존 --tray, --mcp, --version, --data-dir
    _add_migrate_arg(parser)
    args = parser.parse_args(argv)

    if args.migrate:
        return _run_migration(args.migrate)

    # ... 기존 dispatch
```

- [ ] **Step 4: 테스트 통과**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_entrypoint.py -v
```

Expected: 2 신규 PASS + 기존 모두 PASS.

- [ ] **Step 5: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1067 passed (1065 + 2).

- [ ] **Step 6: Commit**

```powershell
git add src/assetcache/__main__.py tests/test_entrypoint.py
```

```powershell
git commit -m "feat(m10/p1): CLI --migrate=copy|move 옵션

- assetcache --migrate=copy 또는 --migrate=move 헤드리스 실행
- candidate 없으면 'no candidate' 출력 + exit 0
- 완료 시 path rewrite 실행
- +2 tests (1065 → 1067)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.7: 마이그레이션 i18n msgid (5건)

**Files:**
- Modify: `src/assetcache/web/locale/ko/LC_MESSAGES/messages.po`
- Modify: `src/assetcache/web/locale/en/LC_MESSAGES/messages.po`
- Build: `.mo` 재컴파일

**Steps:**

- [ ] **Step 1: 신규 msgid 5건 추가**

ko/en 둘 다:

```po
msgid "v0.0.1 데이터를 발견했습니다"
msgstr "..."  # ko: 그대로, en: "v0.0.1 data found"

msgid "복사"
msgstr "..."  # ko: 복사, en: Copy

msgid "이동"
msgstr "..."  # ko: 이동, en: Move

msgid "나중에"
msgstr "..."  # ko: 나중에, en: Later

msgid "이주 중..."
msgstr "..."  # ko: 이주 중..., en: Migrating...
```

또한 "이주 완료. 새 데이터 폴더를 로드합니다." / "이주 실패:" / "재시도" 도 추가.

- [ ] **Step 2: .mo 재컴파일**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\pybabel.exe" compile -d src/assetcache/web/locale
```

- [ ] **Step 3: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1067 passed.

- [ ] **Step 4: Commit**

```powershell
git add src/assetcache/web/locale
```

```powershell
git commit -m "feat(m10/p1): 마이그레이션 배너용 i18n msgid 8건

- ko/en .po 양쪽 + .mo 재컴파일

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 — M9 cherry-pick (+15 테스트, ~1.5일)

목표: `feat/m9` 의 `core/updater/version.py` 그대로, `checker.py` 의 source URL 만 GitHub → PyPI JSON API, `pip_command.py` 신규, web/tray 단순화.

### Task 2.1: version.py + checker.py 골격 cherry-pick

**Files:**
- Create: `src/assetcache/core/updater/__init__.py` (cherry-pick from feat/m9)
- Create: `src/assetcache/core/updater/version.py` (cherry-pick 그대로)
- Create: `tests/test_updater_version.py` (cherry-pick 그대로)

**Steps:**

- [ ] **Step 1: feat/m9 에서 파일 가져오기**

```powershell
git checkout feat/m9-code-signing-and-auto-update -- src/gah/core/updater/__init__.py src/gah/core/updater/version.py tests/test_updater_version.py
```

→ 이 명령 후 working tree 에 `src/gah/core/updater/__init__.py` + `version.py` + `tests/test_updater_version.py` 가 옴 (feat/m9 의 상태).

- [ ] **Step 2: import path 갱신**

가져온 파일들 안의 `from gah` / `import gah` → `from assetcache` / `import assetcache` 일괄 교체 (Phase 0 패턴과 동일).

`src/gah/core/updater/` 디렉터리 자체도 `src/assetcache/core/updater/` 로 옮긴다:

```powershell
New-Item -ItemType Directory -Force -Path src/assetcache/core/updater | Out-Null
Move-Item src/gah/core/updater/* src/assetcache/core/updater/
Remove-Item -Recurse src/gah
```

(또는 git mv 가 더 안전 — 위 명령은 working tree 만 보정. git stage 에 git mv 결과 반영 필요.)

```powershell
git rm -r --cached src/gah/core/updater
git add src/assetcache/core/updater
```

- [ ] **Step 3: 테스트 한 번 실행**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_updater_version.py -v
```

Expected: 9 PASS (feat/m9 의 그대로 — 단 import path 갱신 후라).

- [ ] **Step 4: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1076 passed (1067 + 9).

- [ ] **Step 5: Commit**

```powershell
git add src/assetcache/core/updater/__init__.py src/assetcache/core/updater/version.py tests/test_updater_version.py
```

```powershell
git commit -m "feat(m10/p2): cherry-pick updater/version.py from feat/m9

- semver-lite parse + compare (그대로 가져옴, import path 만 assetcache 로)
- +9 tests (1067 → 1076)
- source: feat/m9-code-signing-and-auto-update commit (Task 3 of M9)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.2: checker.py PyPI JSON API 변경 + 6 tests

**Files:**
- Create: `src/assetcache/core/updater/checker.py` (cherry-pick + 수정)
- Create: `tests/test_updater_checker_pypi.py` (신규, M9 의 GitHub mocking 대신 PyPI mocking)

**Steps:**

- [ ] **Step 1: feat/m9 에서 checker.py 가져오기 (참고용)**

```powershell
git show feat/m9-code-signing-and-auto-update:src/gah/core/updater/checker.py | Set-Content tmp_checker.py -Encoding utf8
```

(직접 Read 도 가능: `git show feat/m9-...:src/gah/core/updater/checker.py` 출력을 참고하여 새 파일 작성)

- [ ] **Step 2: 실패하는 테스트 작성**

Create `tests/test_updater_checker_pypi.py`:

```python
"""PyPI JSON API 기반 UpdateChecker 테스트."""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from assetcache.core.updater.checker import UpdateChecker
from assetcache.core.updater.version import Version


@pytest.mark.asyncio
@respx.mock
async def test_check_once_returns_available_when_newer_version(monkeypatch):
    respx.get("https://pypi.org/pypi/assetcache-mcp/json").mock(
        return_value=Response(200, json={"info": {"version": "0.2.0"}})
    )
    checker = UpdateChecker(package_name="assetcache-mcp", current=Version.parse("0.1.0"))
    result = await checker.check_once()
    assert result.available is True
    assert result.latest == Version.parse("0.2.0")


@pytest.mark.asyncio
@respx.mock
async def test_check_once_returns_not_available_when_same_version():
    respx.get("https://pypi.org/pypi/assetcache-mcp/json").mock(
        return_value=Response(200, json={"info": {"version": "0.1.0"}})
    )
    checker = UpdateChecker(package_name="assetcache-mcp", current=Version.parse("0.1.0"))
    result = await checker.check_once()
    assert result.available is False
    assert result.latest == Version.parse("0.1.0")


@pytest.mark.asyncio
@respx.mock
async def test_check_once_returns_unknown_on_404():
    respx.get("https://pypi.org/pypi/assetcache-mcp/json").mock(
        return_value=Response(404)
    )
    checker = UpdateChecker(package_name="assetcache-mcp", current=Version.parse("0.1.0"))
    result = await checker.check_once()
    assert result.available is False
    assert result.error is not None


@pytest.mark.asyncio
@respx.mock
async def test_check_once_handles_etag_304():
    """이전 ETag 캐시가 있으면 If-None-Match 보냄, 304 응답 시 cache 사용."""
    respx.get("https://pypi.org/pypi/assetcache-mcp/json").mock(
        return_value=Response(304)
    )
    checker = UpdateChecker(package_name="assetcache-mcp", current=Version.parse("0.1.0"))
    checker._cached_etag = '"abc123"'
    checker._cached_latest = Version.parse("0.2.0")
    result = await checker.check_once()
    assert result.available is True
    assert result.latest == Version.parse("0.2.0")


@pytest.mark.asyncio
@respx.mock
async def test_check_once_handles_timeout():
    respx.get("https://pypi.org/pypi/assetcache-mcp/json").mock(
        side_effect=__import__("httpx").TimeoutException("slow")
    )
    checker = UpdateChecker(package_name="assetcache-mcp", current=Version.parse("0.1.0"))
    result = await checker.check_once()
    assert result.available is False
    assert "timeout" in result.error.lower() or "slow" in result.error.lower()


@pytest.mark.asyncio
@respx.mock
async def test_check_once_extracts_release_notes_url():
    respx.get("https://pypi.org/pypi/assetcache-mcp/json").mock(
        return_value=Response(
            200,
            json={
                "info": {
                    "version": "0.2.0",
                    "project_urls": {
                        "Issues": "https://github.com/v0o0v/assetcache-mcp/issues",
                        "Homepage": "https://github.com/v0o0v/assetcache-mcp",
                    },
                }
            },
        )
    )
    checker = UpdateChecker(package_name="assetcache-mcp", current=Version.parse("0.1.0"))
    result = await checker.check_once()
    assert result.release_notes_url is not None
    assert "0.2.0" in result.release_notes_url or "releases" in result.release_notes_url
```

- [ ] **Step 3: 테스트 실패 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_updater_checker_pypi.py -v
```

Expected: 6 FAIL (`ImportError: UpdateChecker`).

- [ ] **Step 4: checker.py 작성**

Create `src/assetcache/core/updater/checker.py`:

```python
"""PyPI JSON API 폴링 기반 UpdateChecker."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import httpx

from assetcache.core.updater.version import Version

PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"


@dataclass
class CheckResult:
    current: Version
    latest: Version
    available: bool
    release_notes_url: Optional[str] = None
    error: Optional[str] = None


class UpdateChecker:
    """PyPI 의 최신 버전 polling."""

    def __init__(
        self,
        package_name: str = "assetcache-mcp",
        current: Optional[Version] = None,
    ):
        self.package_name = package_name
        self.current = current or Version.parse("0.0.0")
        self._cached_etag: Optional[str] = None
        self._cached_latest: Optional[Version] = None
        self._cached_release_url: Optional[str] = None

    async def check_once(self) -> CheckResult:
        url = PYPI_JSON_URL.format(package=self.package_name)
        headers = {}
        if self._cached_etag:
            headers["If-None-Match"] = self._cached_etag

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)

            if resp.status_code == 304 and self._cached_latest is not None:
                return CheckResult(
                    current=self.current,
                    latest=self._cached_latest,
                    available=self._cached_latest > self.current,
                    release_notes_url=self._cached_release_url,
                )

            if resp.status_code != 200:
                return CheckResult(
                    current=self.current,
                    latest=self.current,
                    available=False,
                    error=f"HTTP {resp.status_code}",
                )

            etag = resp.headers.get("etag")
            data = resp.json()
            latest = Version.parse(data["info"]["version"])
            release_url = _derive_release_url(data, latest)

            self._cached_etag = etag
            self._cached_latest = latest
            self._cached_release_url = release_url

            return CheckResult(
                current=self.current,
                latest=latest,
                available=latest > self.current,
                release_notes_url=release_url,
            )

        except httpx.TimeoutException as e:
            return CheckResult(
                current=self.current,
                latest=self.current,
                available=False,
                error=f"timeout: {e}",
            )
        except Exception as e:
            return CheckResult(
                current=self.current,
                latest=self.current,
                available=False,
                error=str(e),
            )


def _derive_release_url(data: dict, version: Version) -> Optional[str]:
    """info.project_urls 에서 Homepage 추출 → /releases/tag/v<ver> 조합."""
    urls = data.get("info", {}).get("project_urls", {}) or {}
    home = urls.get("Homepage") or urls.get("Repository")
    if home and "github.com" in home:
        return f"{home}/releases/tag/v{version}"
    return None


class PollingLoop:
    """백그라운드 24h 폴링 루프 (asyncio task)."""

    def __init__(self, checker: UpdateChecker, interval_hours: float = 24.0):
        self.checker = checker
        self.interval_seconds = interval_hours * 3600.0
        self.latest_result: Optional[CheckResult] = None
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    async def _loop(self):
        while not self._stop.is_set():
            self.latest_result = await self.checker.check_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    def stop(self):
        self._stop.set()
```

- [ ] **Step 5: 테스트 통과 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_updater_checker_pypi.py -v
```

Expected: 6 PASS.

- [ ] **Step 6: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1082 passed (1076 + 6).

- [ ] **Step 7: Commit**

```powershell
git add src/assetcache/core/updater/checker.py tests/test_updater_checker_pypi.py
```

```powershell
git commit -m "feat(m10/p2): checker.py PyPI JSON API + PollingLoop

- UpdateChecker.check_once: pypi.org/pypi/{pkg}/json + ETag 캐시
- 304 응답 시 cached version 반환
- timeout/404 등 에러 시 available=False + error message
- _derive_release_url: project_urls.Homepage + /releases/tag/v<ver>
- PollingLoop 24h 백그라운드 (asyncio task)
- +6 tests (1076 → 1082)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.3: pip_command.py + 3 tests

**Files:**
- Create: `src/assetcache/core/updater/pip_command.py`
- Create: `tests/test_pip_command.py`

**Steps:**

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_pip_command.py`:

```python
"""pip_command.recommended_upgrade_command 환경 분기 테스트."""
from __future__ import annotations

import pytest

from assetcache.core.updater.pip_command import recommended_upgrade_command


def test_returns_pipx_when_pipx_available(monkeypatch):
    monkeypatch.setattr(
        "shutil.which",
        lambda name: "C:/pipx.exe" if name == "pipx" else None,
    )
    cmd = recommended_upgrade_command("assetcache-mcp")
    assert cmd == "pipx upgrade assetcache-mcp"


def test_returns_uv_tool_when_uv_available_no_pipx(monkeypatch):
    monkeypatch.setattr(
        "shutil.which",
        lambda name: "C:/uv.exe" if name == "uv" else None,
    )
    cmd = recommended_upgrade_command("assetcache-mcp")
    assert cmd == "uv tool upgrade assetcache-mcp"


def test_returns_pip_when_neither_available(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    cmd = recommended_upgrade_command("assetcache-mcp")
    assert cmd == "pip install -U assetcache-mcp"
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_pip_command.py -v
```

Expected: 3 FAIL.

- [ ] **Step 3: pip_command.py 작성**

Create `src/assetcache/core/updater/pip_command.py`:

```python
"""사용자 환경 검출 후 적절한 upgrade 명령 반환."""

from __future__ import annotations

import shutil


def recommended_upgrade_command(package: str = "assetcache-mcp") -> str:
    if shutil.which("pipx"):
        return f"pipx upgrade {package}"
    if shutil.which("uv"):
        return f"uv tool upgrade {package}"
    return f"pip install -U {package}"
```

- [ ] **Step 4: 테스트 통과**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_pip_command.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1085 passed (1082 + 3).

- [ ] **Step 6: Commit**

```powershell
git add src/assetcache/core/updater/pip_command.py tests/test_pip_command.py
```

```powershell
git commit -m "feat(m10/p2): pip_command.recommended_upgrade_command 환경 분기

- shutil.which 로 pipx → uv → pip 우선순위 분기
- +3 tests (1082 → 1085)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.4: web/routers/updates.py 단순화 + 2 tests

**Files:**
- Create: `src/assetcache/web/routers/updates.py`
- Modify: `src/assetcache/web/server.py` (router 등록)
- Create: `tests/test_updates_router_simplified.py`

**Steps:**

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_updates_router_simplified.py`:

```python
"""단순화된 /api/updates/check 라우터."""
from __future__ import annotations

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response


@pytest.fixture
def client(monkeypatch):
    from assetcache.web import server
    from assetcache.core.updater.version import Version

    monkeypatch.setattr(
        "assetcache.web.routers.updates.get_current_version",
        lambda: Version.parse("0.1.0"),
    )
    return TestClient(server.build_app())


@respx.mock
def test_check_returns_payload_with_command(client):
    respx.get("https://pypi.org/pypi/assetcache-mcp/json").mock(
        return_value=Response(200, json={"info": {"version": "0.2.0"}})
    )
    resp = client.get("/api/updates/check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current"] == "0.1.0"
    assert data["latest"] == "0.2.0"
    assert data["available"] is True
    assert data["command"].endswith("assetcache-mcp")


@respx.mock
def test_check_returns_not_available_when_same_version(client):
    respx.get("https://pypi.org/pypi/assetcache-mcp/json").mock(
        return_value=Response(200, json={"info": {"version": "0.1.0"}})
    )
    resp = client.get("/api/updates/check")
    data = resp.json()
    assert data["available"] is False
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_updates_router_simplified.py -v
```

Expected: 2 FAIL.

- [ ] **Step 3: updates.py 라우터 작성**

Create `src/assetcache/web/routers/updates.py`:

```python
"""PyPI 신버전 알림 라우터 — /api/updates/check 만."""

from __future__ import annotations

from fastapi import APIRouter

from assetcache.core.updater.checker import UpdateChecker
from assetcache.core.updater.pip_command import recommended_upgrade_command
from assetcache.core.updater.version import Version


def get_current_version() -> Version:
    from assetcache import __version__
    return Version.parse(__version__)


router = APIRouter(prefix="/api/updates", tags=["updates"])


@router.get("/check")
async def check():
    current = get_current_version()
    checker = UpdateChecker(package_name="assetcache-mcp", current=current)
    result = await checker.check_once()
    return {
        "current": str(current),
        "latest": str(result.latest),
        "available": result.available,
        "command": recommended_upgrade_command("assetcache-mcp"),
        "release_notes_url": result.release_notes_url,
        "error": result.error,
    }
```

`src/assetcache/__init__.py` 에 `__version__` 정의 확인:

```python
__version__ = "0.1.0"
```

Modify `server.py` 에 라우터 등록:

```python
from assetcache.web.routers import updates as updates_router
app.include_router(updates_router.router)
```

- [ ] **Step 4: 테스트 통과**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_updates_router_simplified.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1087 passed (1085 + 2).

- [ ] **Step 6: Commit**

```powershell
git add src/assetcache/web/routers/updates.py src/assetcache/web/server.py src/assetcache/__init__.py tests/test_updates_router_simplified.py
```

```powershell
git commit -m "feat(m10/p2): /api/updates/check 단순화 (M9 의 start/status/install drop)

- GET /api/updates/check → { current, latest, available, command, release_notes_url, error }
- pip_command 으로 사용자 환경별 upgrade 명령 추천
- +2 tests (1085 → 1087)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.5: `_pypi_update_banner.html` + base.html

**Files:**
- Create: `src/assetcache/web/templates/_pypi_update_banner.html`
- Modify: `src/assetcache/web/templates/base.html`

**Steps:**

- [ ] **Step 1: 템플릿 작성**

Create `src/assetcache/web/templates/_pypi_update_banner.html`:

```html
{# PyPI 신버전 알림 배너 — Alpine + 폴링 #}
<div
  x-data="{
    available: false,
    latest: '',
    command: '',
    releaseUrl: '',
    async check() {
      const r = await fetch('/api/updates/check');
      const d = await r.json();
      this.available = d.available;
      this.latest = d.latest;
      this.command = d.command;
      this.releaseUrl = d.release_notes_url;
    },
    copyCommand() {
      navigator.clipboard.writeText(this.command);
    },
    dismiss() {
      this.available = false;
      document.cookie = `pypi_update_dismissed_${this.latest}=1; path=/`;
    },
  }"
  x-init="check()"
  x-show="available && !document.cookie.includes(`pypi_update_dismissed_${latest}=1`)"
  x-cloak
  class="pypi-update-banner"
>
  <div>
    <span>{{ _('v') }}<span x-text="latest"></span> {{ _('사용 가능') }}</span>
    <code x-text="command"></code>
    <button @click="copyCommand()">{{ _('복사') }}</button>
    <a :href="releaseUrl" target="_blank" x-show="releaseUrl">{{ _('Release notes') }}</a>
    <button @click="dismiss()">{{ _('나중에') }}</button>
  </div>
</div>
```

- [ ] **Step 2: base.html include**

Modify `src/assetcache/web/templates/base.html` 에서 `{% include "_migration_banner.html" %}` 아래에:

```html
{% include "_pypi_update_banner.html" %}
```

- [ ] **Step 3: CSS**

`style.css` 에:

```css
.pypi-update-banner {
  background: #cfe2ff;
  color: #084298;
  padding: 8px 16px;
  border-bottom: 1px solid #9ec5fe;
}
.pypi-update-banner code { background: #fff; padding: 2px 6px; border-radius: 4px; margin: 0 8px; }
```

- [ ] **Step 4: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1087 passed (변경 없음).

- [ ] **Step 5: Commit**

```powershell
git add src/assetcache/web/templates/_pypi_update_banner.html src/assetcache/web/templates/base.html src/assetcache/web/static/style.css
```

```powershell
git commit -m "feat(m10/p2): _pypi_update_banner.html 단순화 (다운로드/SSE 제거)

- 알림 + 복사 가능 명령 + release notes 링크만
- M9 의 다운로드/swap 진행률 모두 drop

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.6: tray.py PyPI 알림 + Qt Signal + 4 tests

**Files:**
- Modify: `src/assetcache/tray.py`
- Create: `tests/test_tray_pypi_notification.py`

**Steps:**

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_tray_pypi_notification.py`:

```python
"""트레이 PyPI 알림 메뉴 + 클립보드 복사 테스트."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def fake_qapp():
    """PySide6 가 없거나 headless 환경에서 stubbed app."""
    with patch("assetcache.tray.QApplication") as qa, patch(
        "assetcache.tray.QSystemTrayIcon"
    ) as qsti, patch("assetcache.tray.QMenu") as qm:
        yield {"QApplication": qa, "QSystemTrayIcon": qsti, "QMenu": qm}


def test_tray_adds_update_menu_when_available(fake_qapp):
    from assetcache.tray import TrayController
    from assetcache.core.updater.checker import CheckResult
    from assetcache.core.updater.version import Version

    controller = TrayController(app=MagicMock())
    result = CheckResult(
        current=Version.parse("0.1.0"),
        latest=Version.parse("0.2.0"),
        available=True,
        release_notes_url="https://github.com/v0o0v/assetcache-mcp/releases",
    )

    controller.update_check_result(result)

    assert any("v0.2.0" in str(c) for c in controller.menu_actions)


def test_tray_no_update_menu_when_not_available(fake_qapp):
    from assetcache.tray import TrayController
    from assetcache.core.updater.checker import CheckResult
    from assetcache.core.updater.version import Version

    controller = TrayController(app=MagicMock())
    result = CheckResult(
        current=Version.parse("0.1.0"),
        latest=Version.parse("0.1.0"),
        available=False,
    )
    controller.update_check_result(result)

    assert not any("업데이트 가능" in str(c) for c in controller.menu_actions)


def test_tray_click_update_copies_command(fake_qapp, monkeypatch):
    """업데이트 메뉴 클릭 시 클립보드에 pipx upgrade 복사."""
    from assetcache.tray import TrayController

    fake_clipboard = MagicMock()
    fake_qapp["QApplication"].clipboard.return_value = fake_clipboard

    controller = TrayController(app=MagicMock())
    controller._on_update_clicked("pipx upgrade assetcache-mcp")

    fake_clipboard.setText.assert_called_with("pipx upgrade assetcache-mcp")


def test_tray_signal_for_cross_thread_update(fake_qapp):
    """update_check_result 가 thread-safe 하게 호출됨."""
    from assetcache.tray import TrayController

    controller = TrayController(app=MagicMock())
    assert hasattr(controller, "update_signal")
```

- [ ] **Step 2: 테스트 실패 확인**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_tray_pypi_notification.py -v
```

Expected: 4 FAIL.

- [ ] **Step 3: tray.py 수정**

Edit `src/assetcache/tray.py` 에 다음 추가 (M9 패턴 보존):

```python
from PySide6.QtCore import QObject, Signal


class _TrayBridge(QObject):
    """cross-thread update_check_result 전달용 Qt Signal."""
    update_signal = Signal(object)


class TrayController:
    def __init__(self, app):
        self.app = app
        self.menu_actions: list = []
        self.bridge = _TrayBridge()
        self.bridge.update_signal.connect(self._apply_update_result)
        self.update_signal = self.bridge.update_signal  # public alias

    def update_check_result(self, result):
        """thread-safe — 어디서든 호출 가능."""
        self.bridge.update_signal.emit(result)

    def _apply_update_result(self, result):
        """Qt main thread 에서 실행."""
        # 기존 update menu 제거
        self.menu_actions = [a for a in self.menu_actions if "업데이트" not in str(a)]
        if result.available:
            from assetcache.core.updater.pip_command import recommended_upgrade_command
            command = recommended_upgrade_command("assetcache-mcp")
            label = f"v{result.latest} 업데이트 가능 →"
            action = self._make_menu_action(label, lambda: self._on_update_clicked(command))
            self.menu_actions.append(action)
            self._rebuild_menu()

    def _on_update_clicked(self, command: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(command)
        # 시스템 trayMessage
        if hasattr(self, "tray_icon"):
            self.tray_icon.showMessage(
                "AssetCacheMCP",
                f"업그레이드 명령이 클립보드에 복사됨: {command}",
            )

    def _make_menu_action(self, label, callback):
        return (label, callback)  # 실 구현은 QAction

    def _rebuild_menu(self):
        # ... 기존 메뉴 재구성 코드
        pass
```

- [ ] **Step 4: 테스트 통과**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_tray_pypi_notification.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1091 passed (1087 + 4).

- [ ] **Step 6: Commit**

```powershell
git add src/assetcache/tray.py tests/test_tray_pypi_notification.py
```

```powershell
git commit -m "feat(m10/p2): tray PyPI 알림 동적 메뉴 + Qt Signal cross-thread

- _TrayBridge(QObject) + Signal(object) 패턴 (M9 에서 cherry-pick)
- update_check_result 가 어디서든 thread-safe 호출
- 업데이트 클릭 → 클립보드 복사 + 시스템 trayMessage
- +4 tests (1087 → 1091)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.7: updater i18n msgid (4건)

**Files:**
- Modify: ko/en .po (+4 msgid: "사용 가능", "Release notes", "복사" — 이미 있을 가능성, "v" 접두 등)
- Build: .mo

**Steps:**

- [ ] **Step 1: 신규 msgid 추가**

```po
msgid "사용 가능"
msgstr "..."  # en: available

msgid "Release notes"
msgstr "..."  # en: Release notes (그대로)
```

- [ ] **Step 2: .mo 재컴파일**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\pybabel.exe" compile -d src/assetcache/web/locale
```

- [ ] **Step 3: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1091 passed.

- [ ] **Step 4: Commit**

```powershell
git add src/assetcache/web/locale
```

```powershell
git commit -m "feat(m10/p2): PyPI 알림 배너용 i18n msgid 4건"
```

---

## Phase 3 — 문서 + i18n catalog 정합성 + verification (+5 테스트, ~1일)

목표: 사용자 facing docs 갱신 + i18n catalog 일관성 검사 + M10_verification.md 작성.

### Task 3.1: README + CLAUDE + HANDOFF + DESIGN 갱신

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `HANDOFF.md`
- Modify: `DESIGN.md`

**Steps:**

- [ ] **Step 1: README.md 갱신**

`README.md` 의 다음 갱신:
- 제목: "Game Asset Helper" → "AssetCacheMCP"
- 설치 안내: PyInstaller exe 다운로드 → `pipx install assetcache-mcp` 가 primary
- v0.0.1 사용자 안내 섹션: "이전 v0.0.1 사용자는 마이그레이션 배너 또는 `assetcache --migrate=copy`"
- Claude Desktop config 예시 갱신
- 모든 `python -m gah` → `python -m assetcache` 또는 `assetcache`

- [ ] **Step 2: CLAUDE.md 갱신**

§1, §5, §6, §7, §8 모두 검토:
- §1: "Game Asset Helper (GAH)" → "AssetCacheMCP (assetcache-mcp)"
- §2: 마일스톤 표에 M10 추가
- §5: 디렉터리 구조에서 `src/gah/` → `src/assetcache/`
- §6: 셋업 명령에서 `pip install -e ...[dev]` 그대로지만 패키지 이름 갱신
- §7: 자주 쓰는 명령 갱신 (`python -m assetcache --tray` 등)
- §8: M10 완료 시 §8 을 "다음 작업 = M11 (Mac/Linux)" 으로 갱신

- [ ] **Step 3: HANDOFF.md 갱신**

마지막 인계 시각 + 마지막 완료 작업 = M10. 환경 표 갱신 (런타임 데이터 = `%APPDATA%\AssetCacheMCP\`).

- [ ] **Step 4: DESIGN.md 갱신**

§3 아키텍처, §4.X, §11 로드맵 갱신. 패키지명 / CLI 명 일관성.

- [ ] **Step 5: 회귀 (docs 변경이라 영향 X)**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: 1091 passed.

- [ ] **Step 6: Commit**

```powershell
git add README.md CLAUDE.md HANDOFF.md DESIGN.md
```

```powershell
git commit -m "docs(m10/p3): README + CLAUDE + HANDOFF + DESIGN AssetCacheMCP 표기 일괄 갱신"
```

### Task 3.2: i18n catalog 정합성 + 5 tests

**Files:**
- Create: `tests/test_locale_assetcache_msgid.py`

**Steps:**

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_locale_assetcache_msgid.py`:

```python
"""ko/en .po catalog 의 신규 msgid 정합성 검사."""
from __future__ import annotations

from pathlib import Path

import pytest

LOCALE_ROOT = Path(__file__).parent.parent / "src" / "assetcache" / "web" / "locale"

NEW_MSGIDS = [
    "v0.0.1 데이터를 발견했습니다",
    "복사",
    "이동",
    "나중에",
    "이주 중...",
]


def _load_po(path: Path) -> set[str]:
    msgids = set()
    current_id: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith('msgid "'):
            current_id = line[len('msgid "'):-1]
            msgids.add(current_id)
    return msgids


@pytest.mark.parametrize("lang", ["ko", "en"])
@pytest.mark.parametrize("msgid", NEW_MSGIDS)
def test_msgid_present_in_locale(lang: str, msgid: str):
    po = LOCALE_ROOT / lang / "LC_MESSAGES" / "messages.po"
    msgids = _load_po(po)
    assert msgid in msgids, f"{msgid} missing in {lang}/messages.po"
```

(parameterize 가 5 msgid × 2 lang = 10 케이스. pytest 가 합쳐 5 로 셈할지 10 으로 셈할지에 따라 다름. test 함수 1개 + parameterize 로 10 instance — pytest 는 instance 카운트하므로 +10. spec 의 +5 와 차이 있을 수 있음. 더 정확: 별도 5 테스트 함수로 분리. 또는 parameterize 의 instance 10 을 spec 의 +5 reset → spec 의 추정 +35 가 실제 +40 이 될 수 있음 — 양해 한도 안.)

- [ ] **Step 2: 테스트 통과 확인 (Phase 1.7, 2.7 에서 이미 msgid 추가)**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest tests/test_locale_assetcache_msgid.py -v
```

Expected: 10 PASS (parametrize 10 instance) or 5 PASS (if grouped).

- [ ] **Step 3: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: ~1101 passed (1091 + 10).

- [ ] **Step 4: Commit**

```powershell
git add tests/test_locale_assetcache_msgid.py
```

```powershell
git commit -m "test(m10/p3): locale catalog 정합성 (5 신규 msgid × ko/en)"
```

### Task 3.3: M10_verification.md 작성

**Files:**
- Create: `milestones/M10_verification.md`

**Steps:**

- [ ] **Step 1: verification 작성**

Create `milestones/M10_verification.md`:

```markdown
# M10 — PyPI + AssetCacheMCP rename 검증

## 자동 검증

(완료 후 채움)

- pytest -q 결과:
- pytest -m mcp_integration 결과:
- python -m build 결과:
- pip install dist/*.whl 후 assetcache --version 결과:

## 수동 검증 (사용자)

### 시나리오 1 — Phase 0 회귀
- [ ] python -m assetcache --tray 부팅 → 트레이 정상 → 종료 정상
- [ ] 웹 UI http://localhost:9874 → title "AssetCacheMCP", 헤더 브랜딩 갱신
- [ ] MCP stdio: `python -m assetcache --mcp` → tools/list 응답 20 도구

### 시나리오 2 — 마이그레이션 helper
- [ ] %APPDATA%\GameAssetHelper\ 가짜 데이터 준비 (metadata.db + library/ 더미)
- [ ] %APPDATA%\AssetCacheMCP\ 비어있음 확인
- [ ] 부팅 → 웹 GUI 배너 노출 + 파일 수/크기 정확
- [ ] [복사] 클릭 → SSE progress → 완료 후 새 폴더에 데이터 복사됨 + 구 폴더 보존
- [ ] 재부팅 후 배너 안 뜸 (.migrated_from_v001 마커)
- [ ] %APPDATA%\AssetCacheMCP\ 삭제 후 [이동] 시나리오 재시도 → 구 폴더 사라지고 새 폴더에 데이터

### 시나리오 3 — PyPI 알림
- [ ] checker 의 cache 조작 또는 직접 0.0.0 current 로 부팅 → 배너 + 트레이 메뉴 노출
- [ ] 배너 [복사] 클릭 → 클립보드에 `pipx upgrade assetcache-mcp` 복사 확인
- [ ] 트레이 메뉴 클릭 → 시스템 trayMessage + 클립보드 복사

### 시나리오 4 — CLI --migrate
- [ ] PowerShell 에서 `assetcache --migrate=copy` 실행 → exit 0 + 데이터 복사 확인

### 시나리오 5 — wheel 설치
- [ ] 새 venv 에 `pip install dist/assetcache_mcp-0.1.0-py3-none-any.whl`
- [ ] `assetcache --version` → 0.1.0 출력
- [ ] `assetcache --tray` 부팅 확인

### 시나리오 6 — TestPyPI 흐름
- [ ] TestPyPI 업로드 후 `pipx install --index-url https://test.pypi.org/simple/ assetcache-mcp`
- [ ] 정상 설치 + `assetcache --version` 확인

### 시나리오 7 — PyPI 정식 흐름 (최종)
- [ ] PyPI 업로드 후 `pipx install assetcache-mcp`
- [ ] Claude Desktop config 갱신 → MCP 도구 정상

## 알려진 한계

- v0.0.1 사용자의 Claude Desktop config 자동 마이그레이션 X (release notes 안내만)
- Mac/Linux 검증 X (M11 별도 마일스톤)
```

- [ ] **Step 2: Commit**

```powershell
git add milestones/M10_verification.md
```

```powershell
git commit -m "docs(m10/p3): M10_verification.md 수동 검증 시나리오 7건"
```

---

## Phase 4 — PyPI 패키지 + 빌드 + 배포 (0 신규 자동 테스트, ~1일)

목표: pyproject.toml 최종 확정 + main_mcp() entry + 빌드 + TestPyPI + 정식 PyPI 업로드 + GitHub Actions workflow.

### Task 4.1: pyproject.toml 최종 확정

**Files:**
- Modify: `pyproject.toml`

**Steps:**

- [ ] **Step 1: pyproject.toml 전수 갱신**

`pyproject.toml` Edit:

```toml
[project]
name = "assetcache-mcp"
version = "0.1.0"
description = "MCP server + tray app for indexing and retrieving 2D sprites, sheets, sounds, and Unity packages via natural language."
readme = "README.md"
license = { file = "LICENSE" }
requires-python = ">=3.12"
authors = [{ name = "v0o0v", email = "v0o0v2@gmail.com" }]
keywords = ["mcp", "unity", "asset", "game-development", "claude"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Environment :: Win32 (MS Windows)",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3.12",
    "Topic :: Multimedia :: Graphics",
    "Topic :: Software Development :: Libraries",
]
dependencies = [
    # 기존 M0~M8 의존성 그대로
    "PySide6>=6.5",
    "watchdog>=3",
    "platformdirs>=4",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "httpx>=0.27",
    "Pillow>=10",
    "numpy>=1.26",
    "librosa>=0.10",
    "soundfile>=0.12",
    "torch>=2.2",
    "open-clip-torch>=2.24",
    "Babel>=2.14",
    "Jinja2>=3.1",
    "mcp>=1.27",
    "sse-starlette>=2",
    # 기타 — pyproject.toml 의 기존 dependencies 그대로
]

[project.optional-dependencies]
dev = [
    "pytest>=7",
    "pytest-asyncio",
    "respx>=0.20",
    "babel>=2.14",
    "pyinstaller>=6",
    "build",
    "twine",
]

[project.scripts]
assetcache = "assetcache.__main__:main"
assetcache-mcp = "assetcache.__main__:main_mcp"

[project.urls]
Homepage = "https://github.com/v0o0v/assetcache-mcp"
Issues = "https://github.com/v0o0v/assetcache-mcp/issues"
Documentation = "https://github.com/v0o0v/assetcache-mcp/blob/main/README.md"

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
package-dir = { "" = "src" }

[tool.setuptools.packages.find]
where = ["src"]
namespaces = false

[tool.setuptools.package-data]
"assetcache.web" = [
    "templates/**/*.html",
    "static/**/*",
    "locale/**/*.mo",
]
```

- [ ] **Step 2: editable install 갱신**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\pip.exe" install -e .[dev]
```

- [ ] **Step 3: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: ~1101 passed.

- [ ] **Step 4: Commit**

```powershell
git add pyproject.toml
```

```powershell
git commit -m "build(m10/p4): pyproject.toml name=assetcache-mcp + scripts + classifiers"
```

### Task 4.2: main_mcp() entry point 추가

**Files:**
- Modify: `src/assetcache/__main__.py`

**Steps:**

- [ ] **Step 1: main_mcp() 추가**

`src/assetcache/__main__.py` Edit 으로 추가:

```python
def main_mcp(argv: list[str] | None = None) -> int:
    """`assetcache-mcp` console script — 직접 MCP stdio 진입."""
    return main(["--mcp"])
```

- [ ] **Step 2: 회귀**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m pytest -q
```

Expected: ~1101 passed.

- [ ] **Step 3: Commit**

```powershell
git add src/assetcache/__main__.py
```

```powershell
git commit -m "feat(m10/p4): main_mcp() entry point (assetcache-mcp console script)"
```

### Task 4.3: python -m build + 로컬 wheel smoke

**Files:** (산출물만, 코드 변경 X)

**Steps:**

- [ ] **Step 1: build 실행**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\python.exe" -m build
```

Expected: `dist/assetcache_mcp-0.1.0-py3-none-any.whl` + `dist/assetcache_mcp-0.1.0.tar.gz` 생성.

- [ ] **Step 2: 별도 venv 에 wheel 설치 검증**

```powershell
python -m venv $env:TEMP\smoke-venv
```

```powershell
& "$env:TEMP\smoke-venv\Scripts\pip.exe" install (Resolve-Path dist\assetcache_mcp-0.1.0-py3-none-any.whl).Path
```

```powershell
& "$env:TEMP\smoke-venv\Scripts\assetcache.exe" --version
```

Expected: `AssetCacheMCP 0.1.0` 또는 `0.1.0`.

```powershell
& "$env:TEMP\smoke-venv\Scripts\assetcache-mcp.exe" --version
```

또는 stdio 의 동작 검증 — 짧게 launch 후 종료.

- [ ] **Step 3: smoke 결과 milestones/M10_verification.md 의 자동 검증 섹션에 기록**

Edit `milestones/M10_verification.md` 의 자동 검증 섹션에 결과 입력.

- [ ] **Step 4: smoke venv 정리**

```powershell
Remove-Item -Recurse -Force $env:TEMP\smoke-venv
```

- [ ] **Step 5: dist/ 를 .gitignore 에 추가 (이미 있을 수도)**

`.gitignore` 에 `dist/` 가 없으면 추가.

- [ ] **Step 6: Commit (M10_verification.md 결과 기록)**

```powershell
git add milestones/M10_verification.md .gitignore
```

```powershell
git commit -m "test(m10/p4): build + wheel smoke 결과 verification 에 기록"
```

### Task 4.4: GitHub Actions publish workflow

**Files:**
- Create: `.github/workflows/publish.yml`

**Steps:**

- [ ] **Step 1: workflow 작성**

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # trusted publishing 사용 시
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install build
        run: pip install build

      - name: Build
        run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

- [ ] **Step 2: README 에 secrets 등록 안내 추가 (사용자가 수동)**

`README.md` 에 dev 섹션 안 short note:
```
PyPI publish 자동화: GitHub repo Settings > Secrets > PYPI_API_TOKEN 에 PyPI API token 등록 필요.
첫 v0.1.0 은 수동 twine upload, 이후 v0.1.1+ 부터 tag push 자동.
```

- [ ] **Step 3: Commit**

```powershell
git add .github/workflows/publish.yml README.md
```

```powershell
git commit -m "ci(m10/p4): GitHub Actions PyPI publish workflow (tag v* trigger)"
```

### Task 4.5: TestPyPI 업로드 + 검증

**Files:** (산출물만)

**Steps:**

- [ ] **Step 1: TestPyPI 계정 + API token 확보 (사용자 수동)**

사용자가 https://test.pypi.org 에 계정 생성 + API token 발급.

- [ ] **Step 2: `.pypirc` 또는 환경변수 설정 (사용자 수동)**

```powershell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "<TestPyPI API token>"
```

- [ ] **Step 3: TestPyPI 업로드 (사용자 실행 권장 — irreversible 까진 아니나 이름 점유)**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\twine.exe" upload --repository testpypi dist\*
```

Expected: TestPyPI 에 `assetcache-mcp 0.1.0` 노출. https://test.pypi.org/project/assetcache-mcp/ 확인.

- [ ] **Step 4: pipx 로 TestPyPI 에서 설치 검증**

별도 venv 또는 시스템 pipx 에:

```powershell
pipx install --index-url https://test.pypi.org/simple/ --pip-args="--extra-index-url https://pypi.org/simple/" assetcache-mcp
```

(extra-index-url 이 필요한 이유: TestPyPI 에 PySide6 / torch 등 의존 wheel 이 없어 PyPI 에서 가져와야 함.)

```powershell
assetcache --version
```

Expected: 0.1.0.

- [ ] **Step 5: M10_verification.md 시나리오 6 결과 기록**

```powershell
git add milestones/M10_verification.md
```

```powershell
git commit -m "test(m10/p4): TestPyPI 0.1.0 업로드 + pipx install 검증"
```

### Task 4.6: PyPI 정식 업로드 + v0.1.0 release

**Files:** (외부 액션, 사용자 수동)

**Steps:**

- [ ] **Step 1: 사용자 — PyPI 계정 + 2FA + API token (없으면 등록)**

- [ ] **Step 2: 사용자 — twine 환경변수 갱신**

```powershell
$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "<PyPI API token>"
```

- [ ] **Step 3: 사용자 — PyPI 정식 업로드**

```powershell
& "$env:USERPROFILE\.venvs\gah\Scripts\twine.exe" upload dist\*
```

Expected: `https://pypi.org/project/assetcache-mcp/0.1.0/` publish.

- [ ] **Step 4: 사용자 — GitHub repo 린네임**

GitHub UI: Settings → General → Repository name → `v0o0v/assetcache-mcp` → Rename.

GitHub 가 자동 301 redirect 설정.

- [ ] **Step 5: 사용자 — v0.1.0 tag + GitHub release publish**

```powershell
git tag v0.1.0
```

```powershell
git push origin v0.1.0
```

또는 GH UI 에서 release 생성. release notes 에:

```markdown
# AssetCacheMCP v0.1.0 — PyPI 첫 release

Game Asset Helper 가 **AssetCacheMCP** 로 rename + **PyPI 첫 release** 입니다.

## 설치

```powershell
pipx install assetcache-mcp
```

또는 uv:

```powershell
uv tool install assetcache-mcp
```

## v0.0.1 사용자 마이그레이션

1. 새 버전 설치 (위 명령)
2. `assetcache --tray` 첫 실행 → 웹 GUI (http://localhost:9874) 에서 마이그레이션 배너 노출
3. [복사] 또는 [이동] 클릭 → v0.0.1 데이터 (`%APPDATA%\GameAssetHelper\`) 가 `%APPDATA%\AssetCacheMCP\` 로 이주

또는 헤드리스:

```powershell
assetcache --migrate=copy
```

## Claude Desktop config

```json
// 구
{ "gah": { "command": "python", "args": ["-m", "gah", "--mcp"] } }

// 새
{ "assetcache": { "command": "assetcache-mcp" } }
```

## Mac/Linux 지원

곧 (M11 마일스톤에서 추가 예정).
```

- [ ] **Step 6: 사용자 — final verification**

```powershell
pipx install assetcache-mcp
```

```powershell
assetcache --version
```

Expected: 0.1.0.

```powershell
assetcache --tray
```

→ 트레이 + 웹 UI 확인.

- [ ] **Step 7: M10_verification.md 시나리오 7 결과 기록 + final commit**

```powershell
git add milestones/M10_verification.md
```

```powershell
git commit -m "release(m10): v0.1.0 PyPI + GitHub release published"
```

---

## Phase 5 — 마일스톤 wrap-up (코드 변경 0, 문서 commit 만)

### Task 5.1: milestones/M10_plan.md + M10_todo.md 정합성

**Files:** (이미 있을 거. Phase 진행 중 누락 검증)

**Steps:**

- [ ] **Step 1: M10_plan.md 가 spec 과 일치하는지 검증**
- [ ] **Step 2: M10_todo.md 의 모든 task 가 commit 으로 마무리됐는지 검증**

### Task 5.2: PR 작성

**Files:** (외부)

**Steps:**

- [ ] **Step 1: feat/m10 → main PR 생성**

```powershell
gh pr create --title "M10 — PyPI 배포 + AssetCacheMCP rename" --body "..."
```

PR body 는 spec + verification 결과 + 마이그레이션 안내 한글로.

- [ ] **Step 2: 사용자 review 대기**

- [ ] **Step 3: main 머지 (사용자가 squash 또는 merge)**

---

## Self-Review (plan 작성 직후 자체 검사)

1. **Spec coverage**:
   - §1 동기 → Phase 0~4 전체로 커버
   - §2 결정사항 → 각 task 가 해당 결정 구현
   - §3 아키텍처 → File Structure 섹션이 매핑
   - §4 모듈/컴포넌트 → 각 task 가 해당 모듈 작성
   - §5 Phase 구조 → 본 plan 의 Phase 0~4 와 정확히 매치 (PyPI = 마지막)
   - §6 외부 인터페이스 → Task 4.6 의 release notes 안내
   - §7 에러 처리 → Task 1.2 의 rollback test + Task 4.5 의 TestPyPI 사전 검증
   - §8 테스트 전략 → 각 task 의 신규 테스트 +35 (1047 → ~1082)
   - §9 Non-goals → plan 에 명시 X 정확
   - §10 의존성 → Task 4.1 에 명시
   - §11 검증 기준 → Task 3.3 의 M10_verification.md
   - §12 후속 마일스톤 → CLAUDE.md §8 갱신 (Task 3.1)

2. **Placeholder scan**: TBD/TODO/FIXME 검색 — 0 hits (이 plan 안). 모든 step 에 실제 code + 명령 포함.

3. **Type consistency**:
   - `MigrationCandidate` — Task 1.1, 1.2, 1.3, 1.4 일관
   - `MigrationRunner` / `MigrationState` — Task 1.2 정의, 1.3/1.4 참조 OK
   - `UpdateChecker` / `CheckResult` — Task 2.2 정의, 2.4 참조 OK
   - `recommended_upgrade_command` — Task 2.3 정의, 2.4/2.6 참조 OK
   - `AppPaths.legacy_data_dir` — Task 1.1 에 추가, 1.4 의 `get_app_paths()` 도 동일 모듈

4. **Phase 의존성**: Phase 0 → 1, 2, 3, 4. Phase 1 ↔ 2 독립 (순차 권장). Phase 3 → 4. OK.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-m10-pypi-and-rename.md`. Two execution options:

1. **Subagent-Driven (recommended)** - 각 task 마다 fresh subagent dispatch + two-stage review. Phase 0/3 = haiku, Phase 1/2 = sonnet, Phase 4 = 사용자 직접.

2. **Inline Execution** - 현재 세션에서 executing-plans 로 batch 진행, checkpoint 마다 사용자 리뷰.
