"""Document drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.document_drafts.types import GetDocumentDraftResponse


async def get_document_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetDocumentDraftResponse]:
    """Get document_drafts entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT fi.files_id) FILTER (WHERE fi.files_id IS NOT NULL), '{}') AS file_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT img.images_id) FILTER (WHERE img.images_id IS NOT NULL), '{}') AS image_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT pf.parameter_fields_id) FILTER (WHERE pf.parameter_fields_id IS NOT NULL), '{}') AS parameter_field_ids,
            COALESCE(ARRAY_AGG(DISTINCT par.parameters_id) FILTER (WHERE par.parameters_id IS NOT NULL), '{}') AS parameter_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT t.texts_id) FILTER (WHERE t.texts_id IS NOT NULL), '{}') AS text_ids
        FROM document_drafts_entry d
        LEFT JOIN document_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN document_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN document_drafts_files_connection fi ON fi.draft_id = d.id
        LEFT JOIN document_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN document_drafts_images_connection img ON img.draft_id = d.id
        LEFT JOIN document_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN document_drafts_parameter_fields_connection pf ON pf.draft_id = d.id
        LEFT JOIN document_drafts_parameters_connection par ON par.draft_id = d.id
        LEFT JOIN document_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN document_drafts_texts_connection t ON t.draft_id = d.id
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetDocumentDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            file_ids=r["file_ids"],
            flag_ids=r["flag_ids"],
            image_ids=r["image_ids"],
            name_ids=r["name_ids"],
            parameter_field_ids=r["parameter_field_ids"],
            parameter_ids=r["parameter_ids"],
            profile_ids=r["profile_ids"],
            text_ids=r["text_ids"],
        )
        for r in rows
    ]
