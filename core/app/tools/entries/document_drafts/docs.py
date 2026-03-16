"""Document drafts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.document_drafts.create import create_document_draft
from app.tools.entries.document_drafts.get import get_document_drafts
from app.tools.entries.document_drafts.refresh import refresh_document_drafts
from app.tools.entries.document_drafts.search import search_document_drafts


async def get_document_drafts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the document_drafts entry."""
    mv_info = await get_mv_info(conn, "document_drafts_mv")
    entry_table = await get_table_info(conn, "document_drafts_entry")
    departments_connection = await get_table_info(
        conn, "document_drafts_departments_connection"
    )
    descriptions_connection = await get_table_info(
        conn, "document_drafts_descriptions_connection"
    )
    files_connection = await get_table_info(conn, "document_drafts_files_connection")
    flags_connection = await get_table_info(conn, "document_drafts_flags_connection")
    images_connection = await get_table_info(conn, "document_drafts_images_connection")
    names_connection = await get_table_info(conn, "document_drafts_names_connection")
    parameter_fields_connection = await get_table_info(
        conn, "document_drafts_parameter_fields_connection"
    )
    parameters_connection = await get_table_info(
        conn, "document_drafts_parameters_connection"
    )
    profiles_connection = await get_table_info(
        conn, "document_drafts_profiles_connection"
    )
    texts_connection = await get_table_info(conn, "document_drafts_texts_connection")

    tables = [
        t
        for t in [
            entry_table,
            departments_connection,
            descriptions_connection,
            files_connection,
            flags_connection,
            images_connection,
            names_connection,
            parameter_fields_connection,
            parameters_connection,
            profiles_connection,
            texts_connection,
        ]
        if t is not None
    ]

    return DocsResponse(
        name="document_drafts",
        type="entry",
        description=(
            "Document draft artifacts with support for multiple resource connections. "
            "Each draft links to departments, descriptions, files, flags, images, names, "
            "parameter fields, parameters, profiles, and texts via connection tables. "
            "Reads are served from the document_drafts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_document_draft,
                description=(
                    "Creates a new document draft, writing to document_drafts_entry "
                    "and all relevant connection tables."
                ),
            ),
            get_operation_info(
                refresh_document_drafts,
                description="Refreshes document_drafts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_document_drafts,
                description="Batch retrieves document drafts by IDs from document_drafts_mv.",
            ),
            get_operation_info(
                search_document_drafts,
                description="Filtered paginated search against document_drafts_mv.",
            ),
        ],
    )
