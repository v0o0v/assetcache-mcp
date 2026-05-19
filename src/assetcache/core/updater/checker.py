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
