"""Resolve test context — black-box tools only.

Test detail is a single-test view (no drafts, no artifact table).
Uses test_mv, test_invocation_mv, test_invocation_runs_mv,
test_invocation_groups_mv, test_grade_mv, test_feedback_mv, messages_mv.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair
from app.tools.entries.messages.search import search_messages
from app.tools.entries.test.search import search_tests
from app.tools.entries.test_feedback.search import (
    search_test_feedback_entries,
)
from app.tools.entries.test_grade.search import search_test_grades
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.entries.test_invocation_groups.search import (
    search_test_invocation_groups,
)
from app.tools.entries.test_invocation_runs.search import (
    search_test_invocation_runs,
)
from app.tools.resources.agents.get import get_agents
from app.tools.resources.evals.get import get_evals
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.modalities.get import get_modalities
from app.tools.resources.models.get import get_models
from app.tools.resources.prompts.get import get_prompts
from app.tools.resources.qualities.get import get_qualities
from app.tools.resources.reasoning_levels.get import get_reasoning_levels
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.tools.get import get_tools
from app.tools.resources.voices.get import get_voices


async def resolve_test_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    test_id: UUID,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve test context for get.py.

    Entries:
      - tests: test_mv rows (single test)
      - invocations: test_invocation_mv rows
      - runs: test_invocation_runs_mv rows
      - groups: test_invocation_groups_mv rows
      - grades: test_grade_mv rows
      - feedback: test_feedback_mv rows
      - messages: messages_mv rows

    Resources:
      - evals, rubrics, agents, models, voices, temperature_levels,
        reasoning_levels, modalities, prompts, instructions, tools, qualities
    """

    # ── Phase 1: Parallel fetch test + invocations ────────────────────
    async def _fetch_tests() -> list:
        async with pool.acquire() as c:
            items, _total = await search_tests(c, test_ids=[test_id], limit=1)
            return items

    async def _fetch_invocations() -> list:
        async with pool.acquire() as c:
            items, _total_count = await search_test_invocation_entries_internal(
                c, test_ids=[test_id], limit=100000
            )
            return items

    tests, invocations = await asyncio.gather(
        _fetch_tests(),
        _fetch_invocations(),
    )

    if not tests:
        return _empty_context()

    # ── Phase 2: Collect invocation_ids → parallel runs + groups + grades
    invocation_ids = [inv.invocation_id for inv in invocations]

    async def _fetch_runs() -> list:
        if not invocation_ids:
            return []
        async with pool.acquire() as c:
            items, _total_count = await search_test_invocation_runs(
                c, test_invocation_ids=invocation_ids, limit=100000
            )
            return items

    async def _fetch_groups() -> list:
        if not invocation_ids:
            return []
        async with pool.acquire() as c:
            items, _total_count = await search_test_invocation_groups(
                c, test_invocation_ids=invocation_ids, limit=100000
            )
            return items

    async def _fetch_grades() -> list:
        if not invocation_ids:
            return []
        async with pool.acquire() as c:
            return await search_test_grades(
                c, invocation_ids=invocation_ids, limit=100000
            )

    runs, groups, grades = await asyncio.gather(
        _fetch_runs(),
        _fetch_groups(),
        _fetch_grades(),
    )

    # ── Phase 3: Collect grade_ids + run_ids → parallel feedback + messages
    grade_ids = [g.id for g in grades]
    run_ids = [r.id for r in runs]

    async def _fetch_feedback() -> list:
        if not grade_ids:
            return []
        async with pool.acquire() as c:
            return await search_test_feedback_entries(
                c, grade_ids=grade_ids, limit=100000
            )

    async def _fetch_messages() -> list:
        if not run_ids:
            return []
        async with pool.acquire() as c:
            msgs, _ = await search_messages(c, run_ids=run_ids, limit=100000)
            return msgs

    feedback, messages = await asyncio.gather(
        _fetch_feedback(),
        _fetch_messages(),
    )

    # ── Phase 4: Collect resource IDs ─────────────────────────────────
    eval_ids_set: set[UUID] = set()
    rubric_ids_set: set[UUID] = set()
    agent_ids_set: set[UUID] = set()
    quality_ids_set: set[UUID] = set()
    voice_ids_set: set[UUID] = set()
    temp_level_ids_set: set[UUID] = set()
    reasoning_ids_set: set[UUID] = set()
    modality_ids_set: set[UUID] = set()
    prompt_ids_set: set[UUID] = set()
    instruction_ids_set: set[UUID] = set()
    tool_ids_set: set[UUID] = set()

    # From test
    test = tests[0]
    if test.eval_id:
        eval_ids_set.add(test.eval_id)

    # From invocations
    for inv in invocations:
        if inv.rubric_id:
            rubric_ids_set.add(inv.rubric_id)
        for aid in inv.agent_ids or []:
            agent_ids_set.add(aid)
        for aid in inv.run_agent_ids or []:
            agent_ids_set.add(aid)
        for aid in inv.group_agent_ids or []:
            agent_ids_set.add(aid)
        if inv.quality_id:
            quality_ids_set.add(inv.quality_id)
        if inv.voice_id:
            voice_ids_set.add(inv.voice_id)
        if inv.temperature_level_id:
            temp_level_ids_set.add(inv.temperature_level_id)
        if inv.reasoning_level_id:
            reasoning_ids_set.add(inv.reasoning_level_id)
        for mid in inv.modality_ids or []:
            modality_ids_set.add(mid)

    # From runs and groups
    for item in [*runs, *groups]:
        for aid in item.agent_ids or []:
            agent_ids_set.add(aid)
        for rid in item.reasoning_level_ids or []:
            reasoning_ids_set.add(rid)
        for tid in item.temperature_level_ids or []:
            temp_level_ids_set.add(tid)
        for vid in item.voice_ids or []:
            voice_ids_set.add(vid)
        for pid in item.prompt_ids or []:
            prompt_ids_set.add(pid)
        for iid in item.instruction_ids or []:
            instruction_ids_set.add(iid)
        for tid in item.tool_ids or []:
            tool_ids_set.add(tid)
        for qid in item.quality_ids or []:
            quality_ids_set.add(qid)
        for mid in item.modality_ids or []:
            modality_ids_set.add(mid)

    # ── Phase 5: Parallel resource hydration ──────────────────────────
    async def _get(getter: Callable, ids_set: set[UUID]) -> list:
        if not ids_set:
            return []
        async with pool.acquire() as c:
            return await getter(c, list(ids_set), redis, bypass_cache=bypass_cache)

    (
        evals_res,
        rubrics_res,
        agents_res,
        voices_res,
        temp_res,
        reasoning_res,
        modalities_res,
        prompts_res,
        instructions_res,
        tools_res,
        qualities_res,
    ) = await asyncio.gather(
        _get(get_evals, eval_ids_set),
        _get(get_rubrics, rubric_ids_set),
        _get(get_agents, agent_ids_set),
        _get(get_voices, voice_ids_set),
        _get(get_temperature_levels, temp_level_ids_set),
        _get(get_reasoning_levels, reasoning_ids_set),
        _get(get_modalities, modality_ids_set),
        _get(get_prompts, prompt_ids_set),
        _get(get_instructions, instruction_ids_set),
        _get(get_tools, tool_ids_set),
        _get(get_qualities, quality_ids_set),
    )

    # Phase 5b: Collect model_ids from agents → fetch models
    model_ids_set: set[UUID] = set()
    for agent in agents_res:
        if agent.model_id:
            model_ids_set.add(agent.model_id)

    models_res = await _get(get_models, model_ids_set)

    # ── Phase 6: Return ArtifactContext ───────────────────────────────
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={
            "tests": tests,
            "invocations": invocations,
            "runs": runs,
            "groups": groups,
            "grades": grades,
            "feedback": feedback,
            "messages": messages,
        },
        resources={
            "evals": ResourcePair(selected=evals_res, suggestions=[]),
            "rubrics": ResourcePair(selected=rubrics_res, suggestions=[]),
            "agents": ResourcePair(selected=agents_res, suggestions=[]),
            "models": ResourcePair(selected=models_res, suggestions=[]),
            "voices": ResourcePair(selected=voices_res, suggestions=[]),
            "temperature_levels": ResourcePair(selected=temp_res, suggestions=[]),
            "reasoning_levels": ResourcePair(selected=reasoning_res, suggestions=[]),
            "modalities": ResourcePair(selected=modalities_res, suggestions=[]),
            "prompts": ResourcePair(selected=prompts_res, suggestions=[]),
            "instructions": ResourcePair(selected=instructions_res, suggestions=[]),
            "tools": ResourcePair(selected=tools_res, suggestions=[]),
            "qualities": ResourcePair(selected=qualities_res, suggestions=[]),
        },
    )


def _empty_context() -> ArtifactContext:
    """Return an empty ArtifactContext when test not found."""
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={},
        resources={},
    )
