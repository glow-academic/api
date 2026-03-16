"""Document drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.document_drafts.types import (
    CreateDocumentDraftResponse,
)


async def create_document_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    file_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    text_ids: list[UUID] | None = None,
) -> CreateDocumentDraftResponse:
    """Create a document_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO document_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        group_id,
        session_id,
        version,
        not soft,
        mcp,
        id,
    )

    if draft_id is None:
        raise ValueError("Failed to create document_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        (
            "document_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "document_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("document_drafts_files_connection", "files_id", file_ids or []),
        ("document_drafts_flags_connection", "flags_id", flag_ids or []),
        ("document_drafts_images_connection", "images_id", image_ids or []),
        ("document_drafts_names_connection", "names_id", name_ids or []),
        (
            "document_drafts_parameter_fields_connection",
            "parameter_fields_id",
            parameter_field_ids or [],
        ),
        ("document_drafts_parameters_connection", "parameters_id", parameter_ids or []),
        ("document_drafts_profiles_connection", "profiles_id", profile_ids or []),
        ("document_drafts_texts_connection", "texts_id", text_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateDocumentDraftResponse(id=draft_id)
