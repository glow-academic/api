"""Test group — thin wrapper over shared resolve_group_impl + orchestration entry.

Canonical group-resolve logic lives in app.infra.group.resolve. This module
declares the artifact type and per-artifact request/response subclasses so
OpenAPI schemas remain named per artifact, and hosts the test-specific
sequential-run orchestration entry point.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from redis.asyncio import Redis

from app.infra.globals import get_pool
from app.infra.group.resolve import (
    GroupResolveRequest,
    GroupResolveResponse,
    resolve_group_impl,
)
from app.infra.websocket.socket_event import make_emit
from app.infra.websocket.test_events_impl import test_group_impl

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


# ---------------------------------------------------------------------------
# Orchestration handler (sequential test runs in a group)
# ---------------------------------------------------------------------------


async def test_group_internal_impl(data: dict[str, Any], *, emit=None) -> None:
    """Run canonical test group orchestration for any surface."""
    await test_group_impl(data, emit=emit or make_emit(), pool=get_pool())
