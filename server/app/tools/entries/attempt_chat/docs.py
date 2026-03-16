"""Attempt chat entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat.get import get_attempt_chats
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from app.tools.entries.attempt_chat.search import (
    search_attempt_chats,
)


async def get_attempt_chat_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_chat entry."""
    mv_info = await get_mv_info(conn, "attempt_chat_mv")
    entry_table = await get_table_info(conn, "attempt_chat_entry")
    conn_tables = [
        await get_table_info(conn, "attempt_chat_rubrics_connection"),
        await get_table_info(conn, "attempt_chat_standards_connection"),
        await get_table_info(conn, "attempt_chat_standard_groups_connection"),
        await get_table_info(conn, "attempt_chat_departments_connection"),
        await get_table_info(conn, "attempt_chat_personas_connection"),
        await get_table_info(conn, "attempt_chat_problem_statements_connection"),
        await get_table_info(conn, "attempt_chat_objectives_connection"),
        await get_table_info(conn, "attempt_chat_questions_connection"),
        await get_table_info(conn, "attempt_chat_options_connection"),
        await get_table_info(conn, "attempt_chat_videos_connection"),
        await get_table_info(conn, "attempt_chat_images_connection"),
        await get_table_info(conn, "attempt_chat_documents_connection"),
        await get_table_info(conn, "attempt_chat_parameter_fields_connection"),
        await get_table_info(conn, "attempt_chat_names_connection"),
        await get_table_info(conn, "attempt_chat_descriptions_connection"),
        await get_table_info(conn, "attempt_chat_parameters_connection"),
    ]

    tables = [t for t in [entry_table] + conn_tables if t is not None]

    return DocsResponse(
        name="attempt_chat",
        type="entry",
        description=(
            "Individual chats within an attempt, containing configuration flags "
            "and linked resources (rubrics, standards, personas, etc.). "
            "Each chat references a group and base chat, and maintains multiple "
            "connection tables for training config resources. "
            "Reads are served from the attempt_chat_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_chat,
                description=(
                    "Creates a new attempt_chat entry with configuration flags and "
                    "populates all referenced connection tables for resources."
                ),
            ),
            get_operation_info(
                refresh_attempt_chat,
                description="Refreshes attempt_chat_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_chats,
                description="Batch retrieves chats by IDs from attempt_chat_mv.",
            ),
            get_operation_info(
                search_attempt_chats,
                description="Filtered paginated search against attempt_chat_mv.",
            ),
        ],
    )
