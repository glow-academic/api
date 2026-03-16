"""Canonical shared test get operations.

Two-layer BFF pattern:
- get_test_impl(): Core data fetcher, returns TestInternalData
- get_test_impl_cached(): HTTP response layer with caching

Uses composable context resolver with black-box tools.
"""

from uuid import UUID

import asyncpg
from fastapi import HTTPException

from app.infra.globals import get_redis_client
from app.infra.test.context import resolve_test_context
from app.infra.test.permissions import compute_test_status
from app.infra.test.types import (
    GetTestArtifactRequest,
    GetTestArtifactResponse,
    TestEntries,
    TestInternalData,
    TestResources,
    TestRunItem,
    TestStatusSummary,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

# =============================================================================
# Layer 1: Core data fetcher (no caching, no HTTP concerns)
# =============================================================================


async def get_test_impl(
    pool: asyncpg.Pool,
    test_id: UUID,
    bypass_cache: bool = False,
    profile_id: UUID | None = None,
) -> TestInternalData:
    """Core test artifact detail fetcher.

    Fetches all data via context resolver, computes business logic,
    and returns TestInternalData. No caching.
    """
    try:
        # === RESOLVE CONTEXT ===
        ctx = await resolve_test_context(
            pool,
            get_redis_client(),
            test_id=test_id,
            bypass_cache=bypass_cache,
        )

        # === EXTRACT ENTRIES ===
        tests = ctx.entries.get("tests", [])
        invocations = ctx.entries.get("invocations", [])
        runs = ctx.entries.get("runs", [])
        groups = ctx.entries.get("groups", [])
        grades = ctx.entries.get("grades", [])
        feedback = ctx.entries.get("feedback", [])
        messages = ctx.entries.get("messages", [])

        test = tests[0] if tests else None
        if not test:
            return TestInternalData()

        # === EXTRACT RESOURCES ===
        def _res(key: str) -> list:
            return ctx.resources[key].selected if key in ctx.resources else []

        evals_list = _res("evals")
        rubrics_list = _res("rubrics")
        agents_list = _res("agents")
        models_list = _res("models")

        # Build resource lookup maps
        agent_map = {a.id: a for a in agents_list}
        model_map = {m.id: m for m in models_list}
        eval_map = {e.id: e for e in evals_list}
        rubric_map = {r.id: r for r in rubrics_list}

        # === HYDRATE EVAL INFO ===
        eval_name: str | None = None
        eval_description: str | None = None
        if test.eval_id and test.eval_id in eval_map:
            eval_name = eval_map[test.eval_id].name
            eval_description = eval_map[test.eval_id].description

        # === RUBRIC NAME MAP ===
        rubric_name_map: dict[UUID, str] = {}
        for inv in invocations:
            if inv.rubric_id and inv.rubric_id in rubric_map:
                rubric_name_map[inv.rubric_id] = rubric_map[inv.rubric_id].name

        # === DERIVE STATUS FROM INVOCATIONS ===
        num_invocations = len(invocations)
        num_completed = sum(1 for inv in invocations if inv.invocation_completed)
        status = compute_test_status(num_invocations, num_completed)

        # === BUILD RUNS LIST FROM INVOCATIONS ===
        run_items: list[TestRunItem] = []
        completed_count = 0
        not_started_count = 0

        # Index runs by invocation_id for run_id lookup
        runs_by_invocation: dict[UUID, list] = {}
        for r in runs:
            runs_by_invocation.setdefault(r.test_invocation_id, []).append(r)

        for inv in invocations:
            first_run = None
            inv_runs = runs_by_invocation.get(inv.invocation_id, [])
            if inv_runs:
                first_run = inv_runs[0]

            # Resolve agent_name and model_name from resources
            agent_name: str | None = None
            model_name: str | None = None
            first_agent_id = inv.agent_ids[0] if inv.agent_ids else None
            if first_agent_id and first_agent_id in agent_map:
                agent = agent_map[first_agent_id]
                agent_name = agent.name
                if agent.model_id and agent.model_id in model_map:
                    model_name = model_map[agent.model_id].name

            invocation_status = (
                "completed" if inv.invocation_completed else "not_started"
            )
            if invocation_status == "completed":
                completed_count += 1
            else:
                not_started_count += 1

            run_items.append(
                TestRunItem(
                    chat_id=str(inv.invocation_id),
                    invocation_id=str(inv.invocation_id),
                    run_id=str(first_run.id) if first_run else None,
                    group_id=str(inv.group_id) if inv.group_id else None,
                    suite_entry_id=None,
                    model_name=model_name,
                    agent_name=agent_name,
                    status=invocation_status,
                    grade_score=inv.grade_score,
                    grade_passed=inv.grade_passed,
                )
            )

        status_summary = TestStatusSummary(
            total=len(run_items),
            completed=completed_count,
            in_progress=0,
            not_started=not_started_count,
        )

        # === BUILD RESOURCES PAYLOAD ===
        def _to_dict_map(items: list) -> dict[str, dict] | None:
            """Convert resource list to {str(id): dict} map."""
            result: dict[str, dict] = {}
            for item in items:
                result[str(item.id)] = item.model_dump(mode="json")
            return result or None

        resources_payload = TestResources(
            evals=_to_dict_map(evals_list),
            rubrics=_to_dict_map(rubrics_list),
            agents=_to_dict_map(agents_list),
            models=_to_dict_map(models_list),
            voices=_to_dict_map(_res("voices")),
            temperature_levels=_to_dict_map(_res("temperature_levels")),
            reasoning_levels=_to_dict_map(_res("reasoning_levels")),
            modalities=_to_dict_map(_res("modalities")),
            prompts=_to_dict_map(_res("prompts")),
            instructions=_to_dict_map(_res("instructions")),
            tools=_to_dict_map(_res("tools")),
            qualities=_to_dict_map(_res("qualities")),
        )

        # === BUILD ENTRIES PAYLOAD ===
        entries_payload = TestEntries(
            tests=[test],
            invocations=invocations,
            runs=runs if runs else None,
            groups=groups if groups else None,
            grades=grades if grades else None,
            feedback=feedback if feedback else None,
            messages=messages if messages else None,
        )

        # Inline controls data (replaces auth/group resolution)
        current_invocation_id = (
            str(invocations[0].invocation_id) if invocations else None
        )
        has_runs_or_groups = len(runs) > 0 or len(groups) > 0
        show_controls = bool(invocations)

        return TestInternalData(
            test=test,
            invocations=invocations,
            eval_name=eval_name,
            eval_description=eval_description,
            rubric_name_map=rubric_name_map,
            runs=run_items,
            status=status,
            status_summary=status_summary,
            show_controls=show_controls,
            current_invocation_id=current_invocation_id,
            has_runs_or_groups=has_runs_or_groups,
            entries_payload=entries_payload,
            resources_payload=resources_payload,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception:
        raise  # pragma: no cover


# =============================================================================
# Layer 2: HTTP client response (with caching)
# =============================================================================


async def get_test_impl_cached(
    pool: asyncpg.Pool,
    test_id: UUID,
    bypass_cache: bool = False,
    cache_key_path: str = "/v5/test/get",
) -> tuple[GetTestArtifactResponse, bool]:
    """HTTP response layer with caching.

    Calls get_test_impl() and assembles GetTestArtifactResponse.
    Returns (response, cache_hit).
    """
    tags = ["artifacts", "test"]
    body_dict = GetTestArtifactRequest(test_id=test_id).model_dump(mode="json")
    cache_key_val = cache_key(cache_key_path, body_dict)

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return GetTestArtifactResponse.model_validate(cached["data"]), True

    data = await get_test_impl(
        pool=pool,
        test_id=test_id,
        bypass_cache=bypass_cache,
    )

    if not data.test:
        raise HTTPException(status_code=404, detail="Benchmark test not found")

    # Get first rubric name from map for backward compat
    rubric_name: str | None = None
    if data.rubric_name_map:
        rubric_name = next(iter(data.rubric_name_map.values()), None)

    api_response = GetTestArtifactResponse(
        test=data.test,
        invocations=data.invocations,
        status=data.status,
        eval_name=data.eval_name,
        eval_description=data.eval_description,
        rubric_name=rubric_name,
        infinite_mode=data.test.infinite_mode,
        runs=data.runs,
        status_summary=data.status_summary,
        show_controls=data.show_controls,
        current_invocation_id=data.current_invocation_id,
        has_runs_or_groups=data.has_runs_or_groups,
        entries=data.entries_payload,
        resources=data.resources_payload,
    )

    await set_cached(
        cache_key_val,
        {"data": api_response.model_dump(mode="json")},
        ttl=300,
        tags=tags,
        redis=get_redis_client(),
    )

    return api_response, False
