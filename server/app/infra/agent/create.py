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
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.agent.permissions_context import (
    create_denormalized_snapshot,
    resolve_agent_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.agent.create import (
    create_agent as create_agent_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


class CreateAgentItem(BaseModel):
    """Single agent item for create — no agent_id.

    Required fields (name): provide ID or value.
    """

    id: UUID | None = Field(None, description="Client-provided UUID for the agent")

    # Dual-mode: name
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    # Dual-mode: departments (match by name)
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for matching")
    # ID-only fields
    flag_ids: list[UUID] | None = Field(None, description="Associated flag UUIDs")
    model_ids: list[UUID] | None = Field(None, description="Associated model UUIDs")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Associated reasoning level UUIDs")
    temperature_level_ids: list[UUID] | None = Field(None, description="Associated temperature level UUIDs")
    tool_ids: list[UUID] | None = Field(None, description="Associated tool UUIDs")
    voice_ids: list[UUID] | None = Field(None, description="Associated voice UUIDs")
    agent_ids: list[UUID] | None = Field(None, description="Associated agent resource UUIDs")


class AgentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


class AgentResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    agent_id: UUID | None = Field(None, description="UUID of the affected agent")
    message: str = Field(..., description="Human-readable result message")
    errors: list[AgentFieldError] | None = Field(None, description="List of per-field errors")


class CreateAgentApiResponse(BaseModel):
    """Response model for bulk create agent endpoint."""

    results: list[AgentResultItem] = Field(..., description="List of operation results")


async def create_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Agent bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_agent_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.agent.permissions import compute_can_create

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
        draft_id=draft_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Permission check ───────────────────────────────────────

    if not compute_can_create(
        user_role=profile.role,
        user_department_ids=profile.department_ids,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create agents.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[AgentResultItem] = []

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
        return CreateAgentApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[AgentResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        agents_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            model_id=item.model_ids[0] if item.model_ids else None,
            tool_ids=item.tool_ids,
            voice_ids=item.voice_ids,
        )

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_agent_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids,
                    model_ids=item.model_ids,
                    reasoning_level_ids=item.reasoning_level_ids,
                    temperature_level_ids=item.temperature_level_ids,
                    tool_ids=item.tool_ids,
                    voice_ids=item.voice_ids,
                    agent_ids=[agents_resource_id],
                )

        results.append(
            AgentResultItem(
                success=True,
                agent_id=result.id,
                message="Agent created successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["agents"], redis=redis)

    return CreateAgentApiResponse(results=results)
