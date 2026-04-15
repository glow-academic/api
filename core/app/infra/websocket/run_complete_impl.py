"""Run completion — business logic for generate_run_complete events.

Pure business logic with injected dependencies (``emit``, ``conn``, ``redis``).
No socket handler registration, no module-level sio, no global I/O —
importable without triggering the socket tree.

Flow:
  1. Save assistant message + token counts
  2. resolve_run_completion (DB-based) — check if all agents done
  3. If generation_test_id → route to eval (rubric quality gate)
  4. If no eval → results already persisted, emit generation_complete
  5. Chat special case → attempt grade completion
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import asyncpg

from app.infra.websocket.generation_types import GenerationCompleteData
from app.infra.websocket.persist_run_message import persist_run_message
from app.infra.websocket.resolve_run_completion import resolve_run_completion
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.tools.entries.tokens.create import create_token
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def _table_name(target_type: str, target_name: str) -> str:
    """Derive DB table from run_tracker target: names → names_resource, contents → contents_entry."""
    suffix = "resource" if target_type == "resource" else "entry"
    return f"{target_name}_{suffix}"


def build_audio_continue_payload(
    data: dict[str, Any],
    *,
    sid: str,
    artifact_type: str,
    group_id: str,
    profile_id: str | None,
    profiles_id: str | None,
    session_id: str | None,
) -> dict[str, Any]:
    """Build the payload used to re-enter generation for audio continuation."""
    return {
        "sid": sid,
        "profile_id": profile_id,
        "profiles_id": profiles_id,
        "session_id": session_id,
        "artifact_type": data.get("artifact_type") or artifact_type,
        "operations": data.get("operations") or ["get"],
        "group_id": group_id,
        "modality": "audio",
        "metadata": data.get("metadata", {}),
    }



def build_run_complete_payload(
    *,
    sid: str,
    artifact_type: str,
    group_id: str,
    run_id: str,
    tool_results: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the final generation completion payload for run completion."""
    return GenerationCompleteData(
        sid=sid,
        artifact_type=artifact_type,
        group_id=group_id,
        run_id=run_id,
        success=True,
        message=f"{artifact_type.capitalize()} generation completed",
        tool_results=tool_results,
        metadata=metadata,
    ).model_dump(mode="json")


async def run_complete_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    conn: asyncpg.Connection,
    redis: Any,
    upload_folder: Path | None = None,
) -> None:
    """Handle run_complete — triage contested vs uncontested, promote or grade.

    All I/O dependencies are injected — no globals accessed.
    Callable from socket handler, API, or tests.
    """
    sid = data.get("sid", "")

    run_id = data.get("run_id")
    group_id_str = data.get("group_id", "")
    modality = data.get("modality", "text")
    artifact_type = data.get("artifact_type", "unknown")

    # Identity context — propagated through the pipeline
    profile_id_str = data.get("profile_id")
    profiles_id_str = data.get("profiles_id")
    session_id_str = data.get("session_id")

    logger.info(
        f"generate_run_complete - modality={modality}, group_id={group_id_str}, "
        f"input_tokens={data.get('input_text_tokens', 0)}, "
        f"output_tokens={data.get('output_text_tokens', 0)}"
    )

    # Audio continuation: re-enter rate limit gate
    if modality == "audio":
        if group_id_str:
            await emit(
                [
                    internal_event(
                        "generate",
                        build_audio_continue_payload(
                            data,
                            sid=sid,
                            artifact_type=artifact_type,
                            group_id=group_id_str,
                            profile_id=profile_id_str,
                            profiles_id=profiles_id_str,
                            session_id=session_id_str,
                        ),
                    )
                ]
            )
        return

    if not run_id or not session_id_str:
        return

    run_uuid = uuid.UUID(run_id)
    session_id = uuid.UUID(session_id_str)
    assistant_output = data.get("assistant_output") or ""
    input_tokens = data.get("input_text_tokens", 0)
    output_tokens = data.get("output_text_tokens", 0)

    # Step 1: Save assistant message + token counts
    try:
        if assistant_output:
            await persist_run_message(
                conn,
                run_id=run_uuid,
                session_id=session_id,
                role="assistant",
                content=assistant_output,
                upload_folder=upload_folder,
            )

        if input_tokens or output_tokens:
            await create_token(
                conn,
                run_id=run_uuid,
                session_id=session_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
    except Exception as e:
        logger.exception(f"Failed to save run_complete for {artifact_type}: {e}")

    # Step 2: Check if all agents are done (DB-based, no Redis)
    group_id_uuid = uuid.UUID(group_id_str) if group_id_str else None
    if not group_id_uuid:
        logger.warning(f"No group_id in run_complete for {run_id}, skipping coordination")
        return

    completion = await resolve_run_completion(
        conn,
        run_id=run_uuid,
        group_id=group_id_uuid,
    )

    if not completion.all_done:
        return  # More agents pending

    # Step 3: All agents finished
    tool_results = data.get("tool_results") or []
    metadata = data.get("metadata") or {}
    generation_test_id = metadata.get("generation_test_id")

    # Step 4: Eval gate (idempotent — handles first pass and re-entry)
    # If a rubric eval was set up (generation_test_id exists):
    #   - First pass: eval not graded yet → route to test_proceed, return
    #   - Second pass (re-triggered by generation_ended): eval graded → fall through
    if generation_test_id:
        from app.tools.entries.test_grade.search import search_test_grades
        from app.tools.entries.test_invocation.search import (
            search_test_invocation_entries_internal,
        )

        # Check if eval has been graded by looking for grade records
        invocations, _total = await search_test_invocation_entries_internal(
            conn,
            test_ids=[uuid.UUID(generation_test_id)],
            limit=10,
        )
        invocation_ids = [inv.invocation_id for inv in invocations]

        grades = []
        if invocation_ids:
            grades = await search_test_grades(
                conn,
                invocation_ids=invocation_ids,
                bypass_mv=True,
            )

        if not grades:
            # First pass — eval not graded yet, route to eval
            logger.info(
                f"Run {run_id}: eval {generation_test_id} not graded yet, "
                f"routing to test_proceed"
            )
            await emit(
                [
                    internal_event(
                        "test_proceed",
                        {
                            "sid": sid,
                            "test_id": generation_test_id,
                            "force_proceed": True,
                            "profile_id": profile_id_str,
                            "profiles_id": profiles_id_str,
                            "session_id": session_id_str,
                        },
                    )
                ]
            )
            return

        # Second pass — eval graded, fall through to emit completion
        logger.info(
            f"Run {run_id}: eval {generation_test_id} graded "
            f"({len(grades)} grades), proceeding to completion"
        )

    # Step 6: Emit generation_complete (metadata flows through for
    # downstream handlers like generation_channel_chat to pick up)
    await emit(
        [
            internal_event(
                "generation_channel",
                build_run_complete_payload(
                    sid=sid,
                    artifact_type=artifact_type,
                    group_id=group_id_str,
                    run_id=run_id,
                    tool_results=tool_results,
                    metadata=metadata,
                ),
            )
        ]
    )

    # Step 7: No Redis cleanup needed — state is in DB
