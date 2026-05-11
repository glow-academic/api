"""System group — thin wrapper over shared resolve_group_impl.

Canonical logic lives in app.infra.group.resolve. This module declares the
artifact type and per-artifact request/response subclasses so OpenAPI schemas
remain named per artifact. When ``include_detail=True``, the response also
embeds the full runs+messages tree (was previously a separate /group/get
endpoint).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from pydantic import Field
from redis.asyncio import Redis

from app.infra.group.get import get_group_impl
from app.infra.group.resolve import (
    GroupResolveRequest,
    GroupResolveResponse,
    resolve_group_impl,
)
from app.infra.group.types import (
    GroupDetailResourceItem,
    GroupDetailRunWithMessages,
)

ARTIFACT_TYPE = "system"


class GroupSystemApiRequest(GroupResolveRequest):
    """Request body for POST /system/group.

    Inherits the lean resolve fields (``group_id``, ``snapshot_key``) and
    adds optional detail fields. When ``include_detail=True`` the response
    embeds the full group detail tree (runs + messages + hydrated resources).
    Internal audit-linking calls leave ``include_detail`` at the default
    ``False`` for the cheap lean shape.
    """

    include_detail: bool = Field(
        default=False,
        description="When True, embed runs+messages+hydrated resources alongside the lean resolve fields.",
    )
    message_limit: int | None = Field(
        default=None,
        description="When include_detail=True: maximum number of messages per run to return.",
    )
    message_offset: int | None = Field(
        default=None,
        description="When include_detail=True: message pagination offset.",
    )


class GroupSystemApiResponse(GroupResolveResponse):
    """Response body for POST /system/group.

    Lean fields (``group_id``, ``name``, ``snapshot_key``) are always populated.
    Detail fields below are populated only when the request set
    ``include_detail=True``.
    """

    group_exists: bool | None = Field(None, description="(detail) Whether the group exists in storage")
    actor_name: str | None = Field(None, description="(detail) Display name of the current actor")
    total_message_count: int | None = Field(None, description="(detail) Total number of messages in the group")
    runs: list[GroupDetailRunWithMessages] | None = Field(None, description="(detail) Runs with their messages")
    models: list[GroupDetailResourceItem] | None = Field(None, description="(detail) Models used in the group")
    agents: list[GroupDetailResourceItem] | None = Field(None, description="(detail) Agents used in the group")
    profiles: list[GroupDetailResourceItem] | None = Field(None, description="(detail) Profiles in the group")


async def group_system_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID | None = None,
    request: GroupSystemApiRequest | None = None,
    **kwargs,
) -> GroupSystemApiResponse:
    """Resolve/create a system group; optionally include full detail tree.

    Lean path (default) is the hot-path audit-link resolve — cheap.
    Detail path (``include_detail=True``) additionally calls ``get_group_impl``
    to populate runs/messages/resources; replaces the deleted /group/get route.
    """
    # Lean resolve always runs — it returns/creates the time-windowed group.
    resolve_kwargs = {**kwargs}
    if request is not None:
        resolve_kwargs["request"] = request
    if profile_id is not None:
        resolve_kwargs["profile_id"] = profile_id
    result = await resolve_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **resolve_kwargs,
    )
    response = GroupSystemApiResponse.model_validate(result.model_dump())

    # Detail path: hydrate full group detail tree on top of the lean response.
    if request is not None and request.include_detail and profile_id is not None:
        detail = await get_group_impl(
            pool,
            profile_id=profile_id,
            group_id=response.group_id,
            redis=redis,
            message_limit=request.message_limit,
            message_offset=request.message_offset,
        )
        response.group_exists = detail.group_exists
        response.actor_name = detail.actor_name
        response.total_message_count = detail.total_message_count
        response.runs = detail.runs
        response.models = detail.models
        response.agents = detail.agents
        response.profiles = detail.profiles
        # Detail's own ``group_name`` may be more authoritative than resolve's.
        if detail.group_name is not None:
            response.name = detail.group_name

    return response
