"""M5 — HTML 페이지 라우트 (라우터 prefix 없음).

`/` 는 `/library` 로 redirect. 각 페이지가 `base.html` 을 extend.
"""
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse


router = APIRouter(tags=["pages"])


@router.get("/", include_in_schema=False)
def page_root():
    """루트 경로 → 라이브러리 페이지로 리다이렉트."""
    return RedirectResponse(url="/library", status_code=307)


@router.get("/library", response_class=HTMLResponse)
def page_library(request: Request) -> HTMLResponse:
    """라이브러리 페이지 — 검색 바 + 결과 영역 + 사이드 패널 placeholder."""
    templates = request.app.state.templates
    deps = request.app.state.deps
    return templates.TemplateResponse(
        request=request,
        name="library.html",
        context={"deps": deps, "page": "library"},
    )


# /packs, /labels/admin 은 Phase 5 가 채움
