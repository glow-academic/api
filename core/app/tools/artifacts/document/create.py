"""Document artifact CREATE — tool layer.

Idempotent via ON CONFLICT on artifact + upsert_* for junctions.
Re-calling with the same id promotes a dormant artifact.
"""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.document.types import CreateDocumentResponse

OWNER_COL = "document_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("document_names_junction", "names_id", "document_names_pkey"),
    ("document_descriptions_junction", "descriptions_id", "document_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("document_departments_junction", "departments_id", "document_departments_pkey"),
    ("document_files_junction", "files_id", "document_files_junction_pkey"),
    ("document_images_junction", "images_id", "document_images_junction_pkey"),
    ("document_parameter_fields_junction", "parameter_fields_id", "document_parameter_fields_junction_pkey"),
    ("document_texts_junction", "texts_id", "document_texts_junction_pkey"),
    ("document_documents_junction", "documents_id", "document_documents_junction_pkey"),
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
    """Create a document artifact with optional junction links.

    Idempotent: if id is provided and already exists, ON CONFLICT promotes
    the artifact. Junction rows use existing upsert_single/upsert_multi.
    """
    is_active = not soft if active is None else active
    document_id: UUID = await conn.fetchval(
        """
        INSERT INTO document_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions — upsert_single handles ON CONFLICT
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=document_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Multi-select junctions — upsert_multi handles ON CONFLICT
    multi_vals = [
        department_ids,
        file_ids,
        image_ids,
        parameter_field_ids,
        text_ids,
        document_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=document_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Flags
    if flag_ids:
        await upsert_multi(
            conn,
            table="document_flags_junction",
            owner_col=OWNER_COL,
            owner_id=document_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="document_flags_pkey",
            generated=generated,
            mcp=mcp,
            soft=soft,
        )

    return CreateDocumentResponse(id=document_id)
