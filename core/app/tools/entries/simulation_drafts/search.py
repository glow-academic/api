"""Simulation drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.simulation_drafts.types import (
    GetSimulationDraftResponse,
)


async def search_simulation_drafts(
    conn: asyncpg.Connection,
    redis: Redis,
    session_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetSimulationDraftResponse]:
    """Search simulation_drafts with declarative filters and connection data."""
    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT sf.scenario_flags_id) FILTER (WHERE sf.scenario_flags_id IS NOT NULL), '{}') AS scenario_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT sp.scenario_positions_id) FILTER (WHERE sp.scenario_positions_id IS NOT NULL), '{}') AS scenario_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT sr.scenario_rubrics_id) FILTER (WHERE sr.scenario_rubrics_id IS NOT NULL), '{}') AS scenario_rubric_ids,
            COALESCE(ARRAY_AGG(DISTINCT stl.scenario_time_limits_id) FILTER (WHERE stl.scenario_time_limits_id IS NOT NULL), '{}') AS scenario_time_limit_ids,
            COALESCE(ARRAY_AGG(DISTINCT sc.scenarios_id) FILTER (WHERE sc.scenarios_id IS NOT NULL), '{}') AS scenario_ids
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
        WHERE d.active = true
          AND ($1::uuid[] IS NULL OR d.session_id = ANY($1))
          AND ($2::uuid[] IS NULL OR p.profiles_id = ANY($2))
          AND ($3::timestamptz IS NULL OR d.created_at >= $3)
          AND ($4::timestamptz IS NULL OR d.created_at <= $4)
          AND ($5::boolean IS NULL OR d.mcp = $5)
          AND ($6::text IS NULL OR d.name ILIKE '%' || $6 || '%')
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        LIMIT $7 OFFSET $8
        """,
        session_ids,
        profile_ids,
        date_from,
        date_to,
        mcp,
        name,
        limit,
        offset,
    )

    return [
        GetSimulationDraftResponse(
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
        )
        for r in rows
    ]
