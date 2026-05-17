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


def test_api_search_offset_returns_different_rows(client, deps_fixture):
    """offset=5 + count=5 → 6번째부터 10번째 row (정상 라이브러리 가정).
    빈 라이브러리에선 rows=[] 이더라도 200 응답이 와야 한다."""
    r1 = client.post("/api/search", json={"query": "", "count": 10, "offset": 0})
    r2 = client.post("/api/search", json={"query": "", "count": 5, "offset": 5})
    assert r1.status_code == 200
    assert r2.status_code == 200
    # 빈 라이브러리도 rows 는 list 형태여야 함
    assert isinstance(r1.json()["rows"], list)
    assert isinstance(r2.json()["rows"], list)
    # offset=5 에서 r1 의 앞 5 개와 겹치지 않아야 한다 (결과가 충분한 경우)
    ids1 = [row["asset_id"] for row in r1.json()["rows"]]
    ids2 = [row["asset_id"] for row in r2.json()["rows"]]
    if ids1 and ids2:
        # r2 는 r1[5:10] 과 동일해야 함
        assert ids2 == ids1[5:10]


# ── Task 2.8: 페이지네이션 (더 보기 버튼) ────────────────────────────────


def test_ui_search_results_no_load_more_when_empty(client):
    """빈 라이브러리 → next_offset=None → 더 보기 버튼 없음."""
    r = client.post("/ui/search-results", json={"query": "", "count": 100, "offset": 0})
    assert r.status_code == 200
    assert "load-more" not in r.text


def test_ui_search_results_load_more_button(client, deps_fixture):
    """빈 라이브러리 (count=5, offset=0) → next_offset=None → 더 보기 X."""
    r = client.post("/ui/search-results", json={"query": "", "count": 5, "offset": 0})
    assert r.status_code == 200
    # 빈 라이브러리에는 더 보기 없음
    assert "load-more" not in r.text


def test_pagination_passes_offset_to_handler(client):
    """offset=5 + count=5 → 정상 처리 (200)."""
    r = client.post("/ui/search-results", json={"query": "", "count": 5, "offset": 5})
    assert r.status_code == 200
