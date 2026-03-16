"""Model drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.model_drafts.create import create_model_draft
from app.tools.entries.model_drafts.get import get_model_drafts
from app.tools.entries.model_drafts.refresh import refresh_model_drafts
from app.tools.entries.model_drafts.search import search_model_drafts


async def get_model_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the model_drafts entry."""
    mv_info = await get_mv_info(conn, "model_drafts_mv")
    entry_table = await get_table_info(conn, "model_drafts_entry")
    departments_connection = await get_table_info(
        conn, "model_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "model_drafts_descriptions_connection"
    )
    flags_connection = await get_table_info(conn, "model_drafts_flags_connection")
    modalities_connection = await get_table_info(
        conn, "model_drafts_modalities_connection"
    )
    names_connection = await get_table_info(conn, "model_drafts_names_connection")
    pricing_connection = await get_table_info(conn, "model_drafts_pricing_connection")
    profiles_connection = await get_table_info(conn, "model_drafts_profiles_connection")
    providers_connection = await get_table_info(
        conn, "model_drafts_providers_connection"
    )
    qualities_connection = await get_table_info(
        conn, "model_drafts_qualities_connection"
    )
    reasoning_levels_connection = await get_table_info(
        conn, "model_drafts_reasoning_levels_connection"
    )
    temperature_levels_connection = await get_table_info(
        conn, "model_drafts_temperature_levels_connection"
    )
    values_connection = await get_table_info(conn, "model_drafts_values_connection")
    voices_connection = await get_table_info(conn, "model_drafts_voices_connection")

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            flags_connection,
            modalities_connection,
            names_connection,
            pricing_connection,
            profiles_connection,
            providers_connection,
            qualities_connection,
            reasoning_levels_connection,
            temperature_levels_connection,
            values_connection,
            voices_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="model_drafts",
        type="entry",
        description=(
            "Model draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, flags, modalities, names, pricing, profiles, "
            "providers, qualities, reasoning levels, temperature levels, values, and voices via connection tables. "
            "Reads are served from the model_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_model_draft,
                description=(
                    "Creates a new model draft, writing to model_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_model_drafts,
                description="Refreshes model_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_model_drafts,
                description="Batch retrieves model drafts by IDs from model_drafts_mv.",
            ),
            get_operation_info(
                search_model_drafts,
                description="Filtered paginated search against model_drafts_mv.",
            ),
        ],
    )
