"""Attempt title — thin wrapper over shared title_group_impl.

Canonical logic lives in app.infra.group.title. This module only declares
the artifact type and per-artifact request/response subclasses so OpenAPI
schemas remain named per artifact.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.attempt.permissions import enforce_attempt_access_by_group
from app.infra.group.title import (
    TitleGroupRequest,
    TitleGroupResponse,
    title_group_impl,
)
from app.infra.profile_identity_context import resolve_profile_identity_context

ARTIFACT_TYPE = "attempt"


class TitleAttemptApiRequest(TitleGroupRequest):
    """Request body for POST /attempt/title."""


class TitleAttemptApiResponse(TitleGroupResponse):
    """Response body for POST /attempt/title."""


async def title_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    **kwargs,
) -> TitleAttemptApiResponse:
    """Rename a attempt group; see title_group_impl for full semantics.

    AUTHZ (write-IDOR guard, M1 sibling): ``title`` renames a group purely by
    the caller-supplied ``group_id`` — without scoping, any authenticated user
    could rename another user's attempt group. Route the *attempt*-artifact
    rename through the shared group-ownership gate (group → session → owner)
    before delegating to the generic ``title_group_impl``. (The generic impl
    serves multiple artifacts, so the attempt-specific gate lives here in the
    attempt wrapper.)
    """
    # Resolve the group_id the caller is targeting from either the request body
    # or the flattened kwarg, mirroring title_group_impl's own resolution.
    request = kwargs.get("request")
    group_id = kwargs.get("group_id")
    if request is not None and getattr(request, "group_id", None) is not None:
        group_id = request.group_id
    if isinstance(group_id, str):
        group_id = UUID(group_id)

    profile_id = kwargs.get("profile_id")
    requester = (
        await resolve_profile_identity_context(pool, profile_id, redis)
        if profile_id is not None
        else None
    )
    await enforce_attempt_access_by_group(
        pool, redis, group_id=group_id, requester=requester,
    )

    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleAttemptApiResponse.model_validate(result.model_dump())
