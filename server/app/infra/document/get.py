"""Document GET endpoint — composable infra architecture.

Uses composable infra layers:
  1. resolve_common_context — profile + tool graph + runs
  2. resolve_document_permissions_context — fail-fast 404/403
  3. resolve_document_context — artifact + draft → merged + hydrated resources
  4. score_tools — tool graph + artifact resources → per-resource tool picks
  5. Pure Python — permissions, show/required flags, response assembly
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.document.context import resolve_document_context
from app.infra.document.permissions import (
    DOCUMENT_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_fields_required,
    compute_flag_required,
    compute_name_required,
    compute_show_departments,
    compute_show_description,
    compute_show_fields,
    compute_show_flag,
    compute_show_name,
    compute_show_uploads,
    compute_uploads_required,
    has_access,
)
from app.infra.document.permissions_context import resolve_document_permissions_context
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import score_tools
from app.infra.document.types import (
    DocumentDepartmentSection,
    DocumentDescriptionSection,
    DocumentFieldSection,
    DocumentFlagConfig,
    DocumentFlagSection,
    DocumentImageSection,
    DocumentNameSection,
    DocumentParameterSection,
    DocumentTextSection,
    DocumentUploadSection,
    GetDocumentApiResponse,
)

# ---------------------------------------------------------------------------
# get_document_client — composable infra architecture
# ---------------------------------------------------------------------------


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'document_active' -> ('active', 'Active')"""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("document_", "")
    label = key.replace("_", " ").title()
    return (key, label)


def _serialize_model(value):
    """Convert Pydantic-style resource models into route-friendly plain data."""
    if value is None:
        return None
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _serialize_models(values):
    """Convert a list of resource models into plain data for response validation."""
    return [_serialize_model(value) for value in values]


async def get_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    document_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    parameter_ids: list[UUID] | None = None,
    # Search filters
    descriptions_search: str | None = None,
    bypass_cache: bool = False,
) -> GetDocumentApiResponse:
    """Document GET using composable infra functions.

    Flow:
      1. resolve_common_context(profile_id) → profile, tool_graph, runs
      2. resolve_document_permissions_context → access check (404, 403, fail fast)
      3. resolve_document_context(document_id, draft_id, ...) → hydrated resources
      4. score_tools(tool_graph, DOCUMENT_RESOURCES) → per-resource tool picks
      5. Pure Python: permissions, show/required/AI flags, response assembly
    """

    # ── Step 1: Common context (profile → tool_graph + runs) ──────────────

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
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    group_id = group_id or common.profile.group_id
    profile = common.profile

    # ── Step 2: Permissions check (fail fast before full hydration) ──────

    perms = None
    if document_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_document_permissions_context(conn, document_id)

        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found",
            )

        if not has_access(profile.role, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this document. It may be restricted to other departments.",
            )

    # ── Step 3: Document artifact context ─────────────────────────────────

    document = await resolve_document_context(
        pool,
        redis,
        document_id=document_id,
        group_id=group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        parameter_ids=parameter_ids,
        descriptions_search=descriptions_search,
        bypass_cache=bypass_cache,
    )

    # ── Step 4: Tool scoring ─────────────────────────────────────────────

    scores = score_tools(common.tool_graph, DOCUMENT_RESOURCES)

    agent_ids: dict[str, UUID | None] = {
        r: (scores.best[r].agent_id if scores.best.get(r) else None)
        for r in DOCUMENT_RESOURCES
    }

    tool_ids_map: dict[str, UUID | None] = {
        r: (scores.best[r].tool_id if scores.best.get(r) else None)
        for r in DOCUMENT_RESOURCES
    }

    # ── Step 5: Permissions ──────────────────────────────────────────────

    perms_department_ids = perms.department_ids if perms else []
    perms_scenario_count = perms.active_scenario_count if perms else 0

    can_edit = compute_can_edit(
        user_role=profile.role,
        document_department_ids=perms_department_ids,
        active_scenario_count=perms_scenario_count,
        user_department_ids=profile.department_ids,
    )

    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        document_department_ids=perms_department_ids,
        active_scenario_count=perms_scenario_count,
        user_department_ids=profile.department_ids,
    )

    # ── Step 6: Show / Required / AI flags ───────────────────────────────

    names_has_tools = scores.has_any.get("names", False)

    all_departments = dedupe_by_id(
        document.resources["departments"].selected
        + document.resources["departments"].suggestions
    )
    all_fields = dedupe_by_id(
        document.resources["parameter_fields"].selected
        + document.resources["parameter_fields"].suggestions
    )
    all_parameters = dedupe_by_id(
        document.resources["parameters"].selected
        + document.resources["parameters"].suggestions
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "fields": compute_show_fields(len(all_fields)),
        "parameters": len(all_parameters) > 0,
        "uploads": compute_show_uploads(),
        "images": True,
        "texts": True,
    }

    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "fields": compute_fields_required(),
        "parameters": False,
        "uploads": compute_uploads_required(),
        "images": False,
        "texts": False,
    }

    def compute_show_ai_generate(resource: str) -> bool:
        return agent_ids.get(resource) is not None

    show_ai_generate_map = {r: compute_show_ai_generate(r) for r in DOCUMENT_RESOURCES}

    basic_show_ai_generate = any(
        [
            show_ai_generate_map.get("names", False),
            show_ai_generate_map.get("descriptions", False),
            show_ai_generate_map.get("flags", False),
            show_ai_generate_map.get("departments", False),
        ]
    )
    content_show_ai_generate = any(
        [
            show_ai_generate_map.get("fields", False),
            show_ai_generate_map.get("uploads", False),
            show_ai_generate_map.get("images", False),
            show_ai_generate_map.get("texts", False),
        ]
    )

    # ── Step 7: Response assembly ────────────────────────────────────────

    # Flags — enriched format
    all_flags = dedupe_by_id(
        document.resources["flags"].selected + document.resources["flags"].suggestions
    )
    document_flags = [
        DocumentFlagConfig(
            key=derive_flag_key_and_label(flag.name)[0],
            label=derive_flag_key_and_label(flag.name)[1],
            description=flag.description,
            flag_option_id=flag.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=flag.generated,
        )
        for flag in all_flags
        if flag.id
    ]

    current_flags = [
        DocumentFlagConfig(
            key=derive_flag_key_and_label(flag.name)[0],
            label=derive_flag_key_and_label(flag.name)[1],
            description=flag.description,
            flag_option_id=flag.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=flag.generated,
        )
        for flag in document.resources["flags"].selected
        if flag.id
    ]

    # Names, Descriptions — all = selected + suggestions deduped
    all_names = dedupe_by_id(
        document.resources["names"].selected + document.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        document.resources["descriptions"].selected
        + document.resources["descriptions"].suggestions
    )
    all_files = dedupe_by_id(
        document.resources["files"].selected + document.resources["files"].suggestions
    )
    all_images = dedupe_by_id(
        document.resources["images"].selected + document.resources["images"].suggestions
    )
    all_texts = dedupe_by_id(
        document.resources["texts"].selected + document.resources["texts"].suggestions
    )

    # Suggestions maps (IDs only)
    suggestions_map = {
        "names": [n.id for n in document.resources["names"].suggestions],
        "descriptions": [d.id for d in document.resources["descriptions"].suggestions],
        "departments": [d.id for d in document.resources["departments"].suggestions],
        "fields": [f.id for f in document.resources["parameter_fields"].suggestions],
        "parameters": [p.id for p in document.resources["parameters"].suggestions],
        "uploads": [f.id for f in document.resources["files"].suggestions],
        "images": [i.id for i in document.resources["images"].suggestions],
        "texts": [t.id for t in document.resources["texts"].suggestions],
    }

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key, []),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    # Validation: new mode must have departments
    if document_id is None and not all_departments:
        raise HTTPException(
            status_code=400, detail="No accessible departments found for user"
        )

    return GetDocumentApiResponse(
        actor_name=profile.name,
        document_exists=document.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=document.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        content_show_ai_generate=content_show_ai_generate,
        names=DocumentNameSection(
            **_section("names"),
            resource=_serialize_model(document.resources["names"].selected[0])
            if document.resources["names"].selected
            else None,
            resources=_serialize_models(all_names),
        ),
        descriptions=DocumentDescriptionSection(
            **_section("descriptions"),
            resource=_serialize_model(document.resources["descriptions"].selected[0])
            if document.resources["descriptions"].selected
            else None,
            resources=_serialize_models(all_descriptions),
        ),
        flags=DocumentFlagSection(
            **_section("flags"),
            current=current_flags or None,
            resources=document_flags,
        ),
        departments=DocumentDepartmentSection(
            **_section("departments"),
            current=_serialize_models(document.resources["departments"].selected)
            or None,
            resources=_serialize_models(all_departments),
        ),
        fields=DocumentFieldSection(
            **_section("fields"),
            current=_serialize_models(document.resources["parameter_fields"].selected)
            or None,
            resources=_serialize_models(all_fields),
        ),
        parameters=DocumentParameterSection(
            **_section("parameters"),
            current=document.resources["parameters"].selected or None,
            resources=all_parameters,
        ),
        uploads=DocumentUploadSection(
            **_section("uploads"),
            current=_serialize_models(document.resources["files"].selected) or None,
            resources=_serialize_models(all_files),
        ),
        images=DocumentImageSection(
            **_section("images"),
            current=_serialize_models(document.resources["images"].selected) or None,
            resources=_serialize_models(all_images),
        ),
        texts=DocumentTextSection(
            **_section("texts"),
            current=_serialize_models(document.resources["texts"].selected) or None,
            resources=_serialize_models(all_texts),
        ),
    )


# ---------------------------------------------------------------------------
# get_document_websocket — stub (to be rewritten with infra functions)
# ---------------------------------------------------------------------------
