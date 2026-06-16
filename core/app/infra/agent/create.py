"""Agent create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_agent_values — raw value → ID resolution
  4. create_agent_artifact — junction writes
  5. create_denormalized_snapshot — agents_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.agent.permissions_context import (
    create_denormalized_snapshot,
    resolve_agent_values,
)
from app.infra.agent.refresh import refresh_agent_impl
from app.infra.agent.types import (
    AgentResultItem,
    CreateAgentApiRequest,
    CreateAgentApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.agent.create import (
    create_agent as create_agent_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "agent"


async def create_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateAgentApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateAgentApiResponse:
    """Agent bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_agent_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.agent.permissions import compute_can_create

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # ``idempotency_key`` is the originating tool call's ``calls_entry.id``.
    # The ``soft_calls_mv`` ledger holds (artifact, operation, artifact_id)
    # we need to act on. See project_soft_calls_entry_pattern. This runs
    # before the payload is read so a bare ack ({idempotency_key, accept})
    # need not carry ``agents``.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "create":
            raise HTTPException(
                status_code=404,
                detail="No pending agent create for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await create_agent_artifact(conn, id=target_id, soft=False)

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="create",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_agent_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return CreateAgentApiResponse(
            results=[
                AgentResultItem(
                    success=True,
                    agent_id=target_id,
                    message="Agent accepted" if accept else "Agent rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── First-call requirement ────────────────────────────────────────
    if request is None or not request.agents:
        raise HTTPException(
            status_code=400,
            detail="`request.agents` is required for first-call creation "
            "(or pass `idempotency_key` + `accept` for the ack call).",
        )

    items = request.agents
    if idempotency_key is not None and len(items) == 1 and items[0].id is None:
        items = [items[0].model_copy(update={"id": idempotency_key})]

    # ── Step 1: Profile context ────────────────────────────────────────

    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool,
            profile_id,
            redis,
            session_id=session_id,
        )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Permission check ───────────────────────────────────────

    if not compute_can_create(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        user_department_ids=profile.department_ids,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create agents.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[AgentResultItem] = []

    with timed("resolve_values"):
        async with pool.acquire() as conn:
            for idx, item in enumerate(items):
                item_errors = await resolve_agent_values(conn, redis, item, is_create=True)
                if item_errors:
                    has_errors = True
                    error_results.append(
                        AgentResultItem(
                            success=False,
                            message=f"Item {idx}: Validation errors",
                            errors=item_errors,
                        )
                    )
                else:
                    error_results.append(AgentResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateAgentApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[AgentResultItem] = []
    snapshot_ids: list[UUID] = []

    if not soft:
        for item in items:
            agents_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                model_id=item.model_id,
                rubric_id=item.rubric_ids[0] if item.rubric_ids else None,
                tool_ids=item.tool_ids,
                voice_ids=item.voice_ids,
                prompt_id=item.prompt_id,
                instruction_ids=item.instruction_ids,
            )
            snapshot_ids.append(agents_resource_id)

    with timed("db_write"):
        async with pool.acquire() as conn:
            async with transaction_with_writeback(conn):
             for idx, item in enumerate(items):
                combined_flag_ids = list(item.flag_ids or [])

                result = await create_agent_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    model_ids=[item.model_id] if item.model_id else None,
                    reasoning_level_ids=item.reasoning_level_ids,
                    temperature_level_ids=item.temperature_level_ids,
                    tool_ids=item.tool_ids,
                    voice_ids=item.voice_ids,
                    rubric_ids=item.rubric_ids,
                    # Seed the junction from the per-embodiment
                    # primary prompt — matches the pre-junction
                    # derivation and keeps new agents discoverable
                    # through the prompts section.
                    prompt_ids=[item.prompt_id] if item.prompt_id else None,
                    quality_ids=item.quality_ids,
                    agent_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    soft=soft,
                )

                # Soft writes append a pending ledger row tied to the
                # originating tool call so ack lookups can resolve
                # (artifact, operation, artifact_id).
                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="create",
                        artifact_id=result.id,
                    )

                results.append(
                    AgentResultItem(
                        success=True,
                        agent_id=result.id,
                        message=(
                            "Agent accepted"
                            if accept is not None and idempotency_key is not None
                            else "Agent created (pending acceptance)"
                            if soft
                            else "Agent created successfully"
                        ),
                    )
                )

    # Refresh soft_calls_mv synchronously after pending ledger insert so
    # subsequent reads (search, hydrate, group resolve) see the new row.
    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        with timed("refresh"):
            await refresh_agent_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                soft=soft,
                operation_key=idempotency_key or (results[0].agent_id if results else None),
            )

    return CreateAgentApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
