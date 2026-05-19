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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/tray.ico",
)
