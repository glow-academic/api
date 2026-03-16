"""Auth artifact SEARCH — returns matching auth IDs."""

from uuid import UUID

import asyncpg

from app.infra.search.search_artifact import (
    add_junction_filter,
    execute_artifact_search,
)

TABLE = "auth_artifact"
OWNER_COL = "auth_id"


async def search_auths(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    department_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    item_ids: list[UUID] | None = None,
    protocol_ids: list[UUID] | None = None,
    slug_ids: list[UUID] | None = None,
    exclude_ids: list[UUID] | None = None,
    active_only: bool = True,
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Search auth artifacts by filters. Returns (IDs, total_count)."""
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
            f"SELECT 1 FROM auth_names_junction nj "
            f"JOIN names_resource nr ON nr.id = nj.names_id "
            f"WHERE nj.{OWNER_COL} = a.id AND nj.active = true "
            f"AND LOWER(nr.name) LIKE '%%' || LOWER(${idx}) || '%%'"
            f") OR EXISTS ("
            f"SELECT 1 FROM auth_descriptions_junction dj "
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
            junction_table="auth_departments_junction",
            owner_col=OWNER_COL,
            resource_col="departments_id",
            ids=department_ids,
        )

    if name_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="auth_names_junction",
            owner_col=OWNER_COL,
            resource_col="names_id",
            ids=name_ids,
        )

    if description_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="auth_descriptions_junction",
            owner_col=OWNER_COL,
            resource_col="descriptions_id",
            ids=description_ids,
        )

    if auth_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="auth_auths_junction",
            owner_col=OWNER_COL,
            resource_col="auths_id",
            ids=auth_ids,
        )

    if flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="auth_flags_junction",
            owner_col=OWNER_COL,
            resource_col="flags_id",
            ids=flag_ids,
        )

    if item_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="auth_items_junction",
            owner_col=OWNER_COL,
            resource_col="items_id",
            ids=item_ids,
        )

    if protocol_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="auth_protocols_junction",
            owner_col=OWNER_COL,
            resource_col="protocols_id",
            ids=protocol_ids,
        )

    if slug_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="auth_slugs_junction",
            owner_col=OWNER_COL,
            resource_col="slugs_id",
            ids=slug_ids,
        )

    # Exclude
    if exclude_ids:
        conditions.append(f"NOT (a.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Order by name (LEFT JOIN for sorting)
    order_join = (
        f"LEFT JOIN auth_names_junction pnj ON pnj.{OWNER_COL} = a.id AND pnj.active = true "
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
