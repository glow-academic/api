"""Canonical kwargs entry point for the home dashboard.

The real implementation still lives at ``app.routes.attempt.home.get
.get_home_internal`` — this shim exposes it through the standard
``(pool, redis, *, profile_id, session_id=None, ...) -> Response`` shape
so ``execute_infra_operation`` can dispatch it like any other artifact
get.

The internal function is lazy-imported to avoid an import cycle (infra
modules load before routes). A future cleanup should move the internal
function here and point the route + websocket callers at it instead.
"""

from __future__ import annotations

from uuid import UUID

from app.infra.home.types import GetHomeResponse


async def get_home_impl(
    pool,
    redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetHomeResponse:
    from app.routes.attempt.home.get import get_home_internal

    return await get_home_internal(
        pool,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
    )
