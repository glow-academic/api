"""Document drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.document_drafts.types import GetDocumentDraftResponse


async def get_document_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    active: bool | None = True,
) -> list[GetDocumentDraftResponse]:
    """Get document_drafts entries by IDs with connection data.

    ``active=True`` (default) — only returns committed drafts.
    ``active=False`` — only dormant pending drafts (rare).
    ``active=None`` — both. Use when loading a draft for the editor that
    may still be in pending state (soft_calls_entry ledger has it).
    """
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT fi.files_id) FILTER (WHERE fi.files_id IS NOT NULL), '{}') AS file_ids,
            COALESCE(ARRAY_AGG(DISTINCT fi.files_id) FILTER (WHERE fi.files_id IS NOT NULL AND fi.active = false), '{}') AS pending_file_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT img.images_id) FILTER (WHERE img.images_id IS NOT NULL), '{}') AS image_ids,
            COALESCE(ARRAY_AGG(DISTINCT img.images_id) FILTER (WHERE img.images_id IS NOT NULL AND img.active = false), '{}') AS pending_image_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT pf.parameter_fields_id) FILTER (WHERE pf.parameter_fields_id IS NOT NULL), '{}') AS parameter_field_ids,
            COALESCE(ARRAY_AGG(DISTINCT pf.parameter_fields_id) FILTER (WHERE pf.parameter_fields_id IS NOT NULL AND pf.active = false), '{}') AS pending_parameter_field_ids,
            COALESCE(ARRAY_AGG(DISTINCT par.parameters_id) FILTER (WHERE par.parameters_id IS NOT NULL), '{}') AS parameter_ids,
            COALESCE(ARRAY_AGG(DISTINCT par.parameters_id) FILTER (WHERE par.parameters_id IS NOT NULL AND par.active = false), '{}') AS pending_parameter_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT t.texts_id) FILTER (WHERE t.texts_id IS NOT NULL), '{}') AS text_ids,
            COALESCE(ARRAY_AGG(DISTINCT t.texts_id) FILTER (WHERE t.texts_id IS NOT NULL AND t.active = false), '{}') AS pending_text_ids
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
          AND ($2::boolean IS NULL OR d.active = $2)
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        ids,
        active,
    )

    return [
        GetDocumentDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name=r["name"],
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
            pending_department_ids=r["pending_department_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_file_ids=r["pending_file_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_image_ids=r["pending_image_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_parameter_field_ids=r["pending_parameter_field_ids"],
            pending_parameter_ids=r["pending_parameter_ids"],
            pending_text_ids=r["pending_text_ids"],
        )
        for r in rows
    ]
