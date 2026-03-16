"""Persona drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.persona_drafts.create import create_persona_draft
from app.tools.entries.persona_drafts.get import get_persona_drafts
from app.tools.entries.persona_drafts.refresh import refresh_persona_drafts
from app.tools.entries.persona_drafts.search import search_persona_drafts


async def get_persona_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the persona_drafts entry."""
    mv_info = await get_mv_info(conn, "persona_drafts_mv")
    entry_table = await get_table_info(conn, "persona_drafts_entry")
    colors_connection = await get_table_info(conn, "persona_drafts_colors_connection")
    departments_connection = await get_table_info(
        conn, "persona_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "persona_drafts_descriptions_connection"
    )
    examples_connection = await get_table_info(
        conn, "persona_drafts_examples_connection"
    )
    flags_connection = await get_table_info(conn, "persona_drafts_flags_connection")
    icons_connection = await get_table_info(conn, "persona_drafts_icons_connection")
    instructions_connection = await get_table_info(
        conn, "persona_drafts_instructions_connection"
    )
    names_connection = await get_table_info(conn, "persona_drafts_names_connection")
    parameter_fields_connection = await get_table_info(
        conn, "persona_drafts_parameter_fields_connection"
    )
    profiles_connection = await get_table_info(
        conn, "persona_drafts_profiles_connection"
    )
    voices_connection = await get_table_info(conn, "persona_drafts_voices_connection")

    tables = [
        t
        for t in [
            entry_table,
            colors_connection,
            departments_connection,
            descriptions_connection,
            examples_connection,
            flags_connection,
            icons_connection,
            instructions_connection,
            names_connection,
            parameter_fields_connection,
            profiles_connection,
            voices_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="persona_drafts",
        type="entry",
        description=(
            "Persona draft artifacts with support for multiple resource connections. "
            "Each draft links to colors, departments, descriptions, examples, flags, icons, "
            "instructions, names, parameter fields, profiles, and voices via connection tables. "
            "Reads are served from the persona_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_persona_draft,
                description=(
                    "Creates a new persona draft, writing to persona_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_persona_drafts,
                description="Refreshes persona_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_persona_drafts,
                description="Batch retrieves persona drafts by IDs from persona_drafts_mv.",
            ),
            get_operation_info(
                search_persona_drafts,
                description="Filtered paginated search against persona_drafts_mv.",
            ),
        ],
    )
