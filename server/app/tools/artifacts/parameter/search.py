"""Parameter artifact SEARCH — returns matching parameter IDs."""

from uuid import UUID

import asyncpg

from app.infra.search.search_artifact import (
    add_junction_filter,
    execute_artifact_search,
)

TABLE = "parameter_artifact"
OWNER_COL = "parameter_id"


async def search_parameters(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    name_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    exclude_ids: list[UUID] | None = None,
    active_only: bool = True,
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Search parameter artifacts by filters. Returns (IDs, total_count)."""
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
            f"SELECT 1 FROM parameter_names_junction nj "
            f"JOIN names_resource nr ON nr.id = nj.names_id "
            f"WHERE nj.{OWNER_COL} = a.id AND nj.active = true "
            f"AND LOWER(nr.name) LIKE '%%' || LOWER(${idx}) || '%%'"
            f") OR EXISTS ("
            f"SELECT 1 FROM parameter_descriptions_junction dj "
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
            junction_table="parameter_names_junction",
            owner_col=OWNER_COL,
            resource_col="names_id",
            ids=name_ids,
        )

    if description_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="parameter_descriptions_junction",
            owner_col=OWNER_COL,
            resource_col="descriptions_id",
            ids=description_ids,
        )

    if department_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="parameter_departments_junction",
            owner_col=OWNER_COL,
            resource_col="departments_id",
            ids=department_ids,
        )

    if flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="parameter_flags_junction",
            owner_col=OWNER_COL,
            resource_col="flags_id",
            ids=flag_ids,
        )

    if parameter_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="parameter_parameters_junction",
            owner_col=OWNER_COL,
            resource_col="parameters_id",
            ids=parameter_ids,
        )

    # Scenario filter: scenario_ids are scenario_artifact IDs
    # Path: parameter_artifact → parameter_parameters_junction → parameters_resource
    #        → parameter_fields_resource → scenario_parameter_fields_junction → scenario_id
    if scenario_ids:
        conditions.append(
            f"EXISTS ("
            f"SELECT 1 FROM parameter_parameters_junction ppj "
            f"JOIN parameter_fields_resource pfr ON pfr.parameter_id = ppj.parameters_id "
            f"JOIN scenario_parameter_fields_junction spfj ON spfj.parameter_fields_id = pfr.id AND spfj.active = true "
            f"WHERE ppj.{OWNER_COL} = a.id AND ppj.active = true "
            f"AND spfj.scenario_id = ANY(${idx})"
            f")"
        )
        params.append(scenario_ids)
        idx += 1

    # Field filter: field_ids are fields_resource IDs — direct junction lookup
    if field_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="parameter_fields_junction",
            owner_col=OWNER_COL,
            resource_col="fields_id",
            ids=field_ids,
        )

    # Exclude
    if exclude_ids:
        conditions.append(f"NOT (a.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Order by name (LEFT JOIN for sorting)
    order_join = (
        f"LEFT JOIN parameter_names_junction pnj ON pnj.{OWNER_COL} = a.id AND pnj.active = true "
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
