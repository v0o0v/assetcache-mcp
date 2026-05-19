"""Smoke test: every module of assetcache must import without side effects."""

from __future__ import annotations

import importlib


MODULES = [
    "assetcache",
    "assetcache.__main__",
    "assetcache.config",
    "assetcache.logging_setup",
    "assetcache.platform",
    "assetcache.platform.single_instance",
    "assetcache.app",
    "assetcache.tray",
    "assetcache.core",
    "assetcache.core.asset_kind",
    "assetcache.core.manifest",
    "assetcache.core.store",
    "assetcache.core.pack_manager",
    "assetcache.core.scanner",
    "assetcache.core.watcher",
    # M3 신규 모듈
    "assetcache.core.search",
    "assetcache.core.consistency",
    "assetcache.core.usage_tracker",
    "assetcache.mcp",
    "assetcache.mcp.models",
    "assetcache.mcp.tools",
    "assetcache.mcp.server",
]


def test_all_modules_importable() -> None:
    for name in MODULES:
        importlib.import_module(name)
