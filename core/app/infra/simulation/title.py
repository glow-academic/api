"""Simulation title — thin wrapper over shared title_group_impl.

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

ARTIFACT_TYPE = "simulation"


class TitleSimulationApiRequest(TitleGroupRequest):
    """Request body for POST /simulation/title."""


class TitleSimulationApiResponse(TitleGroupResponse):
    """Response body for POST /simulation/title."""


async def title_simulation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleSimulationApiResponse:
    """Rename a simulation group; see title_group_impl for full semantics."""
    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleSimulationApiResponse.model_validate(result.model_dump())
