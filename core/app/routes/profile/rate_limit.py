"""Profile rate-limit status endpoint — the unified "have I exceeded my
request limit?" read (SEC3 read layer).

Generation entry points enforce the per-profile ``request_limit`` via
``enforce_request_limit`` (a fixed-window Redis counter). Until this, the only
way to learn your standing was to be rejected with a 429. This exposes the same
counter read-only so a client can surface remaining quota + a reset countdown
proactively. Self-scoped — a profile may always read its own quota — so it needs
only authentication (the middleware-populated ``request.state.profile_id``), no
extra permission gate, and it never goes through the cached context build (the
count must be live).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.request_limit import (
    RequestLimitStatus,
    get_request_limit_status,
)
from app.infra.profile_identity_context import resolve_profile_identity_context

router = APIRouter()


@router.get("/rate_limit", response_model=RequestLimitStatus)
async def get_profile_rate_limit(http_request: Request) -> RequestLimitStatus:
    """Return the caller's current request-limit usage for the metered
    ``generate`` operation: limit, used, remaining, whether exceeded, and the
    seconds until the window resets. Reads the counter without consuming quota.
    """
    profile_id = http_request.state.profile_id
    session_id = getattr(http_request.state, "session_id", None)
    pool = get_pool()
    redis = get_redis_client()

    identity = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id
    )
    if not identity:
        raise HTTPException(status_code=404, detail="Profile not found")

    return await get_request_limit_status(
        redis,
        profile_id=profile_id,
        request_limit=identity.request_limit,
        request_limit_interval=identity.request_limit_interval,
    )
