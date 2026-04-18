"""Canonical shared document GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.document.context import resolve_document_context
from app.infra.document.permissions import (
    DOCUMENT_RESOURCES,
    compute_can_draft,
    compute_can_edit,
    compute_disabled_reason,
    has_access,
)
from app.infra.document.permissions_context import resolve_document_permissions_context
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import score_tools
from app.infra.document.types import (
    DocumentDepartmentResource,
    DocumentDescriptionResource,
    DocumentFileResource,
    DocumentFlagConfig,
    DocumentImageResource,
    DocumentNameResource,
    DocumentParameterFieldResource,
    DocumentParameterResource,
    DocumentTextResource,
    GetDocumentApiResponse,
    SectionFilter,
)

SECTIONS = [
    "names",
    "descriptions",
    "flags",
    "departments",
    "parameter_fields",
    "parameters",
    "files",
    "images",
    "texts",
]


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
    sf = filters.get(section)
    if sf is None:
        return default
    return getattr(sf, attr, default)


def _derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("document_", "")
    label = key.replace("_", " ").title()
    return (key, label)


def _filter_items(items: list | None, section: str, *, selected_only: dict[str, bool], suggested_only: dict[str, bool]):
    if items is None:
        return None
    result = items
    if selected_only.get(section):
        result = [item for item in result if getattr(item, "selected", False)]
    if suggested_only.get(section):
        result = [item for item in result if getattr(item, "suggested", False)]
    return result


def _text_match(value: str | None, needle: str | None) -> bool:
    if not needle:
        return True
    hay = (value or "").lower()
    return needle.lower() in hay


async def get_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    document_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **legacy_kwargs,
) -> GetDocumentApiResponse:
    """Resolve the canonical document artifact bundle for any surface."""

    f = dict(filters or {})
    if "parameter_fields" not in f and f.get("fields") is not None:
        f["parameter_fields"] = f["fields"]
    if "files" not in f and f.get("uploads") is not None:
        f["files"] = f["uploads"]

    document_id = id or document_id

    raw_param_ids = _sf(f, "parameter_fields", "parameter_ids") or _sf(f, "parameters", "parameter_ids")
    parameter_ids = [UUID(pid) if isinstance(pid, str) else pid for pid in raw_param_ids] if raw_param_ids else None

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="document",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(status_code=401, detail="Profile not found. Please sign in again.")

    effective_group_id = group_id or common.profile.group_id

    perms = None
    if document_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_document_permissions_context(conn, document_id)
        if not perms.exists:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        if not has_access(
            common.profile.role_level,
            common.profile.department_ids,
            perms.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this document. It may be restricted to other departments.",
            )

    document = await resolve_document_context(
        pool,
        redis,
        document_id=document_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=common.profile.department_ids,
        parameter_ids=parameter_ids,
        names_search=_sf(f, "names", "search"),
        descriptions_search=_sf(f, "descriptions", "search"),
        flags_search=_sf(f, "flags", "search"),
        departments_search=_sf(f, "departments", "search"),
        parameter_fields_search=_sf(f, "parameter_fields", "search"),
        parameters_search=_sf(f, "parameters", "search"),
        files_search=_sf(f, "files", "search"),
        images_search=_sf(f, "images", "search"),
        texts_search=_sf(f, "texts", "search"),
        names_limit=_sf(f, "names", "limit"),
        descriptions_limit=_sf(f, "descriptions", "limit"),
        flags_limit=_sf(f, "flags", "limit"),
        departments_limit=_sf(f, "departments", "limit"),
        parameter_fields_limit=_sf(f, "parameter_fields", "limit"),
        parameters_limit=_sf(f, "parameters", "limit"),
        files_limit=_sf(f, "files", "limit"),
        images_limit=_sf(f, "images", "limit"),
        texts_limit=_sf(f, "texts", "limit"),
        names_selected_only=_sf(f, "names", "selected"),
        descriptions_selected_only=_sf(f, "descriptions", "selected"),
        flags_selected_only=_sf(f, "flags", "selected"),
        departments_selected_only=_sf(f, "departments", "selected"),
        parameter_fields_selected_only=_sf(f, "parameter_fields", "selected"),
        parameters_selected_only=_sf(f, "parameters", "selected"),
        files_selected_only=_sf(f, "files", "selected"),
        images_selected_only=_sf(f, "images", "selected"),
        texts_selected_only=_sf(f, "texts", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, DOCUMENT_RESOURCES)
    include = {section: _sf(f, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(f, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(f, section, "suggested")) for section in SECTIONS}

    profile = common.profile
    perms_department_ids = perms.department_ids if perms else []
    perms_scenario_count = perms.active_scenario_count if perms else 0

    can_edit = compute_can_edit(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        document_department_ids=perms_department_ids,
        active_scenario_count=perms_scenario_count,
        user_department_ids=profile.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        document_department_ids=perms_department_ids,
        active_scenario_count=perms_scenario_count,
        user_department_ids=profile.department_ids,
    )
    show_ai_generate = compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    )

    pending_ids: set[UUID] = document.entries.get("pending_ids", set())

    names_selected = document.resources["names"].selected
    names_suggestions = document.resources["names"].suggestions
    descriptions_selected = document.resources["descriptions"].selected
    descriptions_suggestions = document.resources["descriptions"].suggestions
    flags_selected = document.resources["flags"].selected
    flags_suggestions = document.resources["flags"].suggestions
    departments_selected = document.resources["departments"].selected
    departments_suggestions = document.resources["departments"].suggestions
    parameter_fields_selected = document.resources["parameter_fields"].selected
    parameter_fields_suggestions = document.resources["parameter_fields"].suggestions
    parameters_selected = document.resources["parameters"].selected
    parameters_suggestions = document.resources["parameters"].suggestions
    files_selected = document.resources["files"].selected
    files_suggestions = document.resources["files"].suggestions
    images_selected = document.resources["images"].selected
    images_suggestions = document.resources["images"].suggestions
    texts_selected = document.resources["texts"].selected
    texts_suggestions = document.resources["texts"].suggestions

    all_names = dedupe_by_id(names_selected + names_suggestions)
    all_descriptions = dedupe_by_id(descriptions_selected + descriptions_suggestions)
    all_flags = dedupe_by_id(flags_selected + flags_suggestions)
    all_departments = dedupe_by_id(departments_selected + departments_suggestions)
    all_parameter_fields = dedupe_by_id(parameter_fields_selected + parameter_fields_suggestions)
    all_parameters = dedupe_by_id(parameters_selected + parameters_suggestions, id_attr="parameter_id")
    all_files = dedupe_by_id(files_selected + files_suggestions)
    all_images = dedupe_by_id(images_selected + images_suggestions)
    all_texts = dedupe_by_id(texts_selected + texts_suggestions)

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "departments": {item.id for item in departments_selected if item.id},
        "parameter_fields": {item.id for item in parameter_fields_selected if item.id},
        "parameters": {item.parameter_id for item in parameters_selected if item.parameter_id},
        "files": {item.id for item in files_selected if item.id},
        "images": {item.id for item in images_selected if item.id},
        "texts": {item.id for item in texts_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "departments": {item.id for item in departments_suggestions if item.id},
        "parameter_fields": {item.id for item in parameter_fields_suggestions if item.id},
        "parameters": {item.parameter_id for item in parameters_suggestions if item.parameter_id},
        "files": {item.id for item in files_suggestions if item.id},
        "images": {item.id for item in images_suggestions if item.id},
        "texts": {item.id for item in texts_suggestions if item.id},
    }

    field_lookup = {field.id: field for field in document.entries.get("fields", []) if getattr(field, "id", None)}
    file_entry_lookup = {entry.files_id: entry for entry in document.entries.get("file_entries", []) if getattr(entry, "files_id", None)}
    image_entry_lookup = {entry.images_id: entry for entry in document.entries.get("image_entries", []) if getattr(entry, "images_id", None)}
    text_entry_lookup = {entry.texts_id: entry for entry in document.entries.get("text_entries", []) if getattr(entry, "texts_id", None)}

    def _decorate_common(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    def _names() -> list[DocumentNameResource]:
        result: list[DocumentNameResource] = []
        for item in all_names:
            suggested, selected, pending = _decorate_common(item.id, "names")
            result.append(
                DocumentNameResource(
                    id=item.id,
                    name=item.name,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return result

    def _descriptions() -> list[DocumentDescriptionResource]:
        result: list[DocumentDescriptionResource] = []
        for item in all_descriptions:
            suggested, selected, pending = _decorate_common(item.id, "descriptions")
            result.append(
                DocumentDescriptionResource(
                    id=item.id,
                    description=item.description,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return result

    def _flags() -> list[DocumentFlagConfig]:
        result: list[DocumentFlagConfig] = []
        for item in all_flags:
            suggested, selected, pending = _decorate_common(item.id, "flags")
            key, label = _derive_flag_key_and_label(getattr(item, "name", None))
            result.append(
                DocumentFlagConfig(
                    key=key,
                    label=label,
                    description=getattr(item, "description", None),
                    flag_option_id=item.id,
                    generated=getattr(item, "generated", None),
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return result

    def _departments() -> list[DocumentDepartmentResource]:
        result: list[DocumentDepartmentResource] = []
        for item in all_departments:
            suggested, selected, pending = _decorate_common(item.id, "departments")
            result.append(
                DocumentDepartmentResource(
                    department_id=item.id,
                    name=item.name,
                    description=item.description,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return result

    def _parameter_fields() -> list[DocumentParameterFieldResource]:
        items: list[DocumentParameterFieldResource] = []
        needle = _sf(f, "parameter_fields", "search")
        for item in all_parameter_fields:
            field = field_lookup.get(item.field_id)
            name = getattr(field, "name", None)
            description = getattr(field, "description", None)
            if needle and not (_text_match(name, needle) or _text_match(description, needle)):
                continue
            suggested, selected, pending = _decorate_common(item.id, "parameter_fields")
            items.append(
                DocumentParameterFieldResource(
                    id=item.id,
                    field_id=item.field_id,
                    parameter_id=item.parameter_id,
                    name=name,
                    description=description,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    def _parameters() -> list[DocumentParameterResource]:
        items: list[DocumentParameterResource] = []
        for item in all_parameters:
            suggested, selected, pending = _decorate_common(item.parameter_id, "parameters")
            items.append(
                DocumentParameterResource(
                    parameter_id=item.parameter_id,
                    name=item.name,
                    description=item.description,
                    value=item.value,
                    department_ids=item.department_ids,
                    persona_parameter=item.persona_parameter,
                    document_parameter=item.document_parameter,
                    scenario_parameter=item.scenario_parameter,
                    video_parameter=item.video_parameter,
                    field_ids=item.field_ids,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    def _files() -> list[DocumentFileResource]:
        items: list[DocumentFileResource] = []
        needle = _sf(f, "files", "search")
        for item in all_files:
            entry = file_entry_lookup.get(item.id)
            if needle and entry and not (
                _text_match(getattr(entry, "file_path", None), needle)
                or _text_match(getattr(entry, "mime_type", None), needle)
                or _text_match(str(getattr(entry, "upload_id", "")), needle)
            ):
                continue
            suggested, selected, pending = _decorate_common(item.id, "files")
            items.append(
                DocumentFileResource(
                    id=item.id,
                    files_id=item.id,
                    file_path=getattr(entry, "file_path", None),
                    mime_type=getattr(entry, "mime_type", None),
                    size=getattr(entry, "size", None),
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    def _images() -> list[DocumentImageResource]:
        items: list[DocumentImageResource] = []
        for item in all_images:
            entry = image_entry_lookup.get(item.id)
            suggested, selected, pending = _decorate_common(item.id, "images")
            items.append(
                DocumentImageResource(
                    id=item.id,
                    image_id=item.id,
                    name=item.name,
                    description=item.description,
                    file_path=getattr(entry, "file_path", None),
                    mime_type=getattr(entry, "mime_type", None),
                    size=getattr(entry, "size", None),
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    def _texts() -> list[DocumentTextResource]:
        items: list[DocumentTextResource] = []
        needle = _sf(f, "texts", "search")
        for item in all_texts:
            entry = text_entry_lookup.get(item.id)
            if needle and entry and not (
                _text_match(getattr(entry, "file_path", None), needle)
                or _text_match(getattr(entry, "mime_type", None), needle)
                or _text_match(str(getattr(entry, "upload_id", "")), needle)
            ):
                continue
            suggested, selected, pending = _decorate_common(item.id, "texts")
            items.append(
                DocumentTextResource(
                    id=item.id,
                    texts_id=item.id,
                    file_path=getattr(entry, "file_path", None),
                    mime_type=getattr(entry, "mime_type", None),
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    return GetDocumentApiResponse(
        actor_name=profile.name,
        document_exists=document.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        show_ai_generate=show_ai_generate,
        basic_show_ai_generate=show_ai_generate,
        content_show_ai_generate=show_ai_generate,
        pending_ids=list(pending_ids) or None,
        names=_filter_items(_names(), "names", selected_only=selected_only, suggested_only=suggested_only) if include["names"] else None,
        descriptions=_filter_items(_descriptions(), "descriptions", selected_only=selected_only, suggested_only=suggested_only) if include["descriptions"] else None,
        flags=_filter_items(_flags(), "flags", selected_only=selected_only, suggested_only=suggested_only) if include["flags"] else None,
        departments=_filter_items(_departments(), "departments", selected_only=selected_only, suggested_only=suggested_only) if include["departments"] else None,
        parameter_fields=_filter_items(_parameter_fields(), "parameter_fields", selected_only=selected_only, suggested_only=suggested_only) if include["parameter_fields"] else None,
        parameters=_filter_items(_parameters(), "parameters", selected_only=selected_only, suggested_only=suggested_only) if include["parameters"] else None,
        files=_filter_items(_files(), "files", selected_only=selected_only, suggested_only=suggested_only) if include["files"] else None,
        images=_filter_items(_images(), "images", selected_only=selected_only, suggested_only=suggested_only) if include["images"] else None,
        texts=_filter_items(_texts(), "texts", selected_only=selected_only, suggested_only=suggested_only) if include["texts"] else None,
    )
