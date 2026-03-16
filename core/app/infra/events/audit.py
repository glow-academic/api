"""Generic tool-backed audit wrappers for artifact operations."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.globals import UPLOAD_FOLDER, get_internal_sio
from app.infra.tool_graph import SettingsToolGraph
from app.infra.tools.entries.create_tool_call import create_tool_call

T = TypeVar("T")

internal_sio = get_internal_sio()


def resolve_artifact_operation_tool(
    tool_graph: SettingsToolGraph,
    *,
    artifact: str,
    operation: str,
) -> UUID | None:
    """Pick the canonical tool for an artifact operation from the tool graph."""
    matches = [
        tool
        for tool in tool_graph.tools
        if tool.target_type == "artifact"
        and tool.target == artifact
        and tool.operation == operation
    ]
    if not matches:
        return None

    best = min(matches, key=lambda tool: (tool.system_id, tool.agent_id, tool.tool_id))
    return best.tool_id


async def run_artifact_operation_with_audit(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    artifact: str,
    profile_id: UUID,
    operation: str,
    runner: Callable[..., Awaitable[T]],
    arguments: dict[str, Any],
    sid: str = "",
    rooms: list[str] | None = None,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    attempt_id: UUID | None = None,
    test_id: UUID | None = None,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    response_model: type[T] | None = None,
    role: str = "assistant",
    mcp: bool = False,
    upload_folder: Path | None = None,
) -> T:
    """Execute an artifact operation with lifecycle emission and optional audit.

    Emits to internal_sio:
      - {artifact}.{operation}.started
      - {artifact}.{operation}.completed (on success)
      - {artifact}.{operation}.failed (on error)

    Output handlers in ws/v5/output/ pick these up and forward to clients.
    When the tool graph has a matching tool, a tool-call audit record is persisted.
    """
    effective_rooms = rooms or ([sid] if sid else [])
    event_prefix = f"{artifact}.{operation}"

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        attempt_id=attempt_id,
        test_id=test_id,
        artifact_type=artifact,
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise PermissionError("Profile not found. Please sign in again.")

    tool_id = resolve_artifact_operation_tool(
        common.tool_graph,
        artifact=artifact,
        operation=operation,
    )
    effective_session_id = session_id or common.profile.session_id
    effective_group_id = group_id or common.profile.group_id
    effective_profiles_id = common.profile.profiles_id
    effective_upload_folder = upload_folder or UPLOAD_FOLDER

    can_audit = all([
        tool_id,
        effective_session_id,
        effective_group_id,
        effective_profiles_id,
    ])

    # --- Execute ---
    call_upload_id: UUID | None = None
    tool_error: Exception | None = None

    # Check if runner accepts call_id (orchestration runners do, CRUD lambdas don't)
    _runner_accepts_call_id = "call_id" in inspect.signature(runner).parameters

    async def _invoke_runner(call_id: UUID | None = None) -> Any:
        if _runner_accepts_call_id:
            return await runner(call_id=call_id)
        return await runner()

    if can_audit:
        async def _tool_fn(
            _conn: asyncpg.Connection, *, call_id: UUID | None = None, **_arguments: Any
        ) -> Any:
            result = await _invoke_runner(call_id=call_id)
            if hasattr(result, "model_dump"):
                return result.model_dump(mode="json")
            return result

        async with pool.acquire() as conn:
            audit_result = await create_tool_call(
                conn,
                group_id=effective_group_id,  # type: ignore[arg-type]
                session_id=effective_session_id,  # type: ignore[arg-type]
                profile_id=effective_profiles_id,  # type: ignore[arg-type]
                upload_folder=effective_upload_folder,
                tool_fn=_tool_fn,
                arguments=arguments,
                tool_id=tool_id,
                role=role,
                mcp=mcp,
                raise_on_error=False,
            )
        result_data = audit_result.result
        call_upload_id = audit_result.call_upload_id

        # Check if the runner failed (captured by create_tool_call)
        if isinstance(result_data, dict) and result_data.get("success") is False:
            tool_error = Exception(result_data.get("message", "Unknown error"))
    else:
        try:
            result_data = await _invoke_runner()
        except Exception as exc:
            await internal_sio.emit(f"{event_prefix}.failed", {
                "sid": sid,
                "rooms": effective_rooms,
                "message": str(exc),
                "error_type": type(exc).__name__,
            })
            raise

    # --- Started (call_id always available when audited) ---
    await internal_sio.emit(f"{event_prefix}.started", {
        "sid": sid,
        "rooms": effective_rooms,
        "call_id": str(call_upload_id) if call_upload_id else None,
        **arguments,
    })

    # --- Failed ---
    if tool_error is not None:
        await internal_sio.emit(f"{event_prefix}.failed", {
            "sid": sid,
            "rooms": effective_rooms,
            "call_id": str(call_upload_id) if call_upload_id else None,
            "message": str(tool_error),
            "error_type": type(tool_error).__name__,
        })
        raise tool_error

    # --- Completed ---
    output = (
        result_data.model_dump(mode="json")
        if hasattr(result_data, "model_dump")
        else result_data
        if isinstance(result_data, dict)
        else {}
    )

    await internal_sio.emit(f"{event_prefix}.completed", {
        "sid": sid,
        "rooms": effective_rooms,
        "call_id": str(call_upload_id) if call_upload_id else None,
        **output,
    })

    if response_model is not None:
        return response_model.model_validate(result_data)
    return result_data


def build_audit_arguments(data: dict[str, Any]) -> dict[str, Any]:
    """Strip transport-only keys from an audited operation payload."""
    return {
        key: value
        for key, value in data.items()
        if key not in {"sid", "profile_id", "session_id"}
    }
