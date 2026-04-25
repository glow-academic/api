"""Invocation create logic — instantiate a test_invocation_entry from custom inputs.

Mirrors app.infra.attempt.chat_create — creates a new invocation row on a test
when the eval is `use_custom` and the user has supplied their inputs. After
this returns, the workflow can be proceeded with `force_proceed=True`.

Called by:
  - POST /test/invocation/create (HTTP)
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.calls.create import create_call
from app.tools.entries.runs.create import create_run
from app.tools.entries.test.get import get_tests
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation.refresh import refresh_test_invocation
from app.tools.entries.test_invocation.search import search_test_invocation_entries_internal
from app.tools.entries.groups.get import get_groups


class CreateInvocationApiRequest(BaseModel):
    """Create a test_invocation_entry on an existing test, optionally with
    multi-select resource selections supplied by the user."""

    test_id: UUID
    title: str = ""
    use_custom: bool = False
    position: int = 0

    agent_ids: list[UUID] | None = None
    rubric_ids: list[UUID] | None = None
    quality_ids: list[UUID] | None = None
    department_ids: list[UUID] | None = None
    voice_ids: list[UUID] | None = None
    reasoning_level_ids: list[UUID] | None = None
    temperature_level_ids: list[UUID] | None = None
    modality_ids: list[UUID] | None = None


class CreateInvocationApiResponse(BaseModel):
    invocation_id: UUID = Field(..., description="UUID of the created test invocation")


async def create_invocation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: CreateInvocationApiRequest,
) -> CreateInvocationApiResponse:
    """Create a new test_invocation_entry bound to a test."""
    identity = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if not identity or not identity.profiles_id:
        raise HTTPException(status_code=401, detail="Profile context not found")

    if not has_permission(identity.role_permissions, "test", "create"):
        raise HTTPException(status_code=403, detail="Not allowed to create invocations")

    async with pool.acquire() as conn:
        tests = await get_tests(conn, ids=[request.test_id])
        if not tests:
            raise HTTPException(status_code=404, detail=f"Test {request.test_id} not found")

        existing, _total = await search_test_invocation_entries_internal(
            conn,
            test_ids=[request.test_id],
            limit=1,
            bypass_mv=True,
        )
        group_id = existing[0].group_id if existing else None
        if group_id is None:
            raise HTTPException(
                status_code=400,
                detail="Cannot create invocation: test has no existing invocations to inherit group from",
            )

        groups = await get_groups(conn, [group_id])
        if not groups or groups[0].session_id is None:
            raise HTTPException(status_code=400, detail="Group has no session_id")
        group_session_id = groups[0].session_id

        run = await create_run(conn, group_id=group_id, session_id=group_session_id)
        call = await create_call(conn, run_id=run.id, session_id=group_session_id)

        result = await create_test_invocation(
            conn,
            test_id=request.test_id,
            call_id=call.id,
            title=request.title,
            use_custom=request.use_custom,
            position=request.position,
            agent_ids=request.agent_ids,
            rubric_ids=request.rubric_ids,
            quality_ids=request.quality_ids,
            department_ids=request.department_ids,
            voice_ids=request.voice_ids,
            reasoning_level_ids=request.reasoning_level_ids,
            temperature_level_ids=request.temperature_level_ids,
            modality_ids=request.modality_ids,
        )
        await refresh_test_invocation(conn)

    return CreateInvocationApiResponse(invocation_id=result.id)
