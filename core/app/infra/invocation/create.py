"""Invocation create logic — instantiate a test_invocation_entry from a benchmark template.

Mirrors app.infra.attempt.chat_create. Canonical request pair is
``test_id + invocation_id`` — ``invocation_id`` is the benchmark
``invocation_entry.id`` (the template); there is no separate
"template_*" concept, exactly as ``chat_id`` on chat_create is the
parent ``chat_entry.id``.

When ``invocation_id`` is set we materialize from that template:
``tmpl.model_ids → agent_ids`` via the agents resource (one agent per
model), ``tmpl.model_rubric_ids → rubric_ids`` via model_rubrics, and
the rest of the bundle is copied. Caller-supplied fields override.

Called by:
  - POST /test/invocation/create (HTTP)
  - LLM tool ``test.invocation_create`` during /test/generate
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
from app.tools.entries.groups.get import get_groups
from app.tools.entries.invocation.get import get_invocations
from app.tools.entries.runs.create import create_run
from app.tools.entries.test.get import get_tests
from app.infra.invocation.refresh import refresh_invocation_impl
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.resources.agents.search import search_agents
from app.tools.resources.model_rubrics.get import get_model_rubrics


class CreateInvocationApiRequest(BaseModel):
    """Create a test_invocation_entry on an existing test.

    Mirrors CreateAttemptChatApiRequest. ``invocation_id`` is the
    benchmark ``invocation_entry.id`` (the template); the materialized
    ``test_invocation_entry`` inherits its bundle. Caller-supplied
    fields override template defaults.
    """

    test_id: UUID
    invocation_id: UUID | None = None

    title: str = ""
    use_custom: bool = False
    position: int | None = None

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
    **_kwargs,
) -> CreateInvocationApiResponse:
    """Create a new test_invocation_entry bound to a test."""
    identity = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if not identity or not identity.profiles_id:
        raise HTTPException(status_code=401, detail="Profile context not found")

    if not has_permission(identity.role_permissions, "test", "invocation_create"):
        raise HTTPException(status_code=403, detail="Not allowed to create invocations")

    # Canonical group resolve — same shape /attempt/chat/create uses.
    from app.infra.group.resolve import resolve_group_impl
    group_result = await resolve_group_impl(
        pool, redis,
        artifact_type="test",
        profile_id=profile_id,
        session_id=session_id,
        include_history=False,
    )
    group_id = group_result.group_id

    async with pool.acquire() as conn:
        tests = await get_tests(conn, [request.test_id], redis)
        if not tests:
            raise HTTPException(status_code=404, detail=f"Test {request.test_id} not found")

        groups = await get_groups(conn, [group_id], redis)
        if not groups or groups[0].session_id is None:
            raise HTTPException(status_code=400, detail="Group has no session_id")
        group_session_id = groups[0].session_id

        # ── Template path: derive defaults from the benchmark invocation_entry.
        # Caller-supplied fields win over template defaults.
        tmpl_agent_ids: list[UUID] = []
        tmpl_rubric_ids: list[UUID] = []
        tmpl_position: int = 0
        tmpl_use_custom: bool = False
        tmpl_dept: list[UUID] = []
        tmpl_voice: list[UUID] = []
        tmpl_temp: list[UUID] = []
        tmpl_reason: list[UUID] = []
        tmpl_modality: list[UUID] = []
        tmpl_quality: list[UUID] = []

        if request.invocation_id is not None:
            tmpls = await get_invocations(conn, [request.invocation_id], redis)
            if not tmpls:
                raise HTTPException(
                    status_code=404,
                    detail=f"Template invocation {request.invocation_id} not found",
                )
            tmpl = tmpls[0]

            # model_ids → agent_ids: one agent per model (first match wins).
            if tmpl.model_ids:
                agents = await search_agents(
                    conn, redis,
                    model_ids=list(tmpl.model_ids),
                    limit_count=100,
                    bypass_cache=True,
                )
                # Preserve template model order; pick the first agent per model.
                agents_by_model: dict[UUID, UUID] = {}
                for a in agents:
                    if a.model_id and a.model_id not in agents_by_model:
                        agents_by_model[a.model_id] = a.id
                tmpl_agent_ids = [
                    agents_by_model[mid] for mid in tmpl.model_ids if mid in agents_by_model
                ]

            # model_rubric_ids → rubric_ids via model_rubrics.rubric_id.
            if tmpl.model_rubric_ids:
                mrs = await get_model_rubrics(
                    conn, list(tmpl.model_rubric_ids), redis, bypass_cache=True,
                )
                tmpl_rubric_ids = [mr.rubric_id for mr in mrs if mr.rubric_id]

            tmpl_position = tmpl.position or 0
            tmpl_use_custom = bool(tmpl.use_custom)
            tmpl_dept = list(tmpl.department_ids or [])
            tmpl_voice = list(tmpl.voice_ids or [])
            tmpl_temp = list(tmpl.temperature_level_ids or [])
            tmpl_reason = list(tmpl.reasoning_level_ids or [])
            tmpl_modality = list(tmpl.modality_ids or [])
            tmpl_quality = list(tmpl.quality_ids or [])

        # ── Pre-satisfied locking — mirrors attempt/chat_create.py:448-464.
        # When use_custom is False (the canonical default path) and the
        # template already has a value for a section, the caller MUST NOT
        # also pass an override for that section. The eval author already
        # decided; the materialized row inherits the template's choice.
        # This is the hard rail behind the prompt's "skip locked" rule.
        opt_in = bool(request.use_custom) or tmpl_use_custom
        if not opt_in:
            locked_violations: list[str] = []
            if tmpl_agent_ids and request.agent_ids:
                locked_violations.append(
                    "agent_ids (server auto-resolves from template's model_ids)"
                )
            if tmpl_rubric_ids and request.rubric_ids:
                locked_violations.append(
                    "rubric_ids (server auto-resolves from template's model_rubric_ids)"
                )
            if tmpl_quality and request.quality_ids:
                locked_violations.append("quality_ids")
            if tmpl_dept and request.department_ids:
                locked_violations.append("department_ids")
            if tmpl_voice and request.voice_ids:
                locked_violations.append("voice_ids")
            if tmpl_temp and request.temperature_level_ids:
                locked_violations.append("temperature_level_ids")
            if tmpl_reason and request.reasoning_level_ids:
                locked_violations.append("reasoning_level_ids")
            if tmpl_modality and request.modality_ids:
                locked_violations.append("modality_ids")
            if locked_violations:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Sections already configured on the template — "
                        "set use_custom=true to override, or omit these fields "
                        f"to inherit: {', '.join(locked_violations)}"
                    ),
                )

        # Caller overrides win.
        agent_ids = request.agent_ids if request.agent_ids is not None else (tmpl_agent_ids or None)
        rubric_ids = request.rubric_ids if request.rubric_ids is not None else (tmpl_rubric_ids or None)
        quality_ids = request.quality_ids if request.quality_ids is not None else (tmpl_quality or None)
        department_ids = request.department_ids if request.department_ids is not None else (tmpl_dept or None)
        voice_ids = request.voice_ids if request.voice_ids is not None else (tmpl_voice or None)
        reasoning_level_ids = request.reasoning_level_ids if request.reasoning_level_ids is not None else (tmpl_reason or None)
        temperature_level_ids = request.temperature_level_ids if request.temperature_level_ids is not None else (tmpl_temp or None)
        modality_ids = request.modality_ids if request.modality_ids is not None else (tmpl_modality or None)
        position = request.position if request.position is not None else tmpl_position
        use_custom = request.use_custom or tmpl_use_custom

        run = await create_run(conn, redis, group_id=group_id, session_id=group_session_id)
        call = await create_call(conn, redis, run_id=run.id, session_id=group_session_id)

        result = await create_test_invocation(
            conn,
            redis, test_id=request.test_id,
            call_id=call.id,
            title=request.title,
            use_custom=use_custom,
            position=position,
            agent_ids=agent_ids,
            rubric_ids=rubric_ids,
            quality_ids=quality_ids,
            department_ids=department_ids,
            voice_ids=voice_ids,
            reasoning_level_ids=reasoning_level_ids,
            temperature_level_ids=temperature_level_ids,
            modality_ids=modality_ids,
        )

    await refresh_invocation_impl(
        pool, redis, profile_id=profile_id, session_id=session_id,
        targets=["test_invocation_mv"],
    )

    return CreateInvocationApiResponse(invocation_id=result.id)
