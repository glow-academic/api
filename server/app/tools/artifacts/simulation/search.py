"""Simulation artifact SEARCH — returns matching simulation IDs."""

from uuid import UUID

import asyncpg

from app.infra.search.search_artifact import (
    add_junction_filter,
    execute_artifact_search,
)

TABLE = "simulation_artifact"
OWNER_COL = "simulation_id"


async def search_simulations(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    name_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    scenario_flag_ids: list[UUID] | None = None,
    scenario_position_ids: list[UUID] | None = None,
    scenario_rubric_ids: list[UUID] | None = None,
    scenario_time_limit_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    cohort_ids: list[UUID] | None = None,
    exclude_ids: list[UUID] | None = None,
    active_only: bool = True,
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Search simulation artifacts by filters. Returns (IDs, total_count)."""
    conditions: list[str] = []
    params: list[object] = []
    idx = 1

    if active_only:
        conditions.append("a.active = true")

    # Text search across name and description
    if search:
        # OR across both text junctions
        conditions.append(
            f"("
            f"EXISTS ("
            f"SELECT 1 FROM simulation_names_junction nj "
            f"JOIN names_resource nr ON nr.id = nj.names_id "
            f"WHERE nj.{OWNER_COL} = a.id AND nj.active = true "
            f"AND LOWER(nr.name) LIKE '%%' || LOWER(${idx}) || '%%'"
            f") OR EXISTS ("
            f"SELECT 1 FROM simulation_descriptions_junction dj "
            f"JOIN descriptions_resource dr ON dr.id = dj.descriptions_id "
            f"WHERE dj.{OWNER_COL} = a.id AND dj.active = true "
            f"AND LOWER(dr.description) LIKE '%%' || LOWER(${idx}) || '%%'"
            f")"
            f")"
        )
        params.append(search)
        idx += 1

    # Junction filters
    if name_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_names_junction",
            owner_col=OWNER_COL,
            resource_col="names_id",
            ids=name_ids,
        )

    if description_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_descriptions_junction",
            owner_col=OWNER_COL,
            resource_col="descriptions_id",
            ids=description_ids,
        )

    if department_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_departments_junction",
            owner_col=OWNER_COL,
            resource_col="departments_id",
            ids=department_ids,
        )

    if flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_flags_junction",
            owner_col=OWNER_COL,
            resource_col="flags_id",
            ids=flag_ids,
        )

    if scenario_flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_scenario_flags_junction",
            owner_col=OWNER_COL,
            resource_col="scenario_flags_id",
            ids=scenario_flag_ids,
        )

    if scenario_position_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_scenario_positions_junction",
            owner_col=OWNER_COL,
            resource_col="scenario_positions_id",
            ids=scenario_position_ids,
        )

    if scenario_rubric_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_scenario_rubrics_junction",
            owner_col=OWNER_COL,
            resource_col="scenario_rubrics_id",
            ids=scenario_rubric_ids,
        )

    if scenario_time_limit_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_scenario_time_limits_junction",
            owner_col=OWNER_COL,
            resource_col="scenario_time_limits_id",
            ids=scenario_time_limit_ids,
        )

    # scenario_ids are scenarios_resource IDs — direct junction lookup
    if scenario_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_scenarios_junction",
            owner_col=OWNER_COL,
            resource_col="scenarios_id",
            ids=scenario_ids,
        )

    if simulation_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="simulation_simulations_junction",
            owner_col=OWNER_COL,
            resource_col="simulations_id",
            ids=simulation_ids,
        )

    # cohort_ids are cohort_artifact IDs — reverse lookup: simulation → simulations_resource → cohort_simulations_junction
    if cohort_ids:
        conditions.append(
            f"EXISTS ("
            f"SELECT 1 FROM simulation_simulations_junction ssj "
            f"JOIN cohort_simulations_junction csj "
            f"ON csj.simulations_id = ssj.simulations_id AND csj.active = true "
            f"WHERE ssj.{OWNER_COL} = a.id AND ssj.active = true "
            f"AND csj.cohort_id = ANY(${idx})"
            f")"
        )
        params.append(cohort_ids)
        idx += 1

    # Exclude
    if exclude_ids:
        conditions.append(f"NOT (a.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Order by name (LEFT JOIN for sorting)
    order_join = (
        f"LEFT JOIN simulation_names_junction pnj ON pnj.{OWNER_COL} = a.id AND pnj.active = true "
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
