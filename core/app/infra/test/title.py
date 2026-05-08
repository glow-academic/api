"""Test title — thin wrapper over shared title_group_impl.

Canonical logic lives in app.infra.group.title. This module only declares
the artifact type and per-artifact request/response subclasses so OpenAPI
schemas remain named per artifact.
"""

from __future__ import annotations

import asyncpg
from redis.asyncio import Redis

from app.infra.group.title import (
    TitleGroupRequest,
    TitleGroupResponse,
    title_group_impl,
)

ARTIFACT_TYPE = "test"


class TitleTestApiRequest(TitleGroupRequest):
    """Request body for POST /test/title."""


class TitleTestApiResponse(TitleGroupResponse):
    """Response body for POST /test/title."""


async def title_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleTestApiResponse:
    """Rename a test group; see title_group_impl for full semantics."""
    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleTestApiResponse.model_validate(result.model_dump())
