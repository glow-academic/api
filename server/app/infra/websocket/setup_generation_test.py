"""Set up a generation test — create test + invocations for agents with rubrics.

Given a list of agents (from system_context) and a run_id, creates:
  1. A test_entry (finite mode, one invocation per agent with a rubric)
  2. A test_invocation_entry per agent (with agent + rubric + config connections)
  3. A test_invocation_runs_entry per invocation (linking to the shared run)

Returns test_id + per-agent test_invocation_ids for dispatch metadata.
Gate: only agents with a rubric_id participate; others are auto-promoted.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from app.tools.entries.calls.create import create_call
from app.tools.entries.runs.get import get_run
from app.tools.entries.test.create import create_test
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation_runs.create import (
    create_test_invocation_runs,
)


@dataclass(frozen=True)
class AgentTestConfig:
    """Agent config needed to set up a generation test invocation.

    Populated from system_context hydration (agents_resource + junctions).
    """

    agent_id: UUID
    rubric_id: UUID
    department_ids: list[UUID] | None = None
    voice_ids: list[UUID] | None = None
    reasoning_level_ids: list[UUID] | None = None
    temperature_level_ids: list[UUID] | None = None
    quality_ids: list[UUID] | None = None
    modality_ids: list[UUID] | None = None
    # Runs-level config (model execution details)
    prompt_ids: list[UUID] | None = None
    instruction_ids: list[UUID] | None = None
    tool_ids: list[UUID] | None = None


@dataclass(frozen=True)
class GenerationTestResult:
    """Result of setting up a generation test."""

    test_id: UUID
    invocations: dict[UUID, UUID]  # agent_id → test_invocation_id


async def setup_generation_test(
    conn: asyncpg.Connection,
    *,
    agents: list[AgentTestConfig],
    run_id: UUID,
    profile_id: UUID | None = None,
) -> GenerationTestResult:
    """Create a test with one invocation per agent for generation resolution.

    Only agents with rubric_ids should be passed here (caller filters).
    """
    if not agents:
        raise ValueError("setup_generation_test requires at least one agent")

    run = await get_run(conn, run_id)
    if run is None:
        raise ValueError(f"Run not found: {run_id}")

    test_call = await create_call(conn, run_id=run_id, session_id=run.session_id)

    # 1. Create the test entry (finite mode — one invocation per agent)
    # is_dynamic=False: skip LLM re-run, grade existing agent output directly
    test_result = await create_test(
        conn,
        call_id=test_call.id,
        profiles_id=profile_id,
        name="generation_resolution",
        num_invocations=len(agents),
        infinite_mode=False,
        is_dynamic=False,
    )
    test_id = test_result.id

    # 2. Create test_invocation + test_invocation_runs per agent
    invocations: dict[UUID, UUID] = {}

    for agent_config in agents:
        invocation_call = await create_call(
            conn,
            run_id=run_id,
            session_id=run.session_id,
        )

        # Invocation-level: agent identity + rubric + high-level config
        inv_result = await create_test_invocation(
            conn,
            test_id=test_id,
            call_id=invocation_call.id,
            agent_ids=[agent_config.agent_id],
            rubric_ids=[agent_config.rubric_id],
            department_ids=agent_config.department_ids,
            voice_ids=agent_config.voice_ids,
            reasoning_level_ids=agent_config.reasoning_level_ids,
            temperature_level_ids=agent_config.temperature_level_ids,
            quality_ids=agent_config.quality_ids,
            modality_ids=agent_config.modality_ids,
        )
        test_invocation_id = inv_result.id

        # Runs-level: link to the shared run + full agent execution config
        await create_test_invocation_runs(
            conn,
            test_invocation_id=test_invocation_id,
            agent_ids=[agent_config.agent_id],
            prompt_ids=agent_config.prompt_ids,
            instruction_ids=agent_config.instruction_ids,
            tool_ids=agent_config.tool_ids,
            voice_ids=agent_config.voice_ids,
            quality_ids=agent_config.quality_ids,
            reasoning_level_ids=agent_config.reasoning_level_ids,
            temperature_level_ids=agent_config.temperature_level_ids,
            modality_ids=agent_config.modality_ids,
        )

        invocations[agent_config.agent_id] = test_invocation_id

    return GenerationTestResult(test_id=test_id, invocations=invocations)
