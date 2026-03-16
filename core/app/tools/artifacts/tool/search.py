"""Tool artifact SEARCH — returns matching tool IDs."""

from uuid import UUID

import asyncpg

from app.infra.search.search_artifact import (
    add_junction_filter,
    execute_artifact_search,
)

TABLE = "tool_artifact"
OWNER_COL = "tool_id"


async def search_tools(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    name_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    arg_position_ids: list[UUID] | None = None,
    arg_ids: list[UUID] | None = None,
    args_output_ids: list[UUID] | None = None,
    artifact_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    operation_ids: list[UUID] | None = None,
    tool_ids: list[UUID] | None = None,
    exclude_ids: list[UUID] | None = None,
    active_only: bool = True,
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Search tool artifacts by filters. Returns (IDs, total_count)."""
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
            f"SELECT 1 FROM tool_names_junction nj "
            f"JOIN names_resource nr ON nr.id = nj.names_id "
            f"WHERE nj.{OWNER_COL} = a.id AND nj.active = true "
            f"AND LOWER(nr.name) LIKE '%%' || LOWER(${idx}) || '%%'"
            f") OR EXISTS ("
            f"SELECT 1 FROM tool_descriptions_junction dj "
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
            junction_table="tool_names_junction",
            owner_col=OWNER_COL,
            resource_col="names_id",
            ids=name_ids,
        )

    if description_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="tool_descriptions_junction",
            owner_col=OWNER_COL,
            resource_col="descriptions_id",
            ids=description_ids,
        )

    if department_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="tool_departments_junction",
            owner_col=OWNER_COL,
            resource_col="departments_id",
            ids=department_ids,
        )

    if arg_position_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="tool_arg_positions_junction",
            owner_col=OWNER_COL,
            resource_col="arg_positions_id",
            ids=arg_position_ids,
        )

    if arg_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="tool_args_junction",
            owner_col=OWNER_COL,
            resource_col="args_id",
            ids=arg_ids,
        )

    if args_output_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="tool_args_outputs_junction",
            owner_col=OWNER_COL,
            resource_col="args_outputs_id",
            ids=args_output_ids,
        )

    if artifact_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="tool_artifacts_junction",
            owner_col=OWNER_COL,
            resource_col="artifacts_id",
            ids=artifact_ids,
        )

    if flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="tool_flags_junction",
            owner_col=OWNER_COL,
            resource_col="flags_id",
            ids=flag_ids,
        )

    if operation_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="tool_operations_junction",
            owner_col=OWNER_COL,
            resource_col="operations_id",
            ids=operation_ids,
        )

    if tool_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="tool_tools_junction",
            owner_col=OWNER_COL,
            resource_col="tools_id",
            ids=tool_ids,
        )

    # Exclude
    if exclude_ids:
        conditions.append(f"NOT (a.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Order by name (LEFT JOIN for sorting)
    order_join = (
        f"LEFT JOIN tool_names_junction pnj ON pnj.{OWNER_COL} = a.id AND pnj.active = true "
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
