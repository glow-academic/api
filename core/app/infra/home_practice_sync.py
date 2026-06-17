"""Home/practice entry sync — pre-create home/practice + chat entries on cohort save.

Atomic + idempotent (mirrors ``benchmark/sync.py``): the whole scaffold
(session + every home/practice entry + every chat + the bridge rows) is
written in ONE transaction (all-or-nothing), and a re-run for the same cohort
first deactivates that cohort's prior *generated* home/practice/chat tree
before re-creating, so ``/cohort/update`` calling this on every save REPLACES
the scaffold instead of appending duplicates.

The clear is scoped to a single cohort via its stable ``cohort_artifact`` id:
each ``/cohort/update`` mints a fresh ``cohorts_resource`` *snapshot*, so the
prior tree hangs off an older snapshot id, not the current one. We therefore
walk ``cohort_cohorts_junction`` (artifact → all its snapshots, active or not)
to find every snapshot this cohort has ever had, then deactivate the generated
home/practice entries (+ their chats and bridge rows) that link any of those
snapshots. Other cohorts are untouched. Reads gate on ``active = true``
(home_mv / practice_mv), so deactivation drops the stale scaffold from every
consumer; the fresh set is created inside the same transaction → a retry
REPLACES, never appends.

Uses black-box entry creation tools for the writes; the scoped deactivation is
a single guarded SQL statement.
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.resources.scenario_flags.types import GetScenarioFlagResponse
from app.tools.resources.scenario_positions.types import (
    GetScenarioPositionResponse,
)
from app.tools.resources.scenario_rubrics.types import (
    GetScenarioRubricResponse,
)
from app.tools.resources.scenario_time_limits.types import (
    GetScenarioTimeLimitResponse,
)
from app.tools.resources.scenarios.types import GetScenarioResponse
from app.tools.resources.simulation_availability.types import (
    GetSimulationAvailabilityResponse,
)
from app.tools.resources.simulation_positions.types import (
    GetSimulationPositionResponse,
)
from app.utils.cache.hedged_row import invalidate_row, transaction_with_writeback
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# Flag name → chat_entry column mapping (13 entries)
FLAG_NAME_TO_COLUMN: dict[str, str] = {
    "Audio Enabled": "audio_enabled",
    "Text Enabled": "text_enabled",
    "Hints Enabled": "hints_enabled",
    "Copy Paste Allowed": "copy_paste_allowed",
    "Show Images": "show_images",
    "Show Objectives": "show_objectives",
    "Show Problem Statement": "show_problem_statement",
    "Analyses Enabled": "analyses_enabled",
    "Improvements Enabled": "improvements_enabled",
    "Strengths Enabled": "strengths_enabled",
    "Use Custom": "use_custom",
    "Use Previous": "use_previous",
}


async def sync_home_practice_entries(
    pool: asyncpg.Pool,
    cohorts_resource_id: UUID,
    simulation_ids: list[UUID],
    simulation_position_ids: list[UUID],
    simulation_availability_ids: list[UUID],
    department_ids: list[UUID],
    profile_ids: list[UUID],
    profile_persona_ids: list[UUID],
    cohort_artifact_id: UUID | None = None,
) -> int:
    """Sync cohort entries by pre-creating home/practice + chat entries.

    Three-pass approach:
    1. Fetch simulations to get scenario_ids and sub-resource IDs
    2. Parallel fetch all sub-resources
    3. Build data structures and call entry creation tools

    Idempotent when ``cohort_artifact_id`` is supplied: this cohort's prior
    generated home/practice/chat tree is deactivated inside the write
    transaction before the fresh set is created (see module docstring). When
    omitted (e.g. a brand-new cohort with no prior tree) the clear is a no-op.
    """
    from app.infra.globals import get_redis_client
    from app.tools.entries.chat.create import create_chat
    from app.tools.entries.home.create import create_home
    from app.tools.entries.home_chat.create import create_home_chat
    from app.tools.entries.practice.create import create_practice
    from app.tools.entries.practice_chat.create import (
        create_practice_chat,
    )
    from app.tools.entries.sessions.create import create_session
    from app.tools.resources.flags.get import get_flags
    from app.tools.resources.rubrics.get import get_rubrics
    from app.tools.resources.scenario_flags.get import (
        get_scenario_flags,
    )
    from app.tools.resources.scenario_positions.get import (
        get_scenario_positions,
    )
    from app.tools.resources.scenario_rubrics.get import (
        get_scenario_rubrics,
    )
    from app.tools.resources.scenario_time_limits.get import (
        get_scenario_time_limits,
    )
    from app.tools.resources.scenarios.get import get_scenarios
    from app.tools.resources.simulation_availability.get import (
        get_simulation_availability,
    )
    from app.tools.resources.simulation_positions.get import (
        get_simulation_positions,
    )
    from app.tools.resources.simulations.get import get_simulations
    from app.tools.resources.standards.search import search_standards

    if not simulation_ids:
        return 0

    # ── Pass 1: Fetch simulations ──
    simulations = await get_simulations(pool, simulation_ids, get_redis_client(), bypass_cache=True
    )

    if not simulations:
        return 0

    # Collect all sub-resource IDs across simulations
    all_scenario_ids: list[UUID] = []
    all_scenario_rubric_ids: list[UUID] = []
    all_scenario_flag_ids: list[UUID] = []
    all_scenario_position_ids: list[UUID] = []
    all_scenario_time_limit_ids: list[UUID] = []

    for sim in simulations:
        all_scenario_ids.extend(sim.scenario_ids or [])
        all_scenario_rubric_ids.extend(sim.scenario_rubric_ids or [])
        all_scenario_flag_ids.extend(sim.scenario_flag_ids or [])
        all_scenario_position_ids.extend(sim.scenario_position_ids or [])
        all_scenario_time_limit_ids.extend(sim.scenario_time_limit_ids or [])

    # ── Pass 2a: Parallel fetch all sub-resources ──
    # Each fetch acquires its own connection from the pool to avoid
    # asyncpg "another operation is in progress" on concurrent queries.
    async def _fetch_scenarios() -> list[GetScenarioResponse]:
        async with pool.acquire() as c:
            return await get_scenarios(
                c, all_scenario_ids, get_redis_client(), bypass_cache=True
            )

    async def _fetch_scenario_rubrics() -> list[GetScenarioRubricResponse]:
        async with pool.acquire() as c:
            return await get_scenario_rubrics(
                c, all_scenario_rubric_ids, get_redis_client(), bypass_cache=True
            )

    async def _fetch_scenario_flags() -> list[GetScenarioFlagResponse]:
        async with pool.acquire() as c:
            return await get_scenario_flags(
                c, all_scenario_flag_ids, get_redis_client(), bypass_cache=True
            )

    async def _fetch_scenario_positions() -> list[GetScenarioPositionResponse]:
        async with pool.acquire() as c:
            return await get_scenario_positions(
                c, all_scenario_position_ids, get_redis_client(), bypass_cache=True
            )

    async def _fetch_scenario_time_limits() -> list[GetScenarioTimeLimitResponse]:
        async with pool.acquire() as c:
            return await get_scenario_time_limits(
                c, all_scenario_time_limit_ids, get_redis_client(), bypass_cache=True
            )

    async def _fetch_sim_positions() -> list[GetSimulationPositionResponse]:
        async with pool.acquire() as c:
            return await get_simulation_positions(
                c, simulation_position_ids, get_redis_client(), bypass_cache=True
            )

    async def _fetch_sim_availability() -> list[GetSimulationAvailabilityResponse]:
        async with pool.acquire() as c:
            return await get_simulation_availability(
                c, simulation_availability_ids, get_redis_client(), bypass_cache=True
            )

    gather_results = await asyncio.gather(
        _fetch_scenarios(),
        _fetch_scenario_rubrics(),
        _fetch_scenario_flags(),
        _fetch_scenario_positions(),
        _fetch_scenario_time_limits(),
        _fetch_sim_positions(),
        _fetch_sim_availability(),
    )
    scenarios: list[GetScenarioResponse] = gather_results[0]
    scenario_rubrics: list[GetScenarioRubricResponse] = gather_results[1]
    scenario_flags: list[GetScenarioFlagResponse] = gather_results[2]
    scenario_positions: list[GetScenarioPositionResponse] = gather_results[3]
    scenario_time_limits: list[GetScenarioTimeLimitResponse] = gather_results[4]
    sim_positions: list[GetSimulationPositionResponse] = gather_results[5]
    sim_availability: list[GetSimulationAvailabilityResponse] = gather_results[6]

    # ── Pass 2b: Resolve rubrics → standard_group_ids → standards ──
    # Collect all resolved rubric IDs (rubrics_resource.id) from scenario_rubrics
    all_rubric_ids: list[UUID] = []
    for sr in scenario_rubrics:
        if sr.rubric_id:
            all_rubric_ids.append(sr.rubric_id)
    all_rubric_ids = list(set(all_rubric_ids))

    rubrics: list[Any] = []
    standards: list[Any] = []
    if all_rubric_ids:
        async with pool.acquire() as rub_conn:
            rubrics = await get_rubrics(
                rub_conn, all_rubric_ids, get_redis_client(), bypass_cache=True
            )

        # Collect all standard_group_ids from rubrics
        all_standard_group_ids: list[UUID] = []
        for rub in rubrics:
            if rub.standard_group_ids:
                all_standard_group_ids.extend(rub.standard_group_ids)
        all_standard_group_ids = list(set(all_standard_group_ids))

        if all_standard_group_ids:
            # Fetch all standards belonging to these groups via search internal
            async with pool.acquire() as std_conn:
                standards = await search_standards(
                    std_conn,
                    get_redis_client(),
                    standard_group_ids=all_standard_group_ids,
                    limit_count=10000,
                    bypass_cache=True,
                )

    # ── Pass 3: Build lookup dicts ──

    # scenario_id → scenario data
    scenario_map = {s.id: s for s in scenarios if s.id}

    # scenario_rubric_id → rubrics_resource.id (resolved)
    rubric_map: dict[UUID, UUID] = {}
    scenario_rubric_by_id: dict[UUID, GetScenarioRubricResponse] = {}
    for r in scenario_rubrics:
        if r.id:
            scenario_rubric_by_id[r.id] = r
        if r.id and r.rubric_id:
            rubric_map[r.id] = r.rubric_id

    # rubric_id → standard_group_ids
    rubric_sg_map: dict[UUID, list[UUID]] = {}
    for rub in rubrics:
        if rub.id and rub.standard_group_ids:
            rubric_sg_map[rub.id] = list(rub.standard_group_ids)

    # standard_group_id → list of standard_ids
    sg_standards_map: dict[UUID, list[UUID]] = {}
    for std in standards:
        if std.standard_group_id and std.id:
            sg_standards_map.setdefault(std.standard_group_id, []).append(std.id)

    # Resolve flag names from flags_resource (scenario_flags only have flag_id)
    all_flag_ids = list({sf.flag_id for sf in scenario_flags if sf.flag_id})
    flag_name_map: dict[UUID, str] = {}
    if all_flag_ids:
        async with pool.acquire() as flag_conn:
            flags = await get_flags(
                flag_conn, all_flag_ids, get_redis_client(), bypass_cache=True
            )
            flag_name_map = {f.id: f.name for f in flags if f.id and f.name}

    # scenario_flag_id → {column_name: True}
    flag_map: dict[UUID, dict[str, bool]] = {}
    for sf in scenario_flags:
        if sf.id and sf.flag_id:
            flag_name = flag_name_map.get(sf.flag_id)
            if flag_name:
                col = FLAG_NAME_TO_COLUMN.get(flag_name)
                if col:
                    flag_map.setdefault(sf.id, {})[col] = True

    # scenario_position_id → value (int)
    pos_map: dict[UUID, int] = {}
    for p in scenario_positions:
        if p.id and p.value is not None:
            pos_map[p.id] = p.value

    # scenario_time_limit_id → (seconds, negative)
    time_limit_map: dict[UUID, tuple[int | None, bool]] = {}
    for t in scenario_time_limits:
        if t.id:
            time_limit_map[t.id] = (t.time_limit_seconds, t.negative or False)

    # ── Build simulation data (grouped with their chats) ──
    entry_count = 0

    # Build per-simulation structures
    sim_data_list: list[dict[str, Any]] = []
    for sim in simulations:
        if not sim.id:
            continue

        # Resolve position from simulation_positions
        resolved_position = 0
        for p in sim_positions:
            if p.simulation_id and p.simulation_id == sim.id:
                resolved_position = p.value or 0
                break

        # Resolve start/end times from availability
        start_time: datetime | None = None
        end_time: datetime | None = None
        for a in sim_availability:
            if a.simulation_id and a.simulation_id == sim.id:
                if a.type == "start":
                    start_time = (
                        a.time
                        if isinstance(a.time, datetime)
                        else (datetime.fromisoformat(a.time) if a.time else None)
                    )
                elif a.type == "end":
                    end_time = (
                        a.time
                        if isinstance(a.time, datetime)
                        else (datetime.fromisoformat(a.time) if a.time else None)
                    )

        # Resolve position and availability resource IDs for this simulation
        sim_pos_resource_ids = [
            p.id
            for p in sim_positions
            if p.simulation_id and p.simulation_id == sim.id and p.id
        ]
        sim_avail_resource_ids = [
            a.id
            for a in sim_availability
            if a.simulation_id and a.simulation_id == sim.id and a.id
        ]

        # Build chat data for this simulation
        scenario_ids_for_sim = list(sim.scenario_ids or [])
        scenario_rubric_ids_for_sim = list(sim.scenario_rubric_ids or [])
        scenario_flag_ids_for_sim = list(sim.scenario_flag_ids or [])
        scenario_position_ids_for_sim = list(sim.scenario_position_ids or [])
        scenario_time_limit_ids_for_sim = list(sim.scenario_time_limit_ids or [])

        chat_data_list: list[dict[str, Any]] = []
        for scenario_id in scenario_ids_for_sim:
            scenario = scenario_map.get(scenario_id)
            if not scenario:
                continue

            # Resolve rubric IDs (scenario_rubric_id → rubrics_resource.id)
            resolved_rubric_ids: list[UUID] = []
            for sr_id in scenario_rubric_ids_for_sim:
                scenario_rubric = scenario_rubric_by_id.get(sr_id)
                if scenario_rubric and scenario_rubric.scenario_id != scenario_id:
                    continue
                resolved = rubric_map.get(sr_id)
                if resolved:
                    resolved_rubric_ids.append(resolved)

            # Resolve position
            chat_position = 0
            for sp_id in scenario_position_ids_for_sim:
                if sp_id in pos_map:
                    for p in scenario_positions:
                        if p.id == sp_id and p.scenario_id == scenario_id:
                            chat_position = p.value or 0
                            break

            # Resolve time limit
            chat_time_limit: int | None = None
            chat_negative_time = False
            for st_id in scenario_time_limit_ids_for_sim:
                if st_id in time_limit_map:
                    for t in scenario_time_limits:
                        if t.id == st_id and t.scenario_id == scenario_id:
                            chat_time_limit = t.time_limit_seconds
                            chat_negative_time = t.negative or False
                            break

            # Resolve flags (13 booleans)
            flag_bools: dict[str, bool] = {}
            for sf_id in scenario_flag_ids_for_sim:
                if sf_id in flag_map:
                    for f in scenario_flags:
                        if f.id == sf_id and f.scenario_id == scenario_id:
                            flag_bools.update(flag_map[sf_id])
                            break

            # Content-enabled flags (from scenario)
            ps_enabled = scenario.problem_statement_enabled or False
            obj_enabled = scenario.objectives_enabled or False
            vid_enabled = scenario.video_enabled or False
            img_enabled = scenario.images_enabled or False
            q_enabled = scenario.questions_enabled or False

            # Generate flags
            gen_ps = ps_enabled
            gen_obj = obj_enabled
            gen_vid = vid_enabled
            gen_img = img_enabled
            gen_q = q_enabled
            gen_personas = len(scenario.persona_ids or []) > 0
            gen_documents = len(scenario.document_ids or []) > 0
            gen_options = len(scenario.option_ids or []) > 0
            gen_param_fields = len(scenario.parameter_field_ids or []) > 0
            all_others = all(
                [
                    gen_ps,
                    gen_obj,
                    gen_vid,
                    gen_img,
                    gen_q,
                    gen_personas,
                    gen_documents,
                    gen_options,
                    gen_param_fields,
                ]
            )
            gen_names = not all_others
            gen_descriptions = not all_others

            # Scenario flag/position/time_limit resource IDs for this scenario
            chat_scenario_flag_ids = [
                f.id for f in scenario_flags if f.scenario_id == scenario_id and f.id
            ]
            chat_scenario_position_ids = [
                p.id
                for p in scenario_positions
                if p.scenario_id == scenario_id and p.id
            ]
            chat_scenario_time_limit_ids = [
                t.id
                for t in scenario_time_limits
                if t.scenario_id == scenario_id and t.id
            ]

            # Resolve standard_group_ids and standard_ids from rubrics
            chat_standard_group_ids: list[UUID] = []
            chat_standard_ids: list[UUID] = []
            for rub_id in resolved_rubric_ids:
                for sg_id in rubric_sg_map.get(rub_id, []):
                    if sg_id not in chat_standard_group_ids:
                        chat_standard_group_ids.append(sg_id)
                    for std_id in sg_standards_map.get(sg_id, []):
                        if std_id not in chat_standard_ids:
                            chat_standard_ids.append(std_id)

            chat_data_list.append(
                {
                    "scenario_id": scenario_id,
                    "name": scenario.name or "",
                    "description": scenario.description or "",
                    "position": chat_position,
                    "time_limit": chat_time_limit,
                    "negative_time": chat_negative_time,
                    # 13 flag booleans
                    "audio_enabled": flag_bools.get("audio_enabled", True),
                    "text_enabled": flag_bools.get("text_enabled", True),
                    "hints_enabled": flag_bools.get("hints_enabled", True),
                    "copy_paste_allowed": flag_bools.get("copy_paste_allowed", True),
                    "show_images": flag_bools.get("show_images", True),
                    "show_objectives": flag_bools.get("show_objectives", True),
                    "show_problem_statement": flag_bools.get(
                        "show_problem_statement", True
                    ),
                    "analyses_enabled": flag_bools.get("analyses_enabled", True),
                    "improvements_enabled": flag_bools.get(
                        "improvements_enabled", True
                    ),
                    "strengths_enabled": flag_bools.get("strengths_enabled", True),
                    "use_custom": flag_bools.get("use_custom", False),
                    "use_previous": flag_bools.get("use_previous", False),
                    # 5 content-enabled
                    "problem_statement_enabled": ps_enabled,
                    "objectives_enabled": obj_enabled,
                    "video_enabled": vid_enabled,
                    "images_enabled": img_enabled,
                    "questions_enabled": q_enabled,
                    # 11 generate flags
                    "generate_problem_statements": gen_ps,
                    "generate_objectives": gen_obj,
                    "generate_videos": gen_vid,
                    "generate_images": gen_img,
                    "generate_questions": gen_q,
                    "generate_personas": gen_personas,
                    "generate_documents": gen_documents,
                    "generate_options": gen_options,
                    "generate_parameter_fields": gen_param_fields,
                    "generate_names": gen_names,
                    "generate_descriptions": gen_descriptions,
                    # connection resource IDs
                    "rubric_ids": resolved_rubric_ids,
                    "scenario_flag_ids": chat_scenario_flag_ids,
                    "scenario_position_ids": chat_scenario_position_ids,
                    "scenario_time_limit_ids": chat_scenario_time_limit_ids,
                    "persona_ids": list(scenario.persona_ids or []),
                    "document_ids": list(scenario.document_ids or []),
                    "image_ids": list(scenario.image_ids or []),
                    "video_ids": list(scenario.video_ids or []),
                    "question_ids": list(scenario.question_ids or []),
                    "option_ids": list(scenario.option_ids or []),
                    "problem_statement_ids": list(scenario.problem_statement_ids or []),
                    "objective_ids": list(scenario.objective_ids or []),
                    "parameter_field_ids": list(scenario.parameter_field_ids or []),
                    "standard_group_ids": chat_standard_group_ids,
                    "standard_ids": chat_standard_ids,
                }
            )

        sim_data_list.append(
            {
                "simulation_id": sim.id,
                "is_practice": sim.practice or False,
                "position": resolved_position,
                "start_time": start_time,
                "end_time": end_time,
                "sim_pos_resource_ids": sim_pos_resource_ids,
                "sim_avail_resource_ids": sim_avail_resource_ids,
                "chats": chat_data_list,
            }
        )

    # ── Create entries using black-box tools ──
    # One entry per simulation (shared across all profiles), one chat per scenario.
    redis = get_redis_client()
    async with pool.acquire() as conn:
        # HC2: defer the fresh tree's Redis write-backs to post-commit so a
        # rollback of this re-sync leaves no phantom home/practice/chat cache
        # rows (the create tools' write_back_row calls enqueue inside this block).
        async with transaction_with_writeback(conn):
            # ── Idempotency clear (scoped to this cohort) ──
            # ``/cohort/update`` re-runs this on every save and the create
            # tools are plain INSERTs, so without a clear each re-run appended
            # a fresh full home/practice/chat tree → duplicates. Deactivate
            # THIS cohort's prior generated tree first, scoped via the stable
            # ``cohort_artifact`` id: walk ``cohort_cohorts_junction`` to every
            # snapshot this cohort has ever had (a fresh snapshot is minted per
            # update, so the prior tree links an OLDER snapshot, not
            # ``cohorts_resource_id``), find the generated home/practice entries
            # that link any of those snapshots, and soft-delete the entries,
            # their chats, the home/practice↔chat bridge rows, and the cohorts
            # connections. ``generated = true`` keeps us off any hand-authored
            # entry. Reads gate on ``active = true`` (home_mv/practice_mv), so
            # this drops the stale scaffold from every consumer; the fresh set
            # is created below in the same transaction → replace, never append.
            if cohort_artifact_id is not None:
                # HC3 (report-21): the deactivated home/practice/chat rows are
                # served from the hedged per-id cache (home/practice/chat GET +
                # search read ``entry:<ns>:<id>``). Soft-deleting them in
                # Postgres alone left those cache rows live for the TTL, so a
                # GET right after a re-sync would still return the stale (now
                # inactive) scaffold. Capture every deactivated id and bust its
                # cache row below. The final statement is now a ``fetch`` whose
                # CTE collects the three id sets the consumers cache by.
                deact_rows = await conn.fetch(
                    """
                    WITH snaps AS (
                        SELECT ccj.cohorts_id
                        FROM cohort_cohorts_junction ccj
                        WHERE ccj.cohort_id = $1
                    ),
                    prior_home AS (
                        SELECT DISTINCT he.id
                        FROM home_entry he
                        JOIN home_cohorts_connection hcc
                          ON hcc.home_id = he.id
                        WHERE hcc.cohorts_id IN (SELECT cohorts_id FROM snaps)
                          AND he.active = true
                          AND he.generated = true
                    ),
                    prior_practice AS (
                        SELECT DISTINCT pe.id
                        FROM practice_entry pe
                        JOIN practice_cohorts_connection pcc
                          ON pcc.practice_id = pe.id
                        WHERE pcc.cohorts_id IN (SELECT cohorts_id FROM snaps)
                          AND pe.active = true
                          AND pe.generated = true
                    ),
                    home_chats AS (
                        SELECT hce.id AS bridge_id, hce.chat_id
                        FROM home_chat_entry hce
                        WHERE hce.home_id IN (SELECT id FROM prior_home)
                          AND hce.active = true
                    ),
                    practice_chats AS (
                        SELECT pce.id AS bridge_id, pce.chat_id
                        FROM practice_chat_entry pce
                        WHERE pce.practice_id IN (SELECT id FROM prior_practice)
                          AND pce.active = true
                    ),
                    deact_chats AS (
                        UPDATE chat_entry ce
                        SET active = false
                        WHERE ce.id IN (
                                SELECT chat_id FROM home_chats
                                UNION
                                SELECT chat_id FROM practice_chats
                            )
                          AND ce.active = true
                          AND ce.generated = true
                        RETURNING ce.id
                    ),
                    deact_home_bridge AS (
                        UPDATE home_chat_entry hce
                        SET active = false
                        WHERE hce.id IN (SELECT bridge_id FROM home_chats)
                        RETURNING hce.id
                    ),
                    deact_practice_bridge AS (
                        UPDATE practice_chat_entry pce
                        SET active = false
                        WHERE pce.id IN (SELECT bridge_id FROM practice_chats)
                        RETURNING pce.id
                    ),
                    deact_home_conn AS (
                        UPDATE home_cohorts_connection hcc
                        SET active = false
                        WHERE hcc.home_id IN (SELECT id FROM prior_home)
                          AND hcc.active = true
                        RETURNING 1
                    ),
                    deact_practice_conn AS (
                        UPDATE practice_cohorts_connection pcc
                        SET active = false
                        WHERE pcc.practice_id IN (SELECT id FROM prior_practice)
                          AND pcc.active = true
                        RETURNING 1
                    ),
                    deact_home AS (
                        UPDATE home_entry he
                        SET active = false
                        WHERE he.id IN (SELECT id FROM prior_home)
                        RETURNING he.id
                    ),
                    deact_practice AS (
                        UPDATE practice_entry pe
                        SET active = false
                        WHERE pe.id IN (SELECT id FROM prior_practice)
                        RETURNING pe.id
                    )
                    SELECT 'home'          AS ns, id FROM deact_home
                    UNION ALL
                    SELECT 'practice'      AS ns, id FROM deact_practice
                    UNION ALL
                    SELECT 'chat'          AS ns, id FROM deact_chats
                    UNION ALL
                    SELECT 'home_chat'     AS ns, id FROM deact_home_bridge
                    UNION ALL
                    SELECT 'practice_chat' AS ns, id FROM deact_practice_bridge
                    """,
                    cohort_artifact_id,
                )

                # Bust each soft-deleted row's per-id hedged cache key so the
                # stale scaffold is no longer served from cache. ``invalidate_row``
                # is a best-effort DELETE (not a deferred write-back): a rollback
                # of this re-sync would only bust still-valid cache rows, which
                # self-heal on the next read/MV-refresh — never serves stale data.
                for r in deact_rows:
                    await invalidate_row(redis, r["ns"], r["id"])

            session = await create_session(conn, redis)

            for sim_data in sim_data_list:
                if sim_data["is_practice"]:
                    parent = await create_practice(
                        conn, redis,
                        session_id=session.id,
                        cohorts_ids=[cohorts_resource_id],
                        departments_ids=department_ids,
                        simulations_ids=[sim_data["simulation_id"]],
                        profiles_ids=profile_ids,
                        profile_personas_ids=profile_persona_ids,
                        simulation_availability_ids=sim_data["sim_avail_resource_ids"],
                        simulation_positions_ids=sim_data["sim_pos_resource_ids"],
                        position=sim_data["position"],
                        start_time=sim_data["start_time"],
                        end_time=sim_data["end_time"],
                    )
                else:
                    parent = await create_home(
                        conn, redis,
                        session_id=session.id,
                        cohorts_ids=[cohorts_resource_id],
                        departments_ids=department_ids,
                        simulations_ids=[sim_data["simulation_id"]],
                        profiles_ids=profile_ids,
                        profile_personas_ids=profile_persona_ids,
                        simulation_availability_ids=sim_data["sim_avail_resource_ids"],
                        simulation_positions_ids=sim_data["sim_pos_resource_ids"],
                        position=sim_data["position"],
                        start_time=sim_data["start_time"],
                        end_time=sim_data["end_time"],
                    )

                entry_count += 1

                for chat_data in sim_data["chats"]:
                    chat = await create_chat(
                        conn, redis,
                        session_id=session.id,
                        scenario_ids=[chat_data["scenario_id"]],
                        position=chat_data["position"],
                        name=chat_data["name"],
                        description=chat_data["description"],
                        time_limit=chat_data["time_limit"],
                        negative_time=chat_data["negative_time"],
                        # 13 flag booleans
                        audio_enabled=chat_data["audio_enabled"],
                        text_enabled=chat_data["text_enabled"],
                        hints_enabled=chat_data["hints_enabled"],
                        copy_paste_allowed=chat_data["copy_paste_allowed"],
                        show_images=chat_data["show_images"],
                        show_objectives=chat_data["show_objectives"],
                        show_problem_statement=chat_data["show_problem_statement"],
                        analyses_enabled=chat_data["analyses_enabled"],
                        improvements_enabled=chat_data["improvements_enabled"],
                        strengths_enabled=chat_data["strengths_enabled"],
                        use_custom=chat_data["use_custom"],
                        use_previous=chat_data["use_previous"],
                        # 5 content-enabled
                        problem_statement_enabled=chat_data[
                            "problem_statement_enabled"
                        ],
                        objectives_enabled=chat_data["objectives_enabled"],
                        video_enabled=chat_data["video_enabled"],
                        images_enabled=chat_data["images_enabled"],
                        questions_enabled=chat_data["questions_enabled"],
                        # 11 generate flags
                        generate_problem_statements=chat_data[
                            "generate_problem_statements"
                        ],
                        generate_objectives=chat_data["generate_objectives"],
                        generate_videos=chat_data["generate_videos"],
                        generate_images=chat_data["generate_images"],
                        generate_questions=chat_data["generate_questions"],
                        generate_personas=chat_data["generate_personas"],
                        generate_documents=chat_data["generate_documents"],
                        generate_options=chat_data["generate_options"],
                        generate_parameter_fields=chat_data[
                            "generate_parameter_fields"
                        ],
                        generate_names=chat_data["generate_names"],
                        generate_descriptions=chat_data["generate_descriptions"],
                        # connection resource IDs
                        rubric_ids=chat_data["rubric_ids"],
                        scenario_flag_ids=chat_data["scenario_flag_ids"],
                        scenario_position_ids=chat_data["scenario_position_ids"],
                        scenario_time_limit_ids=chat_data["scenario_time_limit_ids"],
                        persona_ids=chat_data["persona_ids"],
                        document_ids=chat_data["document_ids"],
                        image_ids=chat_data["image_ids"],
                        video_ids=chat_data["video_ids"],
                        question_ids=chat_data["question_ids"],
                        option_ids=chat_data["option_ids"],
                        problem_statement_ids=chat_data["problem_statement_ids"],
                        objective_ids=chat_data["objective_ids"],
                        parameter_field_ids=chat_data["parameter_field_ids"],
                        standard_group_ids=chat_data["standard_group_ids"],
                        standard_ids=chat_data["standard_ids"],
                    )

                    if sim_data["is_practice"]:
                        await create_practice_chat(conn, redis, parent.id, chat.id, session.id)
                    else:
                        await create_home_chat(conn, redis, parent.id, chat.id, session.id)

                    entry_count += 1

    return entry_count
