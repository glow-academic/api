"""Cohort drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.cohort_drafts.types import GetCohortDraftResponse


async def get_cohort_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    active: bool | None = True,
) -> list[GetCohortDraftResponse]:
    """Get cohort_drafts entries by IDs with connection data.

    ``active=True`` (default), ``active=False``, or ``active=None`` (both).
    """
    if not ids:
        return []

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
            COALESCE(ARRAY_AGG(DISTINCT pp.profile_personas_id) FILTER (WHERE pp.profile_personas_id IS NOT NULL), '{}') AS profile_persona_ids,
            COALESCE(ARRAY_AGG(DISTINCT pp.profile_personas_id) FILTER (WHERE pp.profile_personas_id IS NOT NULL AND pp.active = false), '{}') AS pending_profile_persona_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL AND p.active = false), '{}') AS pending_profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT sa.simulation_availability_id) FILTER (WHERE sa.simulation_availability_id IS NOT NULL), '{}') AS simulation_availability_ids,
            COALESCE(ARRAY_AGG(DISTINCT sa.simulation_availability_id) FILTER (WHERE sa.simulation_availability_id IS NOT NULL AND sa.active = false), '{}') AS pending_simulation_availability_ids,
            COALESCE(ARRAY_AGG(DISTINCT sp.simulation_positions_id) FILTER (WHERE sp.simulation_positions_id IS NOT NULL), '{}') AS simulation_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT sp.simulation_positions_id) FILTER (WHERE sp.simulation_positions_id IS NOT NULL AND sp.active = false), '{}') AS pending_simulation_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT sim.simulations_id) FILTER (WHERE sim.simulations_id IS NOT NULL), '{}') AS simulation_ids,
            COALESCE(ARRAY_AGG(DISTINCT sim.simulations_id) FILTER (WHERE sim.simulations_id IS NOT NULL AND sim.active = false), '{}') AS pending_simulation_ids
        FROM cohort_drafts_entry d
        LEFT JOIN cohort_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN cohort_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN cohort_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN cohort_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN cohort_drafts_profile_personas_connection pp ON pp.draft_id = d.id
        LEFT JOIN cohort_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN cohort_drafts_simulation_availability_connection sa ON sa.draft_id = d.id
        LEFT JOIN cohort_drafts_simulation_positions_connection sp ON sp.draft_id = d.id
        LEFT JOIN cohort_drafts_simulations_connection sim ON sim.draft_id = d.id
        WHERE d.id = ANY($1)
          AND ($2::boolean IS NULL OR d.active = $2)
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        ids,
        active,
    )

    return [
        GetCohortDraftResponse(
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
            profile_persona_ids=r["profile_persona_ids"],
            profile_ids=r["profile_ids"],
            simulation_availability_ids=r["simulation_availability_ids"],
            simulation_position_ids=r["simulation_position_ids"],
            simulation_ids=r["simulation_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_profile_persona_ids=r["pending_profile_persona_ids"],
            pending_profile_ids=r["pending_profile_ids"],
            pending_simulation_availability_ids=r["pending_simulation_availability_ids"],
            pending_simulation_position_ids=r["pending_simulation_position_ids"],
            pending_simulation_ids=r["pending_simulation_ids"],
        )
        for r in rows
    ]
