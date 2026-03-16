"""Invocation entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.invocation.create import create_invocation
from app.tools.entries.invocation.get import get_invocations


async def get_invocation_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the invocation entry."""
    entry_table = await get_table_info(conn, "invocation_entry")
    departments_connection = await get_table_info(
        conn, "invocation_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "invocation_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "invocation_flags_connection")
    keys_connection = await get_table_info(conn, "invocation_keys_connection")
    modalities_connection = await get_table_info(
        conn, "invocation_modalities_connection"
    )
    model_flags_connection = await get_table_info(
        conn, "invocation_model_flags_connection"
    )
    model_positions_connection = await get_table_info(
        conn, "invocation_model_positions_connection"
    )
    model_rubrics_connection = await get_table_info(
        conn, "invocation_model_rubrics_connection"
    )
    models_connection = await get_table_info(conn, "invocation_models_connection")
    names_connection = await get_table_info(conn, "invocation_names_connection")
    qualities_connection = await get_table_info(conn, "invocation_qualities_connection")
    reasoning_levels_connection = await get_table_info(
        conn, "invocation_reasoning_levels_connection"
    )
    temperature_levels_connection = await get_table_info(
        conn, "invocation_temperature_levels_connection"
    )
    voices_connection = await get_table_info(conn, "invocation_voices_connection")

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            flags_connection,
            keys_connection,
            modalities_connection,
            model_flags_connection,
            model_positions_connection,
            model_rubrics_connection,
            models_connection,
            names_connection,
            qualities_connection,
            reasoning_levels_connection,
            temperature_levels_connection,
            voices_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="invocation",
        type="entry",
        description=(
            "Invocation entries define specific test configurations for benchmark scenarios. "
            "Each invocation connects to 14 different resource types via connection tables, "
            "allowing fine-grained customization of model behavior and output. "
            "Reads are served directly from the invocation_entry table with joined connection data."
        ),
        materialized_view=None,
        tables=tables,
        operations=[
            get_operation_info(
                create_invocation,
                description=(
                    "Creates a new invocation entry with connections to departments, descriptions, flags, "
                    "keys, modalities, model settings, models, names, qualities, reasoning levels, "
                    "temperature levels, and voices."
                ),
            ),
            get_operation_info(
                get_invocations,
                description="Batch retrieves invocation entries by IDs from invocation_entry with all connection data.",
            ),
        ],
    )
