"""Generation progress tracking — pure business logic with emit: EmitFn.

Tracks resource/entry completions via run_tracker.record_unit_soft
and emits progress percentage to generation_channel.
"""

from __future__ import annotations

from typing import Any

from app.infra.websocket.generation_tracker import record_resource_complete
from app.infra.websocket.generation_types import GenerationProgressData
from app.infra.websocket.run_tracker import record_unit_soft
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def resolve_generation_progress_target(
    data: dict[str, Any],
) -> tuple[str, str, str | None]:
    """Resolve the completed target kind, name, and id from a tool result."""
    tool_result = data.get("result") or {}
    resource_id = tool_result.get("resource_id")
    entry_id = tool_result.get("entry_id")
    resource_type = tool_result.get("resource_type") or data.get("resource_type", "")
    entry_type = tool_result.get("entry_type") or ""

    target_type = "resource" if resource_id else "entry"
    target_name = resource_type if resource_id else entry_type
    result_id = resource_id or entry_id
    return target_type, target_name, result_id


def build_generation_progress_payload(
    data: dict[str, Any],
    *,
    completed: int,
    total: int,
    last_completed_resource: str,
) -> dict[str, Any]:
    """Build the generation_channel progress payload."""
    percentage = round((completed / total) * 100) if total > 0 else 0
    return GenerationProgressData(
        sid=data.get("sid", ""),
        artifact_type=data.get("artifact_type", "unknown"),
        group_id=data.get("group_id", ""),
        run_id=data.get("run_id"),
        completed_resources=completed,
        total_resources=total,
        percentage=min(percentage, 100),
        last_completed_resource=last_completed_resource,
    ).model_dump(mode="json")


async def generation_progress_impl(
    data: dict[str, Any], *, emit: EmitFn, redis: Any
) -> None:
    """Track resource/entry completions and emit progress percentage."""
    event_type = data.get("event_type")
    if event_type != "tool_result":
        return

    sid = data.get("sid", "")
    run_id = data.get("run_id")
    if not sid or not run_id:
        return

    tool_result = data.get("result") or {}
    resource_id = tool_result.get("resource_id")
    entry_id = tool_result.get("entry_id")

    if not resource_id and not entry_id:
        return

    target_type, target_name, result_id = resolve_generation_progress_target(data)
    resource_type = tool_result.get("resource_type") or data.get("resource_type", "")

    # New tracker: record_unit_soft
    agent_id = data.get("agent_id") or "unknown"

    try:
        completed, total = await record_unit_soft(
            redis,
            run_id=run_id,
            agent_id=agent_id,
            target_type=target_type,
            target_name=target_name,
            result_id=result_id,
        )
    except Exception as e:
        logger.exception(f"Failed to record unit progress: {e}")
        completed, total = 1, 1

    # Legacy tracker: also update for backward compat during migration
    if resource_id:
        try:
            await record_resource_complete(run_id, resource_type)
        except Exception:
            pass  # Best-effort legacy compat

    await emit(
        [
            internal_event(
                "generation_channel",
                build_generation_progress_payload(
                    data,
                    completed=completed,
                    total=total,
                    last_completed_resource=target_name,
                ),
            )
        ]
    )
