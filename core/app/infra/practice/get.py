"""Canonical kwargs entry point for the practice dashboard.

See ``app.infra.home.get`` for the shim pattern — same rationale here.
"""

from __future__ import annotations

from uuid import UUID

from app.infra.practice.types import GetPracticeResponse


async def get_practice_impl(
    pool,
    redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetPracticeResponse:
    from app.routes.attempt.practice.get import get_practice_internal

    return await get_practice_internal(
        pool,
        profile_id=profile_id,
        bypass_cache=bypass_cache,
    )
