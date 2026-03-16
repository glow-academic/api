"""Document artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    insert_multi,
    insert_single,
)
from app.tools.artifacts.document.types import CreateDocumentResponse

OWNER_COL = "document_id"

# (junction_table, resource_column)
SINGLE_JUNCTIONS: list[tuple[str, str]] = [
    ("document_names_junction", "names_id"),
    ("document_descriptions_junction", "descriptions_id"),
]

MULTI_JUNCTIONS: list[tuple[str, str]] = [
    ("document_departments_junction", "departments_id"),
    ("document_files_junction", "files_id"),
    ("document_images_junction", "images_id"),
    ("document_parameter_fields_junction", "parameter_fields_id"),
    ("document_texts_junction", "texts_id"),
    ("document_documents_junction", "documents_id"),
]


async def create_document(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    file_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    text_ids: list[UUID] | None = None,
    document_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateDocumentResponse:
    """Create a document artifact with optional junction links."""
    is_active = not soft if active is None else active
    document_id: UUID = await conn.fetchval(
        """
        INSERT INTO document_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await insert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=document_id,
                resource_col=col,
                resource_id=val,
                generated=generated,
                mcp=mcp,
            )

    # Multi-select junctions (simple)
    multi_vals = [
        department_ids,
        file_ids,
        image_ids,
        parameter_field_ids,
        text_ids,
        document_ids,
    ]
    for (table, col), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await insert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=document_id,
                resource_col=col,
                resource_ids=vals,
                generated=generated,
                mcp=mcp,
            )

    # Flags
    if flag_ids:
        await insert_multi(
            conn,
            table="document_flags_junction",
            owner_col=OWNER_COL,
            owner_id=document_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            generated=generated,
            mcp=mcp,
        )

    return CreateDocumentResponse(id=document_id)
