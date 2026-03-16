"""Cohort artifact SEARCH — returns matching cohort IDs."""

from uuid import UUID

import asyncpg

from app.infra.search.search_artifact import (
    add_junction_filter,
    execute_artifact_search,
)

TABLE = "cohort_artifact"
OWNER_COL = "cohort_id"


async def search_cohorts(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    department_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    cohort_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    profile_persona_ids: list[UUID] | None = None,
    simulation_availability_ids: list[UUID] | None = None,
    simulation_position_ids: list[UUID] | None = None,
    exclude_ids: list[UUID] | None = None,
    active_only: bool = True,
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Search cohort artifacts by filters. Returns (IDs, total_count)."""
    conditions: list[str] = []
    params: list[object] = []
    idx = 1

    if active_only:
        conditions.append("a.active = true")

    # Text search across name and description
    if search:
        conditions.append(
            f"("
            f"EXISTS ("
            f"SELECT 1 FROM cohort_names_junction nj "
            f"JOIN names_resource nr ON nr.id = nj.names_id "
            f"WHERE nj.{OWNER_COL} = a.id AND nj.active = true "
            f"AND LOWER(nr.name) LIKE '%%' || LOWER(${idx}) || '%%'"
            f") OR EXISTS ("
            f"SELECT 1 FROM cohort_descriptions_junction dj "
            f"JOIN descriptions_resource dr ON dr.id = dj.descriptions_id "
            f"WHERE dj.{OWNER_COL} = a.id AND dj.active = true "
            f"AND LOWER(dr.description) LIKE '%%' || LOWER(${idx}) || '%%'"
            f")"
            f")"
        )
        params.append(search)
        idx += 1

    # Junction filters
    if department_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_departments_junction",
            owner_col=OWNER_COL,
            resource_col="departments_id",
            ids=department_ids,
        )

    if simulation_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_simulations_junction",
            owner_col=OWNER_COL,
            resource_col="simulations_id",
            ids=simulation_ids,
        )

    if profile_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_profiles_junction",
            owner_col=OWNER_COL,
            resource_col="profiles_id",
            ids=profile_ids,
        )

    if name_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_names_junction",
            owner_col=OWNER_COL,
            resource_col="names_id",
            ids=name_ids,
        )

    if description_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_descriptions_junction",
            owner_col=OWNER_COL,
            resource_col="descriptions_id",
            ids=description_ids,
        )

    if cohort_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_cohorts_junction",
            owner_col=OWNER_COL,
            resource_col="cohorts_id",
            ids=cohort_ids,
        )

    if flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_flags_junction",
            owner_col=OWNER_COL,
            resource_col="flags_id",
            ids=flag_ids,
        )

    if profile_persona_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_profile_personas_junction",
            owner_col=OWNER_COL,
            resource_col="profile_personas_id",
            ids=profile_persona_ids,
        )

    if simulation_availability_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_simulation_availability_junction",
            owner_col=OWNER_COL,
            resource_col="simulation_availability_id",
            ids=simulation_availability_ids,
        )

    if simulation_position_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="cohort_simulation_positions_junction",
            owner_col=OWNER_COL,
            resource_col="simulation_positions_id",
            ids=simulation_position_ids,
        )

    # Exclude
    if exclude_ids:
        conditions.append(f"NOT (a.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Order by name
    order_join = (
        f"LEFT JOIN cohort_names_junction pnj ON pnj.{OWNER_COL} = a.id AND pnj.active = true "
        f"LEFT JOIN names_resource nr_sort ON nr_sort.id = pnj.names_id"
    )

    return await execute_artifact_search(
        conn,
        table=TABLE,
        conditions=conditions,
        params=params,
        idx=idx,
        order_join=order_join,
        order_expr="MIN(nr_sort.name) NULLS LAST",
        limit_count=limit_count,
        offset_count=offset_count,
    )
