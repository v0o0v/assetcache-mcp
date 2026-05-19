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
