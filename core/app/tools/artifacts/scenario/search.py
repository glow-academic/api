"""Scenario artifact SEARCH — returns matching scenario IDs."""

from uuid import UUID

import asyncpg

from app.infra.search.search_artifact import (
    add_junction_filter,
    execute_artifact_search,
)

TABLE = "scenario_artifact"
OWNER_COL = "scenario_id"


async def search_scenarios(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    name_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    document_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    objective_ids: list[UUID] | None = None,
    option_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    problem_statement_ids: list[UUID] | None = None,
    question_ids: list[UUID] | None = None,
    scenario_ids: list[UUID] | None = None,
    video_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    exclude_ids: list[UUID] | None = None,
    active_only: bool = True,
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Search scenario artifacts by filters. Returns (IDs, total_count)."""
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
            f"SELECT 1 FROM scenario_names_junction nj "
            f"JOIN names_resource nr ON nr.id = nj.names_id "
            f"WHERE nj.{OWNER_COL} = a.id AND nj.active = true "
            f"AND LOWER(nr.name) LIKE '%%' || LOWER(${idx}) || '%%'"
            f") OR EXISTS ("
            f"SELECT 1 FROM scenario_descriptions_junction dj "
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
            junction_table="scenario_names_junction",
            owner_col=OWNER_COL,
            resource_col="names_id",
            ids=name_ids,
        )

    if description_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_descriptions_junction",
            owner_col=OWNER_COL,
            resource_col="descriptions_id",
            ids=description_ids,
        )

    if department_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_departments_junction",
            owner_col=OWNER_COL,
            resource_col="departments_id",
            ids=department_ids,
        )

    # document_ids are documents_resource IDs — direct junction lookup
    if document_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_documents_junction",
            owner_col=OWNER_COL,
            resource_col="documents_id",
            ids=document_ids,
        )

    if flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_flags_junction",
            owner_col=OWNER_COL,
            resource_col="flags_id",
            ids=flag_ids,
        )

    if image_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_images_junction",
            owner_col=OWNER_COL,
            resource_col="images_id",
            ids=image_ids,
        )

    if objective_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_objectives_junction",
            owner_col=OWNER_COL,
            resource_col="objectives_id",
            ids=objective_ids,
        )

    if option_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_options_junction",
            owner_col=OWNER_COL,
            resource_col="options_id",
            ids=option_ids,
        )

    if parameter_field_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_parameter_fields_junction",
            owner_col=OWNER_COL,
            resource_col="parameter_fields_id",
            ids=parameter_field_ids,
        )

    if problem_statement_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_problem_statements_junction",
            owner_col=OWNER_COL,
            resource_col="problem_statements_id",
            ids=problem_statement_ids,
        )

    if question_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_questions_junction",
            owner_col=OWNER_COL,
            resource_col="questions_id",
            ids=question_ids,
        )

    if scenario_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_scenarios_junction",
            owner_col=OWNER_COL,
            resource_col="scenarios_id",
            ids=scenario_ids,
        )

    if video_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_videos_junction",
            owner_col=OWNER_COL,
            resource_col="videos_id",
            ids=video_ids,
        )

    # parameter_ids are parameter_artifact IDs — two-hop through parameter_fields_resource
    if parameter_ids:
        conditions.append(
            f"EXISTS ("
            f"SELECT 1 FROM scenario_parameter_fields_junction spfj "
            f"JOIN parameter_fields_resource pfr ON pfr.id = spfj.parameter_fields_id "
            f"WHERE spfj.{OWNER_COL} = a.id AND spfj.active = true "
            f"AND pfr.parameter_id = ANY(${idx})"
            f")"
        )
        params.append(parameter_ids)
        idx += 1

    # persona_ids are personas_resource IDs — direct junction lookup
    if persona_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="scenario_personas_junction",
            owner_col=OWNER_COL,
            resource_col="personas_id",
            ids=persona_ids,
        )

    # simulation_ids are simulation_artifact IDs — reverse lookup: scenario → scenarios_resource → simulation_scenarios_junction
    if simulation_ids:
        conditions.append(
            f"EXISTS ("
            f"SELECT 1 FROM scenario_scenarios_junction ssj "
            f"JOIN simulation_scenarios_junction simscj "
            f"ON simscj.scenarios_id = ssj.scenarios_id AND simscj.active = true "
            f"WHERE ssj.{OWNER_COL} = a.id AND ssj.active = true "
            f"AND simscj.simulation_id = ANY(${idx})"
            f")"
        )
        params.append(simulation_ids)
        idx += 1

    # Exclude
    if exclude_ids:
        conditions.append(f"NOT (a.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Order by name (LEFT JOIN for sorting)
    order_join = (
        f"LEFT JOIN scenario_names_junction pnj ON pnj.{OWNER_COL} = a.id AND pnj.active = true "
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
