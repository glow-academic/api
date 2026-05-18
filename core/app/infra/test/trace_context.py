"""Trace context resolver — given a trace_id, derive everything generate needs.

A single black-box lookup from `test_invocation_traces_entry.id` cascades
to the full execution context:
  - trace bundle (instructions/prompts/tools/modalities/voices/temp/
    reasoning/qualities) via test_invocation_traces_mv
  - parent invocation (agents, rubrics, departments) via test_invocation_mv
  - parent test (is_dynamic flag) via tests black box
  - historical run (run_id on the trace) — for replay messages

Returns a single dataclass holding everything `/test/generate` needs to
build the agent payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class TraceContext:
    trace_id: UUID
    test_invocation_id: UUID
    test_id: UUID
    is_dynamic: bool
    historical_run_id: UUID | None
    # Trace bundle (per-turn config)
    instruction_ids: list[UUID] = field(default_factory=list)
    prompt_ids: list[UUID] = field(default_factory=list)
    tool_ids: list[UUID] = field(default_factory=list)
    modality_ids: list[UUID] = field(default_factory=list)
    voice_ids: list[UUID] = field(default_factory=list)
    temperature_level_ids: list[UUID] = field(default_factory=list)
    reasoning_level_ids: list[UUID] = field(default_factory=list)
    quality_ids: list[UUID] = field(default_factory=list)
    # Invocation level (the test target — agent + rubric)
    agent_ids: list[UUID] = field(default_factory=list)
    rubric_id: UUID | None = None
    department_ids: list[UUID] = field(default_factory=list)


async def resolve_trace_context(
    conn: asyncpg.Connection, trace_id: UUID
) -> TraceContext:
    """Look up a trace + its parent invocation + test, return TraceContext.

    Reads from MVs. Bypasses MV when freshness matters (callers can decide).
    """
    from app.tools.entries.test.get import get_tests
    from app.tools.entries.test_invocation.get import get_test_invocations
    from app.tools.entries.test_invocation_traces.get import (
        get_test_invocation_traces,
    )

    traces = await get_test_invocation_traces(conn, [trace_id])
    if not traces:
        raise ValueError(f"Trace not found: {trace_id}")
    trace = traces[0]

    invs = await get_test_invocations(
        conn, [trace.test_invocation_id], bypass_mv=True
    )
    if not invs:
        raise ValueError(
            f"Parent invocation {trace.test_invocation_id} not found for trace {trace_id}"
        )
    inv = invs[0]

    tests = await get_tests(conn, ids=[inv.test_id]) if inv.test_id else []
    if not tests:
        raise ValueError(
            f"Parent test {inv.test_id} not found for trace {trace_id}"
        )
    test = tests[0]

    return TraceContext(
        trace_id=trace_id,
        test_invocation_id=trace.test_invocation_id,
        test_id=inv.test_id,
        is_dynamic=test.is_dynamic,
        historical_run_id=trace.run_id,
        instruction_ids=list(trace.instruction_ids or []),
        prompt_ids=list(trace.prompt_ids or []),
        tool_ids=list(trace.tool_ids or []),
        modality_ids=list(trace.modality_ids or []),
        voice_ids=list(trace.voice_ids or []),
        temperature_level_ids=list(trace.temperature_level_ids or []),
        reasoning_level_ids=list(trace.reasoning_level_ids or []),
        quality_ids=list(trace.quality_ids or []),
        agent_ids=list(inv.agent_ids or []),
        rubric_id=inv.rubric_id,
        department_ids=list(inv.department_ids or []),
    )
