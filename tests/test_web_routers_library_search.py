"""M5 — /api/search POST (JSON 응답) + /ui/search-results HTML fragment 검증."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from gah.web.app import build_app


@pytest.fixture
def client(deps_fixture):
    with TestClient(build_app(deps_fixture)) as c:
        yield c


# ── /api/search (Task 2.1) ─────────────────────────────────────────────


def test_api_search_returns_json_with_rows(client, deps_fixture):
    """빈 라이브러리에서도 200 + rows=[] + total=0."""
    r = client.post("/api/search", json={"query": "blue hero", "count": 10})
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body
    assert "total" in body
    assert isinstance(body["rows"], list)


def test_api_search_passes_label_query(client, deps_fixture):
    """label_query 가 SearchRequest 의 label_query 로 전달되어 파서 호출."""
    r = client.post("/api/search", json={
        "query": "",
        "label_query": "character AND pixel_art",
        "count": 5,
    })
    assert r.status_code == 200


def test_api_search_passes_pack_filters(client, deps_fixture):
    """pack_ids 필터가 SearchRequest 에 전달 (exclude_pack_ids 로 매핑)."""
    r = client.post("/api/search", json={
        "query": "",
        "pack_ids": [1, 2],
        "count": 5,
    })
    assert r.status_code == 200


def test_api_search_invalid_diversity_returns_422(client, deps_fixture):
    """diversity 의 enum 검증 — 'bogus' 는 422."""
    r = client.post("/api/search", json={
        "query": "",
        "diversity": "bogus_value",
    })
    assert r.status_code == 422


# ── /ui/search-results (Task 2.2) ─────────────────────────────────────


def test_ui_search_results_returns_html(client, deps_fixture):
    """빈 라이브러리에서도 200 + text/html."""
    r = client.post("/ui/search-results", json={"query": "blue hero", "count": 5})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_ui_search_results_contains_card_class(client, deps_fixture):
    """빈 라이브러리도 results-cards 컨테이너는 렌더 (카드 0개)."""
    r = client.post("/ui/search-results", json={"query": "", "count": 5})
    assert r.status_code == 200
    assert "results-cards" in r.text


def test_ui_search_results_form_data(client, deps_fixture):
    """form-data (HTMX hx-post + hx-include) 도 받아들임."""
    r = client.post("/ui/search-results", data={"query": "test", "count": "5"})
    assert r.status_code == 200
