"""Field artifact SEARCH — returns matching field IDs."""

from uuid import UUID

import asyncpg

from app.infra.search.search_artifact import (
    add_junction_filter,
    execute_artifact_search,
)

TABLE = "field_artifact"
OWNER_COL = "field_id"


async def search_fields(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    department_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    conditional_parameter_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    exclude_ids: list[UUID] | None = None,
    active_only: bool = True,
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Search field artifacts by filters. Returns (IDs, total_count)."""
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
            f"SELECT 1 FROM field_names_junction nj "
            f"JOIN names_resource nr ON nr.id = nj.names_id "
            f"WHERE nj.{OWNER_COL} = a.id AND nj.active = true "
            f"AND LOWER(nr.name) LIKE '%%' || LOWER(${idx}) || '%%'"
            f") OR EXISTS ("
            f"SELECT 1 FROM field_descriptions_junction dj "
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
            junction_table="field_departments_junction",
            owner_col=OWNER_COL,
            resource_col="departments_id",
            ids=department_ids,
        )

    # Parameter filter: field → parameter_fields_junction (field_id) → parameter_id
    if parameter_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="parameter_fields_junction",
            owner_col="field_id",
            resource_col="parameter_id",
            ids=parameter_ids,
        )

    # Persona filter: field → field_fields_junction → fields_resource →
    # parameter_fields_resource → persona_parameter_fields_junction → persona_id
    if persona_ids:
        conditions.append(
            f"EXISTS ("
            f"SELECT 1 FROM field_fields_junction ffj "
            f"JOIN fields_resource fr ON fr.id = ffj.fields_id "
            f"JOIN parameter_fields_resource pfr ON pfr.field_id = fr.id "
            f"JOIN persona_parameter_fields_junction ppfj ON ppfj.parameter_fields_id = pfr.id AND ppfj.active = true "
            f"WHERE ffj.{OWNER_COL} = a.id AND ffj.active = true "
            f"AND ppfj.persona_id = ANY(${idx})"
            f")"
        )
        params.append(persona_ids)
        idx += 1

    if name_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="field_names_junction",
            owner_col=OWNER_COL,
            resource_col="names_id",
            ids=name_ids,
        )

    if description_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="field_descriptions_junction",
            owner_col=OWNER_COL,
            resource_col="descriptions_id",
            ids=description_ids,
        )

    if conditional_parameter_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="field_conditional_parameters_junction",
            owner_col=OWNER_COL,
            resource_col="conditional_parameters_id",
            ids=conditional_parameter_ids,
        )

    if field_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="field_fields_junction",
            owner_col=OWNER_COL,
            resource_col="fields_id",
            ids=field_ids,
        )

    if flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="field_flags_junction",
            owner_col=OWNER_COL,
            resource_col="flags_id",
            ids=flag_ids,
        )

    # Exclude
    if exclude_ids:
        conditions.append(f"NOT (a.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Order by name (LEFT JOIN for sorting)
    order_join = (
        f"LEFT JOIN field_names_junction pnj ON pnj.{OWNER_COL} = a.id AND pnj.active = true "
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
