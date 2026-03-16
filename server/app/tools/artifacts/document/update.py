"""Document artifact UPDATE — tool layer.

Efficient junction updates: only deactivate removed IDs, upsert new ones,
and touch (updated_at) unchanged ones.
"""

from typing import Any
from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.document.types import UpdateDocumentResponse

_UNSET: Any = object()

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
    (
        "document_parameter_fields_junction",
        "parameter_fields_id",
        "document_parameter_fields_junction_pkey",
    ),
    ("document_texts_junction", "texts_id", "document_texts_junction_pkey"),
    ("document_documents_junction", "documents_id", "document_documents_junction_pkey"),
]


async def update_document(
    conn: asyncpg.Connection,
    document_id: UUID,
    *,
    # Single-select junctions (_UNSET = don't change)
    name_id: UUID | Any = _UNSET,
    description_id: UUID | Any = _UNSET,
    # Multi-select junctions (None = don't change, [] = remove all)
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    file_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    text_ids: list[UUID] | None = None,
    document_ids: list[UUID] | None = None,
    # Base columns
    active: bool | Any = _UNSET,
    soft: bool = False,
    mcp: bool = False,
) -> UpdateDocumentResponse:
    """Update a document artifact with efficient junction diffs."""
    # soft=True forces active=false regardless of the active parameter
    if soft:
        active = False

    # 1. Update artifact row
    if active is not _UNSET:
        await conn.execute(
            "UPDATE document_artifact SET updated_at = NOW(), active = $2, mcp = $3 "
            "WHERE id = $1",
            document_id,
            active,
            mcp,
        )
    else:
        await conn.execute(
            "UPDATE document_artifact SET updated_at = NOW(), mcp = $2 WHERE id = $1",
            document_id,
            mcp,
        )

    # 2. Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not _UNSET:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=document_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                mcp=mcp,
            )

    # 3. Multi-select junctions (simple)
    multi_vals: list[list[UUID] | None] = [
        department_ids,
        file_ids,
        image_ids,
        parameter_field_ids,
        text_ids,
        document_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals is not None:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=document_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                mcp=mcp,
            )

    # 4. Flags
    if flag_ids is not None:
        await upsert_multi(
            conn,
            table="document_flags_junction",
            owner_col=OWNER_COL,
            owner_id=document_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="document_flags_pkey",
            mcp=mcp,
        )

    return UpdateDocumentResponse(id=document_id)
