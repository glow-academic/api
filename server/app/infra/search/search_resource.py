"""Generic resource search — returns IDs matching filters."""

from uuid import UUID

import asyncpg  # type: ignore


async def search_resource_ids(
    conn: asyncpg.Connection,
    *,
    table: str,
    resource: str,
    search_column: str | None = None,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    artifact_filters: dict[str, bool] | None = None,
    junction_artifacts: list[str] | None = None,
    draft_artifacts: list[str] | None = None,
    order_column: str | None = None,
    additional_search_columns: list[str] | None = None,
    extra_conditions: list[tuple[str, object]] | None = None,
) -> list[UUID]:
    """Search a resource table and return matching IDs.

    Builds a dynamic WHERE clause from the provided filters:
    - search: ILIKE on search_column (+ additional_search_columns via OR)
    - exclude_ids: NOT IN filter
    - draft_id + suggest_source='draft': EXISTS across draft connection tables
    - artifact_filters: EXISTS across junction tables for each True filter
    - extra_conditions: list of (sql_template, param) for resource-specific filters.
      sql_template uses {idx} placeholder for param position, {alias} for table alias.
    """
    if limit_count <= 0:
        return []

    alias = "r"
    conditions: list[str] = []
    params: list[object] = []
    idx = 1

    # NOT NULL / non-empty guard on search column (skipped when no text column)
    if search_column:
        conditions.append(f"{alias}.{search_column} IS NOT NULL")
        conditions.append(f"{alias}.{search_column} != ''")

    # Search filter
    if search and search_column:
        all_cols = [search_column] + (additional_search_columns or [])
        if len(all_cols) == 1:
            conditions.append(
                f"LOWER({alias}.{all_cols[0]}) LIKE '%' || LOWER(${idx}) || '%'"
            )
        else:
            or_parts = [
                f"LOWER(COALESCE({alias}.{col}, '')) LIKE '%' || LOWER(${idx}) || '%'"
                for col in all_cols
            ]
            conditions.append(f"({' OR '.join(or_parts)})")
        params.append(search)
        idx += 1

    # Exclude filter
    if exclude_ids:
        conditions.append(f"NOT ({alias}.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Draft filter
    if suggest_source == "draft" and draft_id is not None and draft_artifacts:
        unions = " UNION ALL ".join(
            f"SELECT {resource}_id, draft_id FROM {a}_drafts_{resource}_connection WHERE active = true"
            for a in draft_artifacts
        )
        conditions.append(
            f"EXISTS (SELECT 1 FROM ({unions}) dc WHERE dc.{resource}_id = {alias}.id AND dc.draft_id = ${idx})"
        )
        params.append(draft_id)
        idx += 1

    # Extra resource-specific conditions
    if extra_conditions:
        for sql_template, param in extra_conditions:
            conditions.append(sql_template.format(idx=idx, alias=alias))
            params.append(param)
            idx += 1

    # Artifact boolean filters
    if artifact_filters and junction_artifacts:
        for artifact in junction_artifacts:
            if artifact_filters.get(artifact):
                junction = f"{artifact}_{resource}_junction"
                conditions.append(
                    f"EXISTS (SELECT 1 FROM {junction} j WHERE j.{resource}_id = {alias}.id AND j.active = true)"
                )

    where = " AND ".join(conditions) if conditions else "true"
    order = order_column or search_column or "created_at"

    query = f"""
        SELECT {alias}.id
        FROM {table} {alias}
        WHERE {where}
        ORDER BY {alias}.{order}
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    params.extend([limit_count, offset_count])

    rows = await conn.fetch(query, *params)
    return [row["id"] for row in rows]
