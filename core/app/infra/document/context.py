"""Resolve document artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.document.get import get_documents as get_document_artifacts
from app.tools.entries.document_drafts.get import get_document_drafts
from app.tools.entries.files.search import search_files as search_file_entries
from app.tools.entries.images.search import search_images as search_image_entries
from app.tools.entries.texts.search import search_texts as search_text_entries
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.fields.search import search_fields
from app.tools.resources.files.get import get_files
from app.tools.resources.files.search import search_files
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.images.get import get_images
from app.tools.resources.images.search import search_images
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.parameter_fields.search import search_parameter_fields
from app.tools.resources.parameters.get import get_parameters
from app.tools.resources.parameters.search import search_parameters
from app.tools.resources.texts.get import get_texts
from app.tools.resources.texts.search import search_texts

DOCUMENT_FLAG_TYPES = {"document_active", "template"}


async def resolve_document_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    document_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    parameter_fields_search: str | None = None,
    parameters_search: str | None = None,
    files_search: str | None = None,
    images_search: str | None = None,
    texts_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    parameter_fields_limit: int | None = None,
    parameters_limit: int | None = None,
    files_limit: int | None = None,
    images_limit: int | None = None,
    texts_limit: int | None = None,
    names_selected_only: bool | None = None,
    descriptions_selected_only: bool | None = None,
    flags_selected_only: bool | None = None,
    departments_selected_only: bool | None = None,
    parameter_fields_selected_only: bool | None = None,
    parameters_selected_only: bool | None = None,
    files_selected_only: bool | None = None,
    images_selected_only: bool | None = None,
    texts_selected_only: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a document artifact into fully hydrated resource pairs."""

    user_dept_ids = user_department_ids or []
    requested_parameter_ids = parameter_ids or []

    async def _fetch_artifact() -> list:
        if not document_id:
            return []
        async with pool.acquire() as conn:
            return await get_document_artifacts(
                conn,
                [document_id],
                active=None,
                names=True,
                descriptions=True,
                departments=True,
                flags=True,
                files=True,
                images=True,
                parameter_fields=True,
                parameters=True,
                texts=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_document_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())
    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None
    merged = _merge_junction_ids(artifact, draft, requested_parameter_ids)
    active = artifact.active if artifact else True

    async def _get_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, merged.name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                search=names_search,
                limit_count=names_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if names_selected_only else "all",
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                document=True,
            )

    async def _get_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, merged.description_ids, redis, bypass_cache)

    async def _search_descriptions() -> list:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=descriptions_search,
                limit_count=descriptions_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if descriptions_selected_only else "all",
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                document=True,
            )

    async def _get_flags() -> list:
        async with pool.acquire() as conn:
            return await get_flags(conn, merged.flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=flags_search,
                limit_count=flags_limit or 100,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
                document=True,
            )

    async def _get_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(conn, merged.department_ids, redis, bypass_cache=bypass_cache)

    async def _search_departments() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=departments_search,
                limit_count=departments_limit or 20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="selected" if departments_selected_only else "all",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_parameter_fields() -> list:
        async with pool.acquire() as conn:
            return await get_parameter_fields(conn, merged.parameter_field_ids, redis, bypass_cache)

    async def _search_parameter_fields() -> list:
        if not merged.parameter_ids:
            return []
        async with pool.acquire() as conn:
            return await search_parameter_fields(
                conn,
                redis,
                limit_count=parameter_fields_limit or 200,
                exclude_ids=merged.parameter_field_ids,
                parameter_ids=merged.parameter_ids,
                bypass_cache=bypass_cache,
                document=True,
            )

    async def _get_parameters() -> list:
        if not merged.parameter_ids:
            return []
        async with pool.acquire() as conn:
            return await get_parameters(conn, merged.parameter_ids, redis, bypass_cache)

    async def _search_parameters() -> list:
        async with pool.acquire() as conn:
            return await search_parameters(
                conn,
                redis,
                search=parameters_search,
                limit_count=parameters_limit or 50,
                offset_count=0,
                draft_id=group_id,
                suggest_source="selected" if parameters_selected_only else "all",
                exclude_ids=merged.parameter_ids,
                document_parameter=True,
                document=True,
                bypass_cache=bypass_cache,
            )

    async def _get_files() -> list:
        async with pool.acquire() as conn:
            return await get_files(conn, merged.file_ids, redis, bypass_cache)

    async def _search_files() -> list:
        async with pool.acquire() as conn:
            return await search_files(
                conn,
                redis,
                search=files_search,
                limit_count=files_limit or 20,
                offset_count=0,
                exclude_ids=merged.file_ids,
                bypass_cache=bypass_cache,
                document=True,
            )

    async def _get_images() -> list:
        async with pool.acquire() as conn:
            return await get_images(conn, merged.image_ids, redis, bypass_cache)

    async def _search_images() -> list:
        async with pool.acquire() as conn:
            return await search_images(
                conn,
                redis,
                search=images_search,
                limit_count=images_limit or 20,
                offset_count=0,
                draft_id=group_id,
                suggest_source="selected" if images_selected_only else "all",
                exclude_ids=merged.image_ids,
                bypass_cache=bypass_cache,
                document=True,
            )

    async def _get_texts() -> list:
        async with pool.acquire() as conn:
            return await get_texts(conn, merged.text_ids, redis, bypass_cache)

    async def _search_texts() -> list:
        async with pool.acquire() as conn:
            return await search_texts(
                conn,
                redis,
                search=texts_search,
                limit_count=texts_limit or 20,
                offset_count=0,
                exclude_ids=merged.text_ids,
                bypass_cache=bypass_cache,
            )

    async def _search_fields_catalog() -> list:
        async with pool.acquire() as conn:
            return await search_fields(
                conn,
                redis,
                search=None,
                limit_count=500,
                offset_count=0,
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        flags_selected,
        flags_suggestions,
        departments_selected,
        departments_suggestions,
        parameter_fields_selected,
        parameter_fields_suggestions,
        parameters_selected,
        parameters_suggestions,
        files_selected,
        files_suggestions,
        images_selected,
        images_suggestions,
        texts_selected,
        texts_suggestions,
        fields_catalog,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_parameter_fields(),
        _search_parameter_fields(),
        _get_parameters(),
        _search_parameters(),
        _get_files(),
        _search_files(),
        _get_images(),
        _search_images(),
        _get_texts(),
        _search_texts(),
        _search_fields_catalog(),
    )

    flags_selected = [
        item for item in flags_selected if getattr(item, "type", None) in DOCUMENT_FLAG_TYPES
    ]
    flags_suggestions = [
        item for item in flags_suggestions if getattr(item, "type", None) in DOCUMENT_FLAG_TYPES
    ]

    all_file_resource_ids = [item.id for item in files_selected + files_suggestions if item.id]
    all_image_resource_ids = [item.id for item in images_selected + images_suggestions if item.id]
    all_text_resource_ids = [item.id for item in texts_selected + texts_suggestions if item.id]

    async def _fetch_file_entries() -> list:
        if not all_file_resource_ids:
            return []
        async with pool.acquire() as conn:
            return await search_file_entries(conn, files_ids=all_file_resource_ids, limit=200)

    async def _fetch_image_entries() -> list:
        if not all_image_resource_ids:
            return []
        async with pool.acquire() as conn:
            return await search_image_entries(conn, images_ids=all_image_resource_ids, limit=200)

    async def _fetch_text_entries() -> list:
        if not all_text_resource_ids:
            return []
        async with pool.acquire() as conn:
            return await search_text_entries(conn, text_ids=all_text_resource_ids, limit=200)

    file_entries, image_entries, text_entries = await asyncio.gather(
        _fetch_file_entries(),
        _fetch_image_entries(),
        _fetch_text_entries(),
    )

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=active,
        group_id=group_id,
        resources={
            "names": ResourcePair(selected=names_selected, suggestions=names_suggestions),
            "descriptions": ResourcePair(selected=descriptions_selected, suggestions=descriptions_suggestions),
            "flags": ResourcePair(selected=flags_selected, suggestions=flags_suggestions),
            "departments": ResourcePair(selected=departments_selected, suggestions=departments_suggestions),
            "parameter_fields": ResourcePair(
                selected=parameter_fields_selected,
                suggestions=parameter_fields_suggestions,
            ),
            "parameters": ResourcePair(selected=parameters_selected, suggestions=parameters_suggestions),
            "files": ResourcePair(selected=files_selected, suggestions=files_suggestions),
            "images": ResourcePair(selected=images_selected, suggestions=images_suggestions),
            "texts": ResourcePair(selected=texts_selected, suggestions=texts_suggestions),
        },
        entries={
            "fields": fields_catalog,
            "file_entries": file_entries,
            "image_entries": image_entries,
            "text_entries": text_entries,
            "pending_ids": set(),
        },
    )


@dataclass
class _MergedIds:
    """Merged junction IDs from artifact + draft."""

    name_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    parameter_field_ids: list[UUID]
    parameter_ids: list[UUID]
    file_ids: list[UUID]
    image_ids: list[UUID]
    text_ids: list[UUID]


def _merge_junction_ids(artifact, draft, requested_parameter_ids: list[UUID]) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides."""

    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    parameter_field_ids = list(artifact.parameter_field_ids or []) if artifact else []
    parameter_ids = list(artifact.parameter_ids or []) if artifact else []
    file_ids = list(artifact.files_ids or []) if artifact else []
    image_ids = list(artifact.images_ids or []) if artifact else []
    text_ids = list(artifact.texts_ids or []) if artifact else []

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.parameter_field_ids:
            parameter_field_ids = list(draft.parameter_field_ids)
        if draft.parameter_ids:
            parameter_ids = list(draft.parameter_ids)
        if draft.file_ids:
            file_ids = list(draft.file_ids)
        if draft.image_ids:
            image_ids = list(draft.image_ids)
        if draft.text_ids:
            text_ids = list(draft.text_ids)

    if requested_parameter_ids:
        parameter_ids = list(requested_parameter_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        parameter_field_ids=parameter_field_ids,
        parameter_ids=parameter_ids,
        file_ids=file_ids,
        image_ids=image_ids,
        text_ids=text_ids,
    )
