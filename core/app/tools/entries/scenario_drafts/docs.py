"""Scenario drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.scenario_drafts.create import create_scenario_draft
from app.tools.entries.scenario_drafts.get import get_scenario_drafts
from app.tools.entries.scenario_drafts.refresh import refresh_scenario_drafts
from app.tools.entries.scenario_drafts.search import search_scenario_drafts


async def get_scenario_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the scenario_drafts entry."""
    mv_info = await get_mv_info(conn, "scenario_drafts_mv")
    entry_table = await get_table_info(conn, "scenario_drafts_entry")
    departments_connection = await get_table_info(
        conn, "scenario_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "scenario_drafts_descriptions_connection"
    )
    documents_connection = await get_table_info(
        conn, "scenario_drafts_documents_connection"
    )
    flags_connection = await get_table_info(conn, "scenario_drafts_flags_connection")
    images_connection = await get_table_info(conn, "scenario_drafts_images_connection")
    names_connection = await get_table_info(conn, "scenario_drafts_names_connection")
    objectives_connection = await get_table_info(
        conn, "scenario_drafts_objectives_connection"
    )
    options_connection = await get_table_info(
        conn, "scenario_drafts_options_connection"
    )
    parameter_fields_connection = await get_table_info(
        conn, "scenario_drafts_parameter_fields_connection"
    )
    personas_connection = await get_table_info(
        conn, "scenario_drafts_personas_connection"
    )
    problem_statements_connection = await get_table_info(
        conn, "scenario_drafts_problem_statements_connection"
    )
    profiles_connection = await get_table_info(
        conn, "scenario_drafts_profiles_connection"
    )
    questions_connection = await get_table_info(
        conn, "scenario_drafts_questions_connection"
    )
    videos_connection = await get_table_info(conn, "scenario_drafts_videos_connection")

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            documents_connection,
            flags_connection,
            images_connection,
            names_connection,
            objectives_connection,
            options_connection,
            parameter_fields_connection,
            personas_connection,
            problem_statements_connection,
            profiles_connection,
            questions_connection,
            videos_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="scenario_drafts",
        type="entry",
        description=(
            "Scenario draft artifacts with extensive resource connections. "
            "Each draft links to departments, descriptions, documents, flags, images, names, "
            "objectives, options, parameter fields, personas, problem statements, profiles, "
            "questions, and videos via connection tables. "
            "Reads are served from the scenario_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_scenario_draft,
                description=(
                    "Creates a new scenario draft, writing to scenario_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_scenario_drafts,
                description="Refreshes scenario_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_scenario_drafts,
                description="Batch retrieves scenario drafts by IDs from scenario_drafts_mv.",
            ),
            get_operation_info(
                search_scenario_drafts,
                description="Filtered paginated search against scenario_drafts_mv.",
            ),
        ],
    )
