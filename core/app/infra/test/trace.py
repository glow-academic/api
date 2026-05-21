"""Internal handler: test_trace — create the trace bundle.

Pure setup: writes a test_invocation_traces_entry row binding to a
historical run_id and writes the per-turn bundle config to the trace's
connection tables. The client then calls /test/generate with the
returned trace_id.

No auto-inheritance from the parent test_invocation. The trace records
exactly what the caller passes; downstream readers do not fall back to
invocation-level defaults.

Free-text fields (``prompt_text``, ``instructions``) are minted via
canonical resource black boxes (``create_prompt`` / ``create_instruction``)
and the resulting ids are attached through the connection tables.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn
from app.tools.entries.test_invocation_traces.create import (
    create_test_invocation_traces,
)
from app.tools.entries.test_invocation_traces.refresh import (
    refresh_test_invocation_traces,
)
from app.tools.resources.instructions.create import create_instruction
from app.tools.resources.prompts.create import create_prompt


class TestTracePayload(BaseModel):
    """Client-to-server: open a trace on a test invocation.

    Bundle fields are stored verbatim on the trace's connection tables.
    No auto-inheritance from the parent test_invocation — caller passes
    whatever it wants the trace to record.

    Free-text fields are minted as new resource rows server-side and
    their ids are attached. Pre-minted ids can also be passed directly
    via ``prompt_ids`` / ``instruction_ids`` (combined with any minted
    from text).
    """

    test_id: UUID = Field(..., description="UUID of the test")
    test_invocation_id: UUID = Field(..., description="UUID of the test invocation")
    run_id: UUID | None = Field(
        None, description="Historical run_id we're replaying against (optional)"
    )

    # Direct id overrides — written verbatim to connection tables.
    tool_ids: list[UUID] | None = None
    modality_ids: list[UUID] | None = None
    voice_ids: list[UUID] | None = None
    temperature_level_ids: list[UUID] | None = None
    reasoning_level_ids: list[UUID] | None = None
    quality_ids: list[UUID] | None = None

    # Pre-minted ids — combined with the minted-from-text counterparts.
    prompt_ids: list[UUID] | None = None
    instruction_ids: list[UUID] | None = None

    # Free-text fields — server mints resource rows + attaches.
    prompt_text: str | None = Field(
        None, description="User-typed system prompt; minted as a prompts_resource"
    )
    instructions: list[str] | None = Field(
        None, description="User-typed instruction templates; each minted separately"
    )


class TestTraceInternalResult(BaseModel):
    test_invocation_trace_id: str
    success: bool = True


async def test_trace_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestTraceInternalResult:
    """Insert a test_invocation_traces_entry row + bundle config."""
    redis = get_redis_client()
    payload = TestTracePayload(**data)
    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for test_trace")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for test_trace")

    async def _run() -> TestTraceInternalResult:
        pool = get_pool()
        redis = get_redis_client()
        async with pool.acquire() as conn:
            # Mint a prompt resource if free-text was provided.
            prompt_ids: list[UUID] = list(payload.prompt_ids or [])
            if payload.prompt_text and payload.prompt_text.strip():
                minted_prompt = await create_prompt(
                    conn,
                    system_prompt=payload.prompt_text,
                    name="",
                    description="",
                    redis=redis,
                )
                prompt_ids.append(minted_prompt.id)

            # Mint an instruction resource per non-empty entry.
            instruction_ids: list[UUID] = list(payload.instruction_ids or [])
            for template in payload.instructions or []:
                if not template or not template.strip():
                    continue
                minted_instruction = await create_instruction(
                    conn,
                    template=template,
                    redis=redis,
                )
                instruction_ids.append(minted_instruction.id)

            result = await create_test_invocation_traces(
                conn, redis,
                test_invocation_id=payload.test_invocation_id,
                run_id=payload.run_id,
                instruction_ids=instruction_ids or None,
                prompt_ids=prompt_ids or None,
                tool_ids=payload.tool_ids,
                modality_ids=payload.modality_ids,
                voice_ids=payload.voice_ids,
                temperature_level_ids=payload.temperature_level_ids,
                reasoning_level_ids=payload.reasoning_level_ids,
                quality_ids=payload.quality_ids,
            )
            await refresh_test_invocation_traces(conn)
        return TestTraceInternalResult(test_invocation_trace_id=str(result.id))

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(str(profile_id)),
        operation="trace",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.test_invocation_id,
        test_id=payload.test_id,
        response_model=TestTraceInternalResult,
    )
