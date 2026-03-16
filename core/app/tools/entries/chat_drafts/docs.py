"""Chat drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.chat_drafts.create import create_chat_draft
from app.tools.entries.chat_drafts.get import get_chat_drafts
from app.tools.entries.chat_drafts.refresh import refresh_chat_drafts
from app.tools.entries.chat_drafts.search import search_chat_drafts


async def get_chat_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the chat_drafts entry."""
    mv_info = await get_mv_info(conn, "chat_drafts_mv")
    entry_table = await get_table_info(conn, "chat_drafts_entry")
    departments_connection = await get_table_info(
        conn, "chat_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "chat_drafts_descriptions_connection"
    )
    documents_connection = await get_table_info(
        conn, "chat_drafts_documents_connection"
    )
    fields_connection = await get_table_info(conn, "chat_drafts_fields_connection")
    flags_connection = await get_table_info(conn, "chat_drafts_flags_connection")
    images_connection = await get_table_info(conn, "chat_drafts_images_connection")
    names_connection = await get_table_info(conn, "chat_drafts_names_connection")
    objectives_connection = await get_table_info(
        conn, "chat_drafts_objectives_connection"
    )
    options_connection = await get_table_info(conn, "chat_drafts_options_connection")
    parameter_fields_connection = await get_table_info(
        conn, "chat_drafts_parameter_fields_connection"
    )
    parameters_connection = await get_table_info(
        conn, "chat_drafts_parameters_connection"
    )
    personas_connection = await get_table_info(conn, "chat_drafts_personas_connection")
    problem_statements_connection = await get_table_info(
        conn, "chat_drafts_problem_statements_connection"
    )
    profiles_connection = await get_table_info(conn, "chat_drafts_profiles_connection")
    questions_connection = await get_table_info(
        conn, "chat_drafts_questions_connection"
    )
    scenarios_connection = await get_table_info(
        conn, "chat_drafts_scenarios_connection"
    )
    videos_connection = await get_table_info(conn, "chat_drafts_videos_connection")

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            documents_connection,
            fields_connection,
            flags_connection,
            images_connection,
            names_connection,
            objectives_connection,
            options_connection,
            parameter_fields_connection,
            parameters_connection,
            personas_connection,
            problem_statements_connection,
            profiles_connection,
            questions_connection,
            scenarios_connection,
            videos_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="chat_drafts",
        type="entry",
        description=(
            "Chat draft artifacts with extensive resource connections. "
            "Each draft links to departments, descriptions, documents, fields, flags, images, "
            "names, objectives, options, parameter fields, parameters, personas, problem statements, "
            "profiles, questions, scenarios, and videos via connection tables. "
            "Reads are served from the chat_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_chat_draft,
                description=(
                    "Creates a new chat draft, writing to chat_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_chat_drafts,
                description="Refreshes chat_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_chat_drafts,
                description="Batch retrieves chat drafts by IDs from chat_drafts_mv.",
            ),
            get_operation_info(
                search_chat_drafts,
                description="Filtered paginated search against chat_drafts_mv.",
            ),
        ],
    )
