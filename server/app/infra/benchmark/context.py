"""Resolve benchmark context — black-box tools only.

Benchmark is a dashboard endpoint (no drafts, no artifact table).
Uses benchmark_mv, invocation_mv, test_mv, test_invocation_mv as data grains.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair
from app.tools.entries.benchmark.search import search_benchmarks
from app.tools.entries.invocation.search import search_invocations
from app.tools.entries.test.search import search_tests
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.tools.resources.departments.get import get_departments
from app.tools.resources.evals.get import get_evals
from app.tools.resources.models.get import get_models
from app.tools.resources.rubrics.get import get_rubrics


async def resolve_benchmark_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    department_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve benchmark context for cards (get.py).

    Entries:
      - benchmarks: benchmark_mv rows
      - invocations: invocation_mv rows (templates with model_ids)
      - tests: test_mv rows
      - test_invocations: test_invocation_mv rows (runs with grades)

    Resources:
      - evals, models, departments, rubrics
    """

    # ── Phase 1: Fetch benchmarks ─────────────────────────────────────
    async with pool.acquire() as c:
        benchmarks = await search_benchmarks(
            c,
            department_ids=department_ids,
            date_from=date_from,
            date_to=date_to,
            limit=10000,
        )

    # ── Phase 2: Collect IDs from benchmarks ──────────────────────────
    benchmark_ids: list[UUID] = []
    eval_ids_set: set[UUID] = set()
    dept_ids_set: set[UUID] = set()

    for b in benchmarks:
        benchmark_ids.append(b.benchmark_id)
        for eid in b.eval_ids or []:
            eval_ids_set.add(eid)
        for did in b.department_ids or []:
            dept_ids_set.add(did)

    # ── Phase 3: Parallel fetch invocations + tests ───────────────────
    async def _fetch_invocations() -> list:
        if not benchmark_ids:
            return []
        async with pool.acquire() as c:
            return await search_invocations(c, benchmark_ids=benchmark_ids, limit=10000)

    async def _fetch_tests() -> list:
        if not eval_ids_set:
            return []
        async with pool.acquire() as c:
            items, _total = await search_tests(
                c,
                eval_ids=list(eval_ids_set),
                department_ids=department_ids,
                date_from=date_from,
                date_to=date_to,
                limit=10000,
            )
            return items

    invocations, tests = await asyncio.gather(
        _fetch_invocations(),
        _fetch_tests(),
    )

    # ── Phase 4: Collect test_ids → fetch test_invocations ────────────
    test_ids = [t.test_id for t in tests]
    for t in tests:
        if t.eval_id:
            eval_ids_set.add(t.eval_id)
        for did in t.department_ids or []:
            dept_ids_set.add(did)

    async def _fetch_test_invocations() -> list:
        if not test_ids:
            return []
        async with pool.acquire() as c:
            items, _total_count = await search_test_invocation_entries_internal(
                c, test_ids=test_ids, limit=100000
            )
            return items

    test_invocations = await _fetch_test_invocations()

    # ── Phase 5: Collect resource IDs ─────────────────────────────────
    model_ids_set: set[UUID] = set()
    rubric_ids_set: set[UUID] = set()

    for inv in invocations:
        for mid in inv.model_ids or []:
            model_ids_set.add(mid)

    for ti in test_invocations:
        if ti.rubric_id:
            rubric_ids_set.add(ti.rubric_id)

    # ── Phase 6: Parallel resource hydration ──────────────────────────
    async def _get_evals() -> list:
        if not eval_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_evals(
                c, list(eval_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_models() -> list:
        if not model_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_models(
                c, list(model_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_departments() -> list:
        if not dept_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_departments(
                c, list(dept_ids_set), redis, bypass_cache=bypass_cache
            )

    async def _get_rubrics() -> list:
        if not rubric_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_rubrics(
                c, list(rubric_ids_set), redis, bypass_cache=bypass_cache
            )

    evals_res, models_res, depts_res, rubrics_res = await asyncio.gather(
        _get_evals(),
        _get_models(),
        _get_departments(),
        _get_rubrics(),
    )

    # ── Phase 7: Return ArtifactContext ───────────────────────────────
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={
            "benchmarks": benchmarks,
            "invocations": invocations,
            "tests": tests,
            "test_invocations": test_invocations,
        },
        resources={
            "evals": ResourcePair(selected=evals_res, suggestions=[]),
            "models": ResourcePair(selected=models_res, suggestions=[]),
            "departments": ResourcePair(selected=depts_res, suggestions=[]),
            "rubrics": ResourcePair(selected=rubrics_res, suggestions=[]),
        },
    )


async def resolve_benchmark_search_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    eval_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    is_archived: bool | None = None,
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve benchmark search context for history (search.py).

    Entries:
      - tests: test_mv rows (paginated)
      - test_invocations: test_invocation_mv rows for those tests

    Resources:
      - evals
    """

    # ── Phase 1: Fetch paginated tests ────────────────────────────────
    async with pool.acquire() as c:
        tests, _total_count = await search_tests(
            c,
            eval_ids=eval_ids,
            department_ids=department_ids,
            date_from=date_from,
            date_to=date_to,
            is_archived=is_archived,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

    # ── Phase 2: Collect test_ids → fetch test_invocations ────────────
    test_ids = [t.test_id for t in tests]
    eval_ids_set: set[UUID] = set()
    for t in tests:
        if t.eval_id:
            eval_ids_set.add(t.eval_id)

    async def _fetch_test_invocations() -> list:
        if not test_ids:
            return []
        async with pool.acquire() as c:
            items, _total_count = await search_test_invocation_entries_internal(
                c, test_ids=test_ids, limit=100000
            )
            return items

    async def _get_evals() -> list:
        if not eval_ids_set:
            return []
        async with pool.acquire() as c:
            return await get_evals(
                c, list(eval_ids_set), redis, bypass_cache=bypass_cache
            )

    test_invocations, evals_res = await asyncio.gather(
        _fetch_test_invocations(),
        _get_evals(),
    )

    # ── Phase 3: Return ArtifactContext ───────────────────────────────
    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=None,  # type: ignore[arg-type]
        draft_version=None,
        entries={
            "tests": tests,
            "test_invocations": test_invocations,
        },
        resources={
            "evals": ResourcePair(selected=evals_res, suggestions=[]),
        },
    )
