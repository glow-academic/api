"""Cohort drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.cohort_drafts.types import GetCohortDraftResponse


async def get_cohort_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetCohortDraftResponse]:
    """Get cohort_drafts entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT pp.profile_personas_id) FILTER (WHERE pp.profile_personas_id IS NOT NULL), '{}') AS profile_persona_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT sa.simulation_availability_id) FILTER (WHERE sa.simulation_availability_id IS NOT NULL), '{}') AS simulation_availability_ids,
            COALESCE(ARRAY_AGG(DISTINCT sp.simulation_positions_id) FILTER (WHERE sp.simulation_positions_id IS NOT NULL), '{}') AS simulation_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT sim.simulations_id) FILTER (WHERE sim.simulations_id IS NOT NULL), '{}') AS simulation_ids
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
          AND d.active = true
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetCohortDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            name_ids=r["name_ids"],
            profile_persona_ids=r["profile_persona_ids"],
            profile_ids=r["profile_ids"],
            simulation_availability_ids=r["simulation_availability_ids"],
            simulation_position_ids=r["simulation_position_ids"],
            simulation_ids=r["simulation_ids"],
        )
        for r in rows
    ]
