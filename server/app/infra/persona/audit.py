"""Persona audit wrappers for canonical tool-backed route operations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.events.audit import (
    resolve_artifact_operation_tool,
    run_artifact_operation_with_audit,
)
from app.infra.tool_graph import SettingsToolGraph

T = TypeVar("T")


def resolve_persona_operation_tool(
    tool_graph: SettingsToolGraph,
    *,
    operation: str,
) -> UUID | None:
    """Pick the canonical tool for a persona artifact operation."""
    return resolve_artifact_operation_tool(
        tool_graph,
        artifact="persona",
        operation=operation,
    )


async def run_persona_operation_with_audit(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    operation: str,
    runner: Callable[[], Awaitable[T]],
    arguments: dict[str, Any],
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
    response_model: type[T] | None = None,
    role: str = "assistant",
    mcp: bool = False,
    upload_folder: Path | None = None,
) -> T:
    """Execute a persona operation and persist a tool-call audit receipt when possible.

    TODO: Add typed progress entry emission once call lifecycle progress exists.
    """
    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="persona",
        profile_id=profile_id,
        operation=operation,
        runner=runner,
        arguments=arguments,
        session_id=session_id,
        draft_id=draft_id,
        group_id=group_id,
        bypass_cache=bypass_cache,
        response_model=response_model,
        role=role,
        mcp=mcp,
        upload_folder=upload_folder,
    )
