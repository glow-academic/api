"""Resolve test context — black-box tools only.

Test detail is a single-test view (no drafts, no artifact table).
Uses test_mv, test_invocation_mv, test_invocation_runs_mv,
test_invocation_traces_mv, test_grade_mv, test_feedback_mv, messages_mv.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair
from app.tools.entries.calls.search import search_calls
from app.tools.entries.messages.search import search_messages
from app.tools.entries.test.search import search_tests
from app.tools.entries.test_feedback.search import (
    search_test_feedback_entries,
)
from app.tools.entries.test_grade.search import search_test_grades
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.entries.test_invocation_runs.search import (
    search_test_invocation_runs,
)
from app.tools.entries.test_invocation_traces.search import (
    search_test_invocation_traces,
)
from app.tools.resources.agents.get import get_agents
from app.tools.resources.evals.get import get_evals
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.modalities.get import get_modalities
from app.tools.resources.modalities.search import search_modalities
from app.tools.resources.models.get import get_models
from app.tools.resources.prompts.get import get_prompts
from app.tools.resources.qualities.get import get_qualities
from app.tools.resources.qualities.search import search_qualities
from app.tools.resources.reasoning_levels.get import get_reasoning_levels
from app.tools.resources.reasoning_levels.search import search_reasoning_levels
from app.tools.resources.rubrics.get import get_rubrics
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.temperature_levels.search import search_temperature_levels
from app.tools.resources.tools.get import get_tools
from app.tools.resources.tools.search import search_tools
from app.tools.resources.voices.get import get_voices
from app.tools.resources.voices.search import search_voices


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
      - groups: test_invocation_traces_mv rows
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
                c, test_ids=[test_id], limit=100000, bypass_mv=True,
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
            items, _total_count = await search_test_invocation_traces(
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
    # `runs` rows are test_invocation_runs_entry binding rows; their `.id` is
    # the binding id, not a runs_entry.id. messages_entry.run_id references
    # runs_entry.id, so we must collect `.run_id` (the FK on the binding) to
    # query messages.
    run_ids = [r.run_id for r in runs if r.run_id is not None]

    # Also include the original run's messages (the agent output being graded).
    # Derivation: test_entry.call_id → calls_entry.run_id
    test = tests[0]
    original_run_id: UUID | None = None
    if test.call_id:
        async with pool.acquire() as c:
            from app.tools.entries.calls.get import get_calls
            calls = await get_calls(c, [test.call_id])
            if calls:
                original_run_id = calls[0].run_id
    if original_run_id and original_run_id not in run_ids:
        run_ids.append(original_run_id)

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
            from app.tools.entries.messages.refresh import refresh_messages_internal
            await refresh_messages_internal(conn=c, redis=redis)
            msgs, _ = await search_messages(c, run_ids=run_ids, limit=100000)
            return msgs

    async def _fetch_original_calls() -> list:
        """Fetch tool calls from the original run (the agent output being graded)."""
        if not original_run_id:
            return []
        async with pool.acquire() as c:
            from app.tools.entries.calls.refresh import refresh_calls_internal
            await refresh_calls_internal(c, redis=redis)
            return await search_calls(c, run_ids=[original_run_id], limit=1000)

    feedback, messages, original_calls = await asyncio.gather(
        _fetch_feedback(),
        _fetch_messages(),
        _fetch_original_calls(),
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

    # Runs are pure binding rows after the test_invocation_groups → traces
    # rename — they carry no bundle data. agent_ids come from the parent
    # invocation (loop above); the bundle (reasoning, temperature, voices,
    # prompts, instructions, tools, qualities, modalities) comes from the
    # traces loop below.

    # From traces (no agent_ids — agent lives on parent invocation)
    for item in groups:
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

    # Phase 5b: Collect model_ids from agents, standard_group_ids from rubrics
    model_ids_set: set[UUID] = set()
    for agent in agents_res:
        if agent.model_id:
            model_ids_set.add(agent.model_id)

    sg_ids_set: set[UUID] = set()
    for rubric in rubrics_res:
        for sg_id in rubric.standard_group_ids or []:
            sg_ids_set.add(sg_id)

    models_res, standard_groups_res = await asyncio.gather(
        _get(get_models, model_ids_set),
        _get(get_standard_groups, sg_ids_set),
    )

    # ── Phase 5c: Global catalogs for resource panel pickers ──────────
    # The panel needs full lists of pickable options (not just selected).
    # Suggestions are returned alongside the selected resources so the
    # client can render the picker dropdowns.
    async def _search_all(
        searcher: Callable, *, limit: int = 1000
    ) -> list:
        async with pool.acquire() as c:
            return await searcher(
                c, redis, limit_count=limit, bypass_cache=bypass_cache,
            )

    (
        tools_all,
        qualities_all,
        modalities_all,
        reasoning_all,
        voices_all,
        temperature_all,
    ) = await asyncio.gather(
        _search_all(search_tools),
        _search_all(search_qualities),
        _search_all(search_modalities),
        _search_all(search_reasoning_levels),
        _search_all(search_voices),
        _search_all(search_temperature_levels),
    )

    # ── Phase 6: Sort messages by role priority then created_at ────────
    _ROLE_ORDER = {"system": 0, "developer": 1, "user": 2, "assistant": 3}
    messages.sort(
        key=lambda m: (_ROLE_ORDER.get(m.role, 99), m.message_created_at),
    )

    # ── Phase 7: Return ArtifactContext ───────────────────────────────
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        entries={
            "tests": tests,
            "invocations": invocations,
            "runs": runs,
            "groups": groups,
            "grades": grades,
            "feedback": feedback,
            "messages": messages,
            "calls": original_calls,
        },
        resources={
            "evals": ResourcePair(selected=evals_res, suggestions=[]),
            "rubrics": ResourcePair(selected=rubrics_res, suggestions=[]),
            "agents": ResourcePair(selected=agents_res, suggestions=[]),
            "models": ResourcePair(selected=models_res, suggestions=[]),
            "voices": ResourcePair(selected=voices_res, suggestions=voices_all),
            "temperature_levels": ResourcePair(selected=temp_res, suggestions=temperature_all),
            "reasoning_levels": ResourcePair(selected=reasoning_res, suggestions=reasoning_all),
            "modalities": ResourcePair(selected=modalities_res, suggestions=modalities_all),
            "prompts": ResourcePair(selected=prompts_res, suggestions=[]),
            "instructions": ResourcePair(selected=instructions_res, suggestions=[]),
            "tools": ResourcePair(selected=tools_res, suggestions=tools_all),
            "qualities": ResourcePair(selected=qualities_res, suggestions=qualities_all),
            "standard_groups": ResourcePair(selected=standard_groups_res, suggestions=[]),
        },
    )


def _empty_context() -> ArtifactContext:
    """Return an empty ArtifactContext when test not found."""
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        entries={},
        resources={},
    )
