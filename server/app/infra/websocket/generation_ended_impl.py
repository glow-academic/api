"""Generation resolution — business logic for test_ended events.

Pure business logic with injected dependencies (``emit``, ``conn``, ``redis``).
No socket handler registration, no module-level sio, no global I/O —
importable without triggering the socket tree.

Flow:
  1. Load resolution context from generation_resolution:{test_id} (stored by run_complete_impl)
  2. Call resolve_generation_winner(conn, test_id) → winning agent_id from DB grades
  3. Get all run_tracker units → promote winner's targets, fail losers
  4. Activate winner's dormant DB records
  5. Emit generation_complete via emit callback
  6. Cleanup Redis + run tracker
"""

from __future__ import annotations

import json
import uuid as _uuid
from typing import Any

import asyncpg

from app.infra.activate.activate import activate_rows
from app.infra.websocket.generation_types import GenerationCompleteData
from app.infra.websocket.resolve_generation_winner import resolve_generation_winner
from app.infra.websocket.run_tracker import (
    cleanup_run,
    fail_unit,
    get_all_units,
    promote_unit,
)
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def _table_name(target_type: str, target_name: str) -> str:
    """Derive DB table from run_tracker target."""
    suffix = "resource" if target_type == "resource" else "entry"
    return f"{target_name}_{suffix}"


def parse_generation_resolution_context(
    ctx: dict[str, Any],
    data: dict[str, Any],
) -> tuple[str | None, str, str, str, dict[str, Any]]:
    """Normalize stored resolution context with request fallbacks."""
    run_id = ctx.get("run_id")
    sid = ctx.get("sid", data.get("sid", ""))
    artifact_type = ctx.get("artifact_type", "unknown")
    group_id_str = ctx.get("group_id", "")
    resource_actions = ctx.get("resource_actions", {})
    return run_id, sid, artifact_type, group_id_str, resource_actions


def build_generation_complete_payload(
    *,
    sid: str,
    artifact_type: str,
    group_id: str,
    run_id: str,
    resource_actions: dict[str, Any],
) -> dict[str, Any]:
    """Build the final generation completion payload."""
    return GenerationCompleteData(
        sid=sid,
        artifact_type=artifact_type,
        group_id=group_id,
        run_id=run_id,
        success=True,
        message=f"{artifact_type.capitalize()} generation resolved",
        resource_actions=resource_actions,
    ).model_dump(mode="json")


async def generation_ended_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    conn: asyncpg.Connection,
    redis: Any,
) -> None:
    """Resolve contested targets after test grading completes.

    All I/O dependencies are injected — no globals accessed.
    Callable from socket handler, API, or tests.
    """
    test_id = data.get("test_id")
    if not test_id:
        return

    # Step 1: Resolve the winning agent from DB grades
    winner = await resolve_generation_winner(conn, test_id=_uuid.UUID(test_id))

    if not winner:
        logger.warning(f"No winner resolved for test {test_id}")
        return

    winning_agent_id = str(winner.winning_agent_id)
    logger.info(
        f"Generation test {test_id} resolved: winner={winning_agent_id} "
        f"score={winner.winning_score}"
    )

    # Step 2: Load resolution context (keyed by test_id, stored by run_complete_impl)
    ctx: dict[str, Any] = {}
    try:
        ctx_raw = await redis.get(f"generation_resolution:{test_id}")
        if ctx_raw:
            ctx = json.loads(ctx_raw)
    except Exception as e:
        logger.warning(f"Failed to load resolution context for test {test_id}: {e}")

    run_id, sid, artifact_type, group_id_str, resource_actions = (
        parse_generation_resolution_context(ctx, data)
    )
    if not run_id:
        logger.warning(f"No run_id in resolution context for test {test_id}")
        return

    # Step 3: Get all units and promote winner / fail losers
    units = await get_all_units(redis, run_id=run_id)

    for unit_key, unit_state in units.items():
        parts = unit_key.split(":", 2)
        if len(parts) != 3:
            continue
        agent_id, target_type, target_name = parts

        try:
            if agent_id == winning_agent_id:
                await promote_unit(
                    redis,
                    run_id=run_id,
                    agent_id=agent_id,
                    target_type=target_type,
                    target_name=target_name,
                )
                # Activate the dormant DB record
                if unit_state.result_id:
                    table = _table_name(target_type, target_name)
                    await activate_rows(
                        conn,
                        table=table,
                        ids=[_uuid.UUID(unit_state.result_id)],
                    )
                logger.info(
                    f"Promoted {agent_id}:{target_type}:{target_name} "
                    f"(score={winner.winning_score})"
                )
            else:
                await fail_unit(
                    redis,
                    run_id=run_id,
                    agent_id=agent_id,
                    target_type=target_type,
                    target_name=target_name,
                )
                logger.info(f"Failed {agent_id}:{target_type}:{target_name}")
        except Exception as e:
            logger.exception(
                f"Failed to resolve {agent_id}:{target_type}:{target_name}: {e}"
            )

    # Step 4: Emit generation_complete
    await emit(
        [
            internal_event(
                "generation_channel",
                build_generation_complete_payload(
                    sid=sid,
                    artifact_type=artifact_type,
                    group_id=group_id_str,
                    run_id=run_id,
                    resource_actions=resource_actions,
                ),
            )
        ]
    )

    # Step 5: Cleanup
    await cleanup_run(redis, run_id=run_id)
    try:
        await redis.delete(f"generation_resolution:{test_id}")
    except Exception:
        pass
