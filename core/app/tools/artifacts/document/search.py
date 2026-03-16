"""Document artifact SEARCH — returns matching document IDs."""

from uuid import UUID

import asyncpg

from app.infra.search.search_artifact import (
    add_junction_filter,
    execute_artifact_search,
)

TABLE = "document_artifact"
OWNER_COL = "document_id"


async def search_documents(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    department_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    document_ids: list[UUID] | None = None,
    file_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    text_ids: list[UUID] | None = None,
    exclude_ids: list[UUID] | None = None,
    active_only: bool = True,
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Search document artifacts by filters. Returns (IDs, total_count)."""
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
            f"SELECT 1 FROM document_names_junction nj "
            f"JOIN names_resource nr ON nr.id = nj.names_id "
            f"WHERE nj.{OWNER_COL} = a.id AND nj.active = true "
            f"AND LOWER(nr.name) LIKE '%%' || LOWER(${idx}) || '%%'"
            f") OR EXISTS ("
            f"SELECT 1 FROM document_descriptions_junction dj "
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
            junction_table="document_departments_junction",
            owner_col=OWNER_COL,
            resource_col="departments_id",
            ids=department_ids,
        )

    # Scenario filter: scenario_ids are scenario_artifact IDs
    # Path: document_artifact → document_documents_junction → documents_resource
    #        → scenario_documents_junction → scenario_id
    if scenario_ids:
        conditions.append(
            f"EXISTS ("
            f"SELECT 1 FROM document_documents_junction ddj "
            f"JOIN scenario_documents_junction sdj "
            f"ON sdj.documents_id = ddj.documents_id AND sdj.active = true "
            f"WHERE ddj.{OWNER_COL} = a.id AND ddj.active = true "
            f"AND sdj.scenario_id = ANY(${idx})"
            f")"
        )
        params.append(scenario_ids)
        idx += 1

    # Field filter: field_ids are fields_resource IDs
    # Path: document → document_parameter_fields_junction → parameter_fields_resource.field_id
    if field_ids:
        conditions.append(
            f"EXISTS ("
            f"SELECT 1 FROM document_parameter_fields_junction dpfj "
            f"JOIN parameter_fields_resource pfr ON pfr.id = dpfj.parameter_fields_id "
            f"WHERE dpfj.{OWNER_COL} = a.id AND dpfj.active = true "
            f"AND pfr.field_id = ANY(${idx})"
            f")"
        )
        params.append(field_ids)
        idx += 1

    if name_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="document_names_junction",
            owner_col=OWNER_COL,
            resource_col="names_id",
            ids=name_ids,
        )

    if description_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="document_descriptions_junction",
            owner_col=OWNER_COL,
            resource_col="descriptions_id",
            ids=description_ids,
        )

    if document_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="document_documents_junction",
            owner_col=OWNER_COL,
            resource_col="documents_id",
            ids=document_ids,
        )

    if file_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="document_files_junction",
            owner_col=OWNER_COL,
            resource_col="files_id",
            ids=file_ids,
        )

    if flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="document_flags_junction",
            owner_col=OWNER_COL,
            resource_col="flags_id",
            ids=flag_ids,
        )

    if image_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="document_images_junction",
            owner_col=OWNER_COL,
            resource_col="images_id",
            ids=image_ids,
        )

    if parameter_field_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="document_parameter_fields_junction",
            owner_col=OWNER_COL,
            resource_col="parameter_fields_id",
            ids=parameter_field_ids,
        )

    if parameter_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="document_parameters_junction",
            owner_col=OWNER_COL,
            resource_col="parameters_id",
            ids=parameter_ids,
        )

    if text_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="document_texts_junction",
            owner_col=OWNER_COL,
            resource_col="texts_id",
            ids=text_ids,
        )

    # Exclude
    if exclude_ids:
        conditions.append(f"NOT (a.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Order by name (LEFT JOIN for sorting)
    order_join = (
        f"LEFT JOIN document_names_junction pnj ON pnj.{OWNER_COL} = a.id AND pnj.active = true "
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
