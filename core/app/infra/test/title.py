"""Test title — thin wrapper over shared title_group_impl.

Canonical logic lives in app.infra.group.title. This module only declares
the artifact type and per-artifact request/response subclasses so OpenAPI
schemas remain named per artifact.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.group.title import (
    TitleGroupRequest,
    TitleGroupResponse,
    title_group_impl,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.permissions import enforce_test_access_by_group

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
    """Rename a test group; see title_group_impl for full semantics.

    AUTHZ (write-IDOR guard, F3): ``title`` renames a group purely by the
    caller-supplied ``group_id`` — and unlike the ~18 other ``title`` wrappers
    (which rename org-shared catalog artifacts, safe by design), the *test*
    group chain is per-session-private (``group → session → owner``). Without
    scoping, any authenticated user could rename another user's private test
    group (cross-user defacement). The #372 sweep gated the test mutators but
    not this title sibling; mirror ``title_attempt_impl`` and route the
    test-artifact rename through the shared group-ownership gate before
    delegating to the generic ``title_group_impl``.
    """
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
    await enforce_test_access_by_group(
        pool, redis, group_id=group_id, requester=requester,
    )

    result = await title_group_impl(
        pool, redis, artifact_type=ARTIFACT_TYPE, **kwargs,
    )
    return TitleTestApiResponse.model_validate(result.model_dump())
