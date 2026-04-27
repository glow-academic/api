"""Test group — thin wrapper over shared resolve_group_impl.

Canonical logic lives in app.infra.group.resolve. This module only declares
the artifact type and per-artifact request/response subclasses so OpenAPI
schemas remain named per artifact. Mirrors app.infra.attempt.group.
"""

from __future__ import annotations

import asyncpg
from redis.asyncio import Redis

from app.infra.group.resolve import (
    GroupResolveRequest,
    GroupResolveResponse,
    resolve_group_impl,
)

ARTIFACT_TYPE = "test"


class GroupTestApiRequest(GroupResolveRequest):
    """Request body for POST /test/group."""


class GroupTestApiResponse(GroupResolveResponse):
    """Response body for POST /test/group."""


async def group_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> GroupTestApiResponse:
    """Resolve/create a test group; see resolve_group_impl for full semantics."""
    result = await resolve_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return GroupTestApiResponse.model_validate(result.model_dump())
