"""Simulation drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.simulation_drafts.types import (
    GetSimulationDraftResponse,
)
from app.utils.cache.hedged_row import read_back_row


async def get_simulation_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    active: bool | None = True,
    *,
    bypass_cache: bool = False,
) -> list[GetSimulationDraftResponse]:
    """Get simulation_drafts entries by IDs with connection data.

    ``active=True`` (default) — only committed drafts.
    ``active=None`` — both committed and dormant pending. Use for
    ack short-circuit / auto-accept lookups.
    """
    if not ids:
        return []

    cached_results: dict[str, GetSimulationDraftResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for did in ids:
            cached = await read_back_row(redis, "simulation_drafts", did)
            if cached is not None:
                if active is not None and cached.get("active") != active:
                    continue
                cached_results[str(did)] = GetSimulationDraftResponse.model_validate(cached)
            else:
                missing_ids.append(did)
    else:
        missing_ids = list(ids)

    if not missing_ids:
        return [cached_results[str(did)] for did in ids if str(did) in cached_results]

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT sf.scenario_flags_id) FILTER (WHERE sf.scenario_flags_id IS NOT NULL), '{}') AS scenario_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT sf.scenario_flags_id) FILTER (WHERE sf.scenario_flags_id IS NOT NULL AND sf.active = false), '{}') AS pending_scenario_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT sp.scenario_positions_id) FILTER (WHERE sp.scenario_positions_id IS NOT NULL), '{}') AS scenario_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT sp.scenario_positions_id) FILTER (WHERE sp.scenario_positions_id IS NOT NULL AND sp.active = false), '{}') AS pending_scenario_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT sr.scenario_rubrics_id) FILTER (WHERE sr.scenario_rubrics_id IS NOT NULL), '{}') AS scenario_rubric_ids,
            COALESCE(ARRAY_AGG(DISTINCT sr.scenario_rubrics_id) FILTER (WHERE sr.scenario_rubrics_id IS NOT NULL AND sr.active = false), '{}') AS pending_scenario_rubric_ids,
            COALESCE(ARRAY_AGG(DISTINCT stl.scenario_time_limits_id) FILTER (WHERE stl.scenario_time_limits_id IS NOT NULL), '{}') AS scenario_time_limit_ids,
            COALESCE(ARRAY_AGG(DISTINCT stl.scenario_time_limits_id) FILTER (WHERE stl.scenario_time_limits_id IS NOT NULL AND stl.active = false), '{}') AS pending_scenario_time_limit_ids,
            COALESCE(ARRAY_AGG(DISTINCT sc.scenarios_id) FILTER (WHERE sc.scenarios_id IS NOT NULL), '{}') AS scenario_ids,
            COALESCE(ARRAY_AGG(DISTINCT sc.scenarios_id) FILTER (WHERE sc.scenarios_id IS NOT NULL AND sc.active = false), '{}') AS pending_scenario_ids
        FROM simulation_drafts_entry d
        LEFT JOIN simulation_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN simulation_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN simulation_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN simulation_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN simulation_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN simulation_drafts_scenario_flags_connection sf ON sf.draft_id = d.id
        LEFT JOIN simulation_drafts_scenario_positions_connection sp ON sp.draft_id = d.id
        LEFT JOIN simulation_drafts_scenario_rubrics_connection sr ON sr.draft_id = d.id
        LEFT JOIN simulation_drafts_scenario_time_limits_connection stl ON stl.draft_id = d.id
        LEFT JOIN simulation_drafts_scenarios_connection sc ON sc.draft_id = d.id
        WHERE d.id = ANY($1)
          AND ($2::boolean IS NULL OR d.active = $2)
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        missing_ids,
        active,
    )

    mv_results: dict[str, GetSimulationDraftResponse] = {}
    for r in rows:
        mv_results[str(r["id"])] = GetSimulationDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name=r["name"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            name_ids=r["name_ids"],
            profile_ids=r["profile_ids"],
            scenario_flag_ids=r["scenario_flag_ids"],
            scenario_position_ids=r["scenario_position_ids"],
            scenario_rubric_ids=r["scenario_rubric_ids"],
            scenario_time_limit_ids=r["scenario_time_limit_ids"],
            scenario_ids=r["scenario_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_scenario_flag_ids=r["pending_scenario_flag_ids"],
            pending_scenario_position_ids=r["pending_scenario_position_ids"],
            pending_scenario_rubric_ids=r["pending_scenario_rubric_ids"],
            pending_scenario_time_limit_ids=r["pending_scenario_time_limit_ids"],
            pending_scenario_ids=r["pending_scenario_ids"],
        )

    out: list[GetSimulationDraftResponse] = []
    for did in ids:
        key = str(did)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
