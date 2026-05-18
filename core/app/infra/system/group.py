"""System group — thin wrapper over shared resolve_group_impl.

Canonical logic lives in app.infra.group.resolve. This module declares the
artifact type and per-artifact request/response subclasses so OpenAPI schemas
remain named per artifact. When ``include_detail=True``, ``resolve_group_impl``
populates the analytics fields (runs+messages+resources+actor_name+counts) on
the same response — no separate detail impl required.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from pydantic import Field
from redis.asyncio import Redis

from app.infra.group.resolve import (
    GroupResolveRequest,
    GroupResolveResponse,
    resolve_group_impl,
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

    All fields come straight from the parent ``GroupResolveResponse`` —
    the lean ``{group_id, name, snapshot_key, runs}`` plus the optional
    detail set (``group_exists``, ``actor_name``, ``total_message_count``,
    ``models``, ``agents``, ``profiles``) that ``resolve_group_impl``
    populates when called with ``include_resources=True``.
    """


async def group_system_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID | None = None,
    request: GroupSystemApiRequest | None = None,
    **kwargs,
) -> GroupSystemApiResponse:
    """Resolve/create a system group; optionally include full detail tree.

    Single canonical fan-out: ``resolve_group_impl`` handles both the
    lean and detail shapes via its ``include_resources`` flag. The
    audit-link callers (internal use) leave it at ``False``; the
    analytics ``include_detail=True`` request flips it on so the
    response carries models/agents/profiles/actor_name etc.
    """
    resolve_kwargs = {**kwargs}
    if request is not None:
        resolve_kwargs["request"] = request
    if profile_id is not None:
        resolve_kwargs["profile_id"] = profile_id

    include_resources = bool(request and request.include_detail)

    result = await resolve_group_impl(
        pool,
        redis,
        artifact_type=ARTIFACT_TYPE,
        include_resources=include_resources,
        **resolve_kwargs,
    )

    # ``GroupResolveResponse`` and ``GroupSystemApiResponse`` are
    # structurally identical (the latter is a naming subclass). Build
    # the API response from the resolved fields so OpenAPI keeps the
    # per-artifact schema name.
    return GroupSystemApiResponse(**result.model_dump())
