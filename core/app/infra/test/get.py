"""Canonical shared test get operations.

Two-layer BFF pattern:
- get_test_impl(): Core data fetcher, returns TestInternalData
- get_test_impl_cached(): HTTP response layer with caching

Uses composable context resolver with black-box tools.
"""

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from app.infra.attempt.permissions import (
    compute_achieved_standards,
    compute_passed_standards,
)
from app.infra.attempt.types import (
    FeedbackEntry,
    GradeData,
    GradingStateData,
    RubricStructureData,
    StandardGroupMeta,
    StandardMeta,
)
from app.infra.globals import get_redis_client
from app.infra.test.context import resolve_test_context
from app.infra.test.permissions import compute_test_status
from app.infra.test.types import (
    GetTestArtifactRequest,
    GetTestArtifactResponse,
    InvocationDetail,
    InvocationRunDetail,
    TestConfigGroup,
    TestConfigItem,
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
    redis: Any | None = None,
    *,
    profile_id: UUID | None = None,
    session_id: UUID | None = None,
    group_id: UUID | None = None,
    id: UUID | None = None,
    bypass_cache: bool = False,
    configs_groups_page: int = 1,
    configs_groups_page_size: int = 10,
    configs_expanded: list[UUID] | None = None,
    configs_expanded_page_size: int = 20,
    configs_search: str | None = None,
    configs_selected: list[UUID] | None = None,
    **_kwargs: Any,
) -> GetTestArtifactResponse:
    """Core test artifact detail fetcher.

    Canonical signature: (pool, redis, *, profile_id, session_id, ...).
    Returns Pydantic model (canonical for executor serialization).
    Tools send `id`, internal code uses `test_id`.
    """
    effective_redis = redis or get_redis_client()
    test_id = id  # alias: tools send 'id'
    if not test_id:
        return GetTestArtifactResponse()

    try:
        # === RESOLVE CONTEXT ===
        ctx = await resolve_test_context(
            pool,
            effective_redis,
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

        def _res_all(key: str) -> list:
            """Selected ∪ suggestions, deduped by id. Used for panel
            pickers that need the full catalog of options (selected ones
            visible as already-picked, the rest available to choose)."""
            if key not in ctx.resources:
                return []
            pair = ctx.resources[key]
            seen: dict = {}
            for item in [*pair.selected, *pair.suggestions]:
                if item.id not in seen:
                    seen[item.id] = item
            return list(seen.values())

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
        in_progress_count = 0
        not_started_count = 0

        # Index runs by invocation_id for run_id lookup
        runs_by_invocation: dict[UUID, list] = {}
        for r in runs:
            runs_by_invocation.setdefault(r.test_invocation_id, []).append(r)

        # Per-binding lifecycle signals — derive status from the actual
        # state of each (trace, run) pair, not the parent invocation.
        # Two signals:
        #   1. completion entry on the binding row → "completed"
        #   2. message count on the binding's run_id → "in_progress" (has
        #      partial output) vs "not_started" (no output yet)
        binding_ids = [r.id for r in runs]
        completed_binding_ids: set[UUID] = set()
        if binding_ids:
            from app.tools.entries.test_invocation_runs_completion.search import (
                search_test_invocation_runs_completion,
            )
            async with pool.acquire() as conn:
                completions, _ = await search_test_invocation_runs_completion(
                    conn, redis, test_invocation_runs_ids=binding_ids, limit=100000,
                )
            completed_binding_ids = {c.test_invocation_runs_id for c in completions}

        msg_count_by_run_id: dict[UUID, int] = {}
        for m in messages:
            if m.run_id:
                msg_count_by_run_id[m.run_id] = msg_count_by_run_id.get(m.run_id, 0) + 1

        # Per-binding agent + model lookup. The invocation's
        # agent_ids reflects the test target (one agent), but each
        # binding's run can have been fired by a different agent —
        # see picker fan-out / replay flows where each card targets a
        # distinct agent. Reading agent_name off `inv.agent_ids[0]`
        # would label every history card with the invocation's agent
        # regardless of which agent actually fired the binding's run.
        # Resolve per-binding via runs_mv (the canonical run-level
        # agent connection table source) so each card shows the
        # correct agent.
        from app.tools.entries.runs.search import (
            search_runs as _search_runs_for_history,
        )

        binding_run_ids: list[UUID] = [
            r.run_id for r in runs if r.run_id is not None
        ]
        run_agent_ids_by_run_id: dict[UUID, list[UUID]] = {}
        if binding_run_ids:
            async with pool.acquire() as conn:
                # group_ids=None loads all runs; filter to our binding ids in-mem.
                # search_runs doesn't accept run_ids directly, so we
                # narrow via group_ids when we have them, else loop.
                inv_group_ids = list({inv.group_id for inv in invocations if inv.group_id})
                rows, _total = await _search_runs_for_history(
                    conn,
                    group_ids=inv_group_ids if inv_group_ids else None,
                    limit=10000,
                )
                wanted = set(binding_run_ids)
                for r in rows:
                    if r.run_id in wanted:
                        run_agent_ids_by_run_id[r.run_id] = list(r.agent_ids or [])

        # The per-binding agent ids may reference agents NOT in the
        # ws_ctx-resolved agent_map (which tends to be scoped to the
        # invocation's test target). Hydrate any missing agent
        # resources so the per-binding label lookup below resolves.
        referenced_agent_ids: set[UUID] = set()
        for ids in run_agent_ids_by_run_id.values():
            referenced_agent_ids.update(ids)
        missing_agent_ids = [
            aid for aid in referenced_agent_ids if aid not in agent_map
        ]
        if missing_agent_ids:
            from app.tools.resources.agents.get import (
                get_agents as _get_agents_for_history,
            )

            async with pool.acquire() as conn:
                extra_agents = await _get_agents_for_history(
                    conn, missing_agent_ids, redis or get_redis_client(),
                    bypass_cache=True,
                )
            for a in extra_agents:
                agent_map[a.id] = a
                if a.model_id and a.model_id not in model_map:
                    # Also hydrate the model so model_name resolves.
                    from app.tools.resources.models.get import (
                        get_models as _get_models_for_history,
                    )
                    async with pool.acquire() as conn:
                        extra_models = await _get_models_for_history(
                            conn, [a.model_id], redis or get_redis_client(),
                            bypass_cache=True,
                        )
                    for m in extra_models:
                        model_map[m.id] = m

        def _binding_status(binding) -> str:
            if binding.id in completed_binding_ids:
                return "completed"
            if binding.run_id and msg_count_by_run_id.get(binding.run_id, 0) > 0:
                return "in_progress"
            return "not_started"

        # Invocation-level fallback agent (used when a binding has no
        # explicit run-level agent connection, or the run was deleted).
        inv_fallback_agent_name: str | None = None
        inv_fallback_model_name: str | None = None
        # Will be set per-invocation in the loop below.

        for inv in invocations:
            inv_runs = runs_by_invocation.get(inv.invocation_id, [])

            # Invocation-level fallback (used only when a binding has
            # no run-level agent association).
            inv_fallback_agent_name = None
            inv_fallback_model_name = None
            first_agent_id = inv.agent_ids[0] if inv.agent_ids else None
            if first_agent_id and first_agent_id in agent_map:
                agent = agent_map[first_agent_id]
                inv_fallback_agent_name = agent.name
                if agent.model_id and agent.model_id in model_map:
                    inv_fallback_model_name = model_map[agent.model_id].name

            # Emit one run_item per binding row. Each binding represents
            # a real past trace+run execution. Invocations with no
            # bindings produce no history rows — the picker (configs)
            # is the source of truth for what's runnable; history is
            # for what has actually run.
            #
            # binding.run_id is the FK into runs_entry, which is what
            # messages_entry.run_id references — using binding.id would
            # break the run↔messages join on the client.
            #
            # agent_name / model_name resolve PER BINDING from
            # runs_mv via run_agent_ids_by_run_id — different bindings
            # under the same invocation can have been fired by
            # different agents (picker fan-out, replay flows). Falls
            # back to the invocation's agent only if the run row has
            # no agent connection.
            for binding in inv_runs:
                bstatus = _binding_status(binding)
                if bstatus == "completed":
                    completed_count += 1
                elif bstatus == "in_progress":
                    in_progress_count += 1
                else:
                    not_started_count += 1

                binding_agent_name = inv_fallback_agent_name
                binding_model_name = inv_fallback_model_name
                if binding.run_id:
                    run_agent_ids = run_agent_ids_by_run_id.get(binding.run_id, [])
                    if run_agent_ids:
                        run_agent_id = run_agent_ids[0]
                        if run_agent_id in agent_map:
                            run_agent = agent_map[run_agent_id]
                            binding_agent_name = run_agent.name
                            if run_agent.model_id and run_agent.model_id in model_map:
                                binding_model_name = model_map[run_agent.model_id].name

                run_items.append(
                    TestRunItem(
                        chat_id=str(inv.invocation_id),
                        invocation_id=str(inv.invocation_id),
                        run_id=str(binding.run_id) if binding.run_id else None,
                        group_id=str(inv.group_id) if inv.group_id else None,
                        suite_entry_id=None,
                        model_name=binding_model_name,
                        agent_name=binding_agent_name,
                        status=bstatus,
                        grade_score=inv.grade_score,
                        grade_passed=inv.grade_passed,
                    )
                )

        status_summary = TestStatusSummary(
            total=len(run_items),
            completed=completed_count,
            in_progress=in_progress_count,
            not_started=not_started_count,
        )

        # === BUILD CONFIG POOL FOR PICKER (groups-first) ===
        # Two-axis pagination using only canonical black-boxes:
        #   1. Outer: search_groups(limit, offset) — paginated groups.
        #      For each header, search_runs(group_ids=[gid], limit=1)
        #      gives run_count (via total_count) + last_run_at (via the
        #      first row's run_created_at, ordered DESC).
        #   2. Inner: search_runs(group_ids=[gid], limit=N) for each
        #      group in `configs_expanded`.
        # Outer total is unknown without an extra count, so the client
        # uses len(items) == page_size to enable Next.
        import asyncio

        from app.tools.entries.groups.search import search_groups
        from app.tools.entries.runs.search import search_runs

        groups_offset = max(0, (configs_groups_page - 1) * configs_groups_page_size)
        expanded_set: set[UUID] = set(configs_expanded or [])

        async with pool.acquire() as conn:
            group_summaries = await search_groups(
                conn, redis,
                name=configs_search,
                has_runs=True,
                limit=configs_groups_page_size,
                offset=groups_offset,
            )

        # Per-header stats: parallel search_runs(limit=1) per group.
        # has_models=True drops runs that have no model — those aren't
        # usable as benchmark configs, so they shouldn't inflate the
        # picker's run count or appear in the inner row list.
        async def _group_stats(gid: UUID):
            async with pool.acquire() as conn:
                rows, total = await search_runs(
                    conn, redis,
                    group_ids=[gid],
                    sort_order="desc",
                    has_models=True,
                    limit=1,
                    offset=0,
                )
            last_at = rows[0].run_created_at if rows else None
            return (gid, total, last_at)

        stats_results = (
            await asyncio.gather(*[_group_stats(g.id) for g in group_summaries])
            if group_summaries
            else []
        )
        run_count_by_gid: dict[UUID, int] = {gid: total for gid, total, _ in stats_results}
        last_at_by_gid: dict[UUID, Any] = {gid: last_at for gid, _, last_at in stats_results}

        # Endpoint-layer secondary filter: drop headers whose
        # has_models=True run count is 0. search_groups(has_runs=True)
        # is cheap and admits any group with at least one runs_mv row;
        # this filter is the model-aware refinement that runs_mv can't
        # express without bloating its definition. Pagination under-
        # fills pages by the drop count — acceptable trade-off vs.
        # showing zero-badge headers that expand to nothing.
        config_group_items: list[TestConfigGroup] = []
        configs_per_group_total: dict[str, int] = {}
        configs_total_universe = 0
        for g in group_summaries:
            count = run_count_by_gid.get(g.id, 0)
            if count == 0:
                continue
            last_at = last_at_by_gid.get(g.id)
            configs_per_group_total[str(g.id)] = count
            configs_total_universe += count
            config_group_items.append(
                TestConfigGroup(
                    group_id=str(g.id),
                    name=g.name,
                    run_count=count,
                    last_run_at=last_at.isoformat() if last_at else None,
                )
            )

        # Outer total unknown — caller uses page-size heuristic. Set to
        # current cumulative offset+page when full page returned, else
        # the exact bound (offset + len) once we know we hit the end.
        is_full_page = len(group_summaries) == configs_groups_page_size
        configs_groups_total = (
            groups_offset + len(group_summaries) + (1 if is_full_page else 0)
        )

        # Inner: fetch rows ONLY for expanded groups that appear on
        # this outer page. Skipping off-page expanded groups keeps the
        # response lean — they'd render as collapsed headers next page
        # anyway. For each expanded group fetch up to
        # configs_expanded_page_size, ordered by recency.
        config_items: list[TestConfigItem] = []
        on_page_expanded = [g for g in group_summaries if g.id in expanded_set]

        # Pre-load each visible run's historical permissions so the
        # client can filter the tools picker per selection. Read once
        # here for every run we're about to surface; parse the
        # ``<artifact>.<operation>.completed`` event from each call's
        # persisted JSON. Black-box: search_calls + _load_call_data.
        from app.infra.generation.chat_history import _load_call_data
        from app.tools.entries.calls.search import search_calls as _search_calls

        permissions_by_run_id: dict[UUID, list[tuple[str, str]]] = {}

        if on_page_expanded:
            async with pool.acquire() as conn:
                # Two-pass: collect ALL config rows first so we can
                # hydrate their referenced agents in bulk before the
                # per-cfg projection loop reads from agent_map.
                rows_by_group: dict[UUID, list[Any]] = {}
                for g in on_page_expanded:
                    rows, _total = await search_runs(
                        conn, redis,
                        group_ids=[g.id],
                        sort_order="desc",
                        has_models=True,
                        limit=configs_expanded_page_size,
                        offset=0,
                    )
                    rows_by_group[g.id] = rows
                # Hydrate any agents referenced by config rows but not
                # already in agent_map. Without this, configs whose
                # historical run was fired by a different agent than
                # the test_invocation's target (e.g. picking a Persona
                # run on an Activity test) end up with empty tool_ids /
                # prompt_ids / instruction_ids on the picker — which
                # /test/invocation/trace then stores as empty, and prepare.py
                # silently falls back to the test_invocation's agent
                # for the replay (using its tools, not the historical
                # run's). The bundle the LLM ends up dispatching against
                # has nothing to do with what the trace tape recorded.
                cfg_agent_ids: set[UUID] = set()
                for rows in rows_by_group.values():
                    for cfg in rows:
                        if cfg.agent_ids:
                            cfg_agent_ids.add(cfg.agent_ids[0])
                missing_cfg_agent_ids = [
                    aid for aid in cfg_agent_ids if aid not in agent_map
                ]
                if missing_cfg_agent_ids:
                    from app.tools.resources.agents.get import (
                        get_agents as _get_agents_for_cfg,
                    )
                    extra_cfg_agents = await _get_agents_for_cfg(
                        conn,
                        missing_cfg_agent_ids,
                        redis or get_redis_client(),
                        bypass_cache=True,
                    )
                    for a in extra_cfg_agents:
                        agent_map[a.id] = a
                # Hydrate any models referenced by those agents.
                missing_cfg_model_ids = {
                    a.model_id
                    for aid in missing_cfg_agent_ids
                    if (a := agent_map.get(aid)) is not None and a.model_id is not None
                    and a.model_id not in model_map
                }
                if missing_cfg_model_ids:
                    from app.tools.resources.models.get import (
                        get_models as _get_models_for_cfg,
                    )
                    extra_cfg_models = await _get_models_for_cfg(
                        conn,
                        list(missing_cfg_model_ids),
                        redis or get_redis_client(),
                        bypass_cache=True,
                    )
                    for m in extra_cfg_models:
                        model_map[m.id] = m

                for g in on_page_expanded:
                    rows = rows_by_group[g.id]
                    if rows:
                        # Pull all calls for these runs in one batch.
                        run_ids_for_perms = [r.run_id for r in rows if r.run_id]
                        all_calls = await _search_calls(
                            conn, redis or get_redis_client(), run_ids=run_ids_for_perms, limit=10000,
                        )
                        for call in all_calls:
                            if call.file_path is None or call.run_id is None:
                                continue
                            receipt = await _load_call_data(call.file_path)
                            if receipt is None:
                                continue
                            for evt in receipt.get("events", []):
                                name = evt.get("event", "")
                                parts = name.split(".") if isinstance(name, str) else []
                                if len(parts) >= 3 and parts[-1] == "completed":
                                    permissions_by_run_id.setdefault(
                                        call.run_id, []
                                    ).append((parts[0], parts[1]))
                                    break  # one perm per call
                    for cfg in rows:
                        cfg_agent_name: str | None = None
                        cfg_model_name: str | None = None
                        cfg_agent_id = cfg.agent_ids[0] if cfg.agent_ids else None
                        # Bundle defaults — populated from the historical
                        # run's agent_resource so the picker can pass them
                        # to /test/invocation/trace for faithful replay.
                        cfg_prompt_ids: list[str] = []
                        cfg_tool_ids: list[str] = []
                        cfg_instruction_ids: list[str] = []
                        cfg_model_id: str | None = None
                        cfg_temperature: float | None = None
                        cfg_reasoning: str | None = None
                        cfg_quality: str | None = None
                        if cfg_agent_id and cfg_agent_id in agent_map:
                            a = agent_map[cfg_agent_id]
                            cfg_agent_name = a.name
                            if a.model_id:
                                cfg_model_id = str(a.model_id)
                                if a.model_id in model_map:
                                    cfg_model_name = model_map[a.model_id].name
                            if a.prompt_id:
                                cfg_prompt_ids = [str(a.prompt_id)]
                            cfg_tool_ids = [str(t) for t in (a.tool_ids or [])]
                            cfg_instruction_ids = [
                                str(i) for i in (a.instruction_ids or [])
                            ]
                            cfg_temperature = a.temperature
                            cfg_reasoning = a.reasoning
                            cfg_quality = a.quality
                        if cfg_model_name is None and cfg.model_ids:
                            mid = cfg.model_ids[0]
                            if mid in model_map:
                                cfg_model_name = model_map[mid].name
                        # UUIDv7 timestamp prefix collisions — disambiguate
                        # via created_at + last 6 chars of the UUID.
                        ts_str: str | None = None
                        if cfg.run_created_at:
                            ts_str = cfg.run_created_at.strftime("%b %d %H:%M:%S")
                        label_parts = [
                            cfg_agent_name or "Agent",
                            cfg_model_name,
                            ts_str,
                            str(cfg.run_id)[-6:],
                        ]
                        label = " · ".join(p for p in label_parts if p)
                        # Dedupe permissions for this run.
                        run_perms_raw = permissions_by_run_id.get(cfg.run_id, [])
                        run_perms = list({p for p in run_perms_raw})
                        config_items.append(
                            TestConfigItem(
                                run_id=str(cfg.run_id),
                                group_id=str(cfg.group_id) if cfg.group_id else None,
                                agent_name=cfg_agent_name,
                                model_name=cfg_model_name,
                                label=label,
                                created_at=cfg.run_created_at.isoformat() if cfg.run_created_at else None,
                                prompt_ids=cfg_prompt_ids,
                                tool_ids=cfg_tool_ids,
                                instruction_ids=cfg_instruction_ids,
                                permissions=run_perms,
                                model_id=cfg_model_id,
                                temperature=cfg_temperature,
                                reasoning=cfg_reasoning,
                                quality=cfg_quality,
                            )
                        )

        # === HYDRATE CONFIG-REFERENCED RESOURCES ===
        # Configs surface ids from arbitrary historical agents — their
        # prompts/instructions/tools/models often aren't in the test
        # context's "selected" sets. Pull the missing ones via canonical
        # black-box ``get_*`` so the panel can prefill bodies + display
        # values without a second fetch. Bulk lookup, cache-friendly.
        cfg_prompt_id_set: set[UUID] = set()
        cfg_instruction_id_set: set[UUID] = set()
        cfg_tool_id_set: set[UUID] = set()
        cfg_model_id_set: set[UUID] = set()
        for ci in config_items:
            for pid in ci.prompt_ids:
                cfg_prompt_id_set.add(UUID(pid))
            for iid in ci.instruction_ids:
                cfg_instruction_id_set.add(UUID(iid))
            for tid in ci.tool_ids:
                cfg_tool_id_set.add(UUID(tid))
            if ci.model_id:
                cfg_model_id_set.add(UUID(ci.model_id))

        prompts_list_for_payload: list = list(_res("prompts"))
        instructions_list_for_payload: list = list(_res("instructions"))
        models_list_for_payload: list = list(models_list)
        # Tool list is built below (needs perm hydration). We collect
        # ids here and merge into ``tools_list_for_payload`` after it's
        # initialized from ``_res_all``.

        existing_prompt_ids = {p.id for p in prompts_list_for_payload}
        existing_instruction_ids = {i.id for i in instructions_list_for_payload}
        existing_model_ids = {m.id for m in models_list_for_payload}

        missing_prompt_ids = [pid for pid in cfg_prompt_id_set if pid not in existing_prompt_ids]
        missing_instruction_ids = [iid for iid in cfg_instruction_id_set if iid not in existing_instruction_ids]
        missing_model_ids = [mid for mid in cfg_model_id_set if mid not in existing_model_ids]

        if missing_prompt_ids or missing_instruction_ids or missing_model_ids:
            async with pool.acquire() as conn:
                if missing_prompt_ids:
                    from app.tools.resources.prompts.get import get_prompts
                    extra_prompts = await get_prompts(
                        conn, missing_prompt_ids, effective_redis,
                    )
                    prompts_list_for_payload.extend(extra_prompts)
                if missing_instruction_ids:
                    from app.tools.resources.instructions.get import get_instructions
                    extra_instructions = await get_instructions(
                        conn, missing_instruction_ids, effective_redis,
                    )
                    instructions_list_for_payload.extend(extra_instructions)
                if missing_model_ids:
                    from app.tools.resources.models.get import (
                        get_models as _get_models_for_cfg_payload,
                    )
                    extra_models = await _get_models_for_cfg_payload(
                        conn, missing_model_ids, effective_redis,
                    )
                    models_list_for_payload.extend(extra_models)

        # === BUILD RESOURCES PAYLOAD ===
        def _to_dict_map(items: list) -> dict[str, dict] | None:
            """Convert resource list to {str(id): dict} map."""
            result: dict[str, dict] = {}
            for item in items:
                result[str(item.id)] = item.model_dump(mode="json")
            return result or None

        # Resolve each tool's permission_ids to (artifact, operation)
        # pairs and stamp onto the tool dict. Lets the client filter
        # the tools picker by the union of currently-selected runs'
        # historical permissions without an extra fetch. Bulk
        # permission lookup so this stays O(1) round-trip.
        from app.tools.resources.permissions.get import get_permissions
        tools_list_for_payload = list(_res_all("tools"))
        existing_tool_ids = {t.id for t in tools_list_for_payload}
        missing_tool_ids = [
            tid for tid in cfg_tool_id_set if tid not in existing_tool_ids
        ]
        if missing_tool_ids:
            async with pool.acquire() as conn:
                from app.tools.resources.tools.get import (
                    get_tools as _get_tools_for_cfg_payload,
                )
                extra_tools = await _get_tools_for_cfg_payload(
                    conn, missing_tool_ids, effective_redis,
                )
                tools_list_for_payload.extend(extra_tools)
        all_tool_perm_ids: set[UUID] = set()
        for t in tools_list_for_payload:
            for pid in (getattr(t, "permission_ids", None) or []):
                all_tool_perm_ids.add(pid)
        if all_tool_perm_ids:
            async with pool.acquire() as conn:
                tool_perms = await get_permissions(
                    conn, list(all_tool_perm_ids), effective_redis, bypass_cache=False,
                )
        else:
            tool_perms = []
        perm_pair_by_id = {
            p.id: [p.artifact, p.operation] for p in tool_perms
        }

        def _to_tool_dict_map(items: list) -> dict[str, dict] | None:
            result: dict[str, dict] = {}
            for t in items:
                d = t.model_dump(mode="json")
                d["permissions"] = [
                    perm_pair_by_id[pid]
                    for pid in (getattr(t, "permission_ids", None) or [])
                    if pid in perm_pair_by_id
                ]
                result[str(t.id)] = d
            return result or None

        # Panel pickers need the full catalog of pickable options
        # (selected + suggestions); other maps stay scoped to selected.
        resources_payload = TestResources(
            evals=_to_dict_map(evals_list),
            rubrics=_to_dict_map(rubrics_list),
            agents=_to_dict_map(agents_list),
            models=_to_dict_map(models_list_for_payload),
            voices=_to_dict_map(_res_all("voices")),
            temperature_levels=_to_dict_map(_res_all("temperature_levels")),
            reasoning_levels=_to_dict_map(_res_all("reasoning_levels")),
            modalities=_to_dict_map(_res_all("modalities")),
            prompts=_to_dict_map(prompts_list_for_payload),
            instructions=_to_dict_map(instructions_list_for_payload),
            tools=_to_tool_dict_map(tools_list_for_payload),
            qualities=_to_dict_map(_res_all("qualities")),
            standard_groups=_to_dict_map(_res("standard_groups")),
            standards=_to_dict_map(_res("standards")),
        )

        # === LOAD HISTORICAL MESSAGES FOR PREVIEWED RUNS ===
        # The picker's currently-selected configs render as dashed-
        # border preview cards in the main history area, interleaved
        # with the test's actual bindings. The bindings' messages are
        # already loaded above via the test context; selected configs
        # may reference runs from arbitrary other groups, so load
        # those messages explicitly. Black-box: search_messages with
        # the run_ids set. Skip silently when nothing selected.
        if configs_selected:
            existing_run_ids: set[UUID] = {
                m.run_id for m in messages if m.run_id is not None
            }
            extra_run_ids = [
                rid for rid in configs_selected if rid not in existing_run_ids
            ]
            if extra_run_ids:
                from app.tools.entries.messages.search import (
                    search_messages as _search_messages_for_preview,
                )
                async with pool.acquire() as conn:
                    extra_messages, _ = await _search_messages_for_preview(
                        conn,
                        run_ids=extra_run_ids,
                        sort_order="asc",
                        limit=10000,
                    )
                # Append to the same list — the client uses run_id to
                # slice messages per row, so order across runs doesn't
                # matter.
                messages = list(messages) + list(extra_messages)

        # === BUILD ENTRIES PAYLOAD ===
        calls = ctx.entries.get("calls", [])
        entries_payload = TestEntries(
            tests=[test],
            invocations=invocations,
            runs=runs if runs else None,
            groups=groups if groups else None,
            grades=grades if grades else None,
            feedback=feedback if feedback else None,
            messages=messages if messages else None,
            calls=calls if calls else None,
        )

        # Inline controls data (replaces auth/group resolution)
        current_invocation_id = (
            str(invocations[0].invocation_id) if invocations else None
        )
        has_runs_or_groups = len(runs) > 0 or len(groups) > 0
        show_controls = bool(invocations)

        # Client-orchestrated state machine — first invocation that hasn't
        # been completed yet, by position. Mirrors next_chat_entry_id on
        # /attempt/get. None means all done → client should call /test/complete.
        sorted_invs = sorted(invocations, key=lambda i: (i.position or 0))
        next_invocation_id = next(
            (str(i.invocation_id) for i in sorted_invs if not i.invocation_completed),
            None,
        )

        # Get first rubric name from map for backward compat
        rubric_name: str | None = None
        if rubric_name_map:
            rubric_name = next(iter(rubric_name_map.values()), None)

        # === BUILD GRADED-VIEW PAYLOAD (per-invocation × per-run) ===
        # Mirrors attempt.entries.attempt_chat[] — one InvocationDetail per
        # invocation, each with rubric_structure + runs[] carrying
        # TableRubric-ready grading_state. The client picks an invocation
        # (global switcher) and a run (local switcher) to drive transcript,
        # rubric, and the right-side resource panel.

        # ── Resource lookups (id → row) for rubric_structure assembly ──
        standards_list = _res("standards")
        standard_groups_list = _res("standard_groups")
        rubrics_by_id: dict[UUID, Any] = {r.id: r for r in rubrics_list}
        standard_groups_by_id: dict[UUID, Any] = {sg.id: sg for sg in standard_groups_list}
        standards_by_id: dict[UUID, Any] = {s.id: s for s in standards_list}
        standards_by_group_id: dict[UUID, list] = {}
        for std in standards_list:
            standards_by_group_id.setdefault(std.standard_group_id, []).append(std)

        # ── Grade / feedback / message indexes ─────────────────────────
        # ``grades`` carries ``invocation_id`` but not ``run_id`` directly.
        # Each grade is tied to a single tool-call (``grade.call_id``)
        # which fired during one specific run. We don't currently project
        # that join here — v1 uses the binding's primary grade via the
        # invocation row (``inv.grade_id``) and aligns extras by
        # creation order. Multi-grade-per-invocation cases will need a
        # proper grade↔run join (TODO: follow-up).
        grades_by_invocation: dict[UUID, list] = {}
        for g in grades:
            grades_by_invocation.setdefault(g.invocation_id, []).append(g)
        # Sort each invocation's grades by creation time so the primary
        # (most-recent or first) is deterministic.
        for inv_id in grades_by_invocation:
            grades_by_invocation[inv_id].sort(key=lambda g: g.created_at)

        feedback_by_grade: dict[UUID, list] = {}
        for f in feedback:
            # GetTestFeedbackResponse carries ``grade_id`` (verify via attr).
            gid = getattr(f, "grade_id", None)
            if gid is not None:
                feedback_by_grade.setdefault(gid, []).append(f)

        msg_ids_by_run_id: dict[UUID, list[UUID]] = {}
        for m in messages:
            # SearchMessageResponse uses ``message_id`` (MV column),
            # not ``id`` like resource-level types.
            if m.run_id:
                msg_ids_by_run_id.setdefault(m.run_id, []).append(m.message_id)

        call_ids_by_run_id: dict[UUID, list[UUID]] = {}
        for c in calls:
            run_id_val = getattr(c, "run_id", None)
            call_id_val = getattr(c, "id", None) or getattr(c, "call_id", None)
            if run_id_val and call_id_val:
                call_ids_by_run_id.setdefault(run_id_val, []).append(call_id_val)

        def _build_rubric_structure(
            rubric_id: UUID | None,
        ) -> RubricStructureData | None:
            if not rubric_id:
                return None
            rubric = rubrics_by_id.get(rubric_id)
            if not rubric:
                return None
            sg_ids = list(rubric.standard_group_ids or [])
            if not sg_ids:
                return None
            standard_groups_dict: dict[str, list[str]] = {}
            standard_groups_mapping_dict: dict[str, StandardGroupMeta] = {}
            standards_mapping_dict: dict[str, StandardMeta] = {}
            for sg_id in sg_ids:
                sg = standard_groups_by_id.get(sg_id)
                if not sg:
                    continue
                stds_in_group = standards_by_group_id.get(sg_id, [])
                standard_groups_dict[str(sg_id)] = [
                    str(s.id) for s in stds_in_group
                ]
                standard_groups_mapping_dict[str(sg_id)] = StandardGroupMeta(
                    name=sg.name,
                    description=sg.description,
                    points=sg.points,
                    pass_points=sg.pass_points,
                )
                for s in stds_in_group:
                    standards_mapping_dict[str(s.id)] = StandardMeta(
                        name=s.name,
                        description=s.description,
                        points=s.points,
                    )
            return RubricStructureData(
                standard_groups=standard_groups_dict or None,
                standard_groups_mapping=standard_groups_mapping_dict or None,
                standards_mapping=standards_mapping_dict or None,
            )

        # ── ``standards`` lookup dicts for compute_passed/achieved ─────
        # The attempt helpers expect resource_meta dicts: {id_str: {...}}.
        # Build them in the shape they expect.
        sg_meta_for_compute: dict[str, dict] = {
            str(sg.id): {
                "name": sg.name,
                "description": sg.description,
                "points": sg.points,
                "pass_points": sg.pass_points,
            }
            for sg in standard_groups_list
        }
        std_meta_for_compute: dict[str, dict] = {
            str(s.id): {
                "name": s.name,
                "description": s.description,
                "points": s.points,
                "standard_group_id": s.standard_group_id,
            }
            for s in standards_list
        }

        def _build_grading_state(
            feedback_rows: list,
        ) -> GradingStateData | None:
            """Compute achieved/passed/feedback maps keyed by standard_id.

            Pulls ``standard_id`` off each feedback row (sourced from
            ``test_feedback_mv``'s LEFT JOIN to
            ``feedbacks_standards_connection``). Legacy rows written
            before the connection was populated have ``standard_id =
            None`` — they're filtered out so they don't pollute the
            grading state with an unkeyed bucket.
            """
            if not feedback_rows:
                return None
            scored_rows = [
                f for f in feedback_rows if getattr(f, "standard_id", None) is not None
            ]
            if not scored_rows:
                return None
            achieved_dict: dict[str, bool] = {}
            passed_dict: dict[str, bool] = {}
            feedback_dict: dict[str, str] = {}
            feedbacks_dicts = [
                {
                    "standard_id": getattr(f, "standard_id", None),
                    "total": getattr(f, "total", None),
                }
                for f in scored_rows
            ]
            achieved_raw = compute_achieved_standards(feedbacks_dicts)
            for entry in achieved_raw or []:
                std_id = entry.get("standard_id")
                if std_id:
                    achieved_dict[str(std_id)] = entry.get("achieved", False)
            passed_raw = compute_passed_standards(
                feedbacks_dicts, sg_meta_for_compute, std_meta_for_compute,
            )
            for entry in passed_raw or []:
                std_id = entry.get("standard_id")
                if std_id:
                    passed_dict[str(std_id)] = entry.get("passed", False)
            for f in scored_rows:
                std_id = getattr(f, "standard_id", None)
                text = getattr(f, "feedback", None)
                if std_id and text:
                    feedback_dict[str(std_id)] = text
            return GradingStateData(
                achieved_standards=achieved_dict or None,
                passed_standards=passed_dict or None,
                feedback_by_standard_id=feedback_dict or None,
            )

        invocation_details: list[InvocationDetail] = []
        for inv in invocations:
            inv_bindings = runs_by_invocation.get(inv.invocation_id, [])
            inv_grades = grades_by_invocation.get(inv.invocation_id, [])
            grades_remaining = list(inv_grades)

            inv_run_details: list[InvocationRunDetail] = []
            primary_run_id: UUID | None = None
            for binding in inv_bindings:
                # Pair this binding's run with a grade. Primary grade
                # (``inv.grade_id``) wins for the row-summary binding;
                # the rest pop in creation order. When grades and
                # bindings don't align 1:1 the leftover bindings
                # render ungraded (grade=None / grading_state=None),
                # which the FE handles via "Not graded" state.
                paired_grade = None
                if inv.grade_id is not None:
                    for i, g in enumerate(grades_remaining):
                        if g.id == inv.grade_id:
                            paired_grade = grades_remaining.pop(i)
                            break
                if paired_grade is None and grades_remaining:
                    paired_grade = grades_remaining.pop(0)

                grade_data: GradeData | None = None
                grading_state: GradingStateData | None = None
                fb_entries: list[FeedbackEntry] | None = None
                paired_feedback: list = []
                if paired_grade is not None:
                    # Pull total/pass points off the invocation's rubric
                    # (top-level rubric_resource carries them). Same
                    # source attempt uses.
                    rubric = rubrics_by_id.get(inv.rubric_id) if inv.rubric_id else None
                    grade_data = GradeData(
                        score=paired_grade.score,
                        passed=paired_grade.passed,
                        time_taken=paired_grade.time_taken,
                        total_points=getattr(rubric, "points", None) if rubric else None,
                        pass_points=getattr(rubric, "pass_points", None) if rubric else None,
                    )
                    paired_feedback = feedback_by_grade.get(paired_grade.id, [])
                    grading_state = _build_grading_state(paired_feedback)
                    if paired_feedback:
                        fb_entries = []
                        for f in paired_feedback:
                            std_id = getattr(f, "standard_id", None)
                            std = standards_by_id.get(std_id) if std_id else None
                            fb_entries.append(
                                FeedbackEntry(
                                    # test_feedback_mv exposes ``feedback_id``;
                                    # attempt exposes ``id``. Accept either.
                                    id=(
                                        getattr(f, "feedback_id", None)
                                        or getattr(f, "id", None)
                                    ),
                                    standard_id=std_id,
                                    standard_group_id=(
                                        std.standard_group_id if std else None
                                    ),
                                    total=getattr(f, "total", None),
                                    feedback=getattr(f, "feedback", None),
                                )
                            )

                run_id = binding.run_id
                is_primary = (
                    paired_grade is not None
                    and inv.grade_id is not None
                    and paired_grade.id == inv.grade_id
                )
                if is_primary and run_id:
                    primary_run_id = run_id

                inv_run_details.append(
                    InvocationRunDetail(
                        run_id=run_id or binding.id,
                        binding_id=binding.id,
                        grade_id=paired_grade.id if paired_grade else None,
                        created_at=binding.created_at,
                        completed=binding.id in completed_binding_ids,
                        grade=grade_data,
                        grading_state=grading_state,
                        feedbacks=fb_entries,
                        analyses=None,  # test artifact has no analyses table yet
                        message_ids=(
                            msg_ids_by_run_id.get(run_id) if run_id else None
                        ),
                        call_ids=(
                            call_ids_by_run_id.get(run_id) if run_id else None
                        ),
                    )
                )

            # Fallback: if no binding owned the primary grade, fall back
            # to the first run with a grade, then the first run at all.
            if primary_run_id is None:
                primary_run_id = next(
                    (r.run_id for r in inv_run_details if r.grade is not None),
                    None,
                )
            if primary_run_id is None and inv_run_details:
                primary_run_id = inv_run_details[0].run_id

            # Historical config bundle — pulled from the invocation's
            # first agent. The FE looks these up against ``resources.*``
            # keyed by id to render the read-only snapshot panel.
            agent_id = inv.agent_ids[0] if inv.agent_ids else None
            model_id_for_inv: UUID | None = None
            if agent_id and agent_id in agent_map:
                model_id_for_inv = agent_map[agent_id].model_id

            invocation_details.append(
                InvocationDetail(
                    invocation_id=inv.invocation_id,
                    rubric_id=inv.rubric_id,
                    rubric_structure=_build_rubric_structure(inv.rubric_id),
                    primary_run_id=primary_run_id,
                    agent_id=agent_id,
                    model_id=model_id_for_inv,
                    voice_id=inv.voice_id,
                    temperature_level_id=inv.temperature_level_id,
                    reasoning_level_id=inv.reasoning_level_id,
                    quality_id=inv.quality_id,
                    modality_ids=list(inv.modality_ids or []),
                    runs=inv_run_details,
                )
            )

        return GetTestArtifactResponse(
            test=test,
            invocations=invocations,
            status=status,
            eval_name=eval_name,
            eval_description=eval_description,
            rubric_name=rubric_name,
            infinite_mode=test.infinite_mode,
            runs=run_items,
            configs=config_items,
            configs_groups=config_group_items,
            configs_total=configs_total_universe,
            configs_groups_total=configs_groups_total,
            configs_per_group_total=configs_per_group_total,
            status_summary=status_summary,
            show_controls=show_controls,
            current_invocation_id=current_invocation_id,
            has_runs_or_groups=has_runs_or_groups,
            next_invocation_id=next_invocation_id,
            invocation_details=invocation_details,
            entries=entries_payload,
            resources=resources_payload,
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
    cache_key_path: str = "/test/get",
    configs_groups_page: int = 1,
    configs_groups_page_size: int = 10,
    configs_expanded: list[UUID] | None = None,
    configs_expanded_page_size: int = 20,
    configs_search: str | None = None,
    configs_selected: list[UUID] | None = None,
) -> tuple[GetTestArtifactResponse, bool]:
    """HTTP response layer with caching.

    Calls get_test_impl() and assembles GetTestArtifactResponse.
    Returns (response, cache_hit). Cache key includes pagination kwargs
    so different pages don't collide.
    """
    tags = ["artifacts", "test"]
    body_dict = GetTestArtifactRequest(
        test_id=test_id,
        configs_groups_page=configs_groups_page,
        configs_groups_page_size=configs_groups_page_size,
        configs_expanded=configs_expanded or [],
        configs_expanded_page_size=configs_expanded_page_size,
        configs_search=configs_search,
        configs_selected=configs_selected or [],
    ).model_dump(mode="json")
    cache_key_val = cache_key(cache_key_path, body_dict)

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return GetTestArtifactResponse.model_validate(cached["data"]), True

    api_response = await get_test_impl(
        pool,
        id=test_id,
        bypass_cache=bypass_cache,
        configs_groups_page=configs_groups_page,
        configs_groups_page_size=configs_groups_page_size,
        configs_expanded=configs_expanded,
        configs_expanded_page_size=configs_expanded_page_size,
        configs_search=configs_search,
        configs_selected=configs_selected,
    )

    if not api_response.test:
        raise HTTPException(status_code=404, detail="Benchmark test not found")

    await set_cached(
        cache_key_val,
        {"data": api_response.model_dump(mode="json")},
        ttl=300,
        tags=tags,
        redis=get_redis_client(),
    )

    return api_response, False
