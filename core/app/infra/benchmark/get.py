"""Canonical shared benchmark GET operation."""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.analytics_facets import (
    HIDDEN,
    VISIBLE,
    AnalyticsFacetsConfig,
    resolve_analytics_facets,
)
from app.infra.api_types import FilterOption
from app.infra.attempt.chat.permissions import (
    compute_pass_pct,
    compute_score_status,
    compute_show_continue,
    compute_show_view,
)
from app.infra.auth.types import AnalyticsFilterFields
from app.infra.benchmark.context import (
    resolve_benchmark_context,
    resolve_benchmark_search_context,
)
from app.infra.benchmark.permissions import compute_benchmark_eval_status
from app.infra.benchmark.types import (
    BenchmarkDepartmentItem,
    BenchmarkEvalOperational,
    BenchmarkHistoryItem,
    BenchmarkHistoryResponse,
    BenchmarkRequest,
    BenchmarkResponse,
)
from app.infra.common_context import resolve_common_context
from app.infra.types import ArtifactContext

BENCHMARK_FACETS_CONFIG = AnalyticsFacetsConfig(
    fields=AnalyticsFilterFields(
        date_range=VISIBLE,
        departments=VISIBLE,
        cohorts=HIDDEN,
        roles=HIDDEN,
        attempts=VISIBLE,
    ),
    mv_source="benchmark",
    attempt_options=["general", "archived"],
)


async def get_benchmark_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: BenchmarkRequest | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> BenchmarkResponse:
    """Resolve the canonical benchmark response for any surface.

    See ``get_pricing_impl`` — same optional-request convention so the
    tool-dispatch path can call without pre-building the Pydantic wrapper.
    """
    if request is None:
        request = BenchmarkRequest(**{
            k: v for k, v in _kwargs.items() if k in BenchmarkRequest.model_fields
        })
    department_uuids = (
        [UUID(d) for d in request.department_ids] if request.department_ids else None
    )
    date_from: datetime | None = (
        datetime.fromisoformat(request.start_date) if request.start_date else None
    )
    date_to: datetime | None = (
        datetime.fromisoformat(request.end_date) if request.end_date else None
    )

    common = await resolve_common_context(
        pool, redis, profile_id=profile_id, bypass_cache=bypass_cache
    )
    if not common:
        raise HTTPException(status_code=401, detail="Profile not found")

    (cards_ctx, history_ctx), analytics_facets = await asyncio.gather(
        _resolve_both(
            pool,
            redis,
            request=request,
            department_ids=department_uuids,
            date_from=date_from,
            date_to=date_to,
            bypass_cache=bypass_cache,
        ),
        resolve_analytics_facets(
            pool,
            redis,
            config=BENCHMARK_FACETS_CONFIG,
            profile=common.profile,
            bypass_cache=bypass_cache,
        ),
    )

    benchmarks = cards_ctx.entries.get("benchmarks", [])
    invocations = cards_ctx.entries.get("invocations", [])
    tests = cards_ctx.entries.get("tests", [])
    test_invocations = cards_ctx.entries.get("test_invocations", [])
    evals_list = (
        cards_ctx.resources["evals"].selected if "evals" in cards_ctx.resources else []
    )
    depts_list = (
        cards_ctx.resources["departments"].selected
        if "departments" in cards_ctx.resources
        else []
    )

    eval_cards = _build_eval_cards(
        benchmarks, invocations, tests, test_invocations, evals_list
    )
    department_items = [
        BenchmarkDepartmentItem(
            department_id=str(department.id),
            name=department.name,
            description=department.description,
        )
        for department in depts_list
    ]
    department_options = [
        FilterOption(value=str(department.id), label=department.name)
        for department in depts_list
    ]

    date_range_earliest: str | None = None
    date_range_latest: str | None = None
    if tests:
        dates = [test.test_created_at for test in tests if test.test_created_at]
        if dates:
            date_range_earliest = min(dates).isoformat()
            date_range_latest = max(dates).isoformat()

    history = _build_history(history_ctx, request)
    return BenchmarkResponse(
        evals=eval_cards,
        departments=department_items,
        department_options=department_options,
        date_range_earliest=date_range_earliest,
        date_range_latest=date_range_latest,
        history=history,
        analytics=analytics_facets,
    )


async def _resolve_both(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    request: BenchmarkRequest,
    department_ids: list[UUID] | None,
    date_from: datetime | None,
    date_to: datetime | None,
    bypass_cache: bool,
) -> tuple[ArtifactContext, ArtifactContext]:
    """Resolve cards + history contexts in parallel."""
    eval_uuids = (
        [UUID(e) for e in request.history_eval_ids]
        if request.history_eval_ids
        else None
    )
    return await asyncio.gather(
        resolve_benchmark_context(
            pool,
            redis,
            department_ids=department_ids,
            date_from=date_from,
            date_to=date_to,
            bypass_cache=bypass_cache,
        ),
        resolve_benchmark_search_context(
            pool,
            redis,
            eval_ids=eval_uuids,
            department_ids=department_ids,
            date_from=date_from,
            date_to=date_to,
            is_archived=request.history_archived,
            sort_order=request.history_sort_order,
            limit=request.history_page_size,
            offset=request.history_page * request.history_page_size,
            bypass_cache=bypass_cache,
        ),
    )


def _build_eval_cards(
    benchmarks: list,
    invocations: list,
    tests: list,
    test_invocations: list,
    evals_list: list,
) -> list[BenchmarkEvalOperational]:
    """Build eval cards with aggregated stats."""
    inv_by_benchmark: dict[UUID, list] = defaultdict(list)
    for invocation in invocations:
        if invocation.benchmark_id:
            inv_by_benchmark[invocation.benchmark_id].append(invocation)

    model_ids_per_eval: dict[UUID, set[UUID]] = defaultdict(set)
    dept_ids_per_eval: dict[UUID, set[str]] = defaultdict(set)
    for benchmark in benchmarks:
        benchmark_invocations = inv_by_benchmark.get(benchmark.benchmark_id, [])
        benchmark_model_ids: set[UUID] = set()
        for invocation in benchmark_invocations:
            for model_id in invocation.model_ids or []:
                benchmark_model_ids.add(model_id)
        for eval_id in benchmark.eval_ids or []:
            model_ids_per_eval[eval_id].update(benchmark_model_ids)
            for department_id in benchmark.department_ids or []:
                dept_ids_per_eval[eval_id].add(str(department_id))

    tests_per_eval: Counter[UUID] = Counter()
    archived_per_eval: Counter[UUID] = Counter()
    test_ids_per_eval: dict[UUID, list[UUID]] = defaultdict(list)
    infinite_per_eval: dict[UUID, bool] = {}
    for test in tests:
        if test.eval_id:
            tests_per_eval[test.eval_id] += 1
            test_ids_per_eval[test.eval_id].append(test.test_id)
            if test.archived:
                archived_per_eval[test.eval_id] += 1
            if test.infinite_mode:
                infinite_per_eval[test.eval_id] = True

    ti_by_test: dict[UUID, list] = defaultdict(list)
    for test_invocation in test_invocations:
        if test_invocation.test_id:
            ti_by_test[test_invocation.test_id].append(test_invocation)

    eval_stats: dict[UUID, dict] = {}
    for eval_id, test_ids in test_ids_per_eval.items():
        total = 0
        completed = 0
        highest: float | None = None
        passed = False
        rubric_ids: set[UUID] = set()
        for test_id in test_ids:
            for test_invocation in ti_by_test.get(test_id, []):
                total += 1
                if test_invocation.invocation_completed:
                    completed += 1
                if test_invocation.grade_passed:
                    passed = True
                if test_invocation.grade_score is not None:
                    if highest is None or test_invocation.grade_score > highest:
                        highest = test_invocation.grade_score
                if test_invocation.rubric_id:
                    rubric_ids.add(test_invocation.rubric_id)
        eval_stats[eval_id] = {
            "total_invocations": total,
            "completed_invocations": completed,
            "highest_score": highest,
            "has_passed": passed,
            "rubric_ids": rubric_ids,
        }

    eval_map = {eval_item.id: eval_item for eval_item in evals_list if eval_item.id}
    cards: list[BenchmarkEvalOperational] = []
    for eval_id, eval_item in eval_map.items():
        stats = eval_stats.get(eval_id, {})
        total_invocations = stats.get("total_invocations", 0)
        completed_invocations = stats.get("completed_invocations", 0)
        has_passed = stats.get("has_passed", False)
        cards.append(
            BenchmarkEvalOperational(
                eval_id=str(eval_id),
                eval_name=eval_item.name,
                eval_description=eval_item.description,
                model_ids=sorted(
                    str(model_id) for model_id in model_ids_per_eval.get(eval_id, set())
                ),
                total_tests=tests_per_eval.get(eval_id, 0),
                archived_tests=archived_per_eval.get(eval_id, 0),
                total_invocations=total_invocations,
                completed_invocations=completed_invocations,
                highest_score=stats.get("highest_score"),
                has_passed=has_passed,
                status=compute_benchmark_eval_status(
                    has_passed, completed_invocations, total_invocations
                ),
                infinite_mode=infinite_per_eval.get(eval_id, False),
                department_ids=sorted(dept_ids_per_eval.get(eval_id, set())),
                rubric_ids=sorted(
                    str(rubric_id) for rubric_id in stats.get("rubric_ids", set())
                ),
            )
        )
    return cards


def _build_history(
    ctx: ArtifactContext,
    request: BenchmarkRequest,
) -> BenchmarkHistoryResponse:
    """Build paginated history from search context.

    TODO(path-c): Extract row-builder + score/status helpers to a shared
    history-row module alongside the simulation-side equivalents
    (core/app/routes/attempt/{home,practice}/search.py).
    """
    tests = ctx.entries.get("tests", [])
    test_invocations = ctx.entries.get("test_invocations", [])
    evals_list = ctx.resources["evals"].selected if "evals" in ctx.resources else []
    profiles_list = (
        ctx.resources["profiles"].selected if "profiles" in ctx.resources else []
    )
    rubrics_list = (
        ctx.resources["rubrics"].selected if "rubrics" in ctx.resources else []
    )
    models_list = (
        ctx.resources["models"].selected if "models" in ctx.resources else []
    )

    eval_map = {eval_item.id: eval_item for eval_item in evals_list if eval_item.id}
    profile_map = {p.id: p for p in profiles_list if p.id}
    rubric_map = {r.id: r for r in rubrics_list if r.id}
    model_map = {m.id: m for m in models_list if m.id}

    ti_by_test: dict[UUID, list] = defaultdict(list)
    for test_invocation in test_invocations:
        if test_invocation.test_id:
            ti_by_test[test_invocation.test_id].append(test_invocation)

    items: list[BenchmarkHistoryItem] = []
    eval_counter: Counter[str] = Counter()
    eval_id_to_name: dict[str, str | None] = {}
    model_counter: Counter[str] = Counter()
    model_id_to_name: dict[str, str | None] = {}
    profile_counter: Counter[str] = Counter()
    profile_id_to_name: dict[str, str | None] = {}
    rubric_counter: Counter[str] = Counter()
    rubric_id_to_name: dict[str, str | None] = {}

    for test in tests:
        test_items = ti_by_test.get(test.test_id, [])
        num_models = len(test_items)
        num_models_completed = sum(
            1 for item in test_items if item.invocation_completed
        )

        # Each test has exactly ONE rubric — grab it from the first invocation
        # that carries one (matches the singular-rubric invariant).
        rubric_uuid: UUID | None = None
        for item in test_items:
            if item.rubric_id:
                rubric_uuid = item.rubric_id
                break

        # Score aggregation — best score across invocations, normalised to 0-100.
        # Mirrors simulation pattern in
        # core/app/routes/attempt/home/search.py:_compute_history_aggregates
        # which sums grade_score / grade_total_points across chats. Tests use
        # grade_score directly (already 0-100 per user spec).
        best_score: float | None = None
        has_passed = False
        for item in test_items:
            if item.grade_passed:
                has_passed = True
            if item.grade_score is not None:
                if best_score is None or item.grade_score > best_score:
                    best_score = item.grade_score

        # Eval lookup
        eval_name: str | None = None
        eval_model_uuids: list[UUID] = []
        if test.eval_id and test.eval_id in eval_map:
            ev = eval_map[test.eval_id]
            eval_name = ev.name
            eval_model_uuids = list(ev.model_ids or [])

        # Rubric lookup — pass_pct mirrors compute_pass_pct(total_points, pass_points)
        # from core/app/infra/attempt/chat/permissions.py:87
        rubric_name: str | None = None
        pass_pct: int | None = None
        rubric_pass_threshold_percent: float | None = None
        if rubric_uuid and rubric_uuid in rubric_map:
            rubric = rubric_map[rubric_uuid]
            rubric_name = rubric.name
            pass_pct = compute_pass_pct(rubric.total_points, rubric.pass_points)
            if pass_pct is not None:
                rubric_pass_threshold_percent = float(pass_pct)

        # Profile lookup
        profile_name: str | None = None
        if test.profile_id and test.profile_id in profile_map:
            profile_name = profile_map[test.profile_id].name

        # Model names — mirror the simulation `scenario_titles` lookup in
        # core/app/routes/attempt/home/search.py:135
        model_id_strs: list[str] = [str(mid) for mid in eval_model_uuids]
        model_names: list[str] = []
        for mid in eval_model_uuids:
            if mid in model_map:
                nm = model_map[mid].name
                if nm:
                    model_names.append(nm)

        # Score (canonical 0-100 int) — cast best_score to int.
        # Mirrors `score = round(score_percent)` in
        # core/app/routes/attempt/home/search.py:150
        score: int | None = (
            int(round(best_score)) if best_score is not None else None
        )

        # score_status — port simulation's compute_score_status, threshold from
        # rubric pass_pct (defaults to 70 if rubric missing).
        # core/app/infra/attempt/chat/permissions.py:60
        score_status = compute_score_status(
            best_score, rubric_pass_threshold_percent
        )

        # show_view / show_continue — mirror simulation patterns in
        # core/app/routes/attempt/practice/search.py:152-165
        is_archived = bool(test.archived)
        show_view = compute_show_view(is_archived)
        show_continue = compute_show_continue(
            is_archived=is_archived,
            infinite_mode=test.infinite_mode,
            num_scenarios=num_models,
            num_scenarios_completed=num_models_completed,
            time_limit_seconds=None,
            elapsed_seconds=None,
            num_incomplete_chats=num_models - num_models_completed,
        )

        department_ids = (
            [str(d) for d in test.department_ids] if test.department_ids else None
        )

        items.append(
            BenchmarkHistoryItem(
                test_id=str(test.test_id),
                date=(
                    test.test_created_at.isoformat() if test.test_created_at else None
                ),
                profile_id=test.profile_id,
                profile_name=profile_name,
                eval_id=str(test.eval_id) if test.eval_id else None,
                eval_name=eval_name,
                rubric_id=str(rubric_uuid) if rubric_uuid else None,
                rubric_name=rubric_name,
                num_models=num_models,
                num_models_completed=num_models_completed,
                model_ids=model_id_strs or None,
                model_names=model_names or None,
                score=score,
                score_status=score_status,
                pass_pct=pass_pct,
                show_view=show_view,
                show_continue=show_continue,
                is_archived=is_archived,
                infinite_mode=test.infinite_mode,
                department_ids=department_ids,
            )
        )

        # ── Tally filter-option counts ──────────────────────────────
        if test.eval_id:
            eid_str = str(test.eval_id)
            eval_counter[eid_str] += 1
            eval_id_to_name.setdefault(eid_str, eval_name)
        for mid_str in model_id_strs:
            model_counter[mid_str] += 1
            if mid_str not in model_id_to_name:
                # Recompute the matching name (model_names was filtered)
                try:
                    mid_uuid = UUID(mid_str)
                except (ValueError, TypeError):
                    mid_uuid = None
                if mid_uuid and mid_uuid in model_map:
                    model_id_to_name[mid_str] = model_map[mid_uuid].name
        if test.profile_id:
            pid_str = str(test.profile_id)
            profile_counter[pid_str] += 1
            profile_id_to_name.setdefault(pid_str, profile_name)
        if rubric_uuid:
            rid_str = str(rubric_uuid)
            rubric_counter[rid_str] += 1
            rubric_id_to_name.setdefault(rid_str, rubric_name)

    eval_options = [
        FilterOption(value=eid, label=eval_id_to_name.get(eid), count=count)
        for eid, count in eval_counter.items()
    ]
    eval_options.sort(key=lambda option: option.value)

    model_options = [
        FilterOption(value=mid, label=model_id_to_name.get(mid), count=count)
        for mid, count in model_counter.items()
    ]
    model_options.sort(key=lambda option: option.value)

    profile_options = [
        FilterOption(value=pid, label=profile_id_to_name.get(pid), count=count)
        for pid, count in profile_counter.items()
    ]
    profile_options.sort(key=lambda option: option.value)

    rubric_options = [
        FilterOption(value=rid, label=rubric_id_to_name.get(rid), count=count)
        for rid, count in rubric_counter.items()
    ]
    rubric_options.sort(key=lambda option: option.value)

    return BenchmarkHistoryResponse(
        data=items,
        total_count=len(items),
        page=request.history_page,
        page_size=request.history_page_size,
        eval_options=eval_options,
        model_options=model_options,
        profile_options=profile_options,
        rubric_options=rubric_options,
    )
