"""Run completion — business logic for generate_run_complete events.

Pure business logic with injected dependencies (``emit``, ``conn``, ``redis``).
No socket handler registration, no module-level sio, no global I/O —
importable without triggering the socket tree.

Flow:
  1. Save assistant message + token counts
  2. record_agent_done — wait for all agents
  3. Triage: get all units, separate contested vs uncontested
  4. Uncontested targets (1 soft unit) → promote_unit() immediately
  5. Contested targets (>1 soft units) → emit test_proceed for grading
  6. If no contested → emit generation_complete directly
  7. If contested → return, wait for generation_ended (test_ended handler)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import asyncpg

from app.infra.activate.activate import activate_rows
from app.infra.websocket.attempt_types import AttemptChatStartedData
from app.infra.websocket.generation_types import GenerationCompleteData
from app.infra.websocket.persist_run_message import persist_run_message
from app.infra.websocket.pipeline_helpers import aggregate_tool_results
from app.infra.websocket.run_tracker import (
    cleanup_run,
    find_contested_targets,
    find_uncontested_targets,
    get_all_units,
    promote_unit,
    record_agent_done,
)
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.tools.entries.attempt.refresh import refresh_attempt
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from app.tools.entries.tokens.create import create_token
from app.utils.cache.invalidate_tags import invalidate_tags
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
        "artifact_types": data.get("artifact_types")
        or [{"name": artifact_type, "operation": "get"}],
        "group_id": group_id,
        "metadata": data.get("metadata", {}),
    }


def build_generation_resolution_context(
    *,
    sid: str,
    run_id: str,
    artifact_type: str,
    group_id: str,
    resource_actions: dict[str, Any],
    entry_actions: dict[str, Any],
) -> dict[str, Any]:
    """Build the minimal stored resolution context for contested runs."""
    return {
        "sid": sid,
        "run_id": run_id,
        "artifact_type": artifact_type,
        "group_id": group_id,
        "resource_actions": resource_actions,
        "entry_actions": entry_actions,
    }


def build_run_complete_payload(
    *,
    sid: str,
    artifact_type: str,
    group_id: str,
    run_id: str,
    resource_actions: dict[str, Any],
) -> dict[str, Any]:
    """Build the final generation completion payload for run completion."""
    return GenerationCompleteData(
        sid=sid,
        artifact_type=artifact_type,
        group_id=group_id,
        run_id=run_id,
        success=True,
        message=f"{artifact_type.capitalize()} generation completed",
        resource_actions=resource_actions,
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

    # Step 2: Multi-agent coordination (new tracker)
    tool_results = data.get("tool_results") or []
    is_complete, all_tool_results = await record_agent_done(
        redis,
        run_id=run_id,
        tool_results=tool_results,
    )

    if not is_complete:
        return  # More agents pending

    # Step 3: All agents finished — triage contested vs uncontested
    resource_actions, entry_actions = aggregate_tool_results(all_tool_results)
    units = await get_all_units(redis, run_id=run_id)
    uncontested = find_uncontested_targets(units)
    contested = find_contested_targets(units)

    # Step 4: Auto-promote uncontested targets (single agent per target)
    for (target_type, target_name), (agent_id, unit_state) in uncontested.items():
        try:
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
                    conn, table=table, ids=[uuid.UUID(unit_state.result_id)]
                )
        except Exception as e:
            logger.exception(
                f"Failed to promote uncontested unit "
                f"{agent_id}:{target_type}:{target_name}: {e}"
            )

    # Step 5: Handle contested targets — trigger test grading or auto-promote
    if contested:
        metadata = data.get("metadata") or {}
        generation_test_id = metadata.get("generation_test_id")

        if generation_test_id:
            logger.info(
                f"Run {run_id} has {len(contested)} contested targets, "
                f"emitting test_proceed for grading (test_id={generation_test_id})"
            )

            # Store minimal resolution context in Redis so generation_ended
            # can emit generation_complete with the right fields.
            # Keyed by test_id (which test_ended carries), not run_id.
            resolution_ctx = build_generation_resolution_context(
                sid=sid,
                run_id=run_id,
                artifact_type=artifact_type,
                group_id=group_id_str,
                resource_actions=resource_actions,
                entry_actions=entry_actions,
            )
            try:
                await redis.setex(
                    f"generation_resolution:{generation_test_id}",
                    3600,
                    json.dumps(resolution_ctx),
                )
            except Exception as e:
                logger.warning(f"Failed to store resolution context: {e}")

            # Test already created in generate_prepare — just trigger grading
            await emit(
                [
                    internal_event(
                        "test_proceed",
                        {
                            "sid": sid,
                            "test_id": generation_test_id,
                            "force_proceed": True,
                        },
                    )
                ]
            )
            # Don't cleanup run — generation_ended will do it after resolution.
            return
        else:
            # No generation test — fall back to auto-promoting first agent
            logger.warning(
                f"Run {run_id} has contested targets but no generation_test_id. "
                f"Auto-promoting first agent per target."
            )
            for (target_type, target_name), agents in contested.items():
                agent_id, unit_state = agents[0]
                try:
                    await promote_unit(
                        redis,
                        run_id=run_id,
                        agent_id=agent_id,
                        target_type=target_type,
                        target_name=target_name,
                    )
                    if unit_state.result_id:
                        table = _table_name(target_type, target_name)
                        await activate_rows(
                            conn,
                            table=table,
                            ids=[uuid.UUID(unit_state.result_id)],
                        )
                except Exception:
                    pass

    # Step 6: No contested (or fallback) — emit generation_complete
    # Chat special case: inject _attempt_chat_id
    metadata = data.get("metadata") or {}
    if artifact_type == "chat":
        attempt_chat_id_meta = metadata.get("attempt_chat_id")
        if attempt_chat_id_meta:
            resource_actions["_attempt_chat_id"] = attempt_chat_id_meta

    await emit(
        [
            internal_event(
                "generation_channel",
                build_run_complete_payload(
                    sid=sid,
                    artifact_type=artifact_type,
                    group_id=group_id_str,
                    run_id=run_id,
                    resource_actions=resource_actions,
                ),
            )
        ]
    )

    # Chat special case: MV refresh + cache invalidation
    if artifact_type == "chat":
        attempt_id_data = metadata.get("attempt_id")
        attempt_chat_id_data = metadata.get("attempt_chat_id")
        if (
            attempt_id_data
            and attempt_chat_id_data
            and not metadata.get("chat_started_emitted")
        ):
            try:
                await refresh_attempt(conn)
                await refresh_attempt_chat(conn)
                await invalidate_tags(["attempt", "attempts"], redis=redis)

                await emit(
                    [
                        internal_event(
                            "attempt_chat_started",
                            AttemptChatStartedData(
                                sid=sid,
                                attempt_id=attempt_id_data,
                                chat_id=attempt_chat_id_data,
                            ).model_dump(mode="json"),
                        )
                    ]
                )
            except Exception as e:
                logger.exception(f"Failed chat post-save: {e}")

    if artifact_type in ("attempt", "chat"):
        grade_id_data = metadata.get("grade_id")
        chat_id_data = metadata.get("chat_id")
        if (
            grade_id_data
            and chat_id_data
            and not metadata.get("grade_complete_emitted")
        ):
            try:
                from app.infra.websocket.attempt_types import AttemptGradeCompleteData

                await emit(
                    [
                        internal_event(
                            "attempt_grade_complete",
                            AttemptGradeCompleteData(
                                sid=sid,
                                chat_id=chat_id_data,
                                grade_id=grade_id_data,
                            ).model_dump(mode="json"),
                        )
                    ]
                )
            except Exception as e:
                logger.exception(f"Failed attempt grade completion emit: {e}")

    # Step 7: Cleanup trackers
    await cleanup_run(redis, run_id=run_id)
