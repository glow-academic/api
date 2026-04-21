"""Shared entry point for running a generation from a raw dict payload.

Callers that can't go through a per-artifact handler (e.g. the test
regrading workflow, which needs to synthesize a `generate` request
internally) build a dict shaped like ``GeneratePayload`` + identity
fields and hand it off here. The helper validates, resolves the artifact
config, emits ``<artifact>.generate.started``, runs prepare + execute,
and surfaces errors via ``<artifact>.generate.error``.

There is no top-level ``generate_prepare`` event anymore — direct call
only. WS input handlers that already know their artifact call
``generate_<artifact>_impl`` instead and never come through here.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.generation.execute import execute_generation
from app.infra.generation.prepare import prepare_generation
from app.infra.websocket.generation_types import (
    GenerateErrorApiRequest,
    GeneratePayload,
)
from app.infra.websocket.prepare_pipeline import resolve_primary_artifact_type
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.registry.generate import REGISTRY
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def _emit_error(
    emit: EmitFn,
    *,
    sid: str,
    message: str,
    artifact_type: str,
    group_id: str | None = None,
) -> None:
    await emit(
        [
            internal_event(
                f"{artifact_type}.generate.error",
                GenerateErrorApiRequest(
                    sid=sid,
                    error_message=message,
                    artifact_type=artifact_type,
                    group_id=group_id,
                    resource_type=artifact_type,
                ).model_dump(),
            )
        ]
    )


async def run_generation_from_payload(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    pool: asyncpg.Pool,
    redis: Redis,
) -> None:
    """Validate identity + payload, resolve artifact config, run prepare+execute."""
    sid = data.get("sid", "")
    if not sid:
        return

    artifact_type = resolve_primary_artifact_type(data)
    artifact_config = REGISTRY.get(artifact_type)
    if not artifact_config:
        await _emit_error(
            emit,
            sid=sid,
            message=f"Unknown artifact_type: {artifact_type}",
            artifact_type=artifact_type,
        )
        return

    profile_id_str = data.get("profile_id")
    profiles_id_str = data.get("profiles_id")
    session_id_str = data.get("session_id")
    group_id_str = data.get("group_id")

    if not profile_id_str:
        await _emit_error(emit, sid=sid, message="Profile not found. Please reconnect.", artifact_type=artifact_type)
        return
    if not profiles_id_str:
        await _emit_error(emit, sid=sid, message="Profiles resource not found. Please reconnect.", artifact_type=artifact_type)
        return
    if not session_id_str:
        await _emit_error(emit, sid=sid, message="Session not found. Please reconnect.", artifact_type=artifact_type)
        return
    if not group_id_str:
        await _emit_error(emit, sid=sid, message="group_id is required.", artifact_type=artifact_type)
        return

    try:
        profile_id = UUID(profile_id_str)
        profiles_id = UUID(profiles_id_str)
        session_id = UUID(session_id_str)
        group_id = UUID(group_id_str)
        payload = GeneratePayload(**data)
    except Exception as e:
        await _emit_error(emit, sid=sid, message=f"Invalid request: {str(e)}", artifact_type=artifact_type)
        return

    try:
        prepared = await prepare_generation(
            pool,
            redis,
            profile_id=profile_id,
            profiles_id=profiles_id,
            session_id=session_id,
            group_id=group_id,
            artifact_type=artifact_type,
            artifact_config=artifact_config,
            payload=payload,
        )
    except Exception as e:
        await _emit_error(
            emit,
            sid=sid,
            message=f"Failed to prepare {artifact_type} generation: {str(e)}",
            artifact_type=artifact_type,
            group_id=group_id_str,
        )
        return

    # Artifact-namespaced started event — the per-artifact forwarder fans out to the client.
    await emit(
        [
            internal_event(
                f"{artifact_type}.generate.started",
                {
                    "sid": sid,
                    "artifact_type": artifact_type,
                    "group_id": str(group_id),
                    "run_id": str(prepared.run_id),
                    "resource_types": prepared.resource_types,
                },
            )
        ]
    )

    # Echo persisted user instructions so the generation panel can show them live.
    if payload.instructions:
        for instruction in payload.instructions:
            await emit(
                [
                    internal_event(
                        f"{artifact_type}.generate.text.complete",
                        {
                            "sid": sid,
                            "group_id": str(group_id),
                            "role": "user",
                            "text": instruction,
                            "run_id": str(prepared.run_id),
                            "artifact_type": artifact_type,
                        },
                    )
                ]
            )

    try:
        await execute_generation(
            pool, redis, prepared=prepared, sid=sid, tool_soft=not payload.dangerous,
        )
    except Exception as e:
        await _emit_error(
            emit,
            sid=sid,
            message=f"Failed to execute {artifact_type} generation: {str(e)}",
            artifact_type=artifact_type,
            group_id=group_id_str,
        )


__all__ = ["run_generation_from_payload"]
