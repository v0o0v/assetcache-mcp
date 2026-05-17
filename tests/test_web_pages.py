"""M5 — HTML 페이지 라우트 검증 (/, /library)."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient

from gah.web.app import build_app


@pytest.fixture
def client(deps_fixture):
    with TestClient(build_app(deps_fixture)) as c:
        yield c


def test_root_redirects_to_library(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)
    assert "/library" in r.headers.get("location", "")


def test_library_page_returns_200_html(client):
    r = client.get("/library")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_library_page_contains_search_bar(client):
    r = client.get("/library")
    # 검색 바 (HTMX hx-post → /ui/search-results)
    assert "hx-post" in r.text
    assert "/ui/search-results" in r.text


def test_library_page_includes_static_assets(client):
    r = client.get("/library")
    # HTMX, Alpine, CSS 로드 확인
    assert "htmx.min.js" in r.text
    assert "alpine.min.js" in r.text
    assert "main.css" in r.text


def test_library_page_initializes_alpine_stores(client):
    r = client.get("/library")
    # Alpine.store('search', ...) 초기화 코드 존재
    assert "Alpine.store" in r.text
    assert "'search'" in r.text or '"search"' in r.text
    assert "advanced" in r.text  # ⚙ 토글 상태


def test_library_page_has_advanced_toggle(client):
    r = client.get("/library")
    # ⚙ 고급 버튼 존재
    assert "고급" in r.text  # Korean label


def test_search_bar_has_300ms_debounce(client):
    r = client.get("/library")
    assert "delay:300ms" in r.text


def test_search_bar_targets_results(client):
    r = client.get("/library")
    assert 'hx-target="#results"' in r.text


def test_library_page_has_load_trigger(client):
    """페이지 로드 시 자동으로 디폴트 결과 fetch."""
    r = client.get("/library")
    assert "load" in r.text  # hx-trigger="... , load"


def test_results_container_exists(client):
    r = client.get("/library")
    assert 'id="results"' in r.text


# ── Task 2.7: 결과 툴바 ─────────────────────────────────────────────────


def test_results_grid_includes_toolbar(client):
    """결과 영역에 그리드/리스트 토글 + 카드 크기 + 정렬 + 카운트."""
    r = client.post("/ui/search-results", json={"query": "", "count": 5})
    assert r.status_code == 200
    assert "results-toolbar" in r.text
    assert "view-toggle" in r.text or "view-mode" in r.text


def test_results_toolbar_has_size_buttons(client):
    r = client.post("/ui/search-results", json={"query": "", "count": 5})
    # S/M/L 버튼 — Alpine 의 $store.search.cardSize 조작
    assert "cardSize" in r.text


def test_results_toolbar_has_sort_dropdown(client):
    r = client.post("/ui/search-results", json={"query": "", "count": 5})
    # 정렬 옵션 포함 검증
    assert "정렬" in r.text or "sort" in r.text


def test_results_toolbar_shows_total_count(client):
    """총 자산 카운트 표시."""
    r = client.post("/ui/search-results", json={"query": "", "count": 5})
    # 빈 라이브러리 → "0 자산" 같은 표현
    assert "자산" in r.text or "total" in r.text
