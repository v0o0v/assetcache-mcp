"""M5 — Claude request_user_pick 라우터 (Phase 4 가 채움)."""
from fastapi import APIRouter

router = APIRouter(tags=["picks"])  # /internal/user-pick 은 prefix 없음
