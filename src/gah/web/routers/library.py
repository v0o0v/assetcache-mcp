"""M5 — 라이브러리 페이지 라우터 (검색 + 결과 fragment + 썸네일).

두 라우터를 노출한다.
  - ``router``    : prefix="/api" — JSON 응답 (/search, /thumbnail/{id})
  - ``router_ui`` : prefix="/ui"  — HTML fragment (/search-results)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["library"])
router_ui = APIRouter(prefix="/ui", tags=["library-ui"])


# ── Pydantic 입력 모델 ─────────────────────────────────────────────────


class SearchBody(BaseModel):
    """POST /api/search 및 /ui/search-results 의 공통 입력 모델."""

    query: str = ""
    label_query: str | None = None
    project_id: str | None = None
    # pack_ids: SearchRequest 에 직접 매핑 필드 없음 — exclude_pack_ids 와 구별.
    # v1 에서는 pack_ids 를 무시하고 향후 필터 확장 시 활용.
    pack_ids: list[int] | None = None
    kind: str | None = None  # "sprite" | "sound" | None
    diversity: Literal["none", "mmr", "round_robin"] = "none"
    diversity_lambda: float | None = None
    count: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort: Literal[
        "score", "added_desc", "added_asc",
        "name_asc", "name_desc",
        "size_desc", "size_asc",
    ] = "score"
    # B 탭 칩 선택 + 매칭 모드 (Phase 3 에서 채움)
    labels: list[int] | None = None
    match_mode: Literal["all", "any", "none"] = "all"


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────


def _row_to_dict(row: Any) -> dict[str, Any]:
    """ResultRow dataclass → JSON-직렬화 가능 dict.

    ResultRow 필드: asset_id, pack_id, pack_name, path, score,
    score_breakdown, matched_labels, why, meta.
    name 은 path 의 basename 에서 추출.
    width / height / size_kb 는 meta 에 없으면 None.
    """
    from dataclasses import asdict, is_dataclass

    if is_dataclass(row) and not isinstance(row, type):
        d = asdict(row)
    elif hasattr(row, "model_dump"):
        d = row.model_dump()
    elif hasattr(row, "_asdict"):
        d = row._asdict()
    else:
        d = dict(row.__dict__)

    # name 파생 — path 의 stem
    if "name" not in d or not d.get("name"):
        raw_path = d.get("path", "")
        d["name"] = Path(raw_path).stem if raw_path else ""

    # sprite_meta 에서 width/height 추출 (meta dict 에 있을 수 있음)
    meta = d.get("meta") or {}
    d.setdefault("width", meta.get("width"))
    d.setdefault("height", meta.get("height"))
    d.setdefault("size_kb", meta.get("size_kb"))

    # matched_labels 는 list[dict] 이지만 asdict 이후 그대로 유지됨
    return d


def _apply_sort(rows: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    """sort 옵션에 따라 새 리스트 반환 (in-place 아님)."""
    if sort == "score":
        return rows  # HybridSearcher 가 이미 score DESC 정렬
    key_map = {
        "added_desc": ("added_at", True),
        "added_asc": ("added_at", False),
        "name_asc": ("name", False),
        "name_desc": ("name", True),
        "size_desc": ("size_kb", True),
        "size_asc": ("size_kb", False),
    }
    if sort not in key_map:
        return rows
    key, reverse = key_map[sort]
    try:
        return sorted(rows, key=lambda r: r.get(key) or 0, reverse=reverse)
    except TypeError:
        return rows  # 필드 타입 불일치 시 정렬 안 함


def _do_search(deps: Any, body: SearchBody) -> dict[str, Any]:
    """HybridSearcher 호출 핵심 로직 — /api/search 와 /ui/search-results 가 공유."""
    from ...core.search import SearchRequest

    sr = SearchRequest(
        query=body.query,
        label_query=body.label_query,
        project_id=body.project_id,
        kind=body.kind,
        diversity=body.diversity,
        diversity_lambda=body.diversity_lambda,
        count=body.count,
        # labels_all/any/none — match_mode 에 따라 분배 (Phase 3 활용)
        # body.labels 는 label id 리스트이나 SearchRequest 는 LabelFilter 리스트.
        # v1 에서는 label_query 로 처리하고 labels 는 패스.
    )
    response = deps.search.hybrid(sr)

    rows = [_row_to_dict(r) for r in response.results]
    # offset 클라이언트 슬라이싱 (SearchRequest 에 offset 없음)
    rows = rows[body.offset:body.offset + body.count]
    rows = _apply_sort(rows, body.sort)

    total = len(response.results)
    next_offset: int | None = (
        body.offset + body.count
        if (body.offset + body.count) < total
        else None
    )
    return {
        "query_id": response.query_id,
        "total": total,
        "rows": rows,
        "next_offset": next_offset,
    }


# ── /api/search POST ───────────────────────────────────────────────────


@router.post("/search")
def api_search(body: SearchBody, request: Request) -> dict[str, Any]:
    """HybridSearcher 호출 → JSON 결과.

    반환 형태::

        {
          "query_id": int,
          "total": int,
          "rows": [{"asset_id": ..., "name": ..., "score": ..., ...}],
          "next_offset": int | null,
        }
    """
    deps = request.app.state.deps
    return _do_search(deps, body)


# ── /ui/search-results POST (HTML fragment) ────────────────────────────


@router_ui.post("/search-results", response_class=HTMLResponse)
async def ui_search_results(request: Request) -> HTMLResponse:
    """HTMX hx-post 타깃. JSON body 또는 form-data 모두 수용.

    _results_grid.html 을 렌더해 반환한다.
    """
    deps = request.app.state.deps

    # content-type 에 따라 입력 파싱
    body_dict: dict[str, Any] = {}
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        body_dict = await request.json()
    else:
        # form-data (HTMX 의 hx-include 가 사용하는 경로)
        form = await request.form()
        body_dict = dict(form)
        # 숫자 필드 변환
        for k in ("count", "offset"):
            if k in body_dict and isinstance(body_dict[k], str):
                try:
                    body_dict[k] = int(body_dict[k])
                except ValueError:
                    body_dict.pop(k)
        # multi-value 필드는 v1 에서 무시
        body_dict.pop("pack_ids", None)
        body_dict.pop("labels", None)

    try:
        body = SearchBody(**body_dict)
    except Exception:
        body = SearchBody()  # 잘못된 입력 → 디폴트 (빈 결과)

    result = _do_search(deps, body)

    templates = request.app.state.templates
    ctx = {"request": request, **result}
    return templates.TemplateResponse(request=request, name="_results_grid.html", context=ctx)


# ── /api/thumbnail/{asset_id} GET ─────────────────────────────────────


@router.get("/thumbnail/{asset_id}")
def api_thumbnail(asset_id: int, request: Request) -> Response:
    """sprite 자산의 lazy 256×256 PNG. sound/spritesheet → 404.

    ETag 기반 조건부 요청 지원 (304 Not Modified).
    캐시 디렉터리: AppPaths.cache_dir / thumbnails/.
    """
    from ...core.thumbnails import ensure_thumbnail

    deps = request.app.state.deps
    asset = deps.store.get_asset_by_id(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    if asset.kind != "sprite":
        raise HTTPException(status_code=404, detail="thumbnail only for sprite kind")

    asset_path = Path(asset.path)
    cache_dir = deps.paths.cache_dir / "thumbnails"
    thumb = ensure_thumbnail(asset_path, asset.kind, cache_dir, asset_id, max_size=256)
    if thumb is None or not thumb.exists():
        raise HTTPException(status_code=404, detail="thumbnail generation failed")

    etag = f'"{thumb.stat().st_mtime_ns}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    return FileResponse(
        str(thumb),
        media_type="image/png",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=86400",
        },
    )
